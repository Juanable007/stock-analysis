package com.hermes.longbridge.mcp.tools;

import com.hermes.longbridge.mcp.cache.SnapshotRepository;
import com.hermes.longbridge.mcp.common.ToolResponse;
import com.hermes.longbridge.mcp.longbridge.LongbridgeAccountGateway;
import com.hermes.longbridge.mcp.universe.UniverseService;
import org.springframework.ai.tool.annotation.Tool;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Map;
import java.util.Objects;

@Component
public class AccountTools {

    private final LongbridgeAccountGateway accountGateway;
    private final UniverseService universeService;
    private final SnapshotRepository snapshotRepository;
    private final ToolExecutionSupport support;

    public AccountTools(LongbridgeAccountGateway accountGateway,
                        UniverseService universeService,
                        SnapshotRepository snapshotRepository,
                        ToolExecutionSupport support) {
        this.accountGateway = accountGateway;
        this.universeService = universeService;
        this.snapshotRepository = snapshotRepository;
        this.support = support;
    }

    @Tool(description = "Read-only account asset summary from Longbridge.")
    public ToolResponse<Object> get_account_assets() {
        return support.fromGateway("get_account_assets", accountGateway::assets);
    }

    @Tool(description = "Read-only stock positions normalized for Hermes evidence collection.")
    public ToolResponse<List<Map<String, Object>>> list_stock_positions() {
        ToolResponse<List<Map<String, Object>>> response = support.fromGateway("list_stock_positions", accountGateway::stockPositions);
        if (response.ok() && response.data() != null) {
            String asOf = response.asOf() == null ? null : response.asOf().toString();
            if (asOf != null) {
                response.data().forEach(position -> position.put("as_of", asOf));
            }
            List<String> symbols = response.data().stream()
                    .map(position -> position.get("symbol"))
                    .filter(Objects::nonNull)
                    .map(Object::toString)
                    .toList();
            universeService.mergePositionSymbols(symbols);
            snapshotRepository.savePositions(response.data(), response.asOf());
        }
        return response;
    }
}
