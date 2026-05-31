package com.hermes.longbridge.mcp.knowledge;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.hermes.longbridge.mcp.config.WhopKnowledgeProperties;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.locks.ReentrantLock;

@Service
public class WhopKnowledgeRefreshService {

    private static final TypeReference<Map<String, Object>> MAP_TYPE = new TypeReference<>() {
    };

    private final WhopKnowledgeProperties properties;
    private final WhopKnowledgeService knowledgeService;
    private final ObjectMapper objectMapper;
    private final ReentrantLock refreshLock = new ReentrantLock();
    private volatile Map<String, Object> lastRefresh;

    public WhopKnowledgeRefreshService(WhopKnowledgeProperties properties,
                                       WhopKnowledgeService knowledgeService,
                                       ObjectMapper objectMapper) {
        this.properties = properties;
        this.knowledgeService = knowledgeService;
        this.objectMapper = objectMapper;
    }

    public Map<String, Object> refresh(Boolean runCapture, Boolean rebuildKnowledge) {
        if (!Boolean.TRUE.equals(properties.refreshEnabled())) {
            throw new IllegalStateException("whop knowledge refresh is disabled by configuration");
        }
        if (!refreshLock.tryLock()) {
            Map<String, Object> data = new LinkedHashMap<>();
            data.put("ok", true);
            data.put("skipped", true);
            data.put("reason", "refresh_already_running");
            data.put("last_refresh", refreshStatus());
            return data;
        }
        try {
            return doRefresh(runCapture, rebuildKnowledge);
        } finally {
            refreshLock.unlock();
        }
    }

    public Map<String, Object> refreshStatus() {
        Map<String, Object> current = lastRefresh;
        if (current != null) {
            return current;
        }
        Path path = refreshStatusPath();
        if (!path.toFile().exists()) {
            return Map.of(
                    "configured", Map.of(
                            "auto_refresh_enabled", Boolean.TRUE.equals(properties.autoRefreshEnabled()),
                            "auto_refresh_run_capture", Boolean.TRUE.equals(properties.autoRefreshRunCapture()),
                            "auto_refresh_rebuild", Boolean.TRUE.equals(properties.autoRefreshRebuild()),
                            "auto_refresh_interval_ms", properties.autoRefreshIntervalMs(),
                            "capture_command_configured", properties.captureConfigured()),
                    "last_refresh", null);
        }
        try {
            current = objectMapper.readValue(path.toFile(), MAP_TYPE);
            lastRefresh = current;
            return current;
        } catch (IOException ex) {
            return Map.of(
                    "last_refresh", null,
                    "status_file", path.toString(),
                    "error", ex.getMessage());
        }
    }

    private Map<String, Object> doRefresh(Boolean runCapture, Boolean rebuildKnowledge) {
        boolean shouldRunCapture = Boolean.TRUE.equals(runCapture);
        boolean shouldRebuild = rebuildKnowledge == null || Boolean.TRUE.equals(rebuildKnowledge);
        Instant startedAt = Instant.now();
        List<String> warnings = new ArrayList<>();
        List<Map<String, Object>> commandRuns = new ArrayList<>();
        Map<String, Object> beforeStatus = knowledgeService.status();
        int beforeMessages = intValue(beforeStatus.get("canonical_messages"));

        if (shouldRunCapture) {
            if (properties.captureConfigured()) {
                commandRuns.add(runConfiguredCommand("capture", properties.captureCommand()));
            } else {
                warnings.add("capture_command_not_configured; skipped live Whop capture and rebuilt from local archive only");
            }
        }
        if (shouldRebuild) {
            commandRuns.add(runConfiguredCommand("rebuild", properties.rebuildCommand()));
        }
        knowledgeService.forceReload();
        Map<String, Object> afterStatus = knowledgeService.status();
        int afterMessages = intValue(afterStatus.get("canonical_messages"));
        int netNewMessages = Math.max(0, afterMessages - beforeMessages);

        Map<String, Object> data = new LinkedHashMap<>();
        data.put("ok", commandRuns.stream().allMatch(run -> Boolean.TRUE.equals(run.get("ok"))));
        data.put("skipped", false);
        data.put("started_at", startedAt.toString());
        data.put("finished_at", Instant.now().toString());
        data.put("duration_ms", java.time.Duration.between(startedAt, Instant.now()).toMillis());
        data.put("ran_capture", shouldRunCapture && properties.captureConfigured());
        data.put("ran_rebuild", shouldRebuild);
        data.put("canonical_messages_before", beforeMessages);
        data.put("canonical_messages_after", afterMessages);
        data.put("net_new_messages", netNewMessages);
        data.put("new_xiaozhaolucky_messages", netNewMessages);
        data.put("warnings", warnings);
        data.put("command_runs", commandRuns);
        data.put("status", afterStatus);
        data.put("status_file", refreshStatusPath().toString());
        lastRefresh = Map.copyOf(data);
        writeRefreshStatus(data);
        return data;
    }

