package com.hermes.longbridge.mcp;

import com.hermes.longbridge.mcp.config.LongbridgeProperties;
import com.hermes.longbridge.mcp.config.QuoteCacheProperties;
import com.hermes.longbridge.mcp.config.SqliteProperties;
import com.hermes.longbridge.mcp.config.WhopKnowledgeProperties;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableScheduling
@EnableConfigurationProperties({
        LongbridgeProperties.class,
        SqliteProperties.class,
        QuoteCacheProperties.class,
        WhopKnowledgeProperties.class
})
public class HermesLongbridgeMcpApplication {

    public static void main(String[] args) {
        SpringApplication.run(HermesLongbridgeMcpApplication.class, args);
    }
}
