package au.nemlab.api.simulation;

import au.nemlab.batterylab.SimulationRequest;
import au.nemlab.infrastructure.batterylab.SimulationJobs;
import au.nemlab.infrastructure.jobs.RefreshJobService;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.dao.DataAccessException;
import org.springframework.http.*;
import org.springframework.transaction.TransactionException;
import org.springframework.web.bind.annotation.*;
import tools.jackson.core.JacksonException;
import java.io.IOException;

@RestControllerAdvice(assignableTypes = SimulationController.class)
@ConditionalOnProperty(name = "nemlab.simulation-api.enabled", havingValue = "true")
public class SimulationErrors {
    public record Error(String code, String message, String field, String reason) { }

    @ExceptionHandler(SimulationRequest.Invalid.class)
    public ResponseEntity<Error> invalid(SimulationRequest.Invalid invalid) {
        boolean coverage = invalid.code().equals("PRICE_DAY_UNAVAILABLE") || invalid.code().equals("PRICE_DAY_INCOMPLETE");
        return error(coverage ? 409 : 400, coverage ? invalid.code() : "INVALID_REQUEST",
                "Check scenario fields and complete stored price coverage", invalid.field(), invalid.code());
    }

    @ExceptionHandler({IllegalArgumentException.class, JacksonException.class, IOException.class})
    public ResponseEntity<Error> malformed() {
        return error(400, "INVALID_REQUEST", "Use the documented JSON fields and identifiers", "request", "INVALID_FORMAT");
    }

    @ExceptionHandler({SimulationJobs.QueueFull.class, RefreshJobService.QueueFull.class})
    public ResponseEntity<Error> full() {
        return ResponseEntity.status(429).cacheControl(CacheControl.noStore()).header("Retry-After", "5")
                .body(new Error("QUEUE_FULL", "Wait for pending simulations to finish", "request", "QUEUE_FULL"));
    }

    @ExceptionHandler(SimulationController.PendingData.class)
    public ResponseEntity<Error> pendingData() {
        return ResponseEntity.status(409).cacheControl(CacheControl.noStore()).header("Retry-After", "30")
                .body(new Error("PRICE_REFRESH_PENDING", "Stored prices for this day are being fetched", "day", "PRICE_REFRESH_PENDING"));
    }

    @ExceptionHandler(RefreshJobService.RefreshAttemptsExhausted.class)
    public ResponseEntity<Error> refreshExhausted() {
        return error(409, "PRICE_REFRESH_FAILED", "Stored prices could not be fetched for this day; try again later", "day", "PRICE_REFRESH_FAILED");
    }

    @ExceptionHandler(RefreshJobService.VisitorLimited.class)
    public ResponseEntity<Error> visitorLimited() {
        return ResponseEntity.status(429).cacheControl(CacheControl.noStore()).header("Retry-After", "60")
                .body(new Error("VISITOR_REFRESH_LIMIT", "Too many price fetches are pending", "request", "VISITOR_REFRESH_LIMIT"));
    }

    @ExceptionHandler(SimulationController.NotFound.class)
    public ResponseEntity<Error> missing() { return error(404, "SIMULATION_NOT_FOUND", "Simulation not found", "id", "NOT_FOUND"); }

    @ExceptionHandler(SimulationController.NotReady.class)
    public ResponseEntity<Error> pending() { return error(409, "RESULT_NOT_READY", "Poll simulation status for completion", "id", "NOT_READY"); }

    @ExceptionHandler(SimulationController.Failed.class)
    public ResponseEntity<Error> failed() { return error(409, "SIMULATION_FAILED", "No proven comparison is available; inspect job status", "id", "FAILED"); }

    @ExceptionHandler(SimulationController.TooLarge.class)
    public ResponseEntity<Error> large() { return error(413, "REQUEST_TOO_LARGE", "JSON body must not exceed 16384 bytes", "request", "TOO_LARGE"); }

    @ExceptionHandler(SimulationController.UnsupportedContent.class)
    public ResponseEntity<Error> content() { return error(415, "UNSUPPORTED_CONTENT_TYPE", "Send application/json", "request", "CONTENT_TYPE"); }

    @ExceptionHandler({DataAccessException.class, TransactionException.class})
    public ResponseEntity<Error> storage() { return error(503, "STORAGE_UNAVAILABLE", "Simulation storage is unavailable", "request", "STORAGE_UNAVAILABLE"); }

    private static ResponseEntity<Error> error(int status, String code, String message, String field, String reason) {
        return ResponseEntity.status(status).cacheControl(CacheControl.noStore()).body(new Error(code, message, field, reason));
    }
}
