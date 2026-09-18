package au.nemlab.infrastructure.prices;

import au.nemlab.batterylab.PriceDay;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;
import org.flywaydb.core.Flyway;
import tools.jackson.databind.json.JsonMapper;
import javax.sql.DataSource;
import java.time.*;
import java.sql.Timestamp;
import java.util.*;

public final class PriceStore {
    private final JdbcTemplate jdbc;
    private final TransactionTemplate tx;
    private final JsonMapper json = new JsonMapper();

    public PriceStore(DataSource source) {
        jdbc = new JdbcTemplate(source);
        tx = new TransactionTemplate(new DataSourceTransactionManager(source));
    }

    public static void migrate(DataSource source) {
        Flyway.configure().dataSource(source).locations("classpath:db/migration").load().migrate();
    }

    public record Coverage(UUID revision, int valid, int missing, int sourceNull, Instant retrievedAt) {
    }

    public record Backfill(UUID id, PriceDay.Region region, LocalDate start, LocalDate end, LocalDate next,
            String status, String diagnostic) {
    }

    public UUID save(PriceSource.Fetch fetch) {
        return tx.execute(status -> saveInside(fetch));
    }

    private UUID saveInside(PriceSource.Fetch fetch) {
        var b = fetch.batch();
        UUID candidate = UUID.randomUUID();
        jdbc.update(
                "INSERT INTO price_revision(id,region,market_day,content_hash,slots,valid_count,missing_count,null_count) VALUES (?,?,?,?,?::jsonb,?,?,?) ON CONFLICT(region,market_day,content_hash) DO NOTHING",
                candidate, b.region().name(), b.day(), b.contentHash(), json.writeValueAsString(b.slots()),
                b.count(PriceBatch.Kind.VALUE), b.count(PriceBatch.Kind.MISSING), b.count(PriceBatch.Kind.SOURCE_NULL));
        UUID revision = jdbc.queryForObject(
                "SELECT id FROM price_revision WHERE region=? AND market_day=? AND content_hash=?", UUID.class,
                b.region().name(), b.day(), b.contentHash());
        jdbc.update(
                "INSERT INTO price_current(region,market_day,revision_id,retrieved_at) VALUES (?,?,?,?) ON CONFLICT(region,market_day) DO UPDATE SET revision_id=EXCLUDED.revision_id,retrieved_at=EXCLUDED.retrieved_at WHERE price_current.retrieved_at <= EXCLUDED.retrieved_at",
                b.region().name(), b.day(), revision, Timestamp.from(fetch.retrievedAt()));
        jdbc.update(
                "INSERT INTO price_import_attempt(id,region,market_day,retrieved_at,status,revision_id,response_hash,source_version) VALUES (?,?,?,?,?,?,?,?)",
                UUID.randomUUID(), b.region().name(), b.day(), Timestamp.from(fetch.retrievedAt()),
                b.complete() ? "COMPLETE" : "INCOMPLETE", revision, fetch.responseHash(), fetch.sourceVersion());
        return revision;
    }

    public Optional<Coverage> coverage(PriceDay.Region region, LocalDate day) {
        return jdbc.query(
                "SELECT r.id,r.valid_count,r.missing_count,r.null_count,c.retrieved_at FROM price_current c JOIN price_revision r ON r.id=c.revision_id WHERE c.region=? AND c.market_day=?",
                (rs, n) -> new Coverage(rs.getObject(1, UUID.class), rs.getInt(2), rs.getInt(3), rs.getInt(4),
                        rs.getTimestamp(5).toInstant()),
                region.name(), day).stream().findFirst();
    }

    public record Attempt(UUID id, Instant retrievedAt, String status, UUID revision, String responseHash,
            String sourceVersion, String diagnostic) {
    }

    public java.util.List<Attempt> history(PriceDay.Region region, LocalDate day) {
        return jdbc.query("SELECT * FROM price_import_attempt WHERE region=? AND market_day=? ORDER BY retrieved_at,id",
                (rs, n) -> new Attempt(rs.getObject("id", UUID.class), rs.getTimestamp("retrieved_at").toInstant(),
                        rs.getString("status"),
                        rs.getObject("revision_id", UUID.class), rs.getString("response_hash"),
                        rs.getString("source_version"), rs.getString("diagnostic")),
                region.name(), day);
    }

