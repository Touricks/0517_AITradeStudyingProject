.env 在AITrading/config/中。对于任何敏感凭证请调用.env

## AITrading MarketDataProvider

- 股票信息服务位于 `AITrading/src/MarketDataProvider/`，README 是 Agent 调用指南。
- demo 数据源使用无 API key 的公开源；优先调用 `from src.MarketDataProvider import create_demo_provider`，再使用 `provider.build_stock_context("300059")` 或 `get_quote/get_kline/get_announcements/get_news/get_company_profile/search_reports`。
- 前端 K 线图和股票上下文面板必须走后端 `GET /api/market/kline?symbol=300059&market=A&limit=120`，由 Provider 归一化字段；不要让前端默认直连第三方行情 URL。
- 不要在训练、复盘、评估业务代码里直接拼第三方股票数据 URL；新增源时先更新 `registry.py`、`public_fetchers.py` 和 `MarketDataProvider/README.md`。
- Provider 输出只作为交易能力训练背景，不能生成“买入/卖出/持有/加仓”等投资建议。

## AITrading memory reset

- 新用户或干净状态测试前，可使用 `AITrading/scripts/clear_memory.py` 清空后端 JSON memory。
- 默认是 dry-run，不会改文件：`python3 AITrading/scripts/clear_memory.py`
- 清空全部 memory：`python3 AITrading/scripts/clear_memory.py --yes`
- 只清某个用户：`python3 AITrading/scripts/clear_memory.py --user-id u_001 --yes`
- 脚本默认会在写入前创建 `AITrading/data/memory_store.json.<timestamp>.bak` 备份；只有明确需要时才加 `--no-backup`。

前端启动时应总是使用npm run dev