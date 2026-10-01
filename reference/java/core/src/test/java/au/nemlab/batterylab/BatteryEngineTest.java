package au.nemlab.batterylab;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.junit.jupiter.params.provider.ValueSource;
import java.math.BigDecimal;
import java.time.*;
import java.util.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import static org.junit.jupiter.api.Assertions.*;

class BatteryEngineTest {
    static final ScheduleWindows WINDOWS = new ScheduleWindows(0, 1, 1, 2);
    static final TradingCosts FREE = new TradingCosts(0, 0, 0);

    static Battery battery(double capacity, double initial, double charge, double discharge, Efficiency efficiency) {
        return new Battery(capacity, 0, capacity, initial, charge, discharge, charge, discharge, efficiency);
    }

    static Battery ideal() {
        return battery(1, 0, 12, 12, new Efficiency(1, 1));
    }

    static PriceDay prices(double buy, double sell) {
        var values = new ArrayList<PriceDay.Interval>();
        var date = LocalDate.of(2026, 9, 11);
        var start = date.atStartOfDay().toInstant(PriceDay.NEM_OFFSET);
        for (int i = 0; i < 288; i++)
            values.add(PriceDay.Interval.fromEnd(PriceDay.Region.NSW1,
                    start.plusSeconds((i + 1L) * 300), BigDecimal.valueOf(i == 0 ? buy : i == 1 ? sell : 0)));
        return new PriceDay(PriceDay.Region.NSW1, date, values);
    }

    static BatterySimulation.Result run(Battery battery, double buy, double sell) {
        return new BatterySimulation().run(battery, WINDOWS, FREE, prices(buy, sell));
    }

    static void close(double expected, double actual) {
        assertEquals(expected, actual, 1e-9);
    }

    @ParameterizedTest
    @CsvSource({ "-30,200,230", "100,10,-90", "0,0,0", "-30,-10,20" })
    void referencePrices(double buy, double sell, double margin) {
        var result = run(ideal(), buy, sell);
        close(1, result.accounting().importedMWh());
        close(1, result.accounting().exportedMWh());
        close(margin, result.accounting().margin());
        close(1, result.dispatch().intervals().get(0).endingEnergyMWh());
        close(0, result.dispatch().intervals().get(287).endingEnergyMWh());
    }

    @Test
    void lossAndFeeReference() {
        var result = new BatterySimulation().run(battery(1, 0, 12, 12, new Efficiency(1, .9)),
                WINDOWS, new TradingCosts(2, 2, 10), prices(-30, 200));
        var a = result.accounting();
        close(1, a.importedMWh());
        close(.9, a.exportedMWh());
        close(.1, a.lossesMWh());
        close(-30, a.chargingCost());
        close(180, a.revenue());
        close(3.8, a.fees());
        close(9, a.degradation());
        close(197.2, a.margin());
    }

    @Test
    void connectionLimitCapsTheWholeCycle() {
        var b = new Battery(1, 0, 1, 0, 12, 12, 12, 6, new Efficiency(1, 1));
        var r = run(b, 0, 100);
        close(.5, r.accounting().importedMWh());
        close(.5, r.accounting().exportedMWh());
        close(50, r.accounting().margin());
        assertEquals(Dispatch.Limit.DISCHARGE_WINDOW, r.dispatch().limitingReason());
    }

    @Test
    void idleHasAnExplanation() {
        var full = run(battery(1, 1, 12, 12, new Efficiency(1, 1)), 0, 100);
        close(0, full.accounting().importedMWh());
        close(1, full.dispatch().intervals().getLast().endingEnergyMWh());
        assertEquals(Dispatch.Limit.ENERGY_HEADROOM, full.dispatch().limitingReason());
        var disabled = run(battery(1, 0, 0, 12, new Efficiency(1, 1)), -30, 200);
        close(0, disabled.accounting().margin());
        assertEquals(Dispatch.Limit.CHARGE_WINDOW, disabled.dispatch().limitingReason());
        close(0, run(battery(1, 0, 12, 0, new Efficiency(1, 1)), -30, 200).accounting().importedMWh());
    }

