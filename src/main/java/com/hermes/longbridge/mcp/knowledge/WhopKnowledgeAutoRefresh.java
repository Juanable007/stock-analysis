package com.hermes.longbridge.mcp.knowledge;

import com.hermes.longbridge.mcp.config.WhopKnowledgeProperties;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
@ConditionalOnProperty(prefix = "whop-knowledge", name = "auto-refresh-enabled", havingValue = "true")
public class WhopKnowledgeAutoRefresh {

    private static final org.slf4j.Logger log = org.slf4j.LoggerFactory.getLogger(WhopKnowledgeAutoRefresh.class);

    private final WhopKnowledgeProperties properties;
    private final WhopKnowledgeRefreshService refreshService;

    public WhopKnowledgeAutoRefresh(WhopKnowledgeProperties properties,
                                    WhopKnowledgeRefreshService refreshService) {
        this.properties = properties;
        this.refreshService = refreshService;
    }

    @Scheduled(fixedDelayString = "${whop-knowledge.auto-refresh-interval-ms:300000}")
    public void refresh() {
        try {
            var result = refreshService.refresh(properties.autoRefreshRunCapture(), properties.autoRefreshRebuild());
            log.info(
                    "Whop knowledge auto-refresh finished: skipped={}, ran_capture={}, ran_rebuild={}, net_new_messages={}",
                    result.get("skipped"),
                    result.get("ran_capture"),
                    result.get("ran_rebuild"),
                    result.get("net_new_messages"));
        } catch (RuntimeException ex) {
            log.warn("Whop knowledge auto-refresh failed: {}", ex.getMessage());
        }
    }
}
