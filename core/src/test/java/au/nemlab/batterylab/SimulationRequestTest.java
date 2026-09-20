package au.nemlab.batterylab;

import org.junit.jupiter.api.Test;
import java.math.BigDecimal;
import java.time.*;
import java.util.List;
import static org.junit.jupiter.api.Assertions.*;

class SimulationRequestTest {
    static final Clock CLOCK = Clock.fixed(Instant.parse("2026-09-20T00:00:00Z"), ZoneOffset.UTC);

    static SimulationRequest request() {
        return new SimulationRequest(PriceDay.Region.NSW1, LocalDate.of(2023, 9, 11),
                new SimulationRequest.Site(n("2"), n("0"), n("2"), n("0"), n("1"), n("1"), n("1"), n("1")),
                new SimulationRequest.EfficiencyInput(null, null, n("0.9")),
                new SimulationRequest.Costs(n("2"), n("2"), n("10")),
                new SimulationRequest.Windows(600, 840, 1020, 1260));
    }

    static BigDecimal n(String value) { return new BigDecimal(value); }

    static SimulationRequest with(SimulationRequest.Site site, SimulationRequest.EfficiencyInput efficiency,
            SimulationRequest.Costs costs, SimulationRequest.Windows windows) {
        var r = request();
        return new SimulationRequest(r.region(), r.day(), site, efficiency, costs, windows);
    }

    static void rejects(SimulationRequest r, String field, String code) {
        var error = assertThrows(SimulationRequest.Invalid.class, () -> r.normalise(CLOCK));
        assertEquals(field, error.field());
        assertEquals(code, error.code());
    }

    @Test
    void normalisationPreservesDecimalsAndUsesExistingEngineRules() {
        var r = request();
        var p = r.normalise(CLOCK);
        assertEquals(Efficiency.roundTrip(.9), p.battery().efficiency());
        assertEquals(ScheduleWindows.minutes(600, 840, 1020, 1260), p.windows());
        assertEquals(new TradingCosts(2, 2, 10), p.costs());
        assertEquals(p.canonical(), p.values().normalise(CLOCK).canonical());
        assertNull(p.values().efficiency().roundTrip());
        var exact = new SimulationRequest.Costs(n("2.000000000000000001"), n("2"), n("10"));
        assertEquals(exact.importFee(), with(r.site(), r.efficiency(), exact, r.windows())
                .normalise(CLOCK).values().costs().importFee());
    }

    @Test
    void equivalentScaleAndEfficiencyFormsHaveOneCanonicalRepresentation() {
        var r = request();
        var s = new SimulationRequest.Site(n("2.00"), n("-0.000"), n("2.0"), n("0"),
                n("1.000"), n("1"), n("1"), n("1"));
        var legs = r.normalise(CLOCK).values().efficiency();
        assertEquals(r.normalise(CLOCK).canonical(), with(s, legs, r.costs(), r.windows()).normalise(CLOCK).canonical());
    }

    @Test
    void rejectsRequiredFieldsAndAmbiguousEfficiency() {
        var r = request();
        rejects(with(null, r.efficiency(), r.costs(), r.windows()), "site", "REQUIRED");
        rejects(with(r.site(), null, r.costs(), r.windows()), "efficiency", "REQUIRED");
        rejects(with(r.site(), r.efficiency(), null, r.windows()), "costs", "REQUIRED");
        rejects(with(r.site(), r.efficiency(), r.costs(), null), "windows", "REQUIRED");
        rejects(with(r.site(), new SimulationRequest.EfficiencyInput(n("1"), null, n(".9")), r.costs(), r.windows()),
                "efficiency", "AMBIGUOUS_EFFICIENCY");
        rejects(with(r.site(), new SimulationRequest.EfficiencyInput(n("1"), null, null), r.costs(), r.windows()),
                "efficiency.discharge", "REQUIRED");
        rejects(new SimulationRequest(null, r.day(), r.site(), r.efficiency(), r.costs(), r.windows()), "region", "REQUIRED");
        rejects(new SimulationRequest(r.region(), null, r.site(), r.efficiency(), r.costs(), r.windows()), "day", "REQUIRED");
    }

