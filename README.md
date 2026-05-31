# Hermes Longbridge MCP

Local read-only MCP service for Hermes. It exposes normalized Longbridge facts through atomic tools and intentionally does not make investment decisions, return buy/sell/hold labels, or expose order execution tools.

## What This Service Does

- Runs as a Java 21 / Spring Boot 3.x service on `127.0.0.1:8765`.
- Exposes MCP at `/mcp` through Spring AI MCP Server WebMVC.
- Uses the official Longbridge Java SDK dependency `io.github.longbridge:openapi-sdk`.
- Stores local quote cache, universe, snapshots, and tool-call metadata in SQLite with WAL.
- Reads all Longbridge credentials from environment variables only.

## Realtime Alert Engine Design

The MCP server is the read-only facts layer. The higher-level alert system should live above it and combine Longbridge facts with the Whop `xiaozhaolucky` knowledge base.

See [Hermes Real-Time Alert Engine Design](docs/HERMES_REALTIME_ALERT_ENGINE_DESIGN.md) for the proposed architecture covering real-time alerts, market-turn detection, entry/exit zones, quant-flow capture, holidays/news, and special-stock playbooks for symbols such as `TSLL`, `NVDL`, `MSFT/MSFL`, and `CONL`.

## Whop Knowledge MCP

The same MCP endpoint also exposes the local Whop `xiaozhaolucky` knowledge base built from `data/whop_archive`. These tools use the existing canonical messages, channel map, ticker index, theory notes, calendar notes, and image-meaning files. Source files are hot-reloaded when they change, so newly rebuilt knowledge is available without restarting the MCP service.

For continuous iteration, configure a capture command that uses the already logged-in Whop/Chrome session, then enable MCP refresh or scheduled refresh. If no capture command is configured, refresh still rebuilds the derived knowledge from the local archive.

Official references used during implementation:

