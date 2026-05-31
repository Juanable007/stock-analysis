package com.hermes.longbridge.mcp.cache;

import com.hermes.longbridge.mcp.config.QuoteCacheProperties;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

@Service
public class QuoteCacheService {

    private final Map<String, CachedQuote> quotes = new ConcurrentHashMap<>();
    private final Duration defaultTtl;
    private final Clock clock;

    @Autowired
    public QuoteCacheService(QuoteCacheProperties properties) {
        this(properties, Clock.systemUTC());
    }

    public QuoteCacheService(QuoteCacheProperties properties, Clock clock) {
        this.defaultTtl = Duration.ofMillis(properties.defaultTtlMs());
        this.clock = clock;
    }

    public void put(String symbol, Map<String, Object> quote, Instant asOf) {
        quotes.put(symbol, new CachedQuote(symbol, Map.copyOf(quote), asOf == null ? Instant.now(clock) : asOf));
    }

    public void putAll(Map<String, Map<String, Object>> quoteBySymbol, Instant asOf) {
        quoteBySymbol.forEach((symbol, quote) -> put(symbol, quote, asOf));
    }

    public List<CachedQuote> latest(Optional<List<String>> symbols) {
        if (symbols.isEmpty() || symbols.get().isEmpty()) {
            return quotes.values().stream()
                    .sorted(java.util.Comparator.comparing(CachedQuote::symbol))
                    .toList();
        }
        List<CachedQuote> result = new ArrayList<>();
        for (String symbol : symbols.get()) {
            CachedQuote quote = quotes.get(symbol);
            if (quote != null) {
                result.add(quote);
            }
        }
        return result;
    }

    public boolean isFresh(CachedQuote quote) {
        return quote.age(clock).compareTo(defaultTtl) <= 0;
    }

    public List<Map<String, Object>> latestRows(Optional<List<String>> symbols) {
        return latest(symbols).stream()
                .map(quote -> quote.toResponse(clock, isFresh(quote)))
                .toList();
    }

    public Long maxAgeMillis(List<CachedQuote> rows) {
        return rows.stream()
                .map(quote -> Math.max(0, quote.age(clock).toMillis()))
                .max(Long::compareTo)
                .orElse(null);
    }

    public Instant mostRecentAsOf() {
        return quotes.values().stream()
                .map(CachedQuote::asOf)
                .max(Instant::compareTo)
                .orElse(null);
    }

    public long size() {
        return quotes.size();
    }

    public record CachedQuote(String symbol, Map<String, Object> data, Instant asOf) {
        public Duration age(Clock clock) {
            return Duration.between(asOf, Instant.now(clock));
        }

        public Map<String, Object> toResponse(Clock clock, boolean fresh) {
            Map<String, Object> response = new LinkedHashMap<>(data);
            response.putIfAbsent("symbol", symbol);
            response.put("as_of", asOf.toString());
            response.put("cache_age_ms", Math.max(0, age(clock).toMillis()));
            response.put("fresh", fresh);
            return response;
        }
    }
}
