package com.hermes.longbridge.mcp.knowledge;

import com.hermes.longbridge.mcp.config.WhopKnowledgeProperties;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
@ConditionalOnProperty(prefix = "whop-knowledge", name = "auto-refresh-enabled", havingValue = "true")
public class WhopKnowledgeAutoRefresh {

    private final WhopKnowledgeProperties properties;
    private final WhopKnowledgeRefreshService refreshService;

    public WhopKnowledgeAutoRefresh(WhopKnowledgeProperties properties,
                                    WhopKnowledgeRefreshService refreshService) {
        this.properties = properties;
        this.refreshService = refreshService;
    }

    @Scheduled(fixedDelayString = "${whop-knowledge.auto-refresh-interval-ms:300000}")
    public void refresh() {
        refreshService.refresh(properties.autoRefreshRunCapture(), properties.autoRefreshRebuild());
    }
}
