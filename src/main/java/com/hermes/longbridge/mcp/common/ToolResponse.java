package com.hermes.longbridge.mcp.common;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonFormat;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.time.Instant;
import java.util.List;
import java.util.Map;

@JsonInclude(JsonInclude.Include.ALWAYS)
public record ToolResponse<T>(
        boolean ok,
        T data,
        String source,
        @JsonProperty("as_of")
        @JsonFormat(shape = JsonFormat.Shape.STRING)
        Instant asOf,
        @JsonProperty("is_realtime")
        boolean isRealtime,
        @JsonProperty("cache_age_ms")
        Long cacheAgeMs,
        List<String> warnings,
        List<String> errors,
        @JsonProperty("raw_refs")
        Map<String, Object> rawRefs
) {

    public static final String SOURCE_LONGBRIDGE = "longbridge";
    public static final String SOURCE_LOCAL_CACHE = "local_cache";
    public static final String SOURCE_COMPUTED = "computed";

    public ToolResponse {
        warnings = warnings == null ? List.of() : List.copyOf(warnings);
        errors = errors == null ? List.of() : List.copyOf(errors);
        rawRefs = rawRefs == null ? Map.of() : Map.copyOf(rawRefs);
    }

    public static <T> ToolResponse<T> ok(
            T data,
            String source,
            Instant asOf,
            boolean realtime,
            Long cacheAgeMs,
            List<String> warnings,
            Map<String, Object> rawRefs
    ) {
        return new ToolResponse<>(true, data, source, asOf, realtime, cacheAgeMs, warnings, List.of(), rawRefs);
    }

    public static <T> ToolResponse<T> error(
            String source,
            List<String> warnings,
            List<String> errors,
            Map<String, Object> rawRefs
    ) {
        return new ToolResponse<>(false, null, source, null, false, null, warnings, errors, rawRefs);
    }

    public static <T> ToolResponse<T> parameterError(String error, Map<String, Object> rawRefs) {
        return error(SOURCE_COMPUTED, List.of(), List.of(error), rawRefs);
    }
}
