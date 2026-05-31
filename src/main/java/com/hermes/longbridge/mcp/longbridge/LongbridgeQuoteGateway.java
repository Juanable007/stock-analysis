package com.hermes.longbridge.mcp.longbridge;

import com.hermes.longbridge.mcp.common.SymbolNormalizer;
import org.springframework.stereotype.Component;

import java.time.LocalDate;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentSkipListSet;

@Component
public class LongbridgeQuoteGateway {

    private final LongbridgeClientFactory clientFactory;
    private final SdkObjectMapper sdkObjectMapper;
    private final Set<String> subscribedSymbols = new ConcurrentSkipListSet<>();

    public LongbridgeQuoteGateway(LongbridgeClientFactory clientFactory, SdkObjectMapper sdkObjectMapper) {
        this.clientFactory = clientFactory;
        this.sdkObjectMapper = sdkObjectMapper;
    }

    public GatewayResult<List<Map<String, Object>>> realtimeQuotes(List<String> symbols) {
        List<String> normalized = normalize(symbols);
        Object result = clientFactory.invoke(
                clientFactory.quoteContext(),
                "getRealtimeQuote",
                new Class<?>[]{String[].class},
                (Object) normalized.toArray(String[]::new));
        return GatewayResult.realtime(sdkObjectMapper.normalizeList(result), "QuoteContext.getRealtimeQuote",
                Map.of("symbols", normalized));
    }

    public GatewayResult<Map<String, Object>> subscribeQuotes(List<String> symbols) {
        List<String> normalized = normalize(symbols);
        int flags = clientFactory.intConstant("com.longbridge.quote.SubFlags", "Quote", 1);
        Object result = clientFactory.invoke(
                clientFactory.quoteContext(),
                "subscribe",
                new Class<?>[]{String[].class, int.class},
                (Object) normalized.toArray(String[]::new),
                flags);
        subscribedSymbols.addAll(normalized);
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("requested_symbols", normalized);
        data.put("subscribed_symbols", List.copyOf(subscribedSymbols));
        data.put("sdk_result", sdkObjectMapper.normalize(result));
        return GatewayResult.realtime(data, "QuoteContext.subscribe", Map.of("symbols", normalized));
    }

    public GatewayResult<List<Map<String, Object>>> candles(String symbol, String period, int count) {
        String normalized = SymbolNormalizer.normalize(symbol);
        Object sdkPeriod = period(period);
        Object adjustType = clientFactory.enumConstant("com.longbridge.quote.AdjustType", "NoAdjust", "NO_ADJUST");
        Object tradeSessions = clientFactory.enumConstant("com.longbridge.quote.TradeSessions", "Intraday", "INTRADAY");
        Object result = clientFactory.invoke(
                clientFactory.quoteContext(),
                "getCandlesticks",
                new Class<?>[]{
                        String.class,
                        sdkPeriod.getClass(),
                        int.class,
                        adjustType.getClass(),
                        tradeSessions.getClass()
                },
                normalized,
                sdkPeriod,
                count,
                adjustType,
                tradeSessions);
        return GatewayResult.of(sdkObjectMapper.normalizeList(result), "QuoteContext.getCandlesticks",
                Map.of("symbol", normalized, "period", period, "count", count));
    }

    public GatewayResult<Object> capitalFlow(String symbol) {
        String normalized = SymbolNormalizer.normalize(symbol);
        Object result = clientFactory.invoke(clientFactory.quoteContext(), "getCapitalFlow", new Class<?>[]{String.class}, normalized);
        return GatewayResult.of(sdkObjectMapper.normalize(result), "QuoteContext.getCapitalFlow", Map.of("symbol", normalized));
    }

    public GatewayResult<Object> capitalDistribution(String symbol) {
        String normalized = SymbolNormalizer.normalize(symbol);
        Object result = clientFactory.invoke(clientFactory.quoteContext(), "getCapitalDistribution", new Class<?>[]{String.class}, normalized);
        return GatewayResult.of(sdkObjectMapper.normalize(result), "QuoteContext.getCapitalDistribution", Map.of("symbol", normalized));
    }

    public GatewayResult<List<Map<String, Object>>> watchlist() {
        Object result = clientFactory.invoke(clientFactory.quoteContext(), "getWatchlist", new Class<?>[]{});
        List<Map<String, Object>> rows = sdkObjectMapper.normalizeList(result);
        return GatewayResult.of(rows, "QuoteContext.getWatchlist", Map.of());
    }

    public GatewayResult<Object> marketCalendar(String market, LocalDate date) {
        Object sdkMarket = clientFactory.enumConstant("com.longbridge.Market", normalizeMarket(market));
        LocalDate target = date == null ? LocalDate.now() : date;
        Object days = clientFactory.invoke(
                clientFactory.quoteContext(),
                "getTradingDays",
                new Class<?>[]{sdkMarket.getClass(), LocalDate.class, LocalDate.class},
                sdkMarket,
                target,
                target);
        Object session = clientFactory.invoke(clientFactory.quoteContext(), "getTradingSession", new Class<?>[]{});
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("market", market.toUpperCase(Locale.ROOT));
        data.put("date", target.toString());
        data.put("trading_days", sdkObjectMapper.normalize(days));
        data.put("trading_session", sdkObjectMapper.normalize(session));
        return GatewayResult.of(data, "QuoteContext.getTradingDays/getTradingSession", Map.of("market", market, "date", target.toString()));
    }

    public List<String> subscribedSymbols() {
        return List.copyOf(subscribedSymbols);
    }

    private Object period(String period) {
        return switch (period.toLowerCase(Locale.ROOT)) {
            case "1m" -> clientFactory.enumConstant("com.longbridge.quote.Period", "Min_1", "MIN_1");
            case "5m" -> clientFactory.enumConstant("com.longbridge.quote.Period", "Min_5", "MIN_5");
            case "15m" -> clientFactory.enumConstant("com.longbridge.quote.Period", "Min_15", "MIN_15");
            case "30m" -> clientFactory.enumConstant("com.longbridge.quote.Period", "Min_30", "MIN_30");
            case "60m" -> clientFactory.enumConstant("com.longbridge.quote.Period", "Min_60", "MIN_60");
            case "day" -> clientFactory.enumConstant("com.longbridge.quote.Period", "Day", "DAY");
            case "week" -> clientFactory.enumConstant("com.longbridge.quote.Period", "Week", "WEEK");
            case "month" -> clientFactory.enumConstant("com.longbridge.quote.Period", "Month", "MONTH");
            default -> throw new IllegalArgumentException("unsupported period: " + period);
        };
    }

    private String normalizeMarket(String market) {
        return switch (market.trim().toUpperCase(Locale.ROOT)) {
            case "US", "NYSE", "NASDAQ", "AMEX" -> "US";
            case "HK", "HKG" -> "HK";
            case "CN", "SH", "SSE", "SZ", "SZSE", "SHSE" -> "CN";
            case "SG" -> "SG";
            default -> throw new IllegalArgumentException("unsupported market: " + market);
        };
    }

    private List<String> normalize(List<String> symbols) {
        if (symbols == null || symbols.isEmpty()) {
            throw new IllegalArgumentException("symbols must not be empty");
        }
        return symbols.stream().map(SymbolNormalizer::normalize).distinct().toList();
    }
}
