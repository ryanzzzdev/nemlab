package au.nemlab.infrastructure.batterylab;

import au.nemlab.batterylab.*;
import au.nemlab.infrastructure.prices.PriceStore;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;
import tools.jackson.databind.json.JsonMapper;
import javax.sql.DataSource;
import java.sql.Timestamp;
import java.time.*;
import java.util.*;

/** Short database transactions; computation always runs outside them. */
public final class SimulationJobs {
    private static final long QUEUE_LOCK = 735_040L;
    private final JdbcTemplate jdbc;
    private final TransactionTemplate tx;
    private final PriceStore prices;
    private final JsonMapper json = new JsonMapper();

    public enum Status { QUEUED, RUNNING, SUCCEEDED, FAILED }

    public record Job(UUID id, Status status, int attempts, UUID token, Instant leaseUntil, String diagnostic) {
    }

    public record Input(String key, SimulationRequest request, PriceDay prices, ScenarioPreparation.Versions versions) {
        public SimulationRequest.Normalised parameters() {
            if (!ScenarioPreparation.Versions.current().equals(versions)) throw new UnsupportedVersion();
            var p = request.normalise(Clock.systemUTC());
            if (prices.region() != request.region() || !prices.date().equals(request.day()))
                throw new IllegalArgumentException("price day mismatch");
            return p;
        }
    }

    private static final RowMapper<Job> MAPPER = (row, n) -> {
        Timestamp lease = row.getTimestamp("lease_until");
        return new Job(row.getObject("id", UUID.class), Status.valueOf(row.getString("status")),
                row.getInt("attempts"), row.getObject("claim_token", UUID.class),
                lease == null ? null : lease.toInstant(), row.getString("diagnostic"));
    };

    public SimulationJobs(DataSource source) {
        jdbc = new JdbcTemplate(source);
        tx = new TransactionTemplate(new DataSourceTransactionManager(source));
        tx.setTimeout(30);
        prices = new PriceStore(source);
    }

    public UUID submit(SimulationRequest request) {
        var prepared = new ScenarioPreparation(prices, Clock.systemUTC()).prepare(request);
        return tx.execute(transaction -> {
            lockQueue();
            var existing = jdbc.query("SELECT id FROM simulation_input WHERE scenario_key=?",
                    (row, n) -> row.getObject(1, UUID.class), prepared.key());
            if (!existing.isEmpty()) return existing.getFirst();
            if (jdbc.queryForObject("SELECT count(*) FROM simulation_job WHERE status IN ('QUEUED','RUNNING')", Integer.class) >= 100)
                throw new QueueFull();
            UUID id = UUID.randomUUID();
            jdbc.update("INSERT INTO simulation_input(id,scenario_key,revision_id,request,versions) VALUES (?,?,?,?::jsonb,?::jsonb)",
                    id, prepared.key(), prepared.priceRevision(), json.writeValueAsString(prepared.parameters().values()),
                    json.writeValueAsString(prepared.versions()));
            jdbc.update("INSERT INTO simulation_job(id,status) VALUES (?,'QUEUED')", id);
            return id;
        });
    }

    public Optional<Job> claim() {
        return tx.execute(transaction -> {
            lockQueue();
            for (Job job : jdbc.query("SELECT * FROM simulation_job WHERE status='RUNNING' AND lease_until<=clock_timestamp() FOR UPDATE", MAPPER))
                retry(job, "LEASE_EXPIRED", true, true);
            if (jdbc.queryForObject("SELECT count(*) FROM simulation_job WHERE status='RUNNING'", Integer.class) > 0)
                return Optional.empty();
            var ready = jdbc.query("SELECT * FROM simulation_job WHERE status='QUEUED' AND available_at<=clock_timestamp() ORDER BY available_at,created_at,id LIMIT 1 FOR UPDATE", MAPPER);
            if (ready.isEmpty()) return Optional.empty();
            UUID id = ready.getFirst().id();
            jdbc.update("UPDATE simulation_job SET status='RUNNING',attempts=attempts+1,claim_token=?,lease_until=clock_timestamp()+interval '60 seconds' WHERE id=?",
                    UUID.randomUUID(), id);
            return find(id);
        });
    }

    public Optional<Job> find(UUID id) {
        return jdbc.query("SELECT * FROM simulation_job WHERE id=?", MAPPER, id).stream().findFirst();
    }

    public Input input(UUID id) {
        return jdbc.queryForObject("SELECT * FROM simulation_input WHERE id=?", (row, n) -> new Input(
                row.getString("scenario_key"), json.readValue(row.getString("request"), SimulationRequest.class),
                prices.revision(row.getObject("revision_id", UUID.class)).toPriceDay(),
                json.readValue(row.getString("versions"), ScenarioPreparation.Versions.class)), id);
    }

    public Optional<SimulationComparison> result(UUID id) {
        return jdbc.query("SELECT result::text FROM simulation_result WHERE id=?",
                (row, n) -> json.readValue(row.getString(1), SimulationComparison.class), id).stream().findFirst();
    }

    public void complete(UUID id, UUID token, SimulationComparison result) {
        tx.executeWithoutResult(transaction -> {
            requireLive(id, token);
            Input input = input(id);
            result.validate(input.parameters(), input.prices(), input.versions().limits());
            jdbc.update("INSERT INTO simulation_result(id,result) VALUES (?,?::jsonb)", id, json.writeValueAsString(result));
            boolean optimal = result.hindsight().status() == OrderedHindsight.Status.OPTIMAL;
            finish(id, token, optimal ? "SUCCEEDED" : "FAILED", optimal ? null : "SOLVER_" + result.hindsight().status());
        });
    }

    public void fail(UUID id, UUID token, String code, boolean retryable) {
        if (code == null || !code.matches("[A-Z][A-Z0-9_]{0,79}")) throw new IllegalArgumentException("safe diagnostic code required");
        tx.executeWithoutResult(transaction -> retry(requireLive(id, token), code, retryable, false));
    }

    private Job requireLive(UUID id, UUID token) {
        if (token == null) throw new StaleClaim();
        return jdbc.query("SELECT * FROM simulation_job WHERE id=? AND status='RUNNING' AND claim_token=? AND lease_until>clock_timestamp() FOR UPDATE",
                MAPPER, id, token).stream().findFirst().orElseThrow(StaleClaim::new);
    }

    private void retry(Job job, String code, boolean retryable, boolean expired) {
        String state = retryable && job.attempts() < 3 ? "QUEUED" : "FAILED";
        int changed = jdbc.update("""
                UPDATE simulation_job SET status=?,diagnostic=?,claim_token=NULL,lease_until=NULL,
                    available_at=clock_timestamp()+make_interval(secs => ?)
                WHERE id=? AND claim_token=? AND (? OR lease_until>clock_timestamp())
                """, state, code, 5 * job.attempts(), job.id(), job.token(), expired);
        if (changed != 1) throw new StaleClaim();
    }

    private void finish(UUID id, UUID token, String state, String diagnostic) {
        int changed = jdbc.update("""
                UPDATE simulation_job SET status=?,diagnostic=?,claim_token=NULL,lease_until=NULL
                WHERE id=? AND status='RUNNING' AND claim_token=? AND lease_until>clock_timestamp()
                """, state, diagnostic, id, token);
        if (changed != 1) throw new StaleClaim();
    }

    private void lockQueue() {
        jdbc.query("SELECT pg_advisory_xact_lock(?)", row -> { }, QUEUE_LOCK);
    }

    public static final class StaleClaim extends IllegalStateException { }
    public static final class QueueFull extends IllegalStateException { }
    public static final class UnsupportedVersion extends IllegalStateException { }
}
