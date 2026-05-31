package com.hermes.longbridge.mcp.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "whop-knowledge")
public record WhopKnowledgeProperties(
        String archiveDir,
        String rebuildCommand,
        String captureCommand,
        Boolean refreshEnabled,
        Boolean autoRefreshEnabled,
        Boolean autoRefreshRunCapture,
        Boolean autoRefreshRebuild,
        Long autoRefreshIntervalMs,
        Long commandTimeoutMs,
        Integer maxSearchResults
) {
    public WhopKnowledgeProperties {
        if (archiveDir == null || archiveDir.isBlank()) {
            archiveDir = "./data/whop_archive";
        }
        if (rebuildCommand == null || rebuildCommand.isBlank()) {
            rebuildCommand = "python3 tools/build_whop_knowledge.py";
        }
        if (captureCommand == null) {
            captureCommand = "";
        }
        if (refreshEnabled == null) {
            refreshEnabled = true;
        }
        if (autoRefreshEnabled == null) {
            autoRefreshEnabled = false;
        }
        if (autoRefreshRunCapture == null) {
            autoRefreshRunCapture = false;
        }
        if (autoRefreshRebuild == null) {
            autoRefreshRebuild = true;
        }
        if (autoRefreshIntervalMs == null || autoRefreshIntervalMs <= 0) {
            autoRefreshIntervalMs = 300_000L;
        }
        if (commandTimeoutMs == null || commandTimeoutMs <= 0) {
            commandTimeoutMs = 300_000L;
        }
        if (maxSearchResults == null || maxSearchResults <= 0) {
            maxSearchResults = 50;
        }
    }

    public boolean captureConfigured() {
        return captureCommand != null && !captureCommand.isBlank();
    }
}
