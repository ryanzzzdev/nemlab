package au.nemlab.infrastructure.batterylab;

import au.nemlab.batterylab.*;
import au.nemlab.infrastructure.prices.*;
import org.junit.jupiter.api.*;
import org.postgresql.ds.PGSimpleDataSource;
import org.springframework.jdbc.core.JdbcTemplate;
import org.testcontainers.postgresql.PostgreSQLContainer;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.time.*;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;

class ScenarioPreparationTest {
    static final PostgreSQLContainer POSTGRES = new PostgreSQLContainer("postgres:18.6-alpine");
    static final Instant AT = Instant.parse("2026-09-20T00:00:00Z");
    static final LocalDate DAY = LocalDate.of(2023, 9, 11);
    static PGSimpleDataSource source;
    static PriceSource.Fetch fixture;
    PriceStore prices;
    JdbcTemplate jdbc;
    ScenarioPreparation preparation;

    @BeforeAll
    static void start() throws Exception {
        POSTGRES.start();
        source = new PGSimpleDataSource();
        source.setURL(POSTGRES.getJdbcUrl());
        source.setUser(POSTGRES.getUsername());
        source.setPassword(POSTGRES.getPassword());
        PriceStore.migrate(source);
        String body = new String(Objects.requireNonNull(ScenarioPreparationTest.class
                .getResourceAsStream("/historical-price-response.json")).readAllBytes(), StandardCharsets.UTF_8);
        fixture = OePriceSource.parse(PriceDay.Region.NSW1, DAY, body, AT);
    }

    @AfterAll
    static void stop() { POSTGRES.stop(); }

    @BeforeEach
    void reset() {
        prices = new PriceStore(source);
        jdbc = new JdbcTemplate(source);
        jdbc.execute("TRUNCATE simulation_result, simulation_job, simulation_input, refresh_job_event, refresh_request, refresh_job, price_snapshot, price_current, price_import_attempt, price_revision, price_backfill");
        preparation = new ScenarioPreparation(prices, Clock.fixed(AT, ZoneOffset.UTC));
    }

    static BigDecimal n(String value) { return new BigDecimal(value); }

    static SimulationRequest request() {
        return new SimulationRequest(PriceDay.Region.NSW1, DAY,
                new SimulationRequest.Site(n("2"), n("0"), n("2"), n("0"), n("1"), n("1"), n("1"), n("1")),
                new SimulationRequest.EfficiencyInput(null, null, n(".9")),
                new SimulationRequest.Costs(n("2"), n("2"), n("10")),
                new SimulationRequest.Windows(600, 840, 1020, 1260));
    }

    @Test
    void capturedHistoricalFixtureRunsThroughTheExistingEngine() {
        UUID revision = prices.save(fixture);
        var p = preparation.prepare(request());
        assertEquals(revision, p.priceRevision());
        assertEquals(fixture.batch().toPriceDay(), p.prices());
        assertEquals(64, p.key().length());
        var inputs = p.parameters();
        var fixed = new BatterySimulation().run(inputs.battery(), inputs.windows(), inputs.costs(), p.prices());
        assertEquals(437.258414, fixed.accounting().margin(), .00001);
        var hindsight = new OrderedHindsight().solve(inputs.battery(), inputs.windows(), inputs.costs(), p.prices(), p.versions().limits());
        assertEquals(OrderedHindsight.Status.OPTIMAL, hindsight.status());
        assertEquals(479.141462, hindsight.accounting().margin(), .00001);
        assertEquals(0, count("price_snapshot"));
        assertEquals(0, count("refresh_job"));
        assertEquals(1, count("price_import_attempt"));
    }

    @Test
    void equivalentRequestsAndRepeatedImportsHaveTheSameKey() {
        prices.save(fixture);
        var r = request();
        var p = preparation.prepare(r);
        var s = r.site();
        var scaled = new SimulationRequest.Site(n("2.000"), s.minimumMWh(), s.maximumMWh(), n("-0.00"),
                s.chargeMW(), s.dischargeMW(), s.importLimitMW(), s.exportLimitMW());
        var equivalent = new SimulationRequest(r.region(), r.day(), scaled, p.parameters().values().efficiency(), r.costs(), r.windows());
        prices.save(new PriceSource.Fetch(fixture.batch(), AT.plusSeconds(1), fixture.responseHash(), fixture.sourceVersion()));
        assertEquals(p.key(), preparation.prepare(equivalent).key());
        assertEquals(1, count("price_revision"));
    }

