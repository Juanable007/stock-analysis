package com.hermes.longbridge.mcp.longbridge;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Component;

import java.lang.reflect.Array;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Component
public class SdkObjectMapper {

    private final ObjectMapper objectMapper;

    public SdkObjectMapper(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    public Object normalize(Object value) {
        if (value == null) {
            return null;
        }
        if (value instanceof Map<?, ?> map) {
            Map<String, Object> normalized = new LinkedHashMap<>();
            map.forEach((key, item) -> normalized.put(String.valueOf(key), normalize(item)));
            return normalized;
        }
        if (value instanceof Iterable<?> iterable) {
            List<Object> normalized = new ArrayList<>();
            iterable.forEach(item -> normalized.add(normalize(item)));
            return normalized;
        }
        if (value.getClass().isArray()) {
            List<Object> normalized = new ArrayList<>();
            int length = Array.getLength(value);
            for (int index = 0; index < length; index++) {
                normalized.add(normalize(Array.get(value, index)));
            }
            return normalized;
        }
        if (value instanceof String || value instanceof Number || value instanceof Boolean) {
            return value;
        }
        try {
            return objectMapper.convertValue(value, new TypeReference<Map<String, Object>>() {
            });
        } catch (IllegalArgumentException ex) {
            return value.toString();
        }
    }

    public List<Map<String, Object>> normalizeList(Object value) {
        Object normalized = normalize(value);
        if (normalized instanceof List<?> list) {
            return list.stream()
                    .map(this::asMap)
                    .toList();
        }
        if (normalized instanceof Map<?, ?> map) {
            Object items = firstPresent(map, "items", "list", "quotes", "positions", "data", "news");
            if (items instanceof List<?> list) {
                return list.stream().map(this::asMap).toList();
            }
            return List.of(asMap(map));
        }
        return List.of(Map.of("value", String.valueOf(normalized)));
    }

    public Map<String, Object> normalizeMap(Object value) {
        return asMap(normalize(value));
    }

    private Map<String, Object> asMap(Object value) {
        if (value instanceof Map<?, ?> map) {
            Map<String, Object> normalized = new LinkedHashMap<>();
            map.forEach((key, item) -> normalized.put(String.valueOf(key), normalize(item)));
            return normalized;
        }
        Map<String, Object> fallback = new LinkedHashMap<>();
        fallback.put("value", value == null ? null : value.toString());
        return fallback;
    }

    private Object firstPresent(Map<?, ?> map, String... keys) {
        for (String key : keys) {
            if (map.containsKey(key)) {
                return map.get(key);
            }
        }
        return null;
    }
}
