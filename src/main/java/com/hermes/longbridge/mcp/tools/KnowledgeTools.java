package com.hermes.longbridge.mcp.tools;

import com.hermes.longbridge.mcp.common.ToolResponse;
import com.hermes.longbridge.mcp.knowledge.WhopKnowledgeRefreshService;
import com.hermes.longbridge.mcp.knowledge.WhopKnowledgeService;
import org.springframework.ai.tool.annotation.Tool;
import org.springframework.stereotype.Component;

import java.time.Instant;
import java.util.List;
import java.util.Map;

@Component
public class KnowledgeTools {

    private final ToolExecutionSupport support;
    private final WhopKnowledgeService knowledgeService;
    private final WhopKnowledgeRefreshService refreshService;

    public KnowledgeTools(ToolExecutionSupport support,
                          WhopKnowledgeService knowledgeService,
                          WhopKnowledgeRefreshService refreshService) {
        this.support = support;
        this.knowledgeService = knowledgeService;
        this.refreshService = refreshService;
    }

    @Tool(description = "Return local Whop xiaozhaolucky knowledge-base status, coverage, files, and realtime iteration config.")
    public ToolResponse<Map<String, Object>> get_whop_knowledge_status() {
        return support.local("get_whop_knowledge_status", () ->
                ToolResponse.ok(
                        knowledgeService.status(),
                        ToolResponse.SOURCE_LOCAL_CACHE,
                        Instant.now(),
                        false,
                        null,
                        List.of(),
                        Map.of("knowledge_dir", knowledgeService.knowledgeDir().toString())));
    }

    @Tool(description = "Return Whop channel/group map, roles, slugs, URLs, and coverage counts.")
    public ToolResponse<Map<String, Object>> get_whop_channel_map() {
        return support.local("get_whop_channel_map", () ->
                ToolResponse.ok(
                        knowledgeService.channelMap(),
                        ToolResponse.SOURCE_LOCAL_CACHE,
                        Instant.now(),
                        false,
                        null,
                        List.of(),
                        Map.of("source_file", knowledgeService.knowledgeDir().resolve("channel_map.md").toString())));
    }

    @Tool(description = "Search the local Whop xiaozhaolucky knowledge base across canonical messages and derived theory/image/calendar documents.")
    public ToolResponse<Map<String, Object>> search_whop_knowledge(String query,
                                                                   List<String> symbols,
                                                                   List<String> channels,
                                                                   String start_date,
                                                                   String end_date,
                                                                   Integer limit) {
        return support.local("search_whop_knowledge", () ->
                ToolResponse.ok(
                        knowledgeService.search(query, symbols, channels, start_date, end_date, limit),
                        ToolResponse.SOURCE_LOCAL_CACHE,
                        Instant.now(),
                        false,
                        null,
                        List.of(),
                        Map.of("source_file", knowledgeService.knowledgeDir().resolve("messages_canonical.jsonl").toString())));
    }

    @Tool(description = "Return a symbol-specific Whop knowledge playbook with message evidence and derived theory lines.")
    public ToolResponse<Map<String, Object>> get_whop_symbol_playbook(String symbol, Integer limit) {
        return support.local("get_whop_symbol_playbook", () ->
                ToolResponse.ok(
                        knowledgeService.symbolPlaybook(symbol, limit),
                        ToolResponse.SOURCE_LOCAL_CACHE,
                        Instant.now(),
                        false,
                        null,
                        List.of(),
                        Map.of("symbol", symbol)));
    }

    @Tool(description = "Refresh Whop knowledge from local archive, optionally running the configured live Whop capture command first.")
    public ToolResponse<Map<String, Object>> refresh_whop_knowledge(Boolean run_capture, Boolean rebuild) {
        return support.local("refresh_whop_knowledge", () -> {
            Map<String, Object> data = refreshService.refresh(run_capture, rebuild);
            Map<String, Object> rawRefs = Map.of(
                    "run_capture", Boolean.TRUE.equals(run_capture),
                    "rebuild", rebuild == null || Boolean.TRUE.equals(rebuild));
            return ToolResponse.ok(
                    data,
                    ToolResponse.SOURCE_COMPUTED,
                    Instant.now(),
                    false,
                    null,
                    toolWarnings(data),
                    rawRefs);
        });
    }

    @SuppressWarnings("unchecked")
    private List<String> toolWarnings(Map<String, Object> data) {
        Object warnings = data.get("warnings");
        if (warnings instanceof List<?> list) {
            return list.stream().map(Object::toString).toList();
        }
        return List.of();
    }
}
