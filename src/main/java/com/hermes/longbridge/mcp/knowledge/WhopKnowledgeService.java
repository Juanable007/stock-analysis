package com.hermes.longbridge.mcp.knowledge;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.hermes.longbridge.mcp.config.WhopKnowledgeProperties;
import org.springframework.stereotype.Service;

import java.io.BufferedReader;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.stream.Stream;

@Service
public class WhopKnowledgeService {

    private static final TypeReference<Map<String, Object>> MAP_TYPE = new TypeReference<>() {
    };
    private static final Set<String> DOCUMENT_FILES = Set.of(
            "README.md",
            "channel_map.md",
            "trading_theory.md",
            "ticker_index.md",
            "image_meanings.md",
            "image_queue.md",
            "market_calendar.md",
            "coverage_audit.md",
            "crawl_status.md",
            "image_verification_status.md",
            "next_capture_plan.md");
    private static final Map<String, List<String>> TICKER_ALIASES = Map.ofEntries(
            Map.entry("MSFT", List.of("MSFT", "Microsoft", "微软")),
            Map.entry("MSFL", List.of("MSFL", "MSFT", "Microsoft", "微软")),
            Map.entry("NVDA", List.of("NVDA", "NVIDIA", "英伟达")),
            Map.entry("NVDL", List.of("NVDL", "NVDA", "NVIDIA", "英伟达")),
            Map.entry("TSLA", List.of("TSLA", "Tesla", "特斯拉")),
            Map.entry("TSLL", List.of("TSLL", "TSLA", "Tesla", "特斯拉")),
            Map.entry("CONL", List.of("CONL", "COIN", "加密")),
            Map.entry("COIN", List.of("COIN", "Coinbase", "加密")),
            Map.entry("BTC", List.of("BTC", "Bitcoin", "比特币")),
            Map.entry("QQQ", List.of("QQQ", "纳指")),
            Map.entry("SPY", List.of("SPY", "SPX", "大盘", "指数")),
            Map.entry("HOOD", List.of("HOOD", "Robinhood")),
            Map.entry("IREN", List.of("IREN")),
            Map.entry("CIFR", List.of("CIFR")),
            Map.entry("CRWV", List.of("CRWV")),
            Map.entry("LITE", List.of("LITE")),
            Map.entry("MU", List.of("MU", "美光")),
            Map.entry("SOXL", List.of("SOXL")),
            Map.entry("INTC", List.of("INTC", "Intel", "英特尔")));

    private final WhopKnowledgeProperties properties;
    private final ObjectMapper objectMapper;
    private volatile KnowledgeSnapshot cachedSnapshot;

    public WhopKnowledgeService(WhopKnowledgeProperties properties, ObjectMapper objectMapper) {
        this.properties = properties;
        this.objectMapper = objectMapper;
    }

    public synchronized void forceReload() {
        cachedSnapshot = loadSnapshot();
    }

    public Map<String, Object> status() {
        KnowledgeSnapshot snapshot = snapshot();
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("archive_dir", archiveDir().toString());
        data.put("knowledge_dir", knowledgeDir().toString());
        data.put("loaded_at", snapshot.loadedAt().toString());
        data.put("version_mtime_ms", snapshot.versionMtimeMs());
        data.put("canonical_messages", snapshot.messages().size());
        data.put("documents", fileStatus());
        data.put("status_json", snapshot.statusJson());
        data.put("iteration", Map.of(
                "hot_reload", "MCP tools reload the knowledge snapshot when source files change.",
                "rebuild_command", properties.rebuildCommand(),
                "capture_command_configured", properties.captureConfigured(),
                "auto_refresh_enabled", Boolean.TRUE.equals(properties.autoRefreshEnabled()),
                "discussion_policy", "Only xiaozhaolucky messages are treated as primary evidence in discussion channels."));
        return data;
    }

