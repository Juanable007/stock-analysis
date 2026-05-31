package com.hermes.longbridge.mcp.tools;

import com.hermes.longbridge.mcp.cache.QuoteCacheService;
import com.hermes.longbridge.mcp.cache.SnapshotRepository;
import com.hermes.longbridge.mcp.common.ToolResponse;
import com.hermes.longbridge.mcp.config.QuoteCacheProperties;
import com.hermes.longbridge.mcp.longbridge.GatewayResult;
import com.hermes.longbridge.mcp.longbridge.LongbridgeQuoteGateway;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyBoolean;
import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.doNothing;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class QuoteToolsValidationTest {

    @Test
    void rejectsRealtimeBatchOverOneHundredSymbols() {
        LongbridgeQuoteGateway gateway = mock(LongbridgeQuoteGateway.class);
        SnapshotRepository repository = mock(SnapshotRepository.class);
        ToolExecutionSupport support = new ToolExecutionSupport(repository);
        QuoteTools tools = new QuoteTools(gateway, new QuoteCacheService(new QuoteCacheProperties(10_000)), repository, support);

        List<String> symbols = new ArrayList<>();
        for (int index = 0; index < 101; index++) {
            symbols.add("SYM" + index + ".US");
        }

        ToolResponse<List<Map<String, Object>>> response = tools.get_realtime_quote_batch(symbols);

        assertThat(response.ok()).isFalse();
        assertThat(response.errors()).contains("symbols must not exceed 100 for get_realtime_quote_batch");
    }

    @Test
    void cachesFakeGatewayRealtimeQuotes() {
        LongbridgeQuoteGateway gateway = mock(LongbridgeQuoteGateway.class);
        SnapshotRepository repository = mock(SnapshotRepository.class);
        doNothing().when(repository).recordToolCall(anyString(), anyBoolean(), anyList(), anyList());
        doNothing().when(repository).saveQuote(anyString(), any(), any());
        ToolExecutionSupport support = new ToolExecutionSupport(repository);
        QuoteCacheService cache = new QuoteCacheService(new QuoteCacheProperties(10_000));
        QuoteTools tools = new QuoteTools(gateway, cache, repository, support);

        when(gateway.realtimeQuotes(List.of("AAPL.US"))).thenReturn(GatewayResult.realtime(
                List.of(Map.of("symbol", "AAPL.US", "last_done", "123.45")),
                "fake.realtime",
                Map.of("symbol", "AAPL.US")));

        ToolResponse<List<Map<String, Object>>> realtime = tools.get_realtime_quote_batch(List.of("AAPL"));
        ToolResponse<List<Map<String, Object>>> latest = tools.get_latest_quotes(List.of("AAPL"));

        assertThat(realtime.ok()).isTrue();
        assertThat(latest.ok()).isTrue();
        assertThat(latest.data()).hasSize(1);
        assertThat(latest.data().getFirst()).containsEntry("symbol", "AAPL.US");
        assertThat(latest.data().getFirst()).containsEntry("last_done", "123.45");
    }

    @Test
    void validatesCandlestickCount() {
        LongbridgeQuoteGateway gateway = mock(LongbridgeQuoteGateway.class);
        SnapshotRepository repository = mock(SnapshotRepository.class);
        ToolExecutionSupport support = new ToolExecutionSupport(repository);
        QuoteTools tools = new QuoteTools(gateway, new QuoteCacheService(new QuoteCacheProperties(10_000)), repository, support);

        ToolResponse<List<Map<String, Object>>> response = tools.get_candles("AAPL", "day", 0);

        assertThat(response.ok()).isFalse();
        assertThat(response.errors()).contains("count must be between 1 and 1000");
    }
}
