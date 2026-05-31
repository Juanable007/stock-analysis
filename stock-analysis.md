# Hermes Longbridge MCP: Java Spring Boot 实现计划

## Summary
在 `/Users/didi/Documents/code/work` 下新建 `hermes-longbridge-mcp`，实现一个 Mac mini 常驻运行的只读 MCP 服务。服务使用 Java/Spring Boot 技术栈，底层基于长桥 Java SDK/OpenAPI，向 Hermes 暴露规范化、原子化的股票事实工具；不做买卖决策、不输出交易建议、不暴露下单工具。

## Codex Goal
把下面整段直接给 Codex：

```text
在 /Users/didi/Documents/code/work 下新建并实现一个 Java Spring Boot 项目：hermes-longbridge-mcp。

目标：给我的自动化 agent Hermes 提供基于长桥 OpenAPI/Java SDK 的本地只读 MCP 服务。这个 MCP 是原子金融能力层，不做投资决策、不输出 buy/sell/hold、不下单；只返回规范化事实、指标、来源、时间戳、数据新鲜度、warnings 和 errors。Hermes 自己负责组合调用和决策。

技术栈：
1. Java 21。
2. Spring Boot 3.x。
3. Maven。
4. 使用长桥官方 Java SDK：io.github.longbridge:openapi-sdk。
5. 使用 Spring AI MCP Server 或官方 MCP Java SDK 实现 MCP server；优先选 Spring Boot 集成最自然、依赖最稳定的方式。
6. 服务默认监听 127.0.0.1:8765，MCP endpoint 默认为 /mcp。
7. 使用 SQLite + WAL 做本地轻量缓存和快照存储；可用 JDBC + HikariCP。
8. 使用 application.yml + 环境变量读取密钥：
   - LONGBRIDGE_APP_KEY
   - LONGBRIDGE_APP_SECRET
   - LONGBRIDGE_ACCESS_TOKEN
   - LONGBRIDGE_REGION
   不允许把任何真实 token/key 写进仓库。
9. 生成 launchd plist 模板，方便部署到 Mac mini 24 小时运行。
10. 生成 README.md，包含安装、配置、启动、Hermes MCP 配置示例、故障排查。
11. 生成 docs/HERMES_PE.md，作为 Hermes 的 Prompt Engineering contract。

项目结构：
- pom.xml
- README.md
- .env.example
- src/main/java/com/hermes/longbridge/mcp/
- src/main/resources/application.yml
- src/test/java/com/hermes/longbridge/mcp/
- docs/HERMES_PE.md
- deploy/com.hermes.longbridge-mcp.plist.example

核心模块：
1. config
   - LongbridgeProperties：读取长桥 appKey/appSecret/accessToken/region。
   - McpServerConfig：注册 MCP tools。
   - SqliteConfig：配置 SQLite、WAL、连接池。
2. longbridge
   - LongbridgeClientFactory：创建 QuoteContext、TradeContext 等只读 client。
   - LongbridgeQuoteGateway：封装行情、订阅、K 线、资金流。
   - LongbridgeAccountGateway：封装账户资产、持仓，只读。
   - LongbridgeContentGateway：封装新闻、评级、基本面等能力。
3. universe
   - UniverseService：管理 Hermes 关注标的，来源包括 position/watchlist/manual。
4. cache
   - QuoteCacheService：维护最新行情缓存。
   - SnapshotRepository：SQLite 存储持仓快照、行情快照、工具调用元信息。
5. tools
   - AccountTools
   - QuoteTools
   - UniverseTools
   - ContentTools
   - ContractTools
6. common
   - ToolResponse<T>：所有 MCP 工具统一返回结构。
   - SymbolNormalizer：统一 symbol 格式。
   - ErrorMapper：把长桥 SDK 错误转换为 warnings/errors。

统一返回协议：
所有 MCP tool 返回 JSON object，顶层字段必须包含：
- ok: boolean
- data: object | array | null
- source: "longbridge" | "local_cache" | "computed"
- as_of: ISO8601 UTC timestamp | null
- is_realtime: boolean
- cache_age_ms: number | null
- warnings: string[]
- errors: string[]
- raw_refs: object，只允许放 sdk method、request id、symbol、market，不允许放 token/key

MCP 工具：
1. health_check()
   返回服务版本、长桥配置是否存在、SDK 初始化状态、SQLite 状态、订阅状态、最近数据时间。
2. get_account_assets()
   只读返回账户资产摘要。
3. list_stock_positions()
   返回股票持仓，统一字段包括 symbol、name、market、quantity、cost、market_value、unrealized_pnl、currency、as_of。
4. get_watchlist()
   返回长桥 watchlist；如果 Java SDK 暂不支持，返回本地 watchlist，并在 warnings 说明。
5. set_universe(symbols, mode)
   管理本地 universe，mode 支持 replace/merge/remove。
6. get_universe()
   返回当前 Hermes 关注标的，来源区分 position/watchlist/manual。
7. get_realtime_quote(symbol)
   返回单个标的实时行情。
8. get_realtime_quote_batch(symbols)
   批量实时行情，每次最多 100 个，超过返回参数错误。
9. subscribe_quotes(symbols)
   启动或更新本地行情订阅；遵守长桥每账号最多 500 个订阅标的限制。
10. get_latest_quotes(symbols?)
   从本地缓存读取最新行情，适合 Hermes 高频调用。
11. get_candles(symbol, period, count)
   返回 K 线；period 支持 1m/5m/15m/30m/60m/day/week/month。
12. get_capital_flow(symbol)
   返回资金流事实数据。
13. get_capital_distribution(symbol)
   返回资金分布事实数据。
14. get_symbol_news(symbol, limit, since?)
   返回新闻 title、summary、source、published_at、url。
15. get_fundamentals_summary(symbol)
   返回估值/财务摘要；字段缺失时明确 warnings。
16. get_analyst_ratings(symbol)
   返回评级、目标价、机构、日期等事实数据。
17. get_market_calendar(market, date?)
   返回交易日、开闭市、盘前盘后状态。
18. get_price_alerts()
   只读返回长桥已有价格提醒；如果 Java SDK 暂不支持，返回 unsupported warning。
19. explain_data_contract(tool_name?)
   返回工具返回结构、字段含义、Hermes 调用原则。

决策边界：
- MCP 永远不返回 buy/sell/hold。
- MCP 永远不返回 target action。
- MCP 不实现 submit_order、replace_order、cancel_order。
- MCP 可以返回事实型异常标签，例如 price_gap、volume_spike、stale_data、missing_permission。
- Hermes 必须基于工具事实自行推理。

docs/HERMES_PE.md 必须包含：
1. Hermes 使用该 MCP 的 system prompt。
2. 工具调用顺序：先 health_check，再 universe/positions，再 quote/candles/news/fundamental。
3. 证据要求：任何结论都必须引用工具名、symbol、as_of、关键字段。
4. 数据新鲜度规则：实时行情超过 10 秒视为可能过期。
5. 禁止项：不得把 MCP 输出当作投资建议；不得伪造缺失数据；不得在缺权限时猜测。
6. 示例工作流：开盘前检查持仓、盘中异常波动排查、单股深挖、收盘复盘。

测试要求：
1. 使用 JUnit 5 + Mockito。
2. 单元测试覆盖 SymbolNormalizer、ToolResponse、缓存 TTL、参数校验。
3. 用 fake Longbridge gateway 测试 MCP tools，不依赖真实 token。
4. health_check 在无 token 时也必须可运行并返回清晰错误。
5. mvn test 必须通过。
6. README 给出本地启动命令和 Hermes MCP 配置片段。

实现前请查阅官方长桥文档和 Java SDK 文档，尤其是 SDK、Getting Started、Quote Subscribe、QuoteContext。不要读取我的 Chrome token 页面。完成后运行 mvn test，并给出启动方式。
```

