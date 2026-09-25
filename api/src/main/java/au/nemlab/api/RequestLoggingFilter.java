package au.nemlab.api;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

/** One line per request: method, target, status and elapsed time. Never headers or bodies. */
@Component
public class RequestLoggingFilter extends OncePerRequestFilter {
    private static final Logger LOG = LoggerFactory.getLogger(RequestLoggingFilter.class);

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
            FilterChain chain) throws ServletException, IOException {
        long started = System.nanoTime();
        try {
            chain.doFilter(request, response);
        } finally {
            String target = request.getQueryString() == null
                    ? request.getRequestURI()
                    : request.getRequestURI() + "?" + request.getQueryString();
            LOG.info("{} {} -> {} ({} ms)", request.getMethod(), target, response.getStatus(),
                    (System.nanoTime() - started) / 1_000_000);
        }
    }
}
