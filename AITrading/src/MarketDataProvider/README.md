# MarketDataProvider

`MarketDataProvider` 是 AITrading 的股票信息提供商服务层。Agent 需要股票背景时，优先调用这个包，不要在业务代码里直接拼第三方 URL。

当前 demo 目标是稳定拿到训练背景，不考虑限流，不依赖股票数据 API key。所有数据只能用于交易能力训练、计划检查、复盘背景，不得生成“买入/卖出/持有”等投资建议。

## Agent 标准入口

在 `AITrading` 目录或设置 `PYTHONPATH=/Users/carrick/Hackerson/AITrading` 后使用：

```python
from src.MarketDataProvider import create_demo_provider

provider = create_demo_provider()

quote = provider.get_quote("300059")
klines = provider.get_kline("300059")
announcements = provider.get_announcements("300059", limit=5)
news = provider.get_news("东方财富 300059 股票 新闻", limit=5)
profile = provider.get_company_profile("300059")
reports = provider.search_reports("300059 东方财富 研报 资讯 风险", limit=3)

context = provider.build_stock_context("300059")
```

推荐优先使用 `build_stock_context(symbol)`。它会统一收集：

- `quote`: 现价、涨跌幅、成交额、换手、振幅等。
- `kline`: 日 K 原始列表。
- `technical`: 近 3/5/20 日涨幅、20 日波动率、连续上涨天数、均线距离、近 20 日高低点距离。
- `announcements`: 近期公告。
- `news`: 新闻/事件搜索结果。
- `company_profile`: 公司基本资料、行业、主营/经营范围。
- `reports`: 公开研报背景。

返回值里的每个数据块都遵循同一形状：

```json
{
  "ok": true,
  "source": "eastmoney_push2",
  "fallback": false,
  "data": {},
  "errors": [],
  "metadata": {"attempted": ["eastmoney_push2"]}
}
```

业务逻辑必须先检查 `ok`。`ok=false` 只表示数据缺口，不能推导成股票强弱信号。

## 前端 K 线 API

训练页 K 线图不要直连东方财富或其他第三方源。前端应通过后端只读接口获取绘图数据：

```text
GET /api/market/kline?symbol=300059&market=A&limit=120
```

该接口由 `backend/app/market.py` 调用 `create_demo_provider()` 的 `get_quote()` 和 `get_kline()`，返回前端专用结构：

- `available`: 是否有可绘图 K 线。
- `quote`: 图表头部需要的行情字段。
- `kline`: 仅包含 `date/open/close/high/low/volume/amount/change_pct/turnover_rate`。
- `technical`: 近 3/5/20 日涨幅和 20 日波动摘要。
- `errors`: 数据源失败或 symbol 非法时的错误说明。
- `compliance_note`: 行情只作为训练背景，不是交易建议。

即使数据源不可用或 symbol 非法，后端也返回 HTTP 200，并设置 `available=false`，避免训练页面和训练提交流程崩溃。第三方 request URL 不会透传给前端。直连第三方接口只允许作为本地调试手段，不作为产品默认路径。

## Demo 数据源

| Provider source id | 能力 | URL | 鉴权 |
| --- | --- | --- | --- |
| `eastmoney_report` | `research` | `https://reportapi.eastmoney.com/report/list` | 无 API key |
| `eastmoney_push2` | `quote` | `https://push2.eastmoney.com/api/qt/stock/get` | 无 API key |
| `eastmoney_push2` | `kline` | `http://push2his.eastmoney.com/api/qt/stock/kline/get` | 无 API key |
| `tencent_fqkline` | `kline` fallback | `https://web.ifzq.gtimg.cn/appstock/app/fqkline/get` | 无 API key |
| `eastmoney_announcements` | `announcements` | `https://np-anotice-stock.eastmoney.com/api/security/ann` | 无 API key |
| `eastmoney_profile` | `company_profile` | `https://emweb.securities.eastmoney.com/PC_HSF10/CompanySurvey/PageAjax` | 无 API key |
| `duckduckgo` | `news` | `https://duckduckgo.com/html/` | 无 API key |

`registry.py` 仍保留 `cninfo`、`akshare`、`sina_quote`、`tencent_qt`、`xueqiu` 等候选源。demo factory 只注册当前已经实现的无 key fetcher。

## 环境变量

敏感凭证统一放在 `AITrading/config/.env`。当前 demo 股票数据源不需要 API key，只支持这些 base URL 覆盖项，主要用于测试或 mock：

```text
EASTMONEY_REPORT_BASE_URL=https://reportapi.eastmoney.com
EASTMONEY_PUSH2_BASE_URL=https://push2.eastmoney.com
EASTMONEY_PUSH2HIS_BASE_URL=http://push2his.eastmoney.com
TENCENT_KLINE_BASE_URL=https://web.ifzq.gtimg.cn
EASTMONEY_ANNOUNCEMENT_BASE_URL=https://np-anotice-stock.eastmoney.com
EASTMONEY_HSF10_BASE_URL=https://emweb.securities.eastmoney.com
DUCKDUCKGO_SEARCH_BASE_URL=https://duckduckgo.com
```

不要把 `OPENAI_API_KEY` 当作股票数据源密钥。它只属于 LLM 客户端。

## 股票代码规则

Provider 当前面向 A 股 demo。输入可以是：

```text
300059
SZ300059
sh600519
东方财富 300059
```

内部会抽取 6 位代码并推断交易所：

- `6/5/9` 开头 -> `SH`，东方财富 `secid=1.xxxxxx`。
- 其他常见 A 股代码 -> `SZ`，东方财富 `secid=0.xxxxxx`。

## 新增 fetcher 流程

1. 在 `registry.py` 添加 `DataSource`，声明 `id`、`base_url`、`markets`、`capabilities`、`access`、`health`。
2. 在 `public_fetchers.py` 实现 fetcher，返回 dict 或 list，抛出 `ProviderError` 表示该源不可用。
3. 在 `create_demo_provider()` 里 `register_fetcher(source_id, fetcher)`。
4. 如需训练引擎使用新字段，优先扩展 `build_stock_context()`，不要让训练代码直接访问第三方 URL。
5. 更新本 README 和相关 smoke 测试。

## 合规边界

Provider 输出是事实背景和诊断信息，不是投资建议。调用方可以说：

```text
该股票近期波动较大，训练反馈会检查你的止损、仓位和失效条件是否写清。
```

调用方不能说：

```text
这只股票可以买、应该加仓、建议卖出。
```
