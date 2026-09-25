package au.nemlab.batterylab;

import org.junit.jupiter.api.Test;
import java.math.BigDecimal;
import java.time.*;
import java.util.*;
import java.util.function.IntFunction;
import static org.junit.jupiter.api.Assertions.*;

class PriceThresholdTest {
    static final Thresholds THIRTY_150 = new Thresholds(new BigDecimal("30"), new BigDecimal("150"));

    static Battery site(double capacity, double minimum, double maximum, double initial, double charge,
            double discharge, double importLimit, double exportLimit, Efficiency efficiency) {
        return new Battery(capacity, minimum, maximum, initial, charge, discharge, importLimit,
                exportLimit, efficiency);
    }

    /** 1 MWh site, half full, 12 MW each way, lossless. */
    static Battery ideal() {
        return site(1, 0, 1, .5, 12, 12, 12, 12, new Efficiency(1, 1));
    }

    static PriceDay day(IntFunction<BigDecimal> price) {
        var date = LocalDate.of(2026, 9, 11);
        var start = date.atStartOfDay().toInstant(PriceDay.NEM_OFFSET);
        var values = new ArrayList<PriceDay.Interval>();
        for (int i = 0; i < 288; i++)
            values.add(PriceDay.Interval.fromEnd(PriceDay.Region.NSW1,
                    start.plusSeconds((i + 1L) * 300), price.apply(i)));
        return new PriceDay(PriceDay.Region.NSW1, date, values);
    }

    static PriceDay flat(double price) {
        return day(i -> BigDecimal.valueOf(price));
    }

    static void close(double expected, double actual) {
        assertEquals(expected, actual, 1e-9);
    }

    @Test
    void exactThresholdEqualityHolds() {
        for (double price : new double[] { 30, 150 }) {
            var dispatch = new PriceThreshold().plan(ideal(), THIRTY_150, flat(price));
            for (var step : dispatch.intervals()) {
                close(0, step.importedMWh());
                close(0, step.exportedMWh());
                close(.5, step.endingEnergyMWh());
            }
        }
    }

    @Test
    void decimalBoundariesAreExact() {
        var thresholds = new Thresholds(new BigDecimal("0.1"), new BigDecimal("0.2"));
        var equal = new PriceThreshold().plan(ideal(), thresholds, day(i -> new BigDecimal("0.1")));
        close(0, equal.intervals().get(0).importedMWh());
        var below = new PriceThreshold().plan(ideal(), thresholds, day(i -> new BigDecimal("0.099")));
        assertTrue(below.intervals().get(0).importedMWh() > 0);
    }

    @Test
    void chargesBelowAndDischargesAbove() {
        var prices = day(i -> BigDecimal.valueOf(i == 0 ? 10 : i == 1 ? 200 : 50));
        var dispatch = new PriceThreshold().plan(ideal(), THIRTY_150, prices);
        close(.5, dispatch.intervals().get(0).importedMWh());
        close(1, dispatch.intervals().get(0).endingEnergyMWh());
        close(1, dispatch.intervals().get(1).exportedMWh());
        close(0, dispatch.intervals().get(1).endingEnergyMWh());
        var accounting = Accounting.calculate(ideal(), new TradingCosts(0, 0, 0), prices, dispatch);
        close(.5, accounting.importedMWh());
        close(1, accounting.exportedMWh());
        close(195, accounting.margin()); // 200*1 - 10*0.5
    }

    @Test
    void endsBelowInitialEnergyWithoutForcedTrade() {
        var dispatch = new PriceThreshold().plan(ideal(), THIRTY_150,
                day(i -> BigDecimal.valueOf(i < 2 ? 200 : 50)));
        close(0, dispatch.intervals().get(287).endingEnergyMWh());
        assertDoesNotThrow(() -> DispatchValidator.validateUnrestricted(ideal(), dispatch));
    }

    @Test
    void holdsBetweenThresholdsAllDay() {
        var dispatch = new PriceThreshold().plan(ideal(), THIRTY_150, flat(50));
        close(.5, dispatch.intervals().get(287).endingEnergyMWh());
        assertTrue(dispatch.intervals().stream().allMatch(
                s -> s.importedMWh() == 0 && s.exportedMWh() == 0));
    }

    @Test
    void negativeThresholdsAndPricesWork() {
        var thresholds = new Thresholds(new BigDecimal("-10"), new BigDecimal("-5"));
        var prices = day(i -> BigDecimal.valueOf(i == 0 ? -50 : i == 1 ? 0 : -7));
        var dispatch = new PriceThreshold().plan(ideal(), thresholds, prices);
        close(.5, dispatch.intervals().get(0).importedMWh()); // -50 < -10: charge
        close(1, dispatch.intervals().get(1).exportedMWh()); // 0 > -5: discharge
        close(0, dispatch.intervals().get(2).importedMWh()); // -7 holds between
        close(0, dispatch.intervals().get(2).exportedMWh());
    }