    private Map<String, Object> runConfiguredCommand(String step, String command) {
        Instant startedAt = Instant.now();
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("step", step);
        result.put("command", command);
        result.put("started_at", startedAt.toString());
        if (command == null || command.isBlank()) {
            result.put("ok", false);
            result.put("exit_code", null);
            result.put("stderr", "command is blank");
            result.put("stdout", "");
            return result;
        }

        ProcessBuilder builder = new ProcessBuilder("zsh", "-lc", command);
        builder.directory(Path.of("").toAbsolutePath().normalize().toFile());
        try {
            Process process = builder.start();
            boolean finished = process.waitFor(properties.commandTimeoutMs(), TimeUnit.MILLISECONDS);
            if (!finished) {
                process.destroyForcibly();
                result.put("ok", false);
                result.put("exit_code", null);
                result.put("duration_ms", Duration.between(startedAt, Instant.now()).toMillis());
                result.put("stdout", truncate(new String(process.getInputStream().readAllBytes(), StandardCharsets.UTF_8)));
                result.put("stderr", "command timed out after " + properties.commandTimeoutMs() + "ms");
                return result;
            }
            String stdout = new String(process.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
            String stderr = new String(process.getErrorStream().readAllBytes(), StandardCharsets.UTF_8);
            int exitCode = process.exitValue();
            result.put("ok", exitCode == 0);
            result.put("exit_code", exitCode);
            result.put("duration_ms", Duration.between(startedAt, Instant.now()).toMillis());
            result.put("stdout", truncate(stdout));
            result.put("stderr", truncate(stderr));
            return result;
        } catch (IOException ex) {
            result.put("ok", false);
            result.put("exit_code", null);
            result.put("duration_ms", Duration.between(startedAt, Instant.now()).toMillis());
            result.put("stdout", "");
            result.put("stderr", ex.getMessage());
            return result;
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            result.put("ok", false);
            result.put("exit_code", null);
            result.put("duration_ms", Duration.between(startedAt, Instant.now()).toMillis());
            result.put("stdout", "");
            result.put("stderr", "interrupted");
            return result;
        }
    }

    private String truncate(String value) {
        if (value == null || value.length() <= 8_000) {
            return value;
        }
        return value.substring(0, 8_000) + "...";
    }

    private Path refreshStatusPath() {
        return knowledgeService.knowledgeDir().resolve("refresh_status.json");
    }

    private void writeRefreshStatus(Map<String, Object> data) {
        Path path = refreshStatusPath();
        try {
            java.nio.file.Files.createDirectories(path.getParent());
            objectMapper.writerWithDefaultPrettyPrinter().writeValue(path.toFile(), data);
        } catch (IOException ignored) {
            // The refresh itself has already completed; status-file persistence is best effort.
        }
    }

    private int intValue(Object value) {
        if (value instanceof Number number) {
            return number.intValue();
        }
        if (value == null) {
            return 0;
        }
        try {
            return Integer.parseInt(value.toString());
        } catch (NumberFormatException ex) {
            return 0;
        }
    }
}
