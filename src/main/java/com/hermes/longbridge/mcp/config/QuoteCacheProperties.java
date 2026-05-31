package com.hermes.longbridge.mcp.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "quote-cache")
public record QuoteCacheProperties(long defaultTtlMs) {
    public QuoteCacheProperties {
        if (defaultTtlMs <= 0) {
            defaultTtlMs = 10_000;
        }
    }
}
