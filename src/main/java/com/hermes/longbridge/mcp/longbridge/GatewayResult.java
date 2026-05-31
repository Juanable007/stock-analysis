package com.hermes.longbridge.mcp.longbridge;

import java.time.Instant;
import java.util.List;
import java.util.Map;

public record GatewayResult<T>(
        T data,
        Instant asOf,
        boolean realtime,
        List<String> warnings,
        Map<String, Object> rawRefs
) {
    public GatewayResult {
        warnings = warnings == null ? List.of() : List.copyOf(warnings);
        rawRefs = rawRefs == null ? Map.of() : Map.copyOf(rawRefs);
    }

    public static <T> GatewayResult<T> of(T data, String sdkMethod, Map<String, Object> rawRefs) {
        return new GatewayResult<>(data, Instant.now(), false, List.of(), mergeSdkMethod(sdkMethod, rawRefs));
    }

    public static <T> GatewayResult<T> realtime(T data, String sdkMethod, Map<String, Object> rawRefs) {
        return new GatewayResult<>(data, Instant.now(), true, List.of(), mergeSdkMethod(sdkMethod, rawRefs));
    }

    private static Map<String, Object> mergeSdkMethod(String sdkMethod, Map<String, Object> rawRefs) {
        var refs = new java.util.LinkedHashMap<String, Object>();
        refs.put("sdk_method", sdkMethod);
        if (rawRefs != null) {
            refs.putAll(rawRefs);
        }
        return Map.copyOf(refs);
    }
}
