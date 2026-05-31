package com.hermes.longbridge.mcp.common;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class ToolResponseTest {

    private final ObjectMapper objectMapper = new ObjectMapper()
            .registerModule(new JavaTimeModule())
            .disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);

    @Test
    void serializesRequiredSnakeCaseFields() throws Exception {
        ToolResponse<Map<String, Object>> response = ToolResponse.ok(
                Map.of("symbol", "AAPL.US"),
                ToolResponse.SOURCE_LONGBRIDGE,
                Instant.parse("2026-05-31T00:00:00Z"),
                true,
                42L,
                List.of("sample_warning"),
                Map.of("sdk_method", "QuoteContext.getRealtimeQuote"));

        String json = objectMapper.writeValueAsString(response);

        assertThat(json).contains("\"ok\":true");
        assertThat(json).contains("\"as_of\":\"2026-05-31T00:00:00Z\"");
        assertThat(json).contains("\"is_realtime\":true");
        assertThat(json).contains("\"cache_age_ms\":42");
        assertThat(json).contains("\"raw_refs\"");
        assertThat(json).doesNotContain("access_token");
    }

    @Test
    void createsParameterError() {
        ToolResponse<Object> response = ToolResponse.parameterError("bad input", Map.of("tool", "x"));

        assertThat(response.ok()).isFalse();
        assertThat(response.source()).isEqualTo(ToolResponse.SOURCE_COMPUTED);
        assertThat(response.errors()).containsExactly("bad input");
        assertThat(response.data()).isNull();
    }
}
