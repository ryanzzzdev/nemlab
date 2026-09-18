package au.nemlab.infrastructure.jobs;

import au.nemlab.batterylab.PriceDay;
import au.nemlab.infrastructure.prices.PriceSource;
import au.nemlab.infrastructure.prices.PriceStore;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.transaction.annotation.Transactional;

import javax.sql.DataSource;
import java.sql.Timestamp;
import java.time.Clock;
import java.time.LocalDate;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

/**
 * Database-only transactions. Fetch OE data after claim() returns, then pass the
 * result to complete(). Always call through the Spring-managed bean.
 */
@Transactional(timeout = 30)
public class RefreshJobService {
    private static final int MAX_PENDING_JOBS = 100;
    private static final int MAX_ATTEMPTS = 3;
    private static final int LEASE_SECONDS = 300;

    // Serialises short queue transitions across processes, not network requests.
    private static final long QUEUE_LOCK = 735_028L;

    private static final RowMapper<RefreshJob> JOB_MAPPER = (result, row) -> {
        Timestamp lease = result.getTimestamp("lease_until");
        return new RefreshJob(
                result.getObject("id", UUID.class),
                result.getObject("backfill_id", UUID.class),
                PriceDay.Region.valueOf(result.getString("region")),
                result.getObject("market_day", LocalDate.class),
                RefreshJob.Status.valueOf(result.getString("status")),
                result.getInt("attempts"),
                result.getObject("claim_token", UUID.class),
                lease == null ? null : lease.toInstant(),
                result.getTimestamp("available_at").toInstant(),
                result.getString("diagnostic"));
    };

    private final JdbcTemplate jdbc;
    private final PriceStore prices;

    public RefreshJobService(DataSource dataSource, PriceStore prices) {
        this.jdbc = new JdbcTemplate(dataSource);
        this.prices = prices;
    }

    public UUID submit(String requestKey, PriceDay.Region region, LocalDate day, String actor) {
        validateLabel(requestKey, 120);
        validateLabel(actor, 80);
        if (region == null || day == null) {
            throw new IllegalArgumentException("Region and completed market day are required");
        }
        lockQueue();
        Optional<RefreshJob> existing = jdbc.query("""
                SELECT job.* FROM refresh_job job
                JOIN refresh_request request ON request.job_id = job.id
                WHERE request.request_key = ?
                """, JOB_MAPPER, requestKey).stream().findFirst();
        if (existing.isPresent()) {
            RefreshJob job = existing.get();
            if (job.region() != region || !job.day().equals(day)) {
                throw new IllegalArgumentException("Request key already belongs to another price day");
            }
            event(job.id(), actor, "DUPLICATE_REQUEST", null);
            return job.id();
        }

        Optional<RefreshJob> active = jdbc.query("""
                SELECT * FROM refresh_job
                WHERE region = ? AND market_day = ? AND status IN ('QUEUED', 'RUNNING')
                """, JOB_MAPPER, region.name(), day).stream().findFirst();
        UUID jobId;
        if (active.isPresent()) {
            jobId = active.get().id();
        } else {
            Integer pending = jdbc.queryForObject("""
                    SELECT count(*) FROM refresh_job WHERE status IN ('QUEUED', 'RUNNING')
                    """, Integer.class);
            if (pending >= MAX_PENDING_JOBS) {
                throw new IllegalStateException("Refresh queue is full; wait for existing jobs");
            }
            UUID backfillId = prices.createBackfill(region, day, day.plusDays(1), Clock.systemUTC());
            jobId = UUID.randomUUID();
            jdbc.update("""
                    INSERT INTO refresh_job(id, backfill_id, region, market_day, status)
                    VALUES (?, ?, ?, ?, 'QUEUED')
                    """, jobId, backfillId, region.name(), day);
        }
        jdbc.update("INSERT INTO refresh_request(request_key, job_id) VALUES (?, ?)", requestKey, jobId);
        event(jobId, actor, active.isPresent() ? "DEDUPLICATED" : "SUBMITTED", null);
        return jobId;
    }

    /** Initially permits one running ingestion globally, including multiple worker processes. */
    public Optional<RefreshJob> claim() {
        lockQueue();
        List<RefreshJob> expired = jdbc.query("""
                SELECT * FROM refresh_job
                WHERE status = 'RUNNING' AND lease_until <= clock_timestamp()
                FOR UPDATE
                """, JOB_MAPPER);
        for (RefreshJob job : expired) {
            retryOrFail(job, "LEASE_EXPIRED", true);
        }
        Integer running = jdbc.queryForObject(
                "SELECT count(*) FROM refresh_job WHERE status = 'RUNNING'", Integer.class);
        if (running > 0) {
            return Optional.empty();
        }
        List<RefreshJob> ready = jdbc.query("""
                SELECT * FROM refresh_job
                WHERE status = 'QUEUED' AND available_at <= clock_timestamp()
                ORDER BY available_at, created_at, id
                LIMIT 1 FOR UPDATE SKIP LOCKED
                """, JOB_MAPPER);
        if (ready.isEmpty()) {
            return Optional.empty();
        }
        UUID id = ready.getFirst().id();
        jdbc.update("""
                UPDATE refresh_job
                SET status = 'RUNNING', attempts = attempts + 1, claim_token = ?,
                    lease_until = clock_timestamp() + make_interval(secs => ?)
                WHERE id = ?
                """, UUID.randomUUID(), LEASE_SECONDS, id);
        event(id, "worker", "CLAIMED", null);
        return find(id);
    }

