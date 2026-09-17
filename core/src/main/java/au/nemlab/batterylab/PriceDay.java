package au.nemlab.batterylab;

import java.math.BigDecimal;
import java.time.*;
import java.util.*;

/** Strict complete-day boundary. Exact source decimals survive normalisation. */
public record PriceDay(Region region, LocalDate date, List<Interval> intervals) {
    public static final ZoneOffset NEM_OFFSET = ZoneOffset.ofHours(10);
    public static final int INTERVALS = 288;
    public enum Region { NSW1, QLD1, SA1, TAS1, VIC1 }
    public record Interval(Region region, Instant start, Instant end, BigDecimal price) {
        public Interval {
            Objects.requireNonNull(region, "region");
            Objects.requireNonNull(start, "start");
            Objects.requireNonNull(end, "end");
            Objects.requireNonNull(price, "price");
            Numbers.finite("price", price.doubleValue());
        }
        public static Interval fromEnd(Region region, Instant end, BigDecimal price) {
            return new Interval(region, end.minusSeconds(300), end, price);
        }
    }
    public PriceDay {
        Objects.requireNonNull(region, "region");
        Objects.requireNonNull(date, "date");
        intervals = List.copyOf(intervals);
        if (intervals.size() != INTERVALS) throw new IllegalArgumentException("require exactly 288 prices");
        Instant start = date.atStartOfDay().toInstant(NEM_OFFSET);
        for (int i = 0; i < INTERVALS; i++) {
            Interval interval = intervals.get(i);
            if (interval.region() != region || !interval.start().equals(start.plusSeconds(i * 300L))
                    || !interval.end().equals(start.plusSeconds((i + 1L) * 300)))
                throw new IllegalArgumentException("wrong region or noncontiguous interval at index " + i);
        }
    }
}
