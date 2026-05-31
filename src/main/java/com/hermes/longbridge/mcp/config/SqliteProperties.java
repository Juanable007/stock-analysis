package com.hermes.longbridge.mcp.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "sqlite")
public record SqliteProperties(
        String path,
        int maximumPoolSize
) {
    public SqliteProperties {
        if (path == null || path.isBlank()) {
            path = "./data/hermes-longbridge-mcp.sqlite";
        }
        if (maximumPoolSize <= 0) {
            maximumPoolSize = 4;
        }
    }
}