    public void complete(UUID id, UUID token, PriceSource.Fetch fetch) {
        RefreshJob job = requireLiveClaim(id, token);
        boolean complete = prices.commitDay(job.backfillId(), job.day(), fetch);
        if (complete) {
            finish(job, "SUCCEEDED", null);
            event(id, "worker", "SUCCEEDED", null);
        } else {
            requireLiveClaim(id, token);
            retryOrFail(job, "INCOMPLETE_PRICE_DAY", false);
        }
    }

    public void fail(UUID id, UUID token, String diagnosticCode) {
        validateLabel(diagnosticCode, 80);
        if (!diagnosticCode.matches("[A-Z][A-Z0-9_]*")) {
            throw new IllegalArgumentException("Use a diagnostic code, never an exception message or response body");
        }
        RefreshJob job = requireLiveClaim(id, token);
        prices.recordFailure(prices.backfill(job.backfillId()),
                jdbc.queryForObject("SELECT clock_timestamp()", Timestamp.class).toInstant(), diagnosticCode);
        requireLiveClaim(id, token);
        retryOrFail(job, diagnosticCode, false);
    }

    public boolean cancel(UUID id, String actor) {
        validateLabel(actor, 80);
        // Matching claim() lock order prevents cancellation/recovery deadlocks.
        lockQueue();
        int changed = jdbc.update("""
                UPDATE refresh_job
                SET status = 'CANCELLED', claim_token = NULL, lease_until = NULL,
                    diagnostic = 'CANCELLED_BY_OPERATOR'
                WHERE id = ? AND status IN ('QUEUED', 'RUNNING')
                """, id);
        if (changed == 1) {
            event(id, actor, "CANCELLED", null);
        }
        return changed == 1;
    }

    @Transactional(readOnly = true, timeout = 30)
    public Optional<RefreshJob> find(UUID id) {
        return jdbc.query("SELECT * FROM refresh_job WHERE id = ?", JOB_MAPPER, id).stream().findFirst();
    }

    private RefreshJob requireLiveClaim(UUID id, UUID token) {
        if (token == null) {
            throw new StaleClaimException();
        }
        return jdbc.query("""
                SELECT * FROM refresh_job
                WHERE id = ? AND status = 'RUNNING' AND claim_token = ?
                    AND lease_until > clock_timestamp()
                FOR UPDATE
                """, JOB_MAPPER, id, token).stream().findFirst().orElseThrow(StaleClaimException::new);
    }

    private void retryOrFail(RefreshJob job, String diagnostic, boolean recoveringExpiredClaim) {
        String status = job.attempts() >= MAX_ATTEMPTS ? "FAILED" : "QUEUED";
        // Recovery may operate on an expired lease. Other callers already hold a live row lock.
        int changed = jdbc.update("""
                UPDATE refresh_job
                SET status = ?, claim_token = NULL, lease_until = NULL, diagnostic = ?,
                    available_at = clock_timestamp() + make_interval(secs => ?)
                WHERE id = ? AND claim_token = ?
                    AND (? OR lease_until > clock_timestamp())
                """, status, diagnostic, 30 * job.attempts(), job.id(), job.claimToken(), recoveringExpiredClaim);
        if (changed != 1) {
            throw new StaleClaimException();
        }
        event(job.id(), "worker", status.equals("FAILED") ? "FAILED" : "RETRY_SCHEDULED", diagnostic);
    }

    private void finish(RefreshJob job, String status, String diagnostic) {
        int changed = jdbc.update("""
                UPDATE refresh_job
                SET status = ?, diagnostic = ?, claim_token = NULL, lease_until = NULL
                WHERE id = ? AND claim_token = ? AND lease_until > clock_timestamp()
                """, status, diagnostic, job.id(), job.claimToken());
        if (changed != 1) {
            throw new StaleClaimException();
        }
    }

    private void lockQueue() {
        jdbc.query("SELECT pg_advisory_xact_lock(?)", result -> {
            // The transaction owns the lock until commit or rollback.
        }, QUEUE_LOCK);
    }

    private void event(UUID id, String actor, String action, String diagnostic) {
        jdbc.update("""
                INSERT INTO refresh_job_event(job_id, actor, action, diagnostic)
                VALUES (?, ?, ?, ?)
                """, id, actor, action, diagnostic);
    }

    private static void validateLabel(String value, int maximumLength) {
        if (value == null || !value.matches("[A-Za-z0-9][A-Za-z0-9_.:/-]{0," + (maximumLength - 1) + "}")) {
            throw new IllegalArgumentException("Invalid operational identifier");
        }
    }

    public static class StaleClaimException extends IllegalStateException {
        public StaleClaimException() {
            super("Refresh claim expired, was cancelled, or belongs to another worker");
        }
    }
}
