# AITradingPlatform

AITradingPlatform 是一个面向投资教育与交易能力训练的本地化系统。项目不做真实交易，也不提供买入、卖出、持有、加仓、止损点位或收益承诺；它关注的是用户如何理解风险、制定交易计划、处理情绪与复盘行为。

## Demo

演示视频位于仓库根目录：

- [demo.mp4](./demo.mp4)


## 系统设计

本项目的核心判断是：用户评测本身不适合交给 Agent 完成。

评测阶段需要用户稳定、明确地回答问题，并由系统沉淀结构化结果。如果让 Agent 代替用户完成评测，容易引入推断、补全和迎合，最终得到的用户画像并不可靠。因此系统拆成两部分：

1. 前端负责评测与训练交互：用户在 React 前端完成交易能力评估、行为训练和必要的信息填写。
2. MCP 负责画像提取：当后端已经生成用户画像后，Agent 通过 MCP 读取画像、历史记忆和证据摘要，再基于这些信息提供个性化解释、学习建议和训练反馈。

也就是说，Agent 的角色不是替用户做测试，而是在画像建立之后，参考画像帮助用户更好地理解自己的交易认知、风险偏好、计划能力和情绪纪律。

## 功能

后端提供两个主要能力：

- 用户交易能力评估：通过问卷与评测流程生成用户画像，覆盖交易认知、分析框架、风险控制、仓位管理、交易计划、情绪纪律、复盘能力和场景成熟度。
- 交易行为训练：围绕买入、持有、加仓、减仓、止损、追涨、盘中检查等行为场景，结合用户输入和股票上下文生成训练反馈。

模型与数据来源：

- 模型服务：使用 Kimi，按 OpenAI-compatible 接口配置在 `AITrading/config/.env` 中。
- 股票数据上下文：使用东方财富公开数据源，由 `AITrading/src/MarketDataProvider/` 统一封装，前端通过后端接口读取归一化后的行情和上下文。

## 技术栈

- 后端：Python API 服务，项目设计面向 FastAPI 风格的 HTTP 接口；当前 demo 入口为 `AITrading/backend/app/server.py`，提供本地 HTTP API 与 OpenAPI 契约。
- 前端：React + Vite。
- Agent 集成：STDIO MCP Server，位于 `AITradingMCP/`，用于让 Agent 读取后端已生成的用户画像。
- 模型：Kimi。
- 行情与研报上下文：东方财富公开数据源。

## 目录结构

```text
.
├── demo.mp4
├── AGENTS.md
├── AITrading/
│   ├── backend/
│   │   └── app/                 # 后端 API、评估、训练、记忆、LLM 与编排逻辑
│   ├── config/
│   │   ├── .env                 # 本地敏感配置，不应提交
│   │   └── .env.example         # 环境变量示例
│   ├── src/MarketDataProvider/  # 东方财富等市场数据 Provider 封装
│   ├── assets/questionnaires/   # 评测问卷配置
│   ├── scripts/                 # 后端启动、烟测、清理 memory 等脚本
│   ├── data/                    # 本地 JSON memory 数据
│   └── openapi.yaml             # 后端接口契约
├── AITradingFrontend/
│   ├── src/                     # React 页面、组件、API client
│   ├── package.json             # 前端脚本与依赖
│   └── openapi.yaml             # 前端侧同步的接口契约
├── AITradingMCP/
│   ├── src/aitrading_ability_mcp/
│   │   ├── server.py            # STDIO MCP 入口
│   │   ├── tools.py             # MCP tool 定义与后端包装
│   │   └── schemas.py           # tool input schema 与校验
│   └── tests/                   # MCP schema 与 stdio smoke tests
├── AITradingMCPTest/
│   └── .mcp.json                # Anthropic / Claude Code MCP 配置示例
└── logs/                        # 测试记录、运行日志与问题报告
```

## 环境配置

后端读取 `AITrading/config/.env`。首次运行前请从示例文件复制一份：

```bash
cd AITrading
cp config/.env.example config/.env
```

然后编辑 `AITrading/config/.env`，至少确认以下配置：

```bash
OPENAI_BASE_URL=https://api.moonshot.cn/v1
OPENAI_API_KEY=你的_Kimi_API_Key
OPENAI_MODEL=moonshot-v1-32k
OPENAI_TEMPERATURE=0

WEB_SEARCH_PROVIDER=eastmoney_public
EASTMONEY_REPORT_BASE_URL=https://reportapi.eastmoney.com
```

## 启动后端

在项目根目录执行：

```bash
cd AITrading
python3 scripts/dev_server.py
```

默认地址：

```text
http://127.0.0.1:8000
```

常用接口：

```text
GET  /health
GET  /api/questionnaires
GET  /api/questionnaires/full_assessment
POST /api/questionnaires/full_assessment/submit
POST /api/training/check
GET  /api/market/kline?symbol=300059&market=A&limit=120
GET  /api/memory
```

## 启动前端

前端启动始终使用 `npm run dev`：

```bash
cd AITradingFrontend
npm install
npm run dev
```

Vite 默认会在本地启动前端开发服务。前端会调用后端接口完成评测、训练和股票上下文展示。

## 启动 MCP

MCP 用于 Agent 读取后端已生成的用户画像。使用前请先启动后端，并确保用户已经通过前端完成评测。

本地直接启动：

```bash
cd AITradingMCP
PYTHONPATH=src AITRADING_BACKEND_URL=http://127.0.0.1:8000 python3 -m aitrading_ability_mcp.server
```

Claude / Anthropic 格式示例见：

```text
AITradingMCPTest/.mcp.json
```

如果复制项目到新路径，需要把 `.mcp.json` 中的 `cwd` 和 `PYTHONPATH` 改成当前机器上的绝对路径。例如：

```json
{
  "mcpServers": {
    "aitrading-ability": {
      "command": "/usr/bin/python3",
      "args": ["-m", "aitrading_ability_mcp.server"],
      "cwd": "/absolute/path/to/AITradingMCP",
      "env": {
        "PYTHONPATH": "/absolute/path/to/AITradingMCP/src",
        "AITRADING_BACKEND_URL": "http://127.0.0.1:8000",
        "AITRADING_MCP_ENABLE_WRITE_TOOLS": "false"
      }
    }
  }
}
```

默认暴露的 MCP tools 是只读画像工具，包括：

- `aitrading_health_check`
- `aitrading_extract_user_profile`
- `aitrading_list_user_profile_sources`
- `aitrading_get_user_profile_raw`
- `aitrading_search_user_profile_memories`

这些工具的目标是让 Agent 读取用户画像，而不是让用户在 CLI 或 Agent 中重新完成评测。

## 验证

后端烟测：

```bash
cd AITrading
python3 scripts/http_smoke_frontend_contract.py
```

MCP 测试：

```bash
cd AITradingMCP
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py'
PYTHONPATH=src python3 tests/stdio_smoke.py
```

前端构建：

```bash
cd AITradingFrontend
npm run build
```

## 合规说明

本项目仅用于投资教育、交易能力评估和行为训练。股票行情、研报和上下文信息只作为训练材料，不构成任何投资建议、证券推荐或交易信号。