    @Test
    void rejectsNumericBudgetsAndExactInvalidEnergyOrdering() {
        var r = request();
        for (String value : List.of("-1", "1000001", "0")) {
            var s = new SimulationRequest.Site(n(value), n("0"), n("0"), n("0"), n("1"), n("1"), n("1"), n("1"));
            rejects(with(s, r.efficiency(), r.costs(), r.windows()), "site.capacityMWh", "OUT_OF_RANGE");
        }
        for (String value : List.of("1e-19", "1e100000", "0.000000000000000000000000000000000000001")) {
            rejects(with(r.site(), r.efficiency(), new SimulationRequest.Costs(n(value), n("0"), n("0")), r.windows()),
                    "costs.importFee", "DECIMAL_LIMIT");
        }
        var s = new SimulationRequest.Site(n("2"), n("0"), n("2"), n("2.000000000000000001"),
                n("1"), n("1"), n("1"), n("1"));
        rejects(with(s, r.efficiency(), r.costs(), r.windows()), "site", "INVALID_BOUNDS");
        for (String value : List.of("0", "0.009", "1.01"))
            rejects(with(r.site(), new SimulationRequest.EfficiencyInput(n(value), n("1"), null), r.costs(), r.windows()),
                    "efficiency.charge", "OUT_OF_RANGE");
        rejects(with(r.site(), new SimulationRequest.EfficiencyInput(null, null, n(".00009")), r.costs(), r.windows()),
                "efficiency.roundTrip", "OUT_OF_RANGE");
    }

    @Test
    void acceptsIdleSitesAndExplicitBoundaryEfficiencies() {
        var r = request();
        var site = new SimulationRequest.Site(n("1000000"), n("0"), n("1000000"), n("1000000"),
                n("0"), n("0"), n("0"), n("0"));
        var p = with(site, new SimulationRequest.EfficiencyInput(null, null, n(".0001")), r.costs(), r.windows()).normalise(CLOCK);
        assertEquals(new Efficiency(.01, .01), p.battery().efficiency());
        assertDoesNotThrow(() -> new FixedSchedule().plan(p.battery(), p.windows()));
    }

    @Test
    void validatesWindowsAndAllowsAdjacentWindowsEndingAtMidnight() {
        var r = request();
        for (var w : List.of(new SimulationRequest.Windows(0, 0, 5, 10),
                new SimulationRequest.Windows(0, 20, 10, 30), new SimulationRequest.Windows(600, 840, 0, 120)))
            rejects(with(r.site(), r.efficiency(), r.costs(), w), "windows", "INVALID_WINDOWS");
        rejects(with(r.site(), r.efficiency(), r.costs(), new SimulationRequest.Windows(1, 10, 20, 30)),
                "windows.chargeStart", "INVALID_WINDOWS");
        rejects(with(r.site(), r.efficiency(), r.costs(), new SimulationRequest.Windows(null, 10, 20, 30)),
                "windows.chargeStart", "REQUIRED");
        rejects(with(r.site(), r.efficiency(), r.costs(), new SimulationRequest.Windows(0, 10, 20, 1445)),
                "windows.dischargeEnd", "INVALID_WINDOWS");
        assertEquals(new ScheduleWindows(0, 1, 1, 288),
                with(r.site(), r.efficiency(), r.costs(), new SimulationRequest.Windows(0, 5, 5, 1440)).normalise(CLOCK).windows());
    }

    @Test
    void marketDayEligibilityUsesFixedNemTime() {
        var r = request();
        for (LocalDate day : List.of(LocalDate.of(2021, 9, 30), LocalDate.of(2026, 9, 20), LocalDate.MAX))
            rejects(new SimulationRequest(r.region(), day, r.site(), r.efficiency(), r.costs(), r.windows()), "day", "OUT_OF_RANGE");
        var previous = new SimulationRequest(r.region(), LocalDate.of(2026, 9, 19), r.site(), r.efficiency(), r.costs(), r.windows());
        assertDoesNotThrow(() -> previous.normalise(Clock.fixed(Instant.parse("2026-09-19T14:00:00Z"), ZoneId.of("Australia/Sydney"))));
        assertThrows(SimulationRequest.Invalid.class,
                () -> previous.normalise(Clock.fixed(Instant.parse("2026-09-19T13:59:59Z"), ZoneOffset.UTC)));
    }
}