## Test Plan
- `mvn test` 全通过。
- 无 token 时服务可启动，`health_check` 返回配置缺失而不是崩溃。
- fake gateway 验证所有工具返回统一 `ToolResponse`。
- 配好环境变量后，真实验证 `health_check`、`get_realtime_quote`、`list_stock_positions`。
- 检查 MCP tool list 不包含任何交易执行工具。

## Assumptions
- v1 采用 Java Spring Boot，不用 Python。
- v1 只读，不做下单。
- v1 MCP 做事实能力封装，Hermes 负责决策。
- 底层优先使用长桥 Java SDK；SDK 缺口才用长桥 REST/OpenAPI 补齐，并在 README 标注。




LONGBRIDGE_APP_KEY=aa525b2b9fbbb919eaab0bc7319c0339
LONGBRIDGE_APP_SECRET=9d233a3c6d2b4c84f1550d82b133be6b52d83a9dba090c8d3e305166e2db59d6
LONGBRIDGE_ACCESS_TOKEN=m_eyJhbGciOiJSUzI1NiIsImtpZCI6ImQ5YWRiMGIxYTdlNzYxNzEiLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJsb25nYnJpZGdlIiwic3ViIjoiYWNjZXNzX3Rva2VuIiwiZXhwIjoxNzg3OTA0MTEyLCJpYXQiOjE3ODAxMjgxMTcsImFrIjoiYWE1MjViMmI5ZmJiYjkxOWVhYWIwYmM3MzE5YzAzMzkiLCJhYWlkIjoyMTI5MTcwNiwiYWMiOiJsYl9wYXBlcnRyYWRpbmciLCJtaWQiOjE1MTU2MTk0LCJzaWQiOiJ6azFSSytmcUo4TDFtODVQbmp1eUNBPT0iLCJibCI6MywidWwiOjAsImlrIjoibGJfcGFwZXJ0cmFkaW5nXzIxMjkxNzA2In0.qKsMCvrROpXShVKO9R6fkGWTbHtbg5Qm6_pylmv0DusBzW2Sql6l4niiUGgUPgVdyrNbKZ4iob6mxjUzOgVuQkFErc158q53diDKuWNzzQQFWTYttAb0vRCtd7IRxCfE9MXuTLvdRhe0GI_4HSVOx6lzsrKN-rPcK3fOgFbo-HknO3A6liUP8FemzhOgOMweQOvVFy5cuP9yCSHGDKo9YmkpxANs4N9dyliWrB-JnLuYZfZWW9NQ1cLB6rHLCrK6rmrA8imbG0WyUx2lkv7QZCI_hNJq8ZxljzR-LsLKv6cubsXe2iJikgqm4nG_t3EpTtb3WYKuk9HW0h1ZKV6f2jYq36E5mIMCTo0dBl2y9BkPSkWQHZfSwN5Zp40ToUOypPGJdjCPNU9nESflS-zcEwG-SEHiXa8BpGAgMA4foDkKj_oPtmCw_Vwymee-fPzQpQARKs0j1eFadwL2dhlBlDyjLgxfaDj97qRAqpg-lpsScD6HwevRYhbEJ5y2Ok_MmrrsUHxSFkzbC6Zt__qOlKEBU4lUI5IEQT7OB2W5HF1r3gYoSle3zrQzcGZUtJZ6wdgwghvY4Gd8qaAC4W8ozTSfSZzPkscqbAzsuoaoihAxsSZTBcDTH_UR26-LaRgmV86cuZzgU862BZchB8WX9Ah8gGljuJZikAr8W9rT_KI

App Key


<redacted: set LONGBRIDGE_APP_KEY in environment>
App Secret


<redacted: set LONGBRIDGE_APP_SECRET in environment>
Access Token


This token grants full access to all authorized OpenAPI services. Keep it secure and never expose it publicly.

<redacted: set LONGBRIDGE_ACCESS_TOKEN in environment>
Expiration date: 2026/8/28
