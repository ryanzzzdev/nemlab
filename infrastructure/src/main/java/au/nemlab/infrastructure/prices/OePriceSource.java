package au.nemlab.infrastructure.prices;

import au.nemlab.batterylab.PriceDay;
import tools.jackson.databind.json.JsonMapper;
import tools.jackson.databind.DeserializationFeature;
import java.net.*;
import java.net.http.*;
import java.nio.charset.StandardCharsets;
import java.math.BigDecimal;
import java.time.*;
import java.util.*;

public final class OePriceSource implements PriceSource {
    public static final class Failure extends java.io.IOException {
        private final String code;

        Failure(String code) {
            super(code);
            this.code = code;
        }

        public String code() {
            return code;
        }
    }

    private final HttpClient client;
    private final URI endpoint;
    private final String key;
    private final Clock clock;
    private final Sleeper sleeper;

    @FunctionalInterface
    public interface Sleeper {
        void sleep(long milliseconds) throws InterruptedException;
    }

    public OePriceSource(String key) {
        this(HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(10)).followRedirects(HttpClient.Redirect.NEVER)
                .build(),
                URI.create("https://api.openelectricity.org.au/v4/market/network/NEM"), key, Clock.systemUTC(),
                Thread::sleep);
    }

    OePriceSource(HttpClient client, URI endpoint, String key, Clock clock, Sleeper sleeper) {
        this.client = Objects.requireNonNull(client);
        this.endpoint = Objects.requireNonNull(endpoint);
        if (key == null || key.isBlank() || key.contains("\n") || key.contains("\r"))
            throw new IllegalArgumentException("OE key required");
        this.key = key;
        this.clock = clock;
        this.sleeper = sleeper;
    }

    @Override
    public Fetch fetch(PriceDay.Region region, LocalDate day) throws Exception {
        if (day.isBefore(LocalDate.of(2021, 10, 1))
                || !day.isBefore(LocalDate.now(clock.withZone(PriceDay.NEM_OFFSET))))
            throw new IllegalArgumentException("require a completed post-five-minute-settlement market day");
        String start = day + "T00:00:00", end = day.plusDays(1) + "T00:05:00";
        URI uri = URI.create(endpoint + "?metrics=price&interval=5m&network_region=" + region +
                "&primary_grouping=network_region&date_start=" + URLEncoder.encode(start, StandardCharsets.UTF_8) +
                "&date_end=" + URLEncoder.encode(end, StandardCharsets.UTF_8));
        var request = HttpRequest.newBuilder(uri).timeout(Duration.ofSeconds(30))
                .header("Authorization", "Bearer " + key)
                .header("User-Agent", "NEMLab-data-ingestion/0.1").GET().build();
        for (int attempt = 0; attempt < 3; attempt++) {
            HttpResponse<String> response;
            try {
                response = client.send(request, info -> new LimitedBody());
            } catch (java.io.IOException ex) {
                if (attempt == 2)
                    throw new Failure("TRANSPORT_RETRIES_EXHAUSTED");
                sleeper.sleep(1000L << attempt);
                continue;
            }
            int status = response.statusCode();
            if (status == 200)
                return parse(region, day, response.body(), clock.instant());
            if ((status == 429 || status >= 500) && attempt < 2) {
                long delay = 1000L << attempt;
                String retry = response.headers().firstValue("Retry-After").orElse("");
                try {
                    delay = Math.max(delay, Math.multiplyExact(Long.parseLong(retry), 1000));
                } catch (RuntimeException ignored) {
                    try {
                        delay = Math.max(delay,
                                Duration.between(clock.instant(),
                                        ZonedDateTime
                                                .parse(retry, java.time.format.DateTimeFormatter.RFC_1123_DATE_TIME)
                                                .toInstant())
                                        .toMillis());
                    } catch (RuntimeException malformed) {
                        /* Missing/malformed header uses bounded exponential backoff. */ }
                }
                if (delay > 60_000)
                    throw new Failure("RETRY_AFTER_EXCEEDS_BUDGET");
                sleeper.sleep(delay);
                continue;
            }
            throw new Failure("HTTP_" + status);
        }
        throw new IllegalStateException("unreachable retry state");
    }

    /** Cancel the response stream before retaining more than two megabytes. */
    private static final class LimitedBody implements HttpResponse.BodySubscriber<String> {
        private final HttpResponse.BodySubscriber<String> delegate = HttpResponse.BodySubscribers
                .ofString(StandardCharsets.UTF_8);
        private java.util.concurrent.Flow.Subscription subscription;
        private long bytes;
        private boolean done;

        @Override
        public java.util.concurrent.CompletionStage<String> getBody() {
            return delegate.getBody();
        }

        @Override
        public void onSubscribe(java.util.concurrent.Flow.Subscription s) {
            subscription = s;
            delegate.onSubscribe(s);
        }

        @Override
        public void onNext(List<java.nio.ByteBuffer> buffers) {
            if (done)
                return;
            for (var buffer : buffers)
                bytes += buffer.remaining();
            if (bytes > 2_000_000) {
                done = true;
                subscription.cancel();
                delegate.onError(new Failure("RESPONSE_TOO_LARGE"));
            } else
                delegate.onNext(buffers);
        }

        @Override
        public void onError(Throwable error) {
            if (!done) {
                done = true;
                delegate.onError(error);
            }
        }

        @Override
        public void onComplete() {
            if (!done) {
                done = true;
                delegate.onComplete();
            }
        }
    }

    @SuppressWarnings("unchecked")
    public static Fetch parse(PriceDay.Region region, LocalDate day, String body, Instant retrieved) {
        if (body.length() > 2_000_000)
            throw new IllegalArgumentException("OE price response too large");
        try {
            var mapper = JsonMapper.builder().enable(DeserializationFeature.USE_BIG_DECIMAL_FOR_FLOATS).build();
            Map<String, Object> root = mapper.readValue(body, Map.class);
            if (!Boolean.TRUE.equals(root.get("success")))
                throw new IllegalArgumentException();
            var series = (List<Map<String, Object>>) root.get("data");
            if (series.size() != 1)
                throw new IllegalArgumentException();
            var s = series.getFirst();
            if (!"NEM".equals(s.get("network_code")) || !"price".equals(s.get("metric"))
                    || !"5m".equals(s.get("interval"))
                    || !"$/MWh".equals(s.get("unit")))
                throw new IllegalArgumentException();
            var results = (List<Map<String, Object>>) s.get("results");
            if (results.size() != 1
                    || !region.name().equals(((Map<?, ?>) results.getFirst().get("columns")).get("region")))
                throw new IllegalArgumentException();
            List<PriceBatch.Slot> slots = new ArrayList<>(
                    Collections.nCopies(288, new PriceBatch.Slot(PriceBatch.Kind.MISSING, null)));
            Set<Instant> seen = new HashSet<>();
            Instant start = day.atStartOfDay().toInstant(PriceDay.NEM_OFFSET), end = start.plusSeconds(86400);
            for (var row : (List<List<Object>>) results.getFirst().get("data")) {
                if (row.size() != 2)
                    throw new IllegalArgumentException();
                Instant timestamp = OffsetDateTime.parse((String) row.get(0)).toInstant();
                if (!seen.add(timestamp))
                    throw new IllegalArgumentException();
                if (timestamp.equals(start) || timestamp.equals(end.plusSeconds(300)))
                    continue;
                long seconds = Duration.between(start, timestamp).getSeconds();
                if (timestamp.getNano() != 0 || seconds <= 0 || seconds > 86400 || seconds % 300 != 0)
                    throw new IllegalArgumentException();
                Object raw = row.get(1);
                if (raw != null && !(raw instanceof Number))
                    throw new IllegalArgumentException();
                slots.set((int) (seconds / 300) - 1,
                        raw == null ? new PriceBatch.Slot(PriceBatch.Kind.SOURCE_NULL, null)
                                : new PriceBatch.Slot(PriceBatch.Kind.VALUE, new BigDecimal(raw.toString())));
            }
            return new Fetch(new PriceBatch(region, day, slots), retrieved, PriceBatch.hash(body),
                    (String) root.get("version"));
        } catch (RuntimeException ex) {
            throw new IllegalArgumentException("Invalid OE price response (metadata, duplicate, timestamp or value)");
        }
    }
}
