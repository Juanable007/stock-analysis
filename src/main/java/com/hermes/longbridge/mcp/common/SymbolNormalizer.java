package com.hermes.longbridge.mcp.common;

import java.util.Locale;
import java.util.Objects;
import java.util.regex.Pattern;

public final class SymbolNormalizer {

    private static final Pattern HK_NUMERIC = Pattern.compile("^0*\\d{1,5}$");
    private static final Pattern CN_NUMERIC = Pattern.compile("^\\d{6}$");
    private static final Pattern US_TICKER = Pattern.compile("^[A-Z][A-Z0-9.-]{0,14}$");
    private static final Pattern US_OPTION = Pattern.compile("^[A-Z][A-Z0-9.-]{0,14}\\d{6}[CP]\\d{6,9}$");

    private SymbolNormalizer() {
    }

    public static String normalize(String rawSymbol) {
        if (rawSymbol == null || rawSymbol.isBlank()) {
            throw new IllegalArgumentException("symbol must not be blank");
        }

        String value = rawSymbol.trim().toUpperCase(Locale.ROOT).replace('_', '.');
        String[] parts = value.split("\\.");
        if (parts.length >= 2) {
            String market = parts[parts.length - 1];
            String symbol = String.join(".", java.util.Arrays.copyOf(parts, parts.length - 1));
            return normalizeMarketQualified(symbol, market);
        }

        if (value.startsWith("HK")) {
            return normalizeMarketQualified(value.substring(2), "HK");
        }
        if (value.startsWith("SH")) {
            return normalizeMarketQualified(value.substring(2), "SH");
        }
        if (value.startsWith("SZ")) {
            return normalizeMarketQualified(value.substring(2), "SZ");
        }

        if (CN_NUMERIC.matcher(value).matches()) {
            if (value.startsWith("6")) {
                return value + ".SH";
            }
            if (value.startsWith("0") || value.startsWith("3")) {
                return value + ".SZ";
            }
        }
        if (HK_NUMERIC.matcher(value).matches()) {
            return stripLeadingZeros(value) + ".HK";
        }
        if (US_TICKER.matcher(value).matches() || US_OPTION.matcher(value).matches()) {
            return value + ".US";
        }

        throw new IllegalArgumentException("unsupported symbol format: " + rawSymbol);
    }

    private static String normalizeMarketQualified(String left, String right) {
        String market = normalizeMarket(right);
        String symbol = Objects.requireNonNull(left, "symbol").trim().toUpperCase(Locale.ROOT);

        if ("HK".equals(market)) {
            if (!HK_NUMERIC.matcher(symbol).matches()) {
                throw new IllegalArgumentException("HK symbol must be numeric: " + left + "." + right);
            }
            return stripLeadingZeros(symbol) + ".HK";
        }
        if ("SH".equals(market) || "SZ".equals(market)) {
            if (!CN_NUMERIC.matcher(symbol).matches()) {
                throw new IllegalArgumentException("CN symbol must be 6 digits: " + left + "." + right);
            }
            return symbol + "." + market;
        }
        if ("US".equals(market)) {
            if (!US_TICKER.matcher(symbol).matches() && !US_OPTION.matcher(symbol).matches()) {
                throw new IllegalArgumentException("US symbol is invalid: " + left + "." + right);
            }
            return symbol + ".US";
        }
        throw new IllegalArgumentException("unsupported market: " + right);
    }

    private static String normalizeMarket(String rawMarket) {
        return switch (rawMarket.trim().toUpperCase(Locale.ROOT)) {
            case "US", "NYSE", "NASDAQ", "AMEX" -> "US";
            case "HK", "HKG" -> "HK";
            case "SH", "SSE", "SHSE" -> "SH";
            case "SZ", "SZSE" -> "SZ";
            default -> throw new IllegalArgumentException("unsupported market: " + rawMarket);
        };
    }

    private static String stripLeadingZeros(String value) {
        String stripped = value.replaceFirst("^0+(?!$)", "");
        return stripped.isBlank() ? "0" : stripped;
    }
}