    public Map<String, Object> channelMap() {
        KnowledgeSnapshot snapshot = snapshot();
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("channels", snapshot.channelRows());
        data.put("status_channels", snapshot.statusJson().getOrDefault("channels", Map.of()));
        data.put("source_file", knowledgeDir().resolve("channel_map.md").toString());
        data.put("loaded_at", snapshot.loadedAt().toString());
        return data;
    }

    public Map<String, Object> search(String query,
                                      List<String> symbols,
                                      List<String> channels,
                                      String startDate,
                                      String endDate,
                                      Integer limit) {
        List<String> normalizedSymbols = normalizeSymbols(symbols);
        if ((query == null || query.isBlank()) && normalizedSymbols.isEmpty()
                && (channels == null || channels.isEmpty()) && (startDate == null || startDate.isBlank())
                && (endDate == null || endDate.isBlank())) {
            throw new IllegalArgumentException("at least one of query, symbols, channels, start_date, or end_date is required");
        }
        KnowledgeSnapshot snapshot = snapshot();
        int safeLimit = clampLimit(limit);
        List<Map<String, Object>> messageMatches = snapshot.messages().stream()
                .filter(row -> matchesQuery(row, query))
                .filter(row -> matchesSymbols(row, normalizedSymbols))
                .filter(row -> matchesChannels(row, channels))
                .filter(row -> matchesDate(row, startDate, endDate))
                .sorted(Comparator.comparing(row -> stringValue(row.get("local_datetime")), Comparator.reverseOrder()))
                .limit(safeLimit)
                .map(this::messageResult)
                .toList();
        List<Map<String, Object>> documentMatches = documentMatches(snapshot, query, normalizedSymbols, safeLimit);

        Map<String, Object> data = new LinkedHashMap<>();
        data.put("query", blankToNull(query));
        data.put("symbols", normalizedSymbols);
        data.put("channels", channels == null ? List.of() : channels);
        data.put("start_date", blankToNull(startDate));
        data.put("end_date", blankToNull(endDate));
        data.put("message_matches", messageMatches);
        data.put("document_matches", documentMatches);
        data.put("loaded_at", snapshot.loadedAt().toString());
        data.put("evidence_policy", "Discussion channel conclusions should cite only xiaozhaolucky messages as primary evidence.");
        return data;
    }

    public Map<String, Object> symbolPlaybook(String symbol, Integer limit) {
        if (symbol == null || symbol.isBlank()) {
            throw new IllegalArgumentException("symbol must not be blank");
        }
        String normalized = symbol.trim().toUpperCase(Locale.ROOT);
        List<String> aliases = aliasesFor(normalized);
        Map<String, Object> search = search(null, List.of(normalized), List.of(), null, null, limit);
        KnowledgeSnapshot snapshot = snapshot();
        List<Map<String, Object>> theoryLines = documentMatches(snapshot, null, aliases, clampLimit(limit));
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("symbol", normalized);
        data.put("aliases", aliases);
        data.put("message_evidence", search.get("message_matches"));
        data.put("knowledge_lines", theoryLines);
        data.put("source_files", List.of(
                knowledgeDir().resolve("messages_canonical.jsonl").toString(),
                knowledgeDir().resolve("ticker_index.md").toString(),
                knowledgeDir().resolve("trading_theory.md").toString(),
                knowledgeDir().resolve("image_meanings.md").toString()));
        data.put("usage_note", "Use this as evidence for analysis, not as a direct buy/sell decision.");
        return data;
    }

    public Path archiveDir() {
        return Path.of(properties.archiveDir()).toAbsolutePath().normalize();
    }

    public Path knowledgeDir() {
        return archiveDir().resolve("knowledge");
    }

    private KnowledgeSnapshot snapshot() {
        KnowledgeSnapshot current = cachedSnapshot;
        long latestMtime = latestMtimeMs();
        if (current != null && current.versionMtimeMs() == latestMtime) {
            return current;
        }
        synchronized (this) {
            current = cachedSnapshot;
            if (current == null || current.versionMtimeMs() != latestMtime) {
                cachedSnapshot = loadSnapshot();
            }
            return cachedSnapshot;
        }
    }

