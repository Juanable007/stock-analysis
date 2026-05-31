package com.hermes.longbridge.mcp.longbridge;

import com.hermes.longbridge.mcp.config.LongbridgeProperties;
import org.springframework.stereotype.Component;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.time.Duration;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.TimeUnit;

@Component
public class LongbridgeClientFactory {

    private static final Duration SDK_TIMEOUT = Duration.ofSeconds(20);

    private final LongbridgeProperties properties;
    private final Map<String, Object> contexts = new ConcurrentHashMap<>();
    private volatile Object config;

    public LongbridgeClientFactory(LongbridgeProperties properties) {
        this.properties = properties;
    }

    public boolean credentialsPresent() {
        return properties.credentialsPresent();
    }

    public boolean sdkAvailable() {
        try {
            Class.forName("com.longbridge.Config");
            return true;
        } catch (ClassNotFoundException ex) {
            return false;
        }
    }

    public Object quoteContext() {
        return context("com.longbridge.quote.QuoteContext");
    }

    public Object tradeContext() {
        return context("com.longbridge.trade.TradeContext");
    }

    public Object contentContext() {
        return context("com.longbridge.content.ContentContext");
    }

    public Object fundamentalContext() {
        return context("com.longbridge.fundamental.FundamentalContext");
    }

    public Object alertContext() {
        return context("com.longbridge.alert.AlertContext");
    }

    Object context(String className) {
        requireCredentials();
        return contexts.computeIfAbsent(className, this::createContext);
    }

    Object invoke(Object target, String methodName, Class<?>[] parameterTypes, Object... args) {
        try {
            Method method = target.getClass().getMethod(methodName, parameterTypes);
            Object result = method.invoke(target, args);
            return awaitIfFuture(result);
        } catch (InvocationTargetException ex) {
            throw new LongbridgeSdkException(ex.getTargetException());
        } catch (ReflectiveOperationException ex) {
            throw new LongbridgeSdkException(ex);
        }
    }

    Object invokeFirst(Object target, List<String> methodNames, Object... args) {
        LongbridgeSdkException last = null;
        for (String methodName : methodNames) {
            for (Method method : target.getClass().getMethods()) {
                if (!method.getName().equals(methodName) || method.getParameterCount() != args.length) {
                    continue;
                }
                try {
                    Object result = method.invoke(target, args);
                    return awaitIfFuture(result);
                } catch (IllegalArgumentException ex) {
                    last = new LongbridgeSdkException(ex);
                } catch (InvocationTargetException ex) {
                    throw new LongbridgeSdkException(ex.getTargetException());
                } catch (ReflectiveOperationException ex) {
                    last = new LongbridgeSdkException(ex);
                }
            }
        }
        if (last != null) {
            throw last;
        }
        throw new LongbridgeSdkException("no matching SDK method found: " + methodNames);
    }

    Object enumConstant(String className, String... names) {
        try {
            Class<?> type = Class.forName(className);
            for (String name : names) {
                try {
                    return Enum.valueOf((Class<Enum>) type.asSubclass(Enum.class), name);
                } catch (IllegalArgumentException ignored) {
                    // Try Longbridge's generated constant style below.
                }
                try {
                    return type.getField(name).get(null);
                } catch (ReflectiveOperationException ignored) {
                    // Try next spelling.
                }
            }
            throw new LongbridgeSdkException("missing enum constant " + Arrays.toString(names) + " in " + className);
        } catch (ClassNotFoundException ex) {
            throw new LongbridgeSdkException(ex);
        }
    }

    int intConstant(String className, String name, int fallback) {
        try {
            return Class.forName(className).getField(name).getInt(null);
        } catch (ReflectiveOperationException ex) {
            return fallback;
        }
    }

    Class<?> optionalClass(String className) {
        try {
            return Class.forName(className);
        } catch (ClassNotFoundException ex) {
            throw new LongbridgeSdkException(ex);
        }
    }

    private synchronized Object config() {
        if (config != null) {
            return config;
        }
        requireCredentials();
        try {
            Class<?> configClass = Class.forName("com.longbridge.Config");
            config = createConfig(configClass);
            return config;
        } catch (ReflectiveOperationException ex) {
            throw new LongbridgeSdkException(ex);
        }
    }

    private Object createConfig(Class<?> configClass) throws ReflectiveOperationException {
        List<String> factoryNames = List.of("fromApikey", "fromApiKey", "fromAccessToken");
        Object[] values = new Object[]{
                properties.appKey(),
                properties.appSecret(),
                properties.accessToken(),
                properties.region()
        };

        for (String factoryName : factoryNames) {
            for (Method method : configClass.getMethods()) {
                if (!Modifier.isStatic(method.getModifiers()) || !method.getName().equals(factoryName)) {
                    continue;
                }
                if (method.getParameterCount() < 3 || method.getParameterCount() > 4) {
                    continue;
                }
                Object[] args = Arrays.copyOf(values, method.getParameterCount());
                try {
                    return awaitIfFuture(method.invoke(null, args));
                } catch (InvocationTargetException ex) {
                    throw new LongbridgeSdkException(ex.getTargetException());
                }
            }
        }
        for (String factoryName : List.of("fromApikeyEnv", "fromEnv", "fromEnvironment")) {
            for (Method method : configClass.getMethods()) {
                if (Modifier.isStatic(method.getModifiers()) && method.getName().equals(factoryName) && method.getParameterCount() == 0) {
                    try {
                        return awaitIfFuture(method.invoke(null));
                    } catch (InvocationTargetException ex) {
                        throw new LongbridgeSdkException(ex.getTargetException());
                    }
                }
            }
        }
        throw new LongbridgeSdkException("Longbridge Config factory method not found");
    }

    private Object createContext(String className) {
        try {
            Class<?> contextClass = Class.forName(className);
            Object configValue = config();
            Method create = contextClass.getMethod("create", configValue.getClass());
            return awaitIfFuture(create.invoke(null, configValue));
        } catch (InvocationTargetException ex) {
            throw new LongbridgeSdkException(ex.getTargetException());
        } catch (ReflectiveOperationException ex) {
            throw new LongbridgeSdkException(ex);
        }
    }

    private static Object awaitIfFuture(Object value) {
        if (value instanceof CompletableFuture<?> future) {
            try {
                return future.get(SDK_TIMEOUT.toMillis(), TimeUnit.MILLISECONDS);
            } catch (Exception ex) {
                throw new LongbridgeSdkException(ex);
            }
        }
        return value;
    }

    private void requireCredentials() {
        if (!properties.credentialsPresent()) {
            throw new MissingLongbridgeCredentialsException();
        }
    }

    public static class MissingLongbridgeCredentialsException extends RuntimeException {
        public MissingLongbridgeCredentialsException() {
            super("missing_longbridge_credentials");
        }
    }

    public static class LongbridgeSdkException extends RuntimeException {
        public LongbridgeSdkException(String message) {
            super(message);
        }

        public LongbridgeSdkException(Throwable cause) {
            super(cause);
        }
    }
}
