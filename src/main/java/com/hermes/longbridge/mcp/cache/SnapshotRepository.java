package com.hermes.longbridge.mcp.cache;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import jakarta.annotation.PostConstruct;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Repository
public class SnapshotRepository {

    private final JdbcTemplate jdbcTemplate;
    private final ObjectMapper objectMapper;

    public SnapshotRepository(JdbcTemplate jdbcTemplate, ObjectMapper objectMapper) {
        this.jdbcTemplate = jdbcTemplate;
        this.objectMapper = objectMapper;
    }

    @PostConstruct
    void migrate() {
        jdbcTemplate.execute("""
                CREATE TABLE IF NOT EXISTS universe_symbol (
                    symbol TEXT NOT NULL,
                    source TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (symbol, source)
                )
                """);
        jdbcTemplate.execute("""
                CREATE TABLE IF NOT EXISTS quote_snapshot (
                    symbol TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    as_of TEXT NOT NULL
                )
                """);
        jdbcTemplate.execute("""
                CREATE TABLE IF NOT EXISTS position_snapshot (
                    symbol TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    as_of TEXT NOT NULL
                )
                """);
        jdbcTemplate.execute("""
                CREATE TABLE IF NOT EXISTS tool_call (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tool_name TEXT NOT NULL,
                    ok INTEGER NOT NULL,
                    called_at TEXT NOT NULL,
                    warnings TEXT NOT NULL,
                    errors TEXT NOT NULL
                )
                """);
    }

    public boolean healthy() {
        try {
            Integer one = jdbcTemplate.queryForObject("SELECT 1", Integer.class);
            return one != null && one == 1;
        } catch (RuntimeException ex) {
            return false;
        }
    }

    public void replaceManualUniverse(List<String> symbols) {
        jdbcTemplate.update("DELETE FROM universe_symbol WHERE source = 'manual'");
        mergeUniverse(symbols, "manual");
    }

    public void mergeUniverse(List<String> symbols, String source) {
        Instant now = Instant.now();
        for (String symbol : symbols) {
            jdbcTemplate.update("""
                    INSERT INTO universe_symbol(symbol, source, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(symbol, source) DO UPDATE SET updated_at = excluded.updated_at
                    """, symbol, source, now.toString());
        }
    }

    public void removeManualUniverse(List<String> symbols) {
        for (String symbol : symbols) {
            jdbcTemplate.update("DELETE FROM universe_symbol WHERE symbol = ? AND source = 'manual'", symbol);
        }
    }

    public List<Map<String, Object>> loadUniverse() {
        return jdbcTemplate.query("""
                SELECT symbol, group_concat(source, ',') AS sources, max(updated_at) AS updated_at
                FROM universe_symbol
                GROUP BY symbol
                ORDER BY symbol
                """, (rs, rowNum) -> {
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("symbol", rs.getString("symbol"));
            row.put("sources", List.of(rs.getString("sources").split(",")));
            row.put("updated_at", rs.getString("updated_at"));
            return row;
        });
    }

    public void saveQuote(String symbol, Map<String, Object> payload, Instant asOf) {
        jdbcTemplate.update("""
                INSERT INTO quote_snapshot(symbol, payload, as_of)
                VALUES (?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET payload = excluded.payload, as_of = excluded.as_of
                """, symbol, toJson(payload), asOf.toString());
    }

    public List<Map<String, Object>> loadQuotes(List<String> symbols) {
        if (symbols == null || symbols.isEmpty()) {
            return jdbcTemplate.query("SELECT symbol, payload, as_of FROM quote_snapshot ORDER BY symbol", this::quoteRow);
        }
        String placeholders = String.join(",", java.util.Collections.nCopies(symbols.size(), "?"));
        return jdbcTemplate.query("SELECT symbol, payload, as_of FROM quote_snapshot WHERE symbol IN (" + placeholders + ") ORDER BY symbol",
                this::quoteRow,
                symbols.toArray());
    }

    public Instant latestQuoteTime() {
        String value = jdbcTemplate.queryForObject("SELECT max(as_of) FROM quote_snapshot", String.class);
        return value == null ? null : Instant.parse(value);
    }

    public void savePositions(List<Map<String, Object>> positions, Instant asOf) {
        for (Map<String, Object> position : positions) {
            Object symbol = position.get("symbol");
            if (symbol == null) {
                continue;
            }
            jdbcTemplate.update("""
                    INSERT INTO position_snapshot(symbol, payload, as_of)
                    VALUES (?, ?, ?)
                    ON CONFLICT(symbol) DO UPDATE SET payload = excluded.payload, as_of = excluded.as_of
                    """, symbol.toString(), toJson(position), asOf.toString());
        }
    }

    public void recordToolCall(String toolName, boolean ok, List<String> warnings, List<String> errors) {
        jdbcTemplate.update("""
                INSERT INTO tool_call(tool_name, ok, called_at, warnings, errors)
                VALUES (?, ?, ?, ?, ?)
                """, toolName, ok ? 1 : 0, Instant.now().toString(), toJson(warnings), toJson(errors));
    }

    private Map<String, Object> quoteRow(java.sql.ResultSet rs, int rowNum) throws java.sql.SQLException {
        Map<String, Object> row = new LinkedHashMap<>(fromJsonObject(rs.getString("payload")));
        row.putIfAbsent("symbol", rs.getString("symbol"));
        row.put("as_of", rs.getString("as_of"));
        return row;
    }

    private String toJson(Object value) {
        try {
            return objectMapper.writeValueAsString(value);
        } catch (JsonProcessingException ex) {
            throw new IllegalArgumentException("failed to serialize snapshot", ex);
        }
    }

    private Map<String, Object> fromJsonObject(String value) {
        try {
            return objectMapper.readValue(value, new TypeReference<>() {
            });
        } catch (JsonProcessingException ex) {
            throw new IllegalArgumentException("failed to read snapshot", ex);
        }
    }
}