    private KnowledgeSnapshot loadSnapshot() {
        Path knowledgeDir = knowledgeDir();
        Map<String, Object> statusJson = readJsonObject(knowledgeDir.resolve("status.json"));
        List<Map<String, Object>> messages = readJsonl(knowledgeDir.resolve("messages_canonical.jsonl"));
        Map<String, List<String>> documents = readDocuments(knowledgeDir);
        List<Map<String, Object>> channelRows = parseChannelMap(documents.getOrDefault("channel_map.md", List.of()));
        return new KnowledgeSnapshot(
                Instant.now(),
                latestMtimeMs(),
                statusJson,
                messages,
                documents,
                channelRows);
    }

    private Map<String, Object> readJsonObject(Path path) {
        if (!Files.exists(path)) {
            return Map.of();
        }
        try {
            return objectMapper.readValue(path.toFile(), MAP_TYPE);
        } catch (IOException ex) {
            throw new IllegalStateException("failed to read " + path, ex);
        }
    }

    private List<Map<String, Object>> readJsonl(Path path) {
        if (!Files.exists(path)) {
            return List.of();
        }
        List<Map<String, Object>> rows = new ArrayList<>();
        try (BufferedReader reader = Files.newBufferedReader(path, StandardCharsets.UTF_8)) {
            String line;
            while ((line = reader.readLine()) != null) {
                if (!line.isBlank()) {
                    rows.add(objectMapper.readValue(line, MAP_TYPE));
                }
            }
            return List.copyOf(rows);
        } catch (IOException ex) {
            throw new IllegalStateException("failed to read " + path, ex);
        }
    }

    private Map<String, List<String>> readDocuments(Path knowledgeDir) {
        Map<String, List<String>> documents = new LinkedHashMap<>();
        for (String fileName : DOCUMENT_FILES) {
            Path path = knowledgeDir.resolve(fileName);
            if (Files.exists(path)) {
                try {
                    documents.put(fileName, Files.readAllLines(path, StandardCharsets.UTF_8));
                } catch (IOException ex) {
                    throw new IllegalStateException("failed to read " + path, ex);
                }
            }
        }
        return Map.copyOf(documents);
    }

    private List<Map<String, Object>> parseChannelMap(List<String> lines) {
        List<Map<String, Object>> rows = new ArrayList<>();
        for (String line : lines) {
            if (!line.startsWith("|") || line.contains("---") || line.contains("频道 | slug")) {
                continue;
            }
            String[] cells = line.split("\\|");
            if (cells.length < 6) {
                continue;
            }
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("channel", cells[1].trim());
            row.put("slug", cells[2].trim());
            row.put("messages", parseInteger(cells[3].trim()));
            row.put("role", cells[4].trim());
            row.put("url", cells[5].trim());
            rows.add(row);
        }
        return List.copyOf(rows);
    }