- [Longbridge Java SDK overview](https://longbridge.github.io/openapi/java/)
- [Longbridge `Config`](https://longbridge.github.io/openapi/java/com/longbridge/Config.html)
- [Longbridge `QuoteContext`](https://longbridge.github.io/openapi/java/com/longbridge/quote/QuoteContext.html)
- [Longbridge `TradeContext`](https://longbridge.github.io/openapi/java/com/longbridge/trade/TradeContext.html)
- [Spring AI MCP Server Boot Starter](https://docs.spring.io/spring-ai/reference/api/mcp/mcp-server-boot-starter-docs.html)
- [Spring AI Streamable HTTP Server](https://docs.spring.io/spring-ai/reference/api/mcp/mcp-streamable-http-server-boot-starter-docs.html)

## Tools

The MCP exposes only read-only/factual tools:

- `health_check`
- `get_account_assets`
- `list_stock_positions`
- `get_watchlist`
- `set_universe`
- `get_universe`
- `get_realtime_quote`
- `get_realtime_quote_batch`
- `subscribe_quotes`
- `get_latest_quotes`
- `get_candles`
- `get_capital_flow`
- `get_capital_distribution`
- `get_symbol_news`
- `get_fundamentals_summary`
- `get_analyst_ratings`
- `get_market_calendar`
- `get_price_alerts`
- `explain_data_contract`
- `get_whop_knowledge_status`
- `get_whop_channel_map`
- `search_whop_knowledge`
- `get_whop_symbol_playbook`
- `refresh_whop_knowledge`
- `get_whop_refresh_status`

There are no `submit_order`, `replace_order`, or `cancel_order` tools.

## Response Contract

Every tool returns a JSON object with these top-level fields:

```json
{
  "ok": true,
  "data": {},
  "source": "longbridge",
  "as_of": "2026-05-31T00:00:00Z",
  "is_realtime": false,
  "cache_age_ms": null,
  "warnings": [],
  "errors": [],
  "raw_refs": {
    "sdk_method": "QuoteContext.getRealtimeQuote",
    "symbol": "AAPL.US"
  }
}
```

`raw_refs` must never include tokens, app keys, app secrets, or account credentials.

## Configuration

Copy `.env.example` and set the real values in your shell, launch agent, or secret manager. Do not commit real credentials.

```bash
export LONGBRIDGE_APP_KEY="..."
export LONGBRIDGE_APP_SECRET="..."
export LONGBRIDGE_ACCESS_TOKEN="..."
export LONGBRIDGE_REGION="hk"
```

Optional overrides:

```bash
export SERVER_PORT=8765
export HERMES_LONGBRIDGE_DB=./data/hermes-longbridge-mcp.sqlite
export HERMES_WHOP_ARCHIVE_DIR=./data/whop_archive
export HERMES_WHOP_REBUILD_COMMAND="python3 tools/build_whop_knowledge.py"
export HERMES_WHOP_CAPTURE_COMMAND="tools/refresh_whop_knowledge_incremental.sh"
```

To let the MCP service pull fresh Whop data before rebuilding knowledge, set a command that writes new captures into `data/whop_archive/raw_captures`, imports them into `data/whop_archive/parsed`, and then lets `refresh_whop_knowledge` run the rebuild command. Keep this command local because it depends on your authenticated Chrome session.

```bash
export HERMES_WHOP_AUTO_REFRESH_ENABLED=true
export HERMES_WHOP_AUTO_REFRESH_RUN_CAPTURE=true
export HERMES_WHOP_AUTO_REFRESH_INTERVAL_MS=300000
```

The included incremental capture command covers the priority channels: 市值理论, 不用翻墙美股发布, 不用翻墙期权, 历史股票期权记录区, and 不用翻墙美股讨论区. It finds an already-open Whop tab in Chrome, uses that authenticated browser session to call Whop GraphQL, imports captures, updates image metadata, and rebuilds the knowledge files.

When auto-refresh is enabled, the MCP service runs this capture/rebuild task on the configured interval, prevents overlapping refreshes, writes the latest run status to `data/whop_archive/knowledge/refresh_status.json`, and reports `net_new_messages` / `new_xiaozhaolucky_messages` through `get_whop_knowledge_status` and `get_whop_refresh_status`.

Command shape:

```bash
tools/refresh_whop_knowledge_incremental.sh
```

## Build And Run

Use Java 21 and Maven.

```bash
mvn test
mvn spring-boot:run
```

Build a runnable jar:

```bash
mvn package
java -jar target/hermes-longbridge-mcp-0.1.0.jar
```

Service endpoint:

```text
http://127.0.0.1:8765/mcp
```

`health_check` works without Longbridge credentials and reports missing configuration instead of crashing.

## Hermes MCP Config Example

```json
{
  "mcpServers": {
    "longbridge": {
      "type": "streamable-http",
      "url": "http://127.0.0.1:8765/mcp"
    }
  }
}
```

If your Hermes runtime expects command-launched servers instead of Streamable HTTP, keep this service running with launchd and point Hermes at the local HTTP URL.

## Mac mini launchd

Use `deploy/com.hermes.longbridge-mcp.plist.example` as a template.

```bash
mvn package
cp deploy/com.hermes.longbridge-mcp.plist.example ~/Library/LaunchAgents/com.hermes.longbridge-mcp.plist
launchctl load ~/Library/LaunchAgents/com.hermes.longbridge-mcp.plist
launchctl start com.hermes.longbridge-mcp
```

Before loading, replace the placeholder environment variables and confirm the jar path matches this project.

## Troubleshooting

- `health_check` shows missing credentials: export `LONGBRIDGE_APP_KEY`, `LONGBRIDGE_APP_SECRET`, and `LONGBRIDGE_ACCESS_TOKEN`.
- SQLite errors: ensure the directory in `HERMES_LONGBRIDGE_DB` is writable.
- Stale quotes: call `subscribe_quotes` or `get_realtime_quote_batch`, then use `get_latest_quotes` for high-frequency local reads.
- Unsupported Longbridge SDK method: the tool returns a warning/error rather than guessing missing data.
- Maven cannot find Java: install JDK 21 and set `JAVA_HOME` to the JDK directory.

## Real-credential Smoke Test

After credentials are set and the service starts:

1. Call `health_check` and verify `credentials_present=true`, `sqlite_healthy=true`, and `sdk_available=true`.
2. Call `get_realtime_quote` with a symbol such as `AAPL.US` or `700.HK`.
3. Call `list_stock_positions` to verify read-only account access.
4. Call `explain_data_contract` and confirm Hermes understands the evidence and freshness rules.