    @Test
    void repeatsCyclesAcrossTheDay() {
        var battery = site(.5, 0, .5, 0, 6, 6, 6, 6, new Efficiency(1, 1)); // .5 MWh per interval
        var prices = day(i -> BigDecimal.valueOf(i % 2 == 0 ? 0 : 200));
        var dispatch = new PriceThreshold().plan(battery, THIRTY_150, prices);
        for (int i = 0; i < 288; i++) {
            var step = dispatch.intervals().get(i);
            close(i % 2 == 0 ? .5 : 0, step.importedMWh());
            close(i % 2 == 0 ? 0 : .5, step.exportedMWh());
        }
        var accounting = Accounting.calculate(battery, new TradingCosts(0, 0, 0), prices, dispatch);
        close(72, accounting.importedMWh());
        close(72, accounting.exportedMWh());
        close(14400, accounting.margin());
    }

    @Test
    void clampsPartialIntervalsAtEnergyBounds() {
        var battery = site(.6, .1, .6, .5, 12, 12, 12, 12, new Efficiency(1, 1));
        var prices = day(i -> BigDecimal.valueOf(i == 0 ? 0 : i == 1 ? 200 : 50));
        var dispatch = new PriceThreshold().plan(battery, THIRTY_150, prices);
        close(.1, dispatch.intervals().get(0).importedMWh()); // headroom .6-.5
        close(.6, dispatch.intervals().get(0).endingEnergyMWh());
        close(.5, dispatch.intervals().get(1).exportedMWh()); // (.6-.1) available
        close(.1, dispatch.intervals().get(1).endingEnergyMWh());
    }

    @Test
    void fullAndEmptySitesDoNotTrade() {
        var full = site(1, 0, 1, 1, 12, 12, 12, 12, new Efficiency(1, 1));
        close(0, new PriceThreshold().plan(full, THIRTY_150, flat(-100)).intervals().get(0).importedMWh());
        var empty = site(1, .4, 1, .4, 12, 12, 12, 12, new Efficiency(1, 1));
        close(0, new PriceThreshold().plan(empty, THIRTY_150, flat(1000)).intervals().get(0).exportedMWh());
    }

    @Test
    void powerAndConnectionLimitsApply() {
        var limited = site(2, 0, 2, 0, 12, 12, 6, 3, new Efficiency(1, 1));
        var prices = day(i -> BigDecimal.valueOf(i < 4 ? 0 : i == 4 ? 200 : 50));
        var dispatch = new PriceThreshold().plan(limited, THIRTY_150, prices);
        close(.5, dispatch.intervals().get(0).importedMWh()); // 6 MW import limit
        close(2, dispatch.intervals().get(3).endingEnergyMWh());
        close(.25, dispatch.intervals().get(4).exportedMWh()); // 3 MW export limit
        var dead = site(2, 0, 2, 1, 0, 12, 12, 12, new Efficiency(1, 1));
        close(0, new PriceThreshold().plan(dead, THIRTY_150, flat(-50)).intervals().get(0).importedMWh());
    }

    @Test
    void lossesAndFeesCanEraseAttractiveTrades() {
        var thresholds = new Thresholds(new BigDecimal("35"), new BigDecimal("40"));
        var lossy = site(4, 0, 4, 0, 12, 12, 12, 12, new Efficiency(.8, .8));
        var costs = new TradingCosts(2, 2, 10);
        var prices = day(i -> BigDecimal.valueOf(i < 4 ? 29 : i == 4 ? 41 : 37));
        var dispatch = new PriceThreshold().plan(lossy, thresholds, prices);
        var a = Accounting.calculate(lossy, costs, prices, dispatch);
        close(4, a.importedMWh()); // 4 intervals * 1 MWh grid-side
        close(1, a.exportedMWh()); // stored 3.2 MWh, interval-limited to 1 MWh out
        close(-95, a.margin()); // 41 - 116 - 8 - 2 - 10
        assertTrue(a.margin() < 0, "losses and fees erase a 29-to-41 spread: " + a.margin());
    }

    @Test
    void laterPricesDoNotChangeEarlierDispatch() {
        var first = day(i -> BigDecimal.valueOf(i < 100 ? (i % 2 == 0 ? 0 : 200) : 50));
        var second = day(i -> BigDecimal.valueOf(i < 100 ? (i % 2 == 0 ? 0 : 200) : (i % 3 == 0 ? -500 : 2000)));
        var a = new PriceThreshold().plan(ideal(), THIRTY_150, first).intervals();
        var b = new PriceThreshold().plan(ideal(), THIRTY_150, second).intervals();
        for (int i = 0; i < 100; i++) assertEquals(a.get(i), b.get(i), "interval " + i);
    }

    @Test
    void rejectsUnorderedOrMissingThresholds() {
        assertThrows(IllegalArgumentException.class,
                () -> new Thresholds(new BigDecimal("150"), new BigDecimal("30")));
        assertThrows(IllegalArgumentException.class,
                () -> new Thresholds(new BigDecimal("30"), new BigDecimal("30")));
        assertThrows(NullPointerException.class, () -> new Thresholds(null, new BigDecimal("30")));
        assertThrows(NullPointerException.class, () -> new Thresholds(new BigDecimal("30"), null));
    }
}