    @Test
    void partialAllocationAndNonzeroInitialInventory() {
        var b = new Battery(3, .5, 2.5, 1, 12, 12, 12, 12, new Efficiency(1, 1));
        var w = new ScheduleWindows(0, 3, 5, 8);
        var d = new FixedSchedule().plan(b, w);
        close(1, d.intervals().get(0).importedMWh());
        close(.5, d.intervals().get(1).importedMWh());
        close(0, d.intervals().get(2).importedMWh());
        close(0, d.intervals().get(4).exportedMWh());
        close(1, d.intervals().get(5).exportedMWh());
        close(.5, d.intervals().get(6).exportedMWh());
        close(1, d.intervals().getLast().endingEnergyMWh());
    }

    @Test
    void splitEfficiencyIsAppliedOncePerLeg() {
        var r = run(battery(2, .3, 12, 12, Efficiency.roundTrip(.81)), -30, 200);
        close(1, r.accounting().importedMWh());
        close(.81, r.accounting().exportedMWh());
        close(.19, r.accounting().lossesMWh());
        close(.3, r.dispatch().intervals().getLast().endingEnergyMWh());
    }

    @Test
    void pricePermutationAndCostsCannotChangeDispatch() {
        var first = run(ideal(), -30, 200);
        var second = new BatterySimulation().run(ideal(), WINDOWS, new TradingCosts(500, 500, 500), prices(200, -30));
        assertEquals(first.dispatch(), second.dispatch());
        assertNotEquals(first.accounting().margin(), second.accounting().margin());
        assertArrayEquals(new Class<?>[] { Battery.class, ScheduleWindows.class },
                Arrays.stream(FixedSchedule.class.getDeclaredMethods()).filter(m -> m.getName().equals("plan"))
                        .findFirst().orElseThrow().getParameterTypes());
    }

    @Test
    void independentRandomisedPhysicalAndFinancialChecks() {
        Random random = new Random(9341);
        for (int n = 0; n < 200; n++) {
            double capacity = .01 + random.nextDouble() * 1000;
            var b = battery(capacity, capacity * random.nextDouble(), random.nextDouble() * 100,
                    random.nextDouble() * 100, Efficiency.roundTrip(.5 + random.nextDouble() * .5));
            var w = new ScheduleWindows(60, 170, 200, 280);
            var template = prices(0, 0);
            var observations = new ArrayList<PriceDay.Interval>();
            for (var interval : template.intervals())
                observations.add(PriceDay.Interval.fromEnd(
                        template.region(), interval.end(), BigDecimal.valueOf(random.nextDouble() * 600 - 200)));
            var day = new PriceDay(template.region(), template.date(), observations);
            var costs = new TradingCosts(2, 3, 4);
            var r = new BatterySimulation().run(b, w, costs, day);
            double energy = b.initialMWh(), bought = 0, sold = 0, money = 0;
            for (int i = 0; i < 288; i++) {
                var step = r.dispatch().intervals().get(i);
                double c = step.importedMWh(), d = step.exportedMWh();
                assertTrue(c == 0 || d == 0);
                assertTrue(c <= b.effectiveChargeMW() / 12 + 1e-9);
                assertTrue(d <= b.effectiveDischargeMW() / 12 + 1e-9);
                assertTrue(w.canCharge(i) || c == 0);
                assertTrue(w.canDischarge(i) || d == 0);
                energy += c * b.efficiency().charge() - d / b.efficiency().discharge();
                assertTrue(energy >= b.minimumMWh() - 1e-8 && energy <= b.maximumMWh() + 1e-8);
                assertEquals(energy, step.endingEnergyMWh(), 1e-8);
                bought += c;
                sold += d;
                double price = day.intervals().get(i).price().doubleValue();
                money += (price - 3 - 4) * d - (price + 2) * c;
            }
            assertEquals(b.initialMWh(), energy, 1e-8);
            assertEquals(money, r.accounting().margin(), 1e-7);
            assertEquals(bought - sold, r.accounting().lossesMWh(), 1e-7);
        }
    }

    @ParameterizedTest
    @ValueSource(doubles = { Double.NaN, Double.POSITIVE_INFINITY, -1 })
    void invalidPhysicalInputs(double value) {
        assertThrows(IllegalArgumentException.class, () -> battery(1, 0, value, 12, new Efficiency(1, 1)));
        assertThrows(IllegalArgumentException.class, () -> new TradingCosts(value, 0, 0));
    }

