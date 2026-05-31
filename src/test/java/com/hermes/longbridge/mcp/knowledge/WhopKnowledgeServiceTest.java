package com.hermes.longbridge.mcp.knowledge;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.hermes.longbridge.mcp.config.WhopKnowledgeProperties;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class WhopKnowledgeServiceTest {

    @TempDir
    Path tempDir;

    @Test
    void searchesCanonicalMessagesAndDerivedDocuments() throws Exception {
        Path knowledgeDir = tempDir.resolve("knowledge");
        Files.createDirectories(knowledgeDir);
        Files.writeString(knowledgeDir.resolve("status.json"), """
                {"total_messages":1,"channels":{"-Gi":{"channel_name":"不用翻墙美股发布","messages":1}}}
                """);
        Files.writeString(knowledgeDir.resolve("channel_map.md"), """
                # 频道职责

                | 频道 | slug | 已采消息 | 职责判断 | URL |
                | --- | --- | --- | --- | --- |
                | 不用翻墙美股发布 | -Gi | 1 | 美股交易发布。 | https://example.test |
                """);
        Files.writeString(knowledgeDir.resolve("messages_canonical.jsonl"), """
                {"id":"m1","channel_name":"不用翻墙美股发布","channel_slug":"-Gi","author":"xiaozhaolucky","local_datetime":"2026-05-29T20:27:24+08:00","local_date":"2026-05-29","local_weekday":"Friday","et_datetime":"2026-05-29T08:27:24-04:00","et_date":"2026-05-29","et_weekday":"Friday","market_session":"premarket","content":"msfl 注意 20.67 前高，长线目标在微软正股450上方缺口","signal_tags":["gap"],"calendar_tags":["month_end_window"],"has_image":false}
                """);
        Files.writeString(knowledgeDir.resolve("trading_theory.md"), """
                | 2026-05-29 | MSFT,MSFL | 微软长线的目标在正股450这个上方缺口 |
                """);

        WhopKnowledgeService service = new WhopKnowledgeService(
                new WhopKnowledgeProperties(tempDir.toString(), "", "", true, false, false, true, 300_000L, 300_000L, 20),
                new ObjectMapper());

        Map<String, Object> result = service.search("缺口", List.of("MSFT"), List.of("美股发布"), null, null, 10);

        assertThat((List<?>) result.get("message_matches")).hasSize(1);
        assertThat((List<?>) result.get("document_matches")).isNotEmpty();
    }

    @Test
    void infersSymbolsFromNaturalLanguageAliasQueries() throws Exception {
        Path knowledgeDir = tempDir.resolve("knowledge");
        Files.createDirectories(knowledgeDir);
        Files.writeString(knowledgeDir.resolve("status.json"), "{\"total_messages\":1}");
        Files.writeString(knowledgeDir.resolve("messages_canonical.jsonl"), """
                {"id":"m1","channel_name":"不用翻墙美股发布","channel_slug":"-Gi","author":"xiaozhaolucky","local_datetime":"2026-05-30T03:58:42+08:00","local_date":"2026-05-30","content":"微软尾盘再平衡 达到了一直说的450附近","signal_tags":["rebalancing"],"calendar_tags":[],"has_image":false}
                """);
        Files.writeString(knowledgeDir.resolve("ticker_index.md"), """
                ## MSFT
                | 2026-05-30 | rebalancing | 微软尾盘再平衡 达到了一直说的450附近 |
                """);

        WhopKnowledgeService service = new WhopKnowledgeService(
                new WhopKnowledgeProperties(tempDir.toString(), "", "", true, false, false, true, 300_000L, 300_000L, 20),
                new ObjectMapper());

        Map<String, Object> result = service.search("MSFT / Microsoft / 微软的专属条目", null, null, null, null, 10);

        assertThat((List<?>) result.get("message_matches")).hasSize(1);
        assertThat((List<?>) result.get("document_matches")).isNotEmpty();
        assertThat(result.get("symbols")).asList().contains("MSFT");
        assertThat(result.get("effective_query")).isNull();
    }

    @Test
    void relaxesBroadKeywordQueriesWhenSymbolEvidenceExists() throws Exception {
        Path knowledgeDir = tempDir.resolve("knowledge");
        Files.createDirectories(knowledgeDir);
        Files.writeString(knowledgeDir.resolve("status.json"), "{\"total_messages\":1}");
        Files.writeString(knowledgeDir.resolve("messages_canonical.jsonl"), """
                {"id":"m1","channel_name":"不用翻墙美股发布","channel_slug":"-Gi","author":"xiaozhaolucky","local_datetime":"2026-05-30T03:58:42+08:00","local_date":"2026-05-30","content":"微软尾盘再平衡 达到了一直说的450附近","signal_tags":["rebalancing"],"calendar_tags":[],"has_image":false}
                """);
        Files.writeString(knowledgeDir.resolve("ticker_index.md"), """
                ## MSFT
                | 2026-05-30 | rebalancing | 微软尾盘再平衡 达到了一直说的450附近 |
                """);

        WhopKnowledgeService service = new WhopKnowledgeService(
                new WhopKnowledgeProperties(tempDir.toString(), "", "", true, false, false, true, 300_000L, 300_000L, 20),
                new ObjectMapper());

        Map<String, Object> result = service.search("MSFT / Microsoft / 微软 / AI / 云 / 科技股 / QQQ", null, null, null, null, 10);

        assertThat((List<?>) result.get("message_matches")).hasSize(1);
        assertThat((List<?>) result.get("document_matches")).isNotEmpty();
        assertThat(result.get("query_relaxed")).isEqualTo(true);
    }

    @Test
    void parsesChannelMapAndStatus() throws Exception {
        Path knowledgeDir = tempDir.resolve("knowledge");
        Files.createDirectories(knowledgeDir);
        Files.writeString(knowledgeDir.resolve("status.json"), "{\"total_messages\":2}");
        Files.writeString(knowledgeDir.resolve("messages_canonical.jsonl"), "");
        Files.writeString(knowledgeDir.resolve("channel_map.md"), """
                | 频道 | slug | 已采消息 | 职责判断 | URL |
                | --- | --- | --- | --- | --- |
                | 市值理论100跌50 公式记录 | 100-50 | 2 | 记录市值理论。 | https://example.test |
                """);

        WhopKnowledgeService service = new WhopKnowledgeService(
                new WhopKnowledgeProperties(tempDir.toString(), "", "", true, false, false, true, 300_000L, 300_000L, 20),
                new ObjectMapper());

        Map<String, Object> channels = service.channelMap();
        Map<String, Object> status = service.status();

        assertThat((List<?>) channels.get("channels")).hasSize(1);
        assertThat(status).containsKey("status_json");
        assertThat(status.get("canonical_messages")).isEqualTo(0);
    }
}
