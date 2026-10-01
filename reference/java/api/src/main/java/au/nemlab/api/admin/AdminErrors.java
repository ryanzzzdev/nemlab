package au.nemlab.api.admin;

import au.nemlab.infrastructure.jobs.RefreshJobService;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.dao.DataAccessException;
import org.springframework.transaction.TransactionException;
import java.time.DateTimeException;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.bind.MissingRequestHeaderException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;

@RestControllerAdvice(assignableTypes = AdminRefreshController.class)
@ConditionalOnProperty(name = "nemlab.admin.enabled", havingValue = "true")
public class AdminErrors {
    public record Error(String code, String message) {
    }

    @ExceptionHandler(RefreshJobService.RequestKeyConflict.class)
    public ResponseEntity<Error> conflict() {
        return error(409, "IDEMPOTENCY_CONFLICT", "Request key belongs to a different price day");
    }

    @ExceptionHandler(RefreshJobService.QueueFull.class)
    public ResponseEntity<Error> full() {
        return ResponseEntity.status(429).header("Retry-After", "30")
                .body(new Error("QUEUE_FULL", "Wait for existing refresh jobs to finish"));
    }

    @ExceptionHandler(AdminRefreshController.NotFound.class)
    public ResponseEntity<Error> notFound() {
        return error(404, "JOB_NOT_FOUND", "Refresh job not found");
    }

    @ExceptionHandler({IllegalArgumentException.class, HttpMessageNotReadableException.class,
            MissingRequestHeaderException.class, MethodArgumentTypeMismatchException.class, DateTimeException.class})
    public ResponseEntity<Error> invalid() {
        return error(400, "INVALID_REQUEST", "Check the request fields, completed market day and identifiers");
    }

    @ExceptionHandler({DataAccessException.class, TransactionException.class})
    public ResponseEntity<Error> unavailable() {
        return error(503, "STORAGE_UNAVAILABLE", "Refresh storage is temporarily unavailable");
    }

    private static ResponseEntity<Error> error(int status, String code, String message) {
        return ResponseEntity.status(status).body(new Error(code, message));
    }
}
