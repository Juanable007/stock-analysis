package com.hermes.longbridge.mcp.tools;

import com.hermes.longbridge.mcp.cache.QuoteCacheService;
import com.hermes.longbridge.mcp.cache.SnapshotRepository;
import com.hermes.longbridge.mcp.common.ToolResponse;
import com.hermes.longbridge.mcp.config.LongbridgeProperties;
import com.hermes.longbridge.mcp.longbridge.LongbridgeClientFactory;
import com.hermes.longbridge.mcp.longbridge.LongbridgeQuoteGateway;
import org.springframework.ai.tool.annotation.Tool;
import org.springframework.stereotype.Component;

import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Component
public class HealthTools {

    private final LongbridgeProperties longbridgeProperties;
    private final LongbridgeClientFactory clientFactory;
    private final SnapshotRepository snapshotRepository;
    private final QuoteCacheService quoteCacheService;
    private final LongbridgeQuoteGateway quoteGateway;
    private final ToolExecutionSupport support;

    public HealthTools(LongbridgeProperties longbridgeProperties,
                       LongbridgeClientFactory clientFactory,
                       SnapshotRepository snapshotRepository,
                       QuoteCacheService quoteCacheService,
                       LongbridgeQuoteGateway quoteGateway,
                       ToolExecutionSupport support) {
        this.longbridgeProperties = longbridgeProperties;
        this.clientFactory = clientFactory;
        this.snapshotRepository = snapshotRepository;
        this.quoteCacheService = quoteCacheService;
        this.quoteGateway = quoteGateway;
        this.support = support;
    }

    @Tool(description = "Return service, configuration, SDK, SQLite, subscription, and latest data status.")
    public ToolResponse<Map<String, Object>> health_check() {
        return support.local("health_check", () -> {
            Map<String, Object> data = new LinkedHashMap<>();
            data.put("service", "hermes-longbridge-mcp");
            data.put("version", "0.1.0");
            data.put("longbridge_config", Map.of(
                    "app_key_present", longbridgeProperties.appKeyPresent(),
                    "app_secret_present", longbridgeProperties.appSecretPresent(),
                    "access_token_present", longbridgeProperties.accessTokenPresent(),
                    "region_present", longbridgeProperties.regionPresent(),
                    "credentials_present", longbridgeProperties.credentialsPresent()));
            data.put("sdk_available", clientFactory.sdkAvailable());
            data.put("sdk_initializable", longbridgeProperties.credentialsPresent() && clientFactory.sdkAvailable());
            data.put("sqlite_healthy", snapshotRepository.healthy());
            data.put("subscription_status", Map.of(
                    "count", quoteGateway.subscribedSymbols().size(),
                    "symbols", quoteGateway.subscribedSymbols()));
            data.put("quote_cache_size", quoteCacheService.size());
            Instant latest = quoteCacheService.mostRecentAsOf();
            if (latest == null) {
                latest = snapshotRepository.latestQuoteTime();
            }
            data.put("recent_data_time", latest == null ? null : latest.toString());

            List<String> warnings = longbridgeProperties.credentialsPresent()
                    ? List.of()
                    : List.of("longbridge_credentials_missing; data tools will return explicit errors until env vars are set");
            return ToolResponse.ok(data, ToolResponse.SOURCE_COMPUTED, Instant.now(), false, null, warnings, Map.of());
        });
    }
}
