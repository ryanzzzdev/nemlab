package au.nemlab.api.admin;

import au.nemlab.batterylab.PriceDay;
import au.nemlab.infrastructure.jobs.RefreshJob;
import au.nemlab.infrastructure.jobs.RefreshJobService;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.net.URI;
import java.security.Principal;
import java.time.Instant;
import java.time.LocalDate;
import java.util.List;
import java.util.UUID;

@RestController
@ConditionalOnProperty(name = "nemlab.admin.enabled", havingValue = "true")
@RequestMapping("/api/admin/v1/price-refreshes")
public class AdminRefreshController {
    private final RefreshJobService jobs;

    public AdminRefreshController(RefreshJobService jobs) {
        this.jobs = jobs;
    }

    public record Submission(PriceDay.Region region, LocalDate day) {
    }

    /** Explicit API projection: claim tokens and internal backfill IDs never leave the service. */
    public record JobView(UUID id, PriceDay.Region region, LocalDate day, RefreshJob.Status status,
            int attempts, Instant availableAt, String diagnostic) {
        static JobView of(RefreshJob job) {
            return new JobView(job.id(), job.region(), job.day(), job.status(), job.attempts(),
                    job.availableAt(), job.diagnostic());
        }
    }

    @PostMapping
    public ResponseEntity<JobView> submit(@RequestHeader("Idempotency-Key") String key,
            @RequestBody Submission submission, Principal principal) {
        UUID id = jobs.submit(key, submission.region(), submission.day(), principal.getName());
        return ResponseEntity.accepted()
                .location(URI.create("/api/admin/v1/price-refreshes/" + id))
                .body(JobView.of(required(id)));
    }

    @GetMapping
    public List<JobView> recent(@RequestParam(defaultValue = "50") int limit) {
        return jobs.recent(limit).stream().map(JobView::of).toList();
    }

    @GetMapping("/{id}")
    public JobView status(@PathVariable UUID id) {
        return JobView.of(required(id));
    }

    @GetMapping("/{id}/events")
    public List<RefreshJobService.JobEvent> events(@PathVariable UUID id,
            @RequestParam(defaultValue = "0") long after,
            @RequestParam(defaultValue = "50") int limit) {
        required(id);
        return jobs.events(id, after, limit);
    }

    @PostMapping("/{id}/cancel")
    public JobView cancel(@PathVariable UUID id, Principal principal) {
        required(id);
        jobs.cancel(id, principal.getName());
        return JobView.of(required(id));
    }

    private RefreshJob required(UUID id) {
        return jobs.find(id).orElseThrow(NotFound::new);
    }

    public static class NotFound extends RuntimeException {
    }
}
