package com.hermes.longbridge.mcp.knowledge;

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

@Service
public class WhopKnowledgeRefreshService {

    private final WhopKnowledgeProperties properties;
    private final WhopKnowledgeService knowledgeService;

    public WhopKnowledgeRefreshService(WhopKnowledgeProperties properties,
                                       WhopKnowledgeService knowledgeService) {
        this.properties = properties;
        this.knowledgeService = knowledgeService;
    }

    public Map<String, Object> refresh(Boolean runCapture, Boolean rebuildKnowledge) {
        if (!Boolean.TRUE.equals(properties.refreshEnabled())) {
            throw new IllegalStateException("whop knowledge refresh is disabled by configuration");
        }
        boolean shouldRunCapture = Boolean.TRUE.equals(runCapture);
        boolean shouldRebuild = rebuildKnowledge == null || Boolean.TRUE.equals(rebuildKnowledge);
        List<String> warnings = new ArrayList<>();
        List<Map<String, Object>> commandRuns = new ArrayList<>();

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

        Map<String, Object> data = new LinkedHashMap<>();
        data.put("ran_capture", shouldRunCapture && properties.captureConfigured());
        data.put("ran_rebuild", shouldRebuild);
        data.put("warnings", warnings);
        data.put("command_runs", commandRuns);
        data.put("status", knowledgeService.status());
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
}
