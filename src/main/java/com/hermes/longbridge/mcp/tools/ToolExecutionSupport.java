package com.hermes.longbridge.mcp.tools;

import com.hermes.longbridge.mcp.cache.SnapshotRepository;
import com.hermes.longbridge.mcp.common.ErrorMapper;
import com.hermes.longbridge.mcp.common.ToolResponse;
import com.hermes.longbridge.mcp.longbridge.GatewayResult;
import com.hermes.longbridge.mcp.longbridge.LongbridgeClientFactory;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Map;
import java.util.function.Supplier;

@Component
public class ToolExecutionSupport {

    private final SnapshotRepository snapshotRepository;

    public ToolExecutionSupport(SnapshotRepository snapshotRepository) {
        this.snapshotRepository = snapshotRepository;
    }

    public <T> ToolResponse<T> fromGateway(String toolName, Supplier<GatewayResult<T>> supplier) {
        ToolResponse<T> response;
        try {
            GatewayResult<T> result = supplier.get();
            response = ToolResponse.ok(
                    result.data(),
                    ToolResponse.SOURCE_LONGBRIDGE,
                    result.asOf(),
                    result.realtime(),
                    null,
                    result.warnings(),
                    result.rawRefs());
        } catch (LongbridgeClientFactory.MissingLongbridgeCredentialsException ex) {
            response = ToolResponse.error(ToolResponse.SOURCE_LONGBRIDGE, List.of(), ErrorMapper.missingCredentials(), Map.of("tool", toolName));
        } catch (IllegalArgumentException ex) {
            response = ToolResponse.parameterError(ex.getMessage(), Map.of("tool", toolName));
        } catch (RuntimeException ex) {
            response = ToolResponse.error(ToolResponse.SOURCE_LONGBRIDGE, List.of(), List.of(ErrorMapper.sdkError(ex)), Map.of("tool", toolName));
        }
        record(toolName, response);
        return response;
    }

    public <T> ToolResponse<T> local(String toolName, Supplier<ToolResponse<T>> supplier) {
        ToolResponse<T> response;
        try {
            response = supplier.get();
        } catch (IllegalArgumentException ex) {
            response = ToolResponse.parameterError(ex.getMessage(), Map.of("tool", toolName));
        } catch (RuntimeException ex) {
            response = ToolResponse.error(ToolResponse.SOURCE_COMPUTED, List.of(), List.of(ErrorMapper.sdkError(ex)), Map.of("tool", toolName));
        }
        record(toolName, response);
        return response;
    }

    private void record(String toolName, ToolResponse<?> response) {
        try {
            snapshotRepository.recordToolCall(toolName, response.ok(), response.warnings(), response.errors());
        } catch (RuntimeException ignored) {
            // Tool calls must keep returning useful diagnostics even if metadata persistence is unavailable.
        }
    }
}