    @ParameterizedTest
    @ValueSource(doubles = { 0, -1, 1.1, Double.NaN, Double.POSITIVE_INFINITY })
    void invalidEfficiency(double value) {
        assertThrows(IllegalArgumentException.class, () -> Efficiency.roundTrip(value));
        assertThrows(IllegalArgumentException.class, () -> new Efficiency(1, value));
    }

    @Test
    void invalidBoundsAndDerivedOverflow() {
        assertThrows(IllegalArgumentException.class, () -> battery(0, 0, 1, 1, new Efficiency(1, 1)));
        assertThrows(IllegalArgumentException.class, () -> battery(1, 2, 1, 1, new Efficiency(1, 1)));
        assertThrows(IllegalArgumentException.class, () -> new Battery(1, .5, 1, .2, 1, 1, 1, 1, new Efficiency(1, 1)));
        assertThrows(IllegalArgumentException.class, () -> new FixedSchedule().plan(
                battery(1, 0, 12, 12, new Efficiency(1, Double.MIN_VALUE)), WINDOWS));
        assertThrows(IllegalArgumentException.class, () -> run(
                battery(100, 0, 1200, 1200, new Efficiency(1, 1)), Double.MAX_VALUE, 0));
    }

    @ParameterizedTest
    @CsvSource({ "0,0,1,2", "0,3,2,4", "10,12,0,2", "-1,1,2,3", "0,1,2,289" })
    void rejectsUnsupportedWindows(int a, int b, int c, int d) {
        assertThrows(IllegalArgumentException.class, () -> new ScheduleWindows(a, b, c, d));
    }

    @Test
    void minuteBoundariesIncludeMidnightButRejectMisalignment() {
        assertEquals(new ScheduleWindows(120, 168, 204, 288), ScheduleWindows.minutes(600, 840, 1020, 1440));
        assertThrows(IllegalArgumentException.class, () -> ScheduleWindows.minutes(601, 840, 1020, 1440));
    }

    @Test
    void priceDayRejectsGapsDuplicatesWrongRegionsAndWrongDurations() {
        var good = prices(0, -1);
        var list = new ArrayList<>(good.intervals());
        list.removeLast();
        assertThrows(IllegalArgumentException.class, () -> new PriceDay(good.region(), good.date(), list));
        for (int variant = 0; variant < 4; variant++) {
            var bad = new ArrayList<>(good.intervals());
            var original = bad.get(1);
            bad.set(1, switch (variant) {
                case 0 -> bad.get(0);
                case 1 ->
                    new PriceDay.Interval(PriceDay.Region.QLD1, original.start(), original.end(), original.price());
                case 2 -> new PriceDay.Interval(original.region(), original.start(), original.end().plusSeconds(1),
                        original.price());
                default -> new PriceDay.Interval(original.region(), original.start().plusSeconds(300),
                        original.end().plusSeconds(300), original.price());
            });
            assertThrows(IllegalArgumentException.class, () -> new PriceDay(good.region(), good.date(), bad));
        }
        assertThrows(IllegalArgumentException.class,
                () -> new PriceDay(good.region(), good.date().plusDays(1), good.intervals()));
        assertThrows(IllegalArgumentException.class, () -> PriceDay.Interval.fromEnd(good.region(),
                good.intervals().getFirst().end(), new BigDecimal("1e999")));
    }

    @Test
    void marketDayIsAlwaysFixedOffsetIncludingSydneyDst() {
        var date = LocalDate.of(2026, 10, 4);
        var start = date.atStartOfDay().toInstant(PriceDay.NEM_OFFSET);
        var entries = new ArrayList<PriceDay.Interval>();
        BigDecimal exact = new BigDecimal("-0.123456789123456789");
        for (int i = 0; i < 288; i++)
            entries.add(PriceDay.Interval.fromEnd(PriceDay.Region.NSW1, start.plusSeconds((i + 1L) * 300), exact));
        var day = new PriceDay(PriceDay.Region.NSW1, date, entries);
        assertEquals(Duration.ofHours(24),
                Duration.between(day.intervals().getFirst().start(), day.intervals().getLast().end()));
        assertEquals(exact, day.intervals().getFirst().price());
        entries.clear();
        assertEquals(288, day.intervals().size());
        assertThrows(UnsupportedOperationException.class, () -> day.intervals().clear());
    }

