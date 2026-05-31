package com.hermes.longbridge.mcp.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "longbridge")
public record LongbridgeProperties(
        String appKey,
        String appSecret,
        String accessToken,
        String region
) {
    public boolean credentialsPresent() {
        return hasText(appKey) && hasText(appSecret) && hasText(accessToken);
    }

    public boolean appKeyPresent() {
        return hasText(appKey);
    }

    public boolean appSecretPresent() {
        return hasText(appSecret);
    }

    public boolean accessTokenPresent() {
        return hasText(accessToken);
    }

    public boolean regionPresent() {
        return hasText(region);
    }

    private static boolean hasText(String value) {
        return value != null && !value.isBlank();
    }
}
