package com.hermes.longbridge.mcp.tools;

import com.hermes.longbridge.mcp.common.ToolResponse;
import org.springframework.ai.tool.annotation.Tool;
import org.springframework.stereotype.Component;

import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Component
public class ContractTools {

    private final ToolExecutionSupport support;

    public ContractTools(ToolExecutionSupport support) {
        this.support = support;
    }

    @Tool(description = "Explain the Hermes MCP data contract, field meanings, and tool calling principles.")
    public ToolResponse<Map<String, Object>> explain_data_contract(String tool_name) {
        return support.local("explain_data_contract", () -> {
            Map<String, Object> data = new LinkedHashMap<>();
            data.put("top_level_fields", Map.of(
                    "ok", "boolean success flag",
                    "data", "tool-specific object/array or null",
                    "source", "longbridge | local_cache | computed",
                    "as_of", "ISO8601 UTC timestamp for the data, or null",
                    "is_realtime", "true only for realtime Longbridge quote/subscription responses",
                    "cache_age_ms", "age of local cached data, or null",
                    "warnings", "non-fatal caveats such as stale_data, missing_permission, unsupported_sdk_method",
                    "errors", "fatal errors; empty when ok=true",
                    "raw_refs", "safe trace refs only: sdk method, request id, symbol, market; never token/key"));
            data.put("decision_boundary", List.of(
                    "Tools return facts only.",
                    "Tools never return buy/sell/hold.",
                    "Tools never submit, replace, or cancel orders.",
                    "Whop knowledge tools return local derived evidence and treat discussion-channel xiaozhaolucky messages as primary evidence only.",
                    "Hermes must cite tool name, symbol, as_of, and key fields for conclusions."));
            data.put("freshness_rule", "Realtime quotes older than 10 seconds should be treated as possibly stale.");
            data.put("tool_name", tool_name == null || tool_name.isBlank() ? "all" : tool_name);
            return ToolResponse.ok(data, ToolResponse.SOURCE_COMPUTED, Instant.now(), false, null, List.of(), Map.of());
        });
    }
}