    @Test
    void correctionsChangeNewKeysButNeverCapturedInputs() {
        prices.save(fixture);
        var before = preparation.prepare(request());
        var slots = new ArrayList<>(fixture.batch().slots());
        slots.set(0, new PriceBatch.Slot(PriceBatch.Kind.VALUE, n("123.4567890123456789")));
        prices.save(new PriceSource.Fetch(new PriceBatch(PriceDay.Region.NSW1, DAY, slots), AT.plusSeconds(1), PriceBatch.hash("test"), "test"));
        var after = preparation.prepare(request());
        assertNotEquals(before.key(), after.key());
        assertNotEquals(before.priceRevision(), after.priceRevision());
        assertEquals(fixture.batch().toPriceDay(), before.prices());
        assertEquals(before.prices(), prices.revision(before.priceRevision()).toPriceDay());
        assertEquals(n("123.4567890123456789"), after.prices().intervals().getFirst().price());
    }

    @Test
    void unavailableAndIncompleteDaysNeverCreateWork() {
        assertEquals("PRICE_DAY_UNAVAILABLE", assertThrows(SimulationRequest.Invalid.class,
                () -> preparation.prepare(request())).code());
        for (var kind : List.of(PriceBatch.Kind.MISSING, PriceBatch.Kind.SOURCE_NULL)) {
            var slots = new ArrayList<>(fixture.batch().slots());
            slots.set(0, new PriceBatch.Slot(kind, null));
            prices.save(new PriceSource.Fetch(new PriceBatch(PriceDay.Region.NSW1, DAY, slots), AT, PriceBatch.hash("test"), "test"));
            assertEquals("PRICE_DAY_INCOMPLETE", assertThrows(SimulationRequest.Invalid.class,
                    () -> preparation.prepare(request())).code());
        }
        assertEquals(0, count("price_snapshot"));
        assertEquals(0, count("refresh_job"));
        assertEquals(0, count("price_backfill"));
    }

    @Test
    void invalidParametersAreRejectedBeforeDatabaseAccess() {
        var unavailableSource = new PGSimpleDataSource();
        unavailableSource.setURL("jdbc:postgresql://127.0.0.1:1/unused");
        var service = new ScenarioPreparation(new PriceStore(unavailableSource), Clock.fixed(AT, ZoneOffset.UTC));
        var r = request();
        assertEquals("REQUIRED", assertThrows(SimulationRequest.Invalid.class, () -> service.prepare(null)).code());
        assertEquals("site", assertThrows(SimulationRequest.Invalid.class, () -> service.prepare(
                new SimulationRequest(r.region(), r.day(), null, r.efficiency(), r.costs(), r.windows()))).field());
    }

    @Test
    void eachResultAffectingParameterParticipatesInIdentity() {
        prices.save(fixture);
        var r = request();
        String baseline = preparation.prepare(r).key();
        List<SimulationRequest> variants = new ArrayList<>();
        // Vary every site field independently, preserving valid exact energy ordering.
        for (int field = 0; field < 8; field++) {
            var values = new BigDecimal[] { n("2"), n("0"), n("2"), n("0"), n("1"), n("1"), n("1"), n("1") };
            values[field] = n(field == 0 ? "3" : field == 2 ? "1.5" : ".5");
            if (field == 1) values[3] = n(".5");
            var s = new SimulationRequest.Site(values[0], values[1], values[2], values[3], values[4], values[5], values[6], values[7]);
            variants.add(new SimulationRequest(r.region(), r.day(), s, r.efficiency(), r.costs(), r.windows()));
        }
        for (int field = 0; field < 3; field++) {
            var values = new BigDecimal[] { n("2"), n("2"), n("10") };
            values[field] = n("3");
            variants.add(new SimulationRequest(r.region(), r.day(), r.site(), r.efficiency(),
                    new SimulationRequest.Costs(values[0], values[1], values[2]), r.windows()));
        }
        var leg = r.normalise(Clock.fixed(AT, ZoneOffset.UTC)).values().efficiency().charge();
        for (var e : List.of(new SimulationRequest.EfficiencyInput(n(".8"), leg, null),
                new SimulationRequest.EfficiencyInput(leg, n(".8"), null)))
            variants.add(new SimulationRequest(r.region(), r.day(), r.site(), e, r.costs(), r.windows()));
        for (int field = 0; field < 4; field++) {
            var minutes = new int[] { 600, 840, 1020, 1260 };
            minutes[field] += 5;
            variants.add(new SimulationRequest(r.region(), r.day(), r.site(), r.efficiency(), r.costs(),
                    new SimulationRequest.Windows(minutes[0], minutes[1], minutes[2], minutes[3])));
        }
        Set<String> keys = new HashSet<>();
        for (var variant : variants) {
            String key = preparation.prepare(variant).key();
            assertNotEquals(baseline, key);
            assertTrue(keys.add(key));
        }
        var version = ScenarioPreparation.Versions.current();
        assertTrue(version.canonical().contains(BatterySimulation.MODEL_VERSION));
        assertTrue(version.canonical().contains(OrderedHindsight.SOLVER));
        assertTrue(version.canonical().contains(FixedSchedule.VERSION));
        assertTrue(version.canonical().contains(OrderedHindsight.VERSION));
    }

    private int count(String table) {
        return jdbc.queryForObject("SELECT count(*) FROM " + table, Integer.class);
    }
}
