package au.nemlab.api.simulation;

import au.nemlab.batterylab.*;
import au.nemlab.infrastructure.batterylab.*;
import au.nemlab.infrastructure.jobs.RefreshJobService;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
import java.io.IOException;
import java.time.Instant;
import java.util.*;

@RestController
@ConditionalOnProperty(name = "nemlab.simulation-api.enabled", havingValue = "true")
@RequestMapping("/api/v1/simulations")
public class SimulationController {
    private final SimulationJobs jobs;
    private final RefreshJobService refreshes;

    public SimulationController(SimulationJobs jobs, RefreshJobService refreshes) {
        this.jobs = jobs;
        this.refreshes = refreshes;
    }

    public record JobResponse(UUID id, SimulationJobs.Status status, int attempts, String failureCode,
            String statusUrl, String resultUrl) { }
    public record PriceInterval(Instant start, Instant end, String price) { }
    public record Strategy(Dispatch dispatch, Accounting accounting) { }
    public record ThresholdView(String version, Map<String, String> thresholds, Dispatch dispatch,
            Accounting accounting) { }
    public record Solver(OrderedHindsight.Status status, Double objective, Double upperBound, Double absoluteGap) { }
    public record ResultResponse(UUID id, Map<String, Object> inputs, UUID priceRevision,
            ScenarioPreparation.Versions versions, String marketOffset, int intervalSeconds,
            String intervalLabel, Map<String, String> units, List<PriceInterval> prices,
            Strategy fixed, Strategy hindsight, ThresholdView threshold, Solver solver) { }

    @PostMapping
    public ResponseEntity<JobResponse> submit(HttpServletRequest request) throws IOException {
        if (request.getContentType() == null
                || !MediaType.APPLICATION_JSON.isCompatibleWith(MediaType.parseMediaType(request.getContentType())))
            throw new UnsupportedContent();
        byte[] body = request.getInputStream().readNBytes(16_385);
        if (body.length > 16_384) throw new TooLarge();
        SimulationRequest parsed = SimulationJson.parse(body);
        UUID id;
        try {
            id = jobs.submit(parsed);
        } catch (SimulationRequest.Invalid invalid) {
            // A coverage failure means the day itself is valid but unfetched; eligible days
            // trigger a bounded, deduplicated visitor refresh rather than a dead end.
            if (!invalid.code().equals("PRICE_DAY_UNAVAILABLE") && !invalid.code().equals("PRICE_DAY_INCOMPLETE"))
                throw invalid;
            refreshes.submitVisitor(parsed.region(), parsed.day());
            throw new PendingData();
        }
        var job = jobs.find(id).orElseThrow(NotFound::new);
        boolean pending = job.status() == SimulationJobs.Status.QUEUED || job.status() == SimulationJobs.Status.RUNNING;
        var response = ResponseEntity.status(pending ? 202 : 200).cacheControl(CacheControl.noStore())
                .header(HttpHeaders.LOCATION, path(id));
        if (pending) response.header(HttpHeaders.RETRY_AFTER, "2");
        return response.body(view(job));
    }

    @GetMapping("/{id}")
    public ResponseEntity<JobResponse> status(@PathVariable("id") String identifier) {
        UUID id = id(identifier);
        return ResponseEntity.ok().cacheControl(CacheControl.noStore()).body(view(jobs.find(id).orElseThrow(NotFound::new)));
    }

