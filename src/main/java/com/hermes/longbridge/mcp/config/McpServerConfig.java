package com.hermes.longbridge.mcp.config;

import com.hermes.longbridge.mcp.tools.AccountTools;
import com.hermes.longbridge.mcp.tools.ContentTools;
import com.hermes.longbridge.mcp.tools.ContractTools;
import com.hermes.longbridge.mcp.tools.HealthTools;
import com.hermes.longbridge.mcp.tools.KnowledgeTools;
import com.hermes.longbridge.mcp.tools.QuoteTools;
import com.hermes.longbridge.mcp.tools.UniverseTools;
import org.springframework.ai.tool.ToolCallbackProvider;
import org.springframework.ai.tool.method.MethodToolCallbackProvider;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class McpServerConfig {

    @Bean
    public ToolCallbackProvider hermesLongbridgeTools(HealthTools healthTools,
                                                      AccountTools accountTools,
                                                      UniverseTools universeTools,
                                                      QuoteTools quoteTools,
                                                      ContentTools contentTools,
                                                      ContractTools contractTools,
                                                      KnowledgeTools knowledgeTools) {
        return MethodToolCallbackProvider.builder()
                .toolObjects(healthTools, accountTools, universeTools, quoteTools, contentTools, contractTools, knowledgeTools)
                .build();
    }
}
