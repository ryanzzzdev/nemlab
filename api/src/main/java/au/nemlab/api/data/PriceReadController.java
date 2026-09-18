package au.nemlab.api.data;

import au.nemlab.batterylab.PriceDay;
import au.nemlab.infrastructure.prices.PriceBatch;
import au.nemlab.infrastructure.prices.PriceStore;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.http.CacheControl;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.Instant;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

@RestController
@ConditionalOnProperty(name = "nemlab.data.enabled", havingValue = "true")
@RequestMapping("/api/v1/prices")
public class PriceReadController {
    private final PriceStore prices;

    public PriceReadController(PriceStore prices) {
        this.prices = prices;
    }

    public enum Availability {
        NOT_IMPORTED, COMPLETE, INCOMPLETE
    }

    public record DayCoverage(LocalDate day, Availability availability, UUID revision,
            Instant retrievedAt, Integer valid, Integer missing, Integer sourceNull) {
        static DayCoverage absent(LocalDate day) {
            return new DayCoverage(day, Availability.NOT_IMPORTED, null, null, null, null, null);
        }

        static DayCoverage imported(LocalDate day, PriceStore.Coverage coverage) {
            Availability state = coverage.valid() == PriceDay.INTERVALS
                    ? Availability.COMPLETE : Availability.INCOMPLETE;
            return new DayCoverage(day, state, coverage.revision(), coverage.retrievedAt(),
                    coverage.valid(), coverage.missing(), coverage.sourceNull());
        }
    }

    public record CoverageResponse(PriceDay.Region region, LocalDate start, LocalDate endExclusive,
            String marketOffset, List<DayCoverage> days) {
    }

    public record Interval(Instant start, Instant end, PriceBatch.Kind state, String price) {
    }

    public record SeriesResponse(PriceDay.Region region, LocalDate day, String source, String unit,
            int intervalSeconds, String intervalLabel, String marketOffset, DayCoverage coverage,
            List<Interval> intervals) {
    }

    @GetMapping("/{region}/coverage")
    public ResponseEntity<CoverageResponse> coverage(@PathVariable PriceDay.Region region,
            @RequestParam LocalDate start, @RequestParam LocalDate endExclusive) {
        validateRange(start, endExclusive);
        var coverage = prices.coverageRange(region, start, endExclusive);
        List<DayCoverage> days = new ArrayList<>();
        for (LocalDate day = start; day.isBefore(endExclusive); day = day.plusDays(1)) {
            PriceStore.Coverage stored = coverage.get(day);
            days.add(stored == null ? DayCoverage.absent(day) : DayCoverage.imported(day, stored));
        }
        return ResponseEntity.ok().cacheControl(CacheControl.noStore())
                .body(new CoverageResponse(region, start, endExclusive, "+10:00", List.copyOf(days)));
    }

    @GetMapping("/{region}/{day}")
    public ResponseEntity<SeriesResponse> series(@PathVariable PriceDay.Region region, @PathVariable LocalDate day) {
        validateRange(day, day.plusDays(1));
        PriceStore.Coverage coverage = prices.coverage(region, day).orElseThrow(NotImported::new);
        // Resolve the captured immutable revision, even if a refresh advances the current pointer meanwhile.
        PriceBatch batch = prices.revision(coverage.revision());
        Instant midnight = day.atStartOfDay().toInstant(PriceDay.NEM_OFFSET);
        List<Interval> intervals = new ArrayList<>();
        for (int index = 0; index < PriceDay.INTERVALS; index++) {
            PriceBatch.Slot slot = batch.slots().get(index);
            intervals.add(new Interval(midnight.plusSeconds(index * 300L),
                    midnight.plusSeconds((index + 1L) * 300), slot.kind(),
                    slot.price() == null ? null : slot.price().toPlainString()));
        }
        return ResponseEntity.ok().cacheControl(CacheControl.noStore())
                .body(new SeriesResponse(region, day, "Open Electricity", "AUD/MWh", 300, "END", "+10:00",
                        DayCoverage.imported(day, coverage), List.copyOf(intervals)));
    }

    private static void validateRange(LocalDate start, LocalDate end) {
        LocalDate today = LocalDate.now(PriceDay.NEM_OFFSET);
        if (start.isBefore(LocalDate.of(2021, 10, 1)) || !start.isBefore(end)
                || start.plusDays(31).isBefore(end) || end.isAfter(today)) {
            throw new IllegalArgumentException("Require 1–31 completed NEM market days since 2021-10-01");
        }
    }

    public static class NotImported extends RuntimeException {
    }
}
