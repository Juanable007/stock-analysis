package com.hermes.longbridge.mcp.tools;

import com.hermes.longbridge.mcp.cache.QuoteCacheService;
import com.hermes.longbridge.mcp.cache.SnapshotRepository;
import com.hermes.longbridge.mcp.common.SymbolNormalizer;
import com.hermes.longbridge.mcp.common.ToolResponse;
import com.hermes.longbridge.mcp.longbridge.GatewayResult;
import com.hermes.longbridge.mcp.longbridge.LongbridgeQuoteGateway;
import org.springframework.ai.tool.annotation.Tool;
import org.springframework.stereotype.Component;

import java.time.Instant;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

@Component
public class QuoteTools {

    private final LongbridgeQuoteGateway quoteGateway;
    private final QuoteCacheService quoteCacheService;
    private final SnapshotRepository snapshotRepository;
    private final ToolExecutionSupport support;

    public QuoteTools(LongbridgeQuoteGateway quoteGateway,
                      QuoteCacheService quoteCacheService,
                      SnapshotRepository snapshotRepository,
                      ToolExecutionSupport support) {
        this.quoteGateway = quoteGateway;
        this.quoteCacheService = quoteCacheService;
        this.snapshotRepository = snapshotRepository;
        this.support = support;
    }

    @Tool(description = "Return a single real-time quote from Longbridge.")
    public ToolResponse<Map<String, Object>> get_realtime_quote(String symbol) {
        return support.local("get_realtime_quote", () -> {
            String normalized = SymbolNormalizer.normalize(symbol);
            ToolResponse<List<Map<String, Object>>> batch = get_realtime_quote_batch(List.of(normalized));
            if (!batch.ok()) {
                return ToolResponse.error(batch.source(), batch.warnings(), batch.errors(), batch.rawRefs());
            }
            Map<String, Object> quote = batch.data().isEmpty() ? Map.of("symbol", normalized) : batch.data().getFirst();
            return ToolResponse.ok(quote, batch.source(), batch.asOf(), true, batch.cacheAgeMs(), batch.warnings(), batch.rawRefs());
        });
    }

    @Tool(description = "Return up to 100 real-time quotes from Longbridge.")
    public ToolResponse<List<Map<String, Object>>> get_realtime_quote_batch(List<String> symbols) {
        return support.local("get_realtime_quote_batch", () -> {
            List<String> normalized = normalizeSymbols(symbols);
            if (normalized.size() > 100) {
                return ToolResponse.parameterError("symbols must not exceed 100 for get_realtime_quote_batch", Map.of("limit", 100));
            }
            ToolResponse<List<Map<String, Object>>> response = support.fromGateway(
                    "get_realtime_quote_batch",
                    () -> quoteGateway.realtimeQuotes(normalized));
            if (response.ok() && response.data() != null) {
                cacheQuotes(normalized, response.data(), response.asOf());
            }
            return response;
        });
    }

    @Tool(description = "Start or update local quote subscriptions. Longbridge account limit is 500 symbols.")
    public ToolResponse<Map<String, Object>> subscribe_quotes(List<String> symbols) {
        return support.local("subscribe_quotes", () -> {
            List<String> normalized = normalizeSymbols(symbols);
            if (normalized.size() > 500) {
                return ToolResponse.parameterError("symbols must not exceed Longbridge subscription limit 500", Map.of("limit", 500));
            }
            return support.fromGateway("subscribe_quotes", () -> quoteGateway.subscribeQuotes(normalized));
        });
    }

    @Tool(description = "Read latest quotes from the local cache for high-frequency Hermes calls.")
    public ToolResponse<List<Map<String, Object>>> get_latest_quotes(List<String> symbols) {
        return support.local("get_latest_quotes", () -> {
            Optional<List<String>> normalized = Optional.ofNullable(symbols)
                    .filter(list -> !list.isEmpty())
                    .map(this::normalizeSymbols);
            List<QuoteCacheService.CachedQuote> cached = quoteCacheService.latest(normalized);
            List<Map<String, Object>> rows = quoteCacheService.latestRows(normalized);
            List<String> warnings = new ArrayList<>();
            if (rows.isEmpty()) {
                rows = snapshotRepository.loadQuotes(normalized.orElse(List.of()));
                if (rows.isEmpty()) {
                    warnings.add("no_latest_quotes_in_local_cache");
                } else {
                    warnings.add("served_from_sqlite_snapshot_after_memory_cache_miss");
                }
            }
            Instant asOf = quoteCacheService.mostRecentAsOf();
            if (asOf == null) {
                asOf = snapshotRepository.latestQuoteTime();
            }
            Long cacheAgeMs = cached.isEmpty() ? null : quoteCacheService.maxAgeMillis(cached);
            return ToolResponse.ok(rows, ToolResponse.SOURCE_LOCAL_CACHE, asOf, false, cacheAgeMs, warnings, Map.of("symbols", normalized.orElse(List.of())));
        });
    }

    @Tool(description = "Return candlesticks. period supports 1m, 5m, 15m, 30m, 60m, day, week, month.")
    public ToolResponse<List<Map<String, Object>>> get_candles(String symbol, String period, Integer count) {
        return support.local("get_candles", () -> {
            int safeCount = count == null ? 50 : count;
            if (safeCount <= 0 || safeCount > 1000) {
                return ToolResponse.parameterError("count must be between 1 and 1000", Map.of("count", safeCount));
            }
            return support.fromGateway("get_candles", () -> quoteGateway.candles(symbol, period == null ? "day" : period, safeCount));
        });
    }

    @Tool(description = "Return capital flow facts for a symbol.")
    public ToolResponse<Object> get_capital_flow(String symbol) {
        return support.fromGateway("get_capital_flow", () -> quoteGateway.capitalFlow(symbol));
    }

    @Tool(description = "Return capital distribution facts for a symbol.")
    public ToolResponse<Object> get_capital_distribution(String symbol) {
        return support.fromGateway("get_capital_distribution", () -> quoteGateway.capitalDistribution(symbol));
    }

    @Tool(description = "Return market calendar/session facts for a market and optional date.")
    public ToolResponse<Object> get_market_calendar(String market, String date) {
        return support.local("get_market_calendar", () -> {
            LocalDate parsed = date == null || date.isBlank() ? null : LocalDate.parse(date);
            return support.fromGateway("get_market_calendar", () -> quoteGateway.marketCalendar(market == null ? "US" : market, parsed));
        });
    }

    private void cacheQuotes(List<String> requestedSymbols, List<Map<String, Object>> quotes, Instant asOf) {
        for (int index = 0; index < quotes.size(); index++) {
            Map<String, Object> quote = new LinkedHashMap<>(quotes.get(index));
            String symbol = quote.getOrDefault("symbol", requestedSymbols.get(Math.min(index, requestedSymbols.size() - 1))).toString();
            String normalized = SymbolNormalizer.normalize(symbol);
            quote.put("symbol", normalized);
            quoteCacheService.put(normalized, quote, asOf);
            snapshotRepository.saveQuote(normalized, quote, asOf);
        }
    }

    private List<String> normalizeSymbols(List<String> symbols) {
        if (symbols == null || symbols.isEmpty()) {
            throw new IllegalArgumentException("symbols must not be empty");
        }
        return symbols.stream().map(SymbolNormalizer::normalize).distinct().toList();
    }
}