    private List<Map<String, Object>> documentMatches(KnowledgeSnapshot snapshot,
                                                      String query,
                                                      List<String> symbolsOrAliases,
                                                      int limit) {
        List<String> queryNeedles = new ArrayList<>();
        if (query != null && !query.isBlank()) {
            queryNeedles.addAll(queryTerms(query));
        }
        List<String> symbolNeedles = new ArrayList<>();
        for (String symbol : symbolsOrAliases == null ? List.<String>of() : symbolsOrAliases) {
            symbolNeedles.addAll(aliasesFor(symbol));
        }
        List<String> normalizedQueryNeedles = queryNeedles.stream()
                .filter(Objects::nonNull)
                .map(value -> value.toLowerCase(Locale.ROOT).trim())
                .filter(value -> !value.isBlank())
                .distinct()
                .toList();
        List<String> normalizedSymbolNeedles = symbolNeedles.stream()
                .filter(Objects::nonNull)
                .map(value -> value.toLowerCase(Locale.ROOT).trim())
                .filter(value -> !value.isBlank())
                .distinct()
                .toList();
        if (normalizedQueryNeedles.isEmpty() && normalizedSymbolNeedles.isEmpty()) {
            return List.of();
        }

        List<Map<String, Object>> matches = new ArrayList<>();
        for (Map.Entry<String, List<String>> entry : snapshot.documents().entrySet()) {
            List<String> lines = entry.getValue();
            for (int index = 0; index < lines.size(); index++) {
                String line = lines.get(index);
                String lower = line.toLowerCase(Locale.ROOT);
                boolean queryMatches = normalizedQueryNeedles.isEmpty()
                        || normalizedQueryNeedles.stream().allMatch(lower::contains);
                boolean symbolMatches = normalizedSymbolNeedles.isEmpty()
                        || normalizedSymbolNeedles.stream().anyMatch(lower::contains);
                if (queryMatches && symbolMatches) {
                    Map<String, Object> match = new LinkedHashMap<>();
                    match.put("file", entry.getKey());
                    match.put("line", index + 1);
                    match.put("text", truncate(line.strip(), 1_200));
                    matches.add(match);
                    if (matches.size() >= limit) {
                        return List.copyOf(matches);
                    }
                }
            }
        }
        return List.copyOf(matches);
    }

    private boolean matchesQuery(Map<String, Object> row, String query) {
        if (query == null || query.isBlank()) {
            return true;
        }
        String haystack = haystack(row);
        List<String> terms = queryTerms(query);
        return terms.isEmpty() || terms.stream().allMatch(haystack::contains);
    }

    private boolean matchesSymbols(Map<String, Object> row, List<String> symbols) {
        if (symbols == null || symbols.isEmpty()) {
            return true;
        }
        String haystack = haystack(row);
        return symbols.stream()
                .flatMap(symbol -> aliasesFor(symbol).stream())
                .map(alias -> alias.toLowerCase(Locale.ROOT))
                .anyMatch(haystack::contains);
    }

    private boolean matchesChannels(Map<String, Object> row, List<String> channels) {
        if (channels == null || channels.isEmpty()) {
            return true;
        }
        String channelName = stringValue(row.get("channel_name")).toLowerCase(Locale.ROOT);
        String channelSlug = stringValue(row.get("channel_slug")).toLowerCase(Locale.ROOT);
        return channels.stream()
                .filter(Objects::nonNull)
                .map(value -> value.toLowerCase(Locale.ROOT).trim())
                .anyMatch(value -> channelName.contains(value) || channelSlug.contains(value));
    }

    private boolean matchesDate(Map<String, Object> row, String startDate, String endDate) {
        String localDate = stringValue(row.get("local_date"));
        if (localDate.isBlank()) {
            return true;
        }
        if (startDate != null && !startDate.isBlank() && localDate.compareTo(startDate) < 0) {
            return false;
        }
        return endDate == null || endDate.isBlank() || localDate.compareTo(endDate) <= 0;
    }

    private Map<String, Object> messageResult(Map<String, Object> row) {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("id", row.get("id"));
        result.put("channel_name", row.get("channel_name"));
        result.put("channel_slug", row.get("channel_slug"));
        result.put("author", row.get("author"));
        result.put("local_datetime", row.get("local_datetime"));
        result.put("local_date", row.get("local_date"));
        result.put("local_weekday", row.get("local_weekday"));
        result.put("et_datetime", row.get("et_datetime"));
        result.put("et_date", row.get("et_date"));
        result.put("et_weekday", row.get("et_weekday"));
        result.put("market_session", row.get("market_session"));
        result.put("calendar_tags", row.getOrDefault("calendar_tags", List.of()));
        result.put("signal_tags", row.getOrDefault("signal_tags", List.of()));
        result.put("has_image", row.getOrDefault("has_image", false));
        result.put("attachment_ids", row.getOrDefault("attachment_ids", List.of()));
        result.put("content", truncate(stringValue(row.get("content")), 1_500));
        return result;
    }

