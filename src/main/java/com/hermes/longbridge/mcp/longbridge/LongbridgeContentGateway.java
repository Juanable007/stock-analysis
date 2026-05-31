package com.hermes.longbridge.mcp.longbridge;

import com.hermes.longbridge.mcp.common.SymbolNormalizer;
import org.springframework.stereotype.Component;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Component
public class LongbridgeContentGateway {

    private final LongbridgeClientFactory clientFactory;
    private final SdkObjectMapper sdkObjectMapper;

    public LongbridgeContentGateway(LongbridgeClientFactory clientFactory, SdkObjectMapper sdkObjectMapper) {
        this.clientFactory = clientFactory;
        this.sdkObjectMapper = sdkObjectMapper;
    }

    public GatewayResult<List<Map<String, Object>>> news(String symbol, int limit) {
        String normalized = SymbolNormalizer.normalize(symbol);
        Object result = clientFactory.invokeFirst(
                clientFactory.contentContext(),
                List.of("getNews", "news", "getSymbolNews"),
                normalized);
        List<Map<String, Object>> news = sdkObjectMapper.normalizeList(result).stream()
                .limit(limit)
                .map(this::standardizeNews)
                .toList();
        return GatewayResult.of(news, "ContentContext.getNews", Map.of("symbol", normalized, "limit", limit));
    }

    public GatewayResult<Map<String, Object>> fundamentalsSummary(String symbol) {
        String normalized = SymbolNormalizer.normalize(symbol);
        Map<String, Object> data = new LinkedHashMap<>();
        List<String> missing = new java.util.ArrayList<>();
        tryPut(data, missing, "valuation", "FundamentalContext.getValuation", List.of("getValuation", "valuation"), normalized);
        tryPut(data, missing, "company", "FundamentalContext.getCompany", List.of("getCompany", "company"), normalized);
        tryPut(data, missing, "financial", "FundamentalContext.getFinancial", List.of("getFinancial", "getFinancials", "financial"), normalized);
        tryPut(data, missing, "income", "FundamentalContext.getIncomeStatement", List.of("getIncomeStatement", "incomeStatement"), normalized);
        data.put("symbol", normalized);
        return new GatewayResult<>(data, java.time.Instant.now(), false, missing,
                Map.of("sdk_method", "FundamentalContext.*", "symbol", normalized));
    }

    public GatewayResult<Map<String, Object>> analystRatings(String symbol) {
        String normalized = SymbolNormalizer.normalize(symbol);
        Map<String, Object> data = new LinkedHashMap<>();
        List<String> missing = new java.util.ArrayList<>();
        tryPut(data, missing, "ratings", "FundamentalContext.getInstitutionRating", List.of("getInstitutionRating", "institutionRating"), normalized);
        tryPut(data, missing, "rating_details", "FundamentalContext.getInstitutionRatingDetail", List.of("getInstitutionRatingDetail", "institutionRatingDetail"), normalized);
        data.put("symbol", normalized);
        return new GatewayResult<>(data, java.time.Instant.now(), false, missing,
                Map.of("sdk_method", "FundamentalContext.getInstitutionRating*", "symbol", normalized));
    }

    public GatewayResult<Object> priceAlerts() {
        Object result = clientFactory.invokeFirst(clientFactory.alertContext(), List.of("getListAlerts", "listAlerts", "getPriceAlerts"));
        return GatewayResult.of(sdkObjectMapper.normalize(result), "AlertContext.getListAlerts", Map.of());
    }

    private void tryPut(Map<String, Object> data, List<String> missing, String key, String label, List<String> methodNames, String symbol) {
        try {
            Object result = clientFactory.invokeFirst(clientFactory.fundamentalContext(), methodNames, symbol);
            data.put(key, sdkObjectMapper.normalize(result));
        } catch (LongbridgeClientFactory.MissingLongbridgeCredentialsException ex) {
            throw ex;
        } catch (RuntimeException ex) {
            missing.add("missing_or_unsupported_field: " + label);
        }
    }

    private Map<String, Object> standardizeNews(Map<String, Object> raw) {
        Map<String, Object> news = new LinkedHashMap<>();
        putIfPresent(news, "title", first(raw, "title", "headline"));
        putIfPresent(news, "summary", first(raw, "summary", "description", "content"));
        putIfPresent(news, "source", first(raw, "source", "provider"));
        putIfPresent(news, "published_at", first(raw, "publishedAt", "published_at", "time"));
        putIfPresent(news, "url", first(raw, "url", "link"));
        news.put("raw", raw);
        return news;
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
}
