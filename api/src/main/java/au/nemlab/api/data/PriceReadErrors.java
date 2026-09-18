package au.nemlab.api.data;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.dao.DataAccessException;
import org.springframework.http.ResponseEntity;
import org.springframework.transaction.TransactionException;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.time.DateTimeException;

@RestControllerAdvice(assignableTypes = PriceReadController.class)
@ConditionalOnProperty(name = "nemlab.data.enabled", havingValue = "true")
public class PriceReadErrors {
    public record Error(String code, String message) {
    }

    @ExceptionHandler({IllegalArgumentException.class, DateTimeException.class,
            org.springframework.web.method.annotation.MethodArgumentTypeMismatchException.class,
            MissingServletRequestParameterException.class})
    public ResponseEntity<Error> invalid() {
        return ResponseEntity.badRequest().body(new Error("INVALID_REQUEST",
                "Use a valid region and 1–31 completed market days since 2021-10-01"));
    }

    @ExceptionHandler(PriceReadController.NotImported.class)
    public ResponseEntity<Error> absent() {
        return ResponseEntity.status(404).body(new Error("PRICE_DAY_NOT_IMPORTED", "No stored prices for this day"));
    }

    @ExceptionHandler({DataAccessException.class, TransactionException.class})
    public ResponseEntity<Error> unavailable() {
        return ResponseEntity.status(503).body(new Error("STORAGE_UNAVAILABLE", "Price storage is unavailable"));
    }
}
