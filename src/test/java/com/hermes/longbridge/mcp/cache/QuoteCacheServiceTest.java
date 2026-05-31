package com.hermes.longbridge.mcp.cache;

import com.hermes.longbridge.mcp.config.QuoteCacheProperties;
import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;

class QuoteCacheServiceTest {

    @Test
    void marksQuoteFreshWithinTtl() {
        Clock clock = Clock.fixed(Instant.parse("2026-05-31T00:00:10Z"), ZoneOffset.UTC);
        QuoteCacheService service = new QuoteCacheService(new QuoteCacheProperties(10_000), clock);

        service.put("AAPL.US", Map.of("last_done", "100.00"), Instant.parse("2026-05-31T00:00:02Z"));

        QuoteCacheService.CachedQuote quote = service.latest(Optional.of(List.of("AAPL.US"))).getFirst();
        assertThat(service.isFresh(quote)).isTrue();
        assertThat(quote.age(clock).toMillis()).isEqualTo(8_000);
    }

    @Test
    void marksQuoteStaleBeyondTtl() {
        Clock clock = Clock.fixed(Instant.parse("2026-05-31T00:00:20Z"), ZoneOffset.UTC);
        QuoteCacheService service = new QuoteCacheService(new QuoteCacheProperties(10_000), clock);

        service.put("AAPL.US", Map.of("last_done", "100.00"), Instant.parse("2026-05-31T00:00:02Z"));

        QuoteCacheService.CachedQuote quote = service.latest(Optional.empty()).getFirst();
        assertThat(service.isFresh(quote)).isFalse();
        assertThat(service.latestRows(Optional.empty()).getFirst()).containsEntry("fresh", false);
    }
}
