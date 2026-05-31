package com.hermes.longbridge.mcp.tools;

import com.hermes.longbridge.mcp.common.ToolResponse;
import com.hermes.longbridge.mcp.longbridge.LongbridgeContentGateway;
import org.springframework.ai.tool.annotation.Tool;
import org.springframework.stereotype.Component;

import java.time.Instant;
import java.util.List;
import java.util.Map;

@Component
public class ContentTools {

    private final LongbridgeContentGateway contentGateway;
    private final ToolExecutionSupport support;

    public ContentTools(LongbridgeContentGateway contentGateway, ToolExecutionSupport support) {
        this.contentGateway = contentGateway;
        this.support = support;
    }

    @Tool(description = "Return symbol news facts: title, summary, source, published_at, url.")
    public ToolResponse<List<Map<String, Object>>> get_symbol_news(String symbol, Integer limit, String since) {
        return support.local("get_symbol_news", () -> {
            int safeLimit = limit == null ? 20 : limit;
            if (safeLimit <= 0 || safeLimit > 100) {
                return ToolResponse.parameterError("limit must be between 1 and 100", Map.of("limit", safeLimit));
            }
            ToolResponse<List<Map<String, Object>>> response = support.fromGateway("get_symbol_news", () -> contentGateway.news(symbol, safeLimit));
            if (!response.ok() || since == null || since.isBlank() || response.data() == null) {
                return response;
            }
            Instant sinceInstant = Instant.parse(since);
            List<Map<String, Object>> filtered = response.data().stream()
                    .filter(row -> afterSince(row.get("published_at"), sinceInstant))
                    .toList();
            return ToolResponse.ok(filtered, response.source(), response.asOf(), false, response.cacheAgeMs(), response.warnings(), response.rawRefs());
        });
    }

    @Tool(description = "Return valuation and financial summary facts for a symbol.")
    public ToolResponse<Map<String, Object>> get_fundamentals_summary(String symbol) {
        return support.fromGateway("get_fundamentals_summary", () -> contentGateway.fundamentalsSummary(symbol));
    }

    @Tool(description = "Return analyst ratings, target prices, institution, and date facts where available.")
    public ToolResponse<Map<String, Object>> get_analyst_ratings(String symbol) {
        return support.fromGateway("get_analyst_ratings", () -> contentGateway.analystRatings(symbol));
    }

    @Tool(description = "Read-only list of existing Longbridge price alerts when the SDK supports it.")
    public ToolResponse<Object> get_price_alerts() {
        ToolResponse<Object> response = support.fromGateway("get_price_alerts", contentGateway::priceAlerts);
        if (response.ok()) {
            return response;
        }
        return ToolResponse.ok(
                List.of(),
                ToolResponse.SOURCE_COMPUTED,
                Instant.now(),
                false,
                null,
                List.of("price_alerts_unsupported_or_unavailable_in_current_java_sdk"),
                Map.of("sdk_method", "AlertContext.getListAlerts"));
    }

    private static boolean afterSince(Object publishedAt, Instant since) {
        if (publishedAt == null) {
            return true;
        }
        try {
            return !Instant.parse(publishedAt.toString()).isBefore(since);
        } catch (RuntimeException ex) {
            return true;
        }
    }
}
