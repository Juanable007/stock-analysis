package com.hermes.longbridge.mcp.common;

import java.util.List;
import java.util.regex.Pattern;

public final class ErrorMapper {

    private static final Pattern TOKEN_PATTERN = Pattern.compile("m_[A-Za-z0-9._-]+");
    private static final Pattern LONG_HEX_PATTERN = Pattern.compile("\\b[a-fA-F0-9]{32,}\\b");

    private ErrorMapper() {
    }

    public static List<String> missingCredentials() {
        return List.of("missing_longbridge_credentials: set LONGBRIDGE_APP_KEY, LONGBRIDGE_APP_SECRET, and LONGBRIDGE_ACCESS_TOKEN");
    }

    public static String sdkError(Throwable throwable) {
        String message = throwable == null ? "unknown_longbridge_sdk_error" : throwable.getMessage();
        if (message == null || message.isBlank()) {
            message = throwable.getClass().getSimpleName();
        }
        return "longbridge_sdk_error: " + redactSecrets(message);
    }

    public static String redactSecrets(String text) {
        if (text == null) {
            return "";
        }
        String redacted = TOKEN_PATTERN.matcher(text).replaceAll("[redacted_token]");
        return LONG_HEX_PATTERN.matcher(redacted).replaceAll("[redacted_hex]");
    }
}