    @Test
    void validatorRejectsTamperedDispatch() {
        var good = new FixedSchedule().plan(ideal(), WINDOWS);
        for (int variant = 0; variant < 5; variant++) {
            var list = new ArrayList<>(good.intervals());
            switch (variant) {
                case 0 -> list.set(0, new Dispatch.Interval(1, 0, .8)); // false energy
                case 1 -> list.set(0, new Dispatch.Interval(2, 0, 2)); // power and capacity
                case 2 -> list.set(0, new Dispatch.Interval(1, .1, .9)); // simultaneous
                case 3 -> list.set(5, new Dispatch.Interval(.1, 0, .1)); // outside window
                default -> {
                    for (int i = 1; i < 288; i++)
                        list.set(i, new Dispatch.Interval(0, 0, 1));
                } // unsold inventory
            }
            var bad = new Dispatch(list, good.limitingReason());
            assertThrows(IllegalArgumentException.class, () -> DispatchValidator.validate(ideal(), WINDOWS, bad));
        }
        assertThrows(IllegalArgumentException.class, () -> DispatchValidator.validate(ideal(), WINDOWS,
                new Dispatch(List.of(), Dispatch.Limit.ENERGY_HEADROOM)));
    }

    @Test
    void validatorChecksEachReportedIntervalBalanceAsWellAsCumulativeBalance() {
        var b = battery(1, .5, 0, 0, new Efficiency(1, 1));
        var good = new FixedSchedule().plan(b, WINDOWS);
        var list = new ArrayList<>(good.intervals());
        list.set(0, new Dispatch.Interval(0, 0, .5 + 8e-8));
        list.set(1, new Dispatch.Interval(0, 0, .5 - 8e-8));
        assertThrows(IllegalArgumentException.class, () -> DispatchValidator.validate(b, WINDOWS,
                new Dispatch(list, good.limitingReason())));
    }

    @Test
    void accountingToleranceRejectsMaterialErrorsAndNonfiniteValues() {
        assertTrue(Accounting.reconciles(197.2, 197.2 + 1e-7));
        assertFalse(Accounting.reconciles(197.2, 197.21));
        assertFalse(Accounting.reconciles(Double.NaN, 0));
    }

    @ParameterizedTest
    @ValueSource(strings = { "2023-09-11", "2026-09-11" })
    void sampledOeDays(String dateText) throws IOException {
        var date = LocalDate.parse(dateText);
        var entries = new ArrayList<PriceDay.Interval>();
        try (var reader = new BufferedReader(new InputStreamReader(Objects.requireNonNull(
                getClass().getResourceAsStream("/prices/" + dateText + ".csv")), StandardCharsets.UTF_8))) {
            reader.readLine();
            for (String line; (line = reader.readLine()) != null;) {
                String[] cells = line.split(",");
                entries.add(PriceDay.Interval.fromEnd(PriceDay.Region.NSW1, OffsetDateTime.parse(cells[0]).toInstant(),
                        new BigDecimal(cells[1])));
            }
        }
        var day = new PriceDay(PriceDay.Region.NSW1, date, entries);
        var b = battery(2, 0, 1, 1, Efficiency.roundTrip(.9));
        var r = new BatterySimulation().run(b, ScheduleWindows.minutes(600, 840, 1020, 1260), FREE, day);
        // Independent decimal dot product from source prices and returned dispatch.
        BigDecimal expected = BigDecimal.ZERO;
        for (int i = 0; i < 288; i++) {
            var d = r.dispatch().intervals().get(i);
            expected = expected.add(entries.get(i).price().multiply(BigDecimal.valueOf(d.exportedMWh())
                    .subtract(BigDecimal.valueOf(d.importedMWh()))));
        }
        assertEquals(expected.doubleValue(), r.accounting().margin(), 1e-8);
        close(0, r.dispatch().intervals().getLast().endingEnergyMWh());
        close(2 / Math.sqrt(.9), r.accounting().importedMWh());
        close(2 * Math.sqrt(.9), r.accounting().exportedMWh());
    }
}
