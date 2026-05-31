package com.hermes.longbridge.mcp.tools;

import com.hermes.longbridge.mcp.common.ToolResponse;
import com.hermes.longbridge.mcp.longbridge.LongbridgeQuoteGateway;
import com.hermes.longbridge.mcp.universe.UniverseService;
import org.springframework.ai.tool.annotation.Tool;
import org.springframework.stereotype.Component;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

@Component
public class UniverseTools {

    private final UniverseService universeService;
    private final LongbridgeQuoteGateway quoteGateway;
    private final ToolExecutionSupport support;

    public UniverseTools(UniverseService universeService, LongbridgeQuoteGateway quoteGateway, ToolExecutionSupport support) {
        this.universeService = universeService;
        this.quoteGateway = quoteGateway;
        this.support = support;
    }

    @Tool(description = "Return Longbridge watchlist when supported; otherwise return local watchlist/universe with a warning.")
    public ToolResponse<List<Map<String, Object>>> get_watchlist() {
        ToolResponse<List<Map<String, Object>>> response = support.fromGateway("get_watchlist", quoteGateway::watchlist);
        if (response.ok() && response.data() != null) {
            List<String> symbols = extractSymbols(response.data());
            if (!symbols.isEmpty()) {
                universeService.mergeWatchlistSymbols(symbols);
            }
            return response;
        }
        return support.local("get_watchlist_local_fallback", () -> ToolResponse.ok(
                universeService.getUniverse(),
                ToolResponse.SOURCE_LOCAL_CACHE,
                Instant.now(),
                false,
                null,
                List.of("longbridge_watchlist_unavailable_returning_local_universe"),
                Map.of("sdk_method", "QuoteContext.getWatchlist")));
    }

    @Tool(description = "Set local Hermes universe. mode supports replace, merge, or remove.")
    public ToolResponse<List<Map<String, Object>>> set_universe(List<String> symbols, String mode) {
        return support.local("set_universe", () -> ToolResponse.ok(
                universeService.setManualUniverse(symbols, mode),
                ToolResponse.SOURCE_LOCAL_CACHE,
                Instant.now(),
                false,
                null,
                List.of(),
                Map.of("mode", mode == null ? "merge" : mode)));
    }

    @Tool(description = "Return current Hermes universe with source tags: position, watchlist, manual.")
    public ToolResponse<List<Map<String, Object>>> get_universe() {
        return support.local("get_universe", () -> ToolResponse.ok(
                universeService.getUniverse(),
                ToolResponse.SOURCE_LOCAL_CACHE,
                Instant.now(),
                false,
                null,
                List.of(),
                Map.of()));
    }

    private static List<String> extractSymbols(List<Map<String, Object>> rows) {
        List<String> symbols = new ArrayList<>();
        for (Map<String, Object> row : rows) {
            Object direct = row.get("symbol");
            if (direct != null) {
                symbols.add(direct.toString());
            }
            Object children = row.get("securities");
            if (children instanceof List<?> list) {
                list.stream()
                        .filter(Map.class::isInstance)
                        .map(item -> ((Map<?, ?>) item).get("symbol"))
                        .filter(java.util.Objects::nonNull)
                        .map(Object::toString)
                        .forEach(symbols::add);
            }
        }
        return symbols;
    }
}