    private Map<String, Object> fileStatus() {
        List<Map<String, Object>> files = new ArrayList<>();
        Path knowledgeDir = knowledgeDir();
        try (Stream<Path> stream = Files.exists(knowledgeDir) ? Files.list(knowledgeDir) : Stream.empty()) {
            stream.filter(Files::isRegularFile)
                    .sorted(Comparator.comparing(path -> path.getFileName().toString()))
                    .forEach(path -> files.add(Map.of(
                            "file", path.getFileName().toString(),
                            "size_bytes", size(path),
                            "modified_at", modifiedAt(path).toString())));
        } catch (IOException ex) {
            throw new IllegalStateException("failed to list " + knowledgeDir, ex);
        }
        return Map.of("files", files);
    }

    private long latestMtimeMs() {
        Path knowledgeDir = knowledgeDir();
        if (!Files.exists(knowledgeDir)) {
            return 0L;
        }
        try (Stream<Path> stream = Files.list(knowledgeDir)) {
            return stream.filter(Files::isRegularFile)
                    .mapToLong(this::modifiedMillis)
                    .max()
                    .orElse(0L);
        } catch (IOException ex) {
            throw new IllegalStateException("failed to scan " + knowledgeDir, ex);
        }
    }

    private long modifiedMillis(Path path) {
        try {
            return Files.getLastModifiedTime(path).toMillis();
        } catch (IOException ex) {
            return 0L;
        }
    }

    private Instant modifiedAt(Path path) {
        try {
            return Files.getLastModifiedTime(path).toInstant();
        } catch (IOException ex) {
            return Instant.EPOCH;
        }
    }

    private long size(Path path) {
        try {
            return Files.size(path);
        } catch (IOException ex) {
            return 0L;
        }
    }

    private int parseInteger(String value) {
        try {
            return Integer.parseInt(value);
        } catch (RuntimeException ex) {
            return 0;
        }
    }

    private List<String> normalizeSymbols(List<String> symbols) {
        if (symbols == null) {
            return List.of();
        }
        return symbols.stream()
                .filter(Objects::nonNull)
                .map(value -> value.trim().toUpperCase(Locale.ROOT))
                .filter(value -> !value.isBlank())
                .distinct()
                .toList();
    }

    private List<String> aliasesFor(String symbol) {
        if (symbol == null || symbol.isBlank()) {
            return List.of();
        }
        String normalized = symbol.trim().toUpperCase(Locale.ROOT);
        return TICKER_ALIASES.getOrDefault(normalized, List.of(normalized));
    }

    private List<String> queryTerms(String query) {
        String normalized = query == null ? "" : query.trim().toLowerCase(Locale.ROOT);
        if (normalized.isBlank()) {
            return List.of();
        }
        String[] parts = normalized.split("\\s+");
        return Stream.of(parts).filter(part -> !part.isBlank()).toList();
    }

    private String haystack(Map<String, Object> row) {
        return (stringValue(row.get("content")) + " "
                + stringValue(row.get("channel_name")) + " "
                + stringValue(row.get("channel_slug")) + " "
                + stringValue(row.get("signal_tags")) + " "
                + stringValue(row.get("calendar_tags")))
                .toLowerCase(Locale.ROOT);
    }

    private int clampLimit(Integer limit) {
        int safeLimit = limit == null ? 20 : limit;
        int max = Math.max(1, properties.maxSearchResults());
        return Math.max(1, Math.min(safeLimit, Math.min(max, 200)));
    }

    private String stringValue(Object value) {
        return value == null ? "" : value.toString();
    }

    private Object blankToNull(String value) {
        return value == null || value.isBlank() ? null : value;
    }

    private String truncate(String value, int maxLength) {
        if (value == null || value.length() <= maxLength) {
            return value;
        }
        return value.substring(0, maxLength - 3) + "...";
    }

    private record KnowledgeSnapshot(
            Instant loadedAt,
            long versionMtimeMs,
            Map<String, Object> statusJson,
            List<Map<String, Object>> messages,
            Map<String, List<String>> documents,
            List<Map<String, Object>> channelRows
    ) {
    }
}
