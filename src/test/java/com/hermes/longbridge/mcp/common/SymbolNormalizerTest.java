package com.hermes.longbridge.mcp.common;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class SymbolNormalizerTest {

    @Test
    void normalizesUsSymbols() {
        assertThat(SymbolNormalizer.normalize("aapl")).isEqualTo("AAPL.US");
        assertThat(SymbolNormalizer.normalize("brk.b.us")).isEqualTo("BRK.B.US");
    }

    @Test
    void normalizesUsOptionSymbols() {
        assertThat(SymbolNormalizer.normalize("TSLA270115C450000.US"))
                .isEqualTo("TSLA270115C450000.US");
        assertThat(SymbolNormalizer.normalize("tsla270115p450000"))
                .isEqualTo("TSLA270115P450000.US");
    }

    @Test
    void normalizesHongKongSymbols() {
        assertThat(SymbolNormalizer.normalize("00700.HK")).isEqualTo("700.HK");
        assertThat(SymbolNormalizer.normalize("hk00700")).isEqualTo("700.HK");
    }

    @Test
    void normalizesChinaSymbols() {
        assertThat(SymbolNormalizer.normalize("600519")).isEqualTo("600519.SH");
        assertThat(SymbolNormalizer.normalize("000001")).isEqualTo("000001.SZ");
        assertThat(SymbolNormalizer.normalize("000001.SZ")).isEqualTo("000001.SZ");
    }

    @Test
    void rejectsUnsupportedSymbols() {
        assertThatThrownBy(() -> SymbolNormalizer.normalize(""))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> SymbolNormalizer.normalize("ABC.LN"))
                .isInstanceOf(IllegalArgumentException.class);
    }
}
