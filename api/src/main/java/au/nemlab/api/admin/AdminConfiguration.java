package au.nemlab.api.admin;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.annotation.Order;
import org.springframework.core.env.Environment;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.oauth2.core.DefaultOAuth2AuthenticatedPrincipal;
import org.springframework.security.oauth2.server.resource.introspection.BadOpaqueTokenException;
import org.springframework.security.oauth2.server.resource.introspection.OpaqueTokenIntrospector;
import org.springframework.security.web.SecurityFilterChain;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.List;
import java.util.Map;

@Configuration(proxyBeanMethods = false)
@ConditionalOnProperty(name = "nemlab.admin.enabled", havingValue = "true")
public class AdminConfiguration {
    @Bean
    public OpaqueTokenIntrospector operatorTokens(Environment environment) {
        String operator = required(environment, "NEMLAB_ADMIN_OPERATOR");
        String secret = required(environment, "NEMLAB_ADMIN_TOKEN");
        if (!operator.matches("[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")) {
            throw new IllegalArgumentException("Invalid operator identifier");
        }
        if (!secret.matches("[A-Za-z0-9_-]{43,128}")) {
            throw new IllegalArgumentException("Admin token must be 43–128 base64url characters");
        }
        byte[] expected = digest(secret);
        String actor = "operator:" + operator;
        return supplied -> {
            if (supplied.length() > 128 || !MessageDigest.isEqual(expected, digest(supplied))) {
                throw new BadOpaqueTokenException("Invalid operator credential");
            }
            return new DefaultOAuth2AuthenticatedPrincipal(actor, Map.of("sub", actor),
                    List.of(new SimpleGrantedAuthority("ROLE_OPERATOR")));
        };
    }

    @Bean
    @Order(1)
    public SecurityFilterChain operatorEndpoints(HttpSecurity http, OpaqueTokenIntrospector operatorTokens)
            throws Exception {
        return http
                .securityMatcher("/api/admin/**")
                .csrf(AbstractHttpConfigurer::disable)
                .requestCache(AbstractHttpConfigurer::disable)
                .sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .authorizeHttpRequests(authorize -> authorize.anyRequest().hasRole("OPERATOR"))
                .oauth2ResourceServer(resource -> resource
                        .opaqueToken(opaque -> opaque.introspector(operatorTokens))
                        .authenticationEntryPoint((request, response, failure) -> {
                            response.setHeader("WWW-Authenticate", "Bearer");
                            response.setStatus(401);
                            response.setContentType("application/json");
                            response.getWriter().write("{\"code\":\"UNAUTHORISED\"}");
                        })
                        .accessDeniedHandler((request, response, failure) -> response.setStatus(403)))
                .build();
    }

    private static String required(Environment environment, String name) {
        String value = environment.getProperty(name);
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(name + " is required when admin controls are enabled");
        }
        return value;
    }

    private static byte[] digest(String value) {
        try {
            return MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8));
        } catch (NoSuchAlgorithmException failure) {
            throw new IllegalStateException("SHA-256 unavailable");
        }
    }
}
