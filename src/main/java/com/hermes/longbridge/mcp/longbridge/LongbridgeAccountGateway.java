package com.hermes.longbridge.mcp.longbridge;

import com.hermes.longbridge.mcp.common.SymbolNormalizer;
import org.springframework.stereotype.Component;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Component
public class LongbridgeAccountGateway {

    private final LongbridgeClientFactory clientFactory;
    private final SdkObjectMapper sdkObjectMapper;

    public LongbridgeAccountGateway(LongbridgeClientFactory clientFactory, SdkObjectMapper sdkObjectMapper) {
        this.clientFactory = clientFactory;
        this.sdkObjectMapper = sdkObjectMapper;
    }

    public GatewayResult<Object> assets() {
        Object result = clientFactory.invoke(clientFactory.tradeContext(), "getAccountBalance", new Class<?>[]{});
        return GatewayResult.of(sdkObjectMapper.normalize(result), "TradeContext.getAccountBalance", Map.of());
    }

    public GatewayResult<List<Map<String, Object>>> stockPositions() {
        Class<?> options = clientFactory.optionalClass("com.longbridge.trade.GetStockPositionsOptions");
        Object result = clientFactory.invoke(clientFactory.tradeContext(), "getStockPositions", new Class<?>[]{options}, new Object[]{null});
        List<Map<String, Object>> positions = sdkObjectMapper.normalizeList(result).stream()
                .flatMap(position -> flattenPossiblePositionGroups(position).stream())
                .map(this::standardizePosition)
                .toList();
        return GatewayResult.of(positions, "TradeContext.getStockPositions", Map.of());
    }

    private List<Map<String, Object>> flattenPossiblePositionGroups(Map<String, Object> value) {
        Object channels = first(value, "channels");
        if (channels instanceof List<?> channelList) {
            return channelList.stream()
                    .filter(Map.class::isInstance)
                    .flatMap(channel -> {
                        Map<String, Object> channelMap = (Map<String, Object>) channel;
                        Object positions = first(channelMap, "positions");
                        if (!(positions instanceof List<?> positionList)) {
                            return java.util.stream.Stream.<Map<String, Object>>empty();
                        }
                        String accountChannel = stringValue(first(channelMap, "accountChannel", "account_channel"));
                        return positionList.stream()
                                .filter(Map.class::isInstance)
                                .map(item -> {
                                    Map<String, Object> row = new LinkedHashMap<>((Map<String, Object>) item);
                                    if (accountChannel != null) {
                                        row.put("account_channel", accountChannel);
                                    }
                                    return row;
                                });
                    })
                    .toList();
        }
        Object stockList = first(value, "stockList", "stock_list", "positions", "items");
        if (stockList instanceof List<?> list) {
            return list.stream()
                    .filter(Map.class::isInstance)
                    .map(item -> (Map<String, Object>) item)
                    .toList();
        }
        return List.of(value);
    }

    private Map<String, Object> standardizePosition(Map<String, Object> raw) {
        Map<String, Object> position = new LinkedHashMap<>();
        String rawSymbol = stringValue(first(raw, "symbol", "stockSymbol", "stock_symbol", "securitySymbol"));
        if (rawSymbol != null) {
            try {
                position.put("symbol", SymbolNormalizer.normalize(rawSymbol));
            } catch (IllegalArgumentException ex) {
                position.put("symbol", rawSymbol);
            }
        }
        putIfPresent(position, "name", first(raw, "name", "symbolName", "stockName", "stock_name"));
        putIfPresent(position, "market", first(raw, "market"));
        position.putIfAbsent("market", inferMarket(position.get("symbol")));
        putIfPresent(position, "quantity", first(raw, "quantity", "qty", "availableQuantity"));
        putIfPresent(position, "cost", first(raw, "costPrice", "cost_price", "cost"));
        putIfPresent(position, "market_value", first(raw, "marketValue", "market_value"));
        putIfPresent(position, "unrealized_pnl", first(raw, "unrealizedPnl", "unrealized_pnl", "pl"));
        putIfPresent(position, "currency", first(raw, "currency", "currencyCode"));
        position.put("raw", raw);
        return position;
    }

    private static Object first(Map<String, Object> map, String... keys) {
        for (String key : keys) {
            if (map.containsKey(key)) {
                return map.get(key);
            }
        }
        return null;
    }

    private static void putIfPresent(Map<String, Object> map, String key, Object value) {
        if (value != null) {
            map.put(key, value);
        }
    }

    private static String stringValue(Object value) {
        return value == null ? null : value.toString();
    }

    private static String inferMarket(Object symbol) {
        if (symbol == null) {
            return null;
        }
        String text = symbol.toString();
        int index = text.lastIndexOf('.');
        return index < 0 ? null : text.substring(index + 1);
    }
}
