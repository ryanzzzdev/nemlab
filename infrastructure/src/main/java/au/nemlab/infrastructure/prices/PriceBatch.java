package au.nemlab.infrastructure.prices;

import au.nemlab.batterylab.PriceDay;
import java.math.BigDecimal;
import java.time.*;
import java.util.*;
import java.nio.charset.StandardCharsets;
import java.security.*;

/**
 * A normalised day preserves missing observations separately from explicit
 * source nulls.
 */
public record PriceBatch(PriceDay.Region region, LocalDate day, List<Slot> slots) {
    public enum Kind {
        VALUE, MISSING, SOURCE_NULL
    }

    public record Slot(Kind kind, BigDecimal price) {
        public Slot {
            Objects.requireNonNull(kind);
            if ((kind == Kind.VALUE) != (price != null))
                throw new IllegalArgumentException("invalid slot state");
            if (price != null) {
                if (price.precision() > 38 || Math.abs((long) price.scale()) > 18
                        || !Double.isFinite(price.doubleValue()))
                    throw new IllegalArgumentException("nonfinite price");
                price = price.stripTrailingZeros();
            }
        }
    }

    public PriceBatch {
        Objects.requireNonNull(region);
        Objects.requireNonNull(day);
        slots = List.copyOf(slots);
        if (slots.size() != 288)
            throw new IllegalArgumentException("expected 288 normalised slots");
    }

    public int count(Kind kind) {
        return (int) slots.stream().filter(s -> s.kind() == kind).count();
    }

    public boolean complete() {
        return count(Kind.VALUE) == 288;
    }

    public PriceDay toPriceDay() {
        if (!complete())
            throw new IllegalStateException("incomplete day cannot be simulated");
        Instant start = day.atStartOfDay().toInstant(PriceDay.NEM_OFFSET);
        var intervals = new ArrayList<PriceDay.Interval>();
        for (int i = 0; i < 288; i++)
            intervals.add(PriceDay.Interval.fromEnd(region, start.plusSeconds((i + 1L) * 300), slots.get(i).price()));
        return new PriceDay(region, day, intervals);
    }

    public String contentHash() {
        StringBuilder canonical = new StringBuilder("oe-price-v1|AUD/MWh|5m|interval-end|+10:00|" + region + "|" + day);
        for (var slot : slots)
            canonical.append('|').append(slot.kind()).append(':')
                    .append(slot.price() == null ? "" : slot.price().toPlainString());
        return hash(canonical.toString());
    }

    public static String hash(String text) {
        try {
            return HexFormat.of()
                    .formatHex(MessageDigest.getInstance("SHA-256").digest(text.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }
}
