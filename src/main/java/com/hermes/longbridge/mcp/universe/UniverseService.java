package com.hermes.longbridge.mcp.universe;

import com.hermes.longbridge.mcp.cache.SnapshotRepository;
import com.hermes.longbridge.mcp.common.SymbolNormalizer;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Locale;
import java.util.Map;

@Service
public class UniverseService {

    public enum Mode {
        REPLACE,
        MERGE,
        REMOVE;

        public static Mode parse(String value) {
            if (value == null || value.isBlank()) {
                return MERGE;
            }
            return Mode.valueOf(value.trim().toUpperCase(Locale.ROOT));
        }
    }

    private final SnapshotRepository repository;

    public UniverseService(SnapshotRepository repository) {
        this.repository = repository;
    }

    public List<Map<String, Object>> setManualUniverse(List<String> rawSymbols, String mode) {
        List<String> symbols = normalizeSymbols(rawSymbols);
        Mode parsedMode = Mode.parse(mode);
        switch (parsedMode) {
            case REPLACE -> repository.replaceManualUniverse(symbols);
            case MERGE -> repository.mergeUniverse(symbols, "manual");
            case REMOVE -> repository.removeManualUniverse(symbols);
        }
        return repository.loadUniverse();
    }

    public void mergePositionSymbols(List<String> symbols) {
        repository.mergeUniverse(normalizeSymbols(symbols), "position");
    }

    public void mergeWatchlistSymbols(List<String> symbols) {
        repository.mergeUniverse(normalizeSymbols(symbols), "watchlist");
    }

    public List<Map<String, Object>> getUniverse() {
        return repository.loadUniverse();
    }

    private static List<String> normalizeSymbols(List<String> rawSymbols) {
        if (rawSymbols == null) {
            throw new IllegalArgumentException("symbols must not be null");
        }
        if (rawSymbols.size() > 500) {
            throw new IllegalArgumentException("symbols must not exceed 500");
        }
        return rawSymbols.stream()
                .map(SymbolNormalizer::normalize)
                .distinct()
                .sorted()
                .toList();
    }
}