    @GetMapping("/{id}/result")
    public ResponseEntity<ResultResponse> result(@PathVariable("id") String identifier) {
        UUID id = id(identifier);
        var job = jobs.find(id).orElseThrow(NotFound::new);
        if (job.status() == SimulationJobs.Status.FAILED) throw new Failed();
        if (job.status() != SimulationJobs.Status.SUCCEEDED) throw new NotReady();
        var result = jobs.result(id).orElseThrow(NotReady::new);
        var input = jobs.input(id);
        var h = result.hindsight();
        if (h.status() != OrderedHindsight.Status.OPTIMAL) throw new Failed();
        var t = result.threshold();
        var response = new ResultResponse(id, inputs(input.request()), jobs.priceRevision(id), input.versions(),
                "+10:00", 300, "END", Map.of("energy", "MWh", "power", "MW", "money", "AUD", "price", "AUD/MWh"),
                input.prices().intervals().stream().map(i -> new PriceInterval(i.start(), i.end(), i.price().toPlainString())).toList(),
                new Strategy(result.fixedDispatch(), result.fixedAccounting()), new Strategy(h.dispatch(), h.accounting()),
                t == null ? null : new ThresholdView(t.version(),
                        Map.of("chargeBelow", t.thresholds().chargeBelow().toPlainString(),
                                "dischargeAbove", t.thresholds().dischargeAbove().toPlainString()),
                        t.dispatch(), t.accounting()),
                new Solver(h.status(), h.solverObjective(), h.upperBound(), h.absoluteGap()));
        return ResponseEntity.ok().cacheControl(CacheControl.noStore()).body(response);
    }

    private static Map<String, Object> inputs(SimulationRequest r) {
        var s = r.site();
        var inputs = new LinkedHashMap<String, Object>(Map.of("region", r.region(), "day", r.day(),
                "site", Map.of("capacityMWh", s.capacityMWh().toPlainString(), "minimumMWh", s.minimumMWh().toPlainString(),
                        "maximumMWh", s.maximumMWh().toPlainString(), "initialMWh", s.initialMWh().toPlainString(),
                        "chargeMW", s.chargeMW().toPlainString(), "dischargeMW", s.dischargeMW().toPlainString(),
                        "importLimitMW", s.importLimitMW().toPlainString(), "exportLimitMW", s.exportLimitMW().toPlainString()),
                "efficiency", Map.of("charge", r.efficiency().charge().toPlainString(), "discharge", r.efficiency().discharge().toPlainString()),
                "costs", Map.of("importFee", r.costs().importFee().toPlainString(), "exportFee", r.costs().exportFee().toPlainString(),
                        "degradationPerExportedMWh", r.costs().degradationPerExportedMWh().toPlainString()),
                "windows", r.windows()));
        var t = r.thresholds();
        if (t != null)
            inputs.put("thresholds", Map.of("chargeBelow", t.chargeBelow().toPlainString(),
                    "dischargeAbove", t.dischargeAbove().toPlainString()));
        return inputs;
    }

    private static JobResponse view(SimulationJobs.Job job) {
        String failure = job.diagnostic();
        if (failure != null && !Set.of("LEASE_EXPIRED", "WORKER_STOPPED", "SIMULATION_DEADLINE_EXCEEDED",
                "SIMULATION_PROCESS_FAILED", "INVALID_CHILD_RESULT", "UNSUPPORTED_SIMULATION_VERSION",
                "SOLVER_FEASIBLE_NOT_PROVEN", "SOLVER_NO_SOLUTION", "SOLVER_INFEASIBLE", "SOLVER_FAILED_VALIDATION", "SOLVER_ERROR").contains(failure))
            failure = "SIMULATION_FAILED";
        return new JobResponse(job.id(), job.status(), job.attempts(), failure, path(job.id()), path(job.id()) + "/result");
    }

    private static UUID id(String value) {
        if (!value.matches("[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"))
            throw new SimulationRequest.Invalid("id", "INVALID_VALUE");
        return UUID.fromString(value);
    }

    private static String path(UUID id) { return "/api/v1/simulations/" + id; }
    static final class NotFound extends RuntimeException { }
    static final class NotReady extends RuntimeException { }
    static final class Failed extends RuntimeException { }
    static final class TooLarge extends RuntimeException { }
    static final class UnsupportedContent extends RuntimeException { }
    static final class PendingData extends RuntimeException { }
}