    public PriceBatch revision(UUID id) {
        return jdbc.queryForObject("SELECT region,market_day,slots::text FROM price_revision WHERE id=?",
                (rs, n) -> new PriceBatch(PriceDay.Region.valueOf(rs.getString(1)), rs.getObject(2, LocalDate.class),
                        Arrays.asList(json.readValue(rs.getString(3), PriceBatch.Slot[].class))),
                id);
    }

    public UUID snapshot(UUID revision) {
        UUID id = UUID.randomUUID();
        jdbc.update("INSERT INTO price_snapshot(id,revision_id) VALUES (?,?)", id, revision);
        return id;
    }

    public PriceDay snapshotPrices(UUID snapshot) {
        return revision(jdbc.queryForObject("SELECT revision_id FROM price_snapshot WHERE id=?", UUID.class, snapshot))
                .toPriceDay();
    }

    public UUID createBackfill(PriceDay.Region region, LocalDate start, LocalDate end, Clock clock) {
        if (start.isBefore(LocalDate.of(2021, 10, 1)) || !start.isBefore(end) || start.plusDays(31).isBefore(end)
                || end.isAfter(LocalDate.now(clock.withZone(PriceDay.NEM_OFFSET))))
            throw new IllegalArgumentException("require 1..31 completed post-settlement days");
        UUID id = UUID.randomUUID();
        jdbc.update(
                "INSERT INTO price_backfill(id,region,start_day,end_exclusive,next_day,status) VALUES (?,?,?,?,?,'ACTIVE')",
                id, region.name(), start, end, start);
        return id;
    }

    public Backfill backfill(UUID id) {
        return jdbc.queryForObject("SELECT * FROM price_backfill WHERE id=?",
                (rs, n) -> new Backfill(id, PriceDay.Region.valueOf(rs.getString("region")),
                        rs.getObject("start_day", LocalDate.class), rs.getObject("end_exclusive", LocalDate.class),
                        rs.getObject("next_day", LocalDate.class), rs.getString("status"), rs.getString("diagnostic")),
                id);
    }

    /**
     * Optimistic checkpoint fence: concurrent/stale work rolls back its entire
     * write.
     */
    public boolean commitDay(UUID id, LocalDate expected, PriceSource.Fetch fetch) {
        return Boolean.TRUE.equals(tx.execute(status -> {
            Backfill b = backfill(id);
            if (!b.next().equals(expected) || !fetch.batch().day().equals(expected)
                    || b.region() != fetch.batch().region() || !expected.isBefore(b.end()))
                throw new IllegalStateException("stale or mismatched backfill day");
            saveInside(fetch);
            boolean complete = fetch.batch().complete();
            LocalDate next = complete ? expected.plusDays(1) : expected;
            String state = complete ? (next.equals(b.end()) ? "COMPLETE" : "ACTIVE") : "PAUSED";
            int changed = jdbc.update(
                    "UPDATE price_backfill SET next_day=?,status=?,diagnostic=? WHERE id=? AND next_day=?",
                    next, state, complete ? null : "Incomplete price day; refresh before advancing", id, expected);
            if (changed != 1)
                throw new IllegalStateException("backfill checkpoint changed concurrently");
            return complete;
        }));
    }

    public void recordFailure(Backfill b, Instant at, String category) {
        tx.executeWithoutResult(status -> {
            jdbc.update(
                    "INSERT INTO price_import_attempt(id,region,market_day,retrieved_at,status,diagnostic) VALUES (?,?,?,?,'FAILED',?)",
                    UUID.randomUUID(), b.region().name(), b.next(), Timestamp.from(at), category);
            jdbc.update(
                    "UPDATE price_backfill SET status='PAUSED',diagnostic=? WHERE id=? AND next_day=? AND status<>'COMPLETE'",
                    category, b.id(), b.next());
        });
    }
}
