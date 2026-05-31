package com.hermes.longbridge.mcp.tools;

import com.hermes.longbridge.mcp.cache.QuoteCacheService;
import com.hermes.longbridge.mcp.cache.SnapshotRepository;
import com.hermes.longbridge.mcp.common.ToolResponse;
import com.hermes.longbridge.mcp.config.LongbridgeProperties;
import com.hermes.longbridge.mcp.config.QuoteCacheProperties;
import com.hermes.longbridge.mcp.longbridge.LongbridgeClientFactory;
import com.hermes.longbridge.mcp.longbridge.LongbridgeQuoteGateway;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class HealthToolsNoTokenTest {

    @Test
    void healthCheckWorksWithoutCredentials() {
        LongbridgeProperties properties = new LongbridgeProperties("", "", "", "");
        SnapshotRepository repository = mock(SnapshotRepository.class);
        LongbridgeQuoteGateway quoteGateway = mock(LongbridgeQuoteGateway.class);
        when(repository.healthy()).thenReturn(true);
        when(repository.latestQuoteTime()).thenReturn(null);
        when(quoteGateway.subscribedSymbols()).thenReturn(List.of());
        ToolExecutionSupport support = new ToolExecutionSupport(repository);
        HealthTools tools = new HealthTools(
                properties,
                new LongbridgeClientFactory(properties),
                repository,
                new QuoteCacheService(new QuoteCacheProperties(10_000)),
                quoteGateway,
                support);

        ToolResponse<Map<String, Object>> response = tools.health_check();

        assertThat(response.ok()).isTrue();
        assertThat(response.warnings()).contains("longbridge_credentials_missing; data tools will return explicit errors until env vars are set");
        Map<?, ?> config = (Map<?, ?>) response.data().get("longbridge_config");
        assertThat(config.get("credentials_present")).isEqualTo(false);
    }
}
