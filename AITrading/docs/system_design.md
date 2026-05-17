# AI Trading Ability Backend System Design

## 1. Design Boundary

The product is an investment education and trading ability training system. It must not act as a stock recommendation engine.

The backend therefore answers three questions:

1. What capability level is the user currently showing?
2. Is the current trading behavior complete and disciplined enough for the user's training stage?
3. What repeatable memory should be written so the next session can detect old behavior patterns?

Every report must end with the compliance notice:

```text
本系统仅用于投资教育与交易能力训练，不构成任何投资建议、个股推荐或买卖信号。
```

## 2. Runtime Architecture

```text
Frontend
  -> Backend API
  -> Orchestrator
  -> Intent Router
  -> Memory Store
  -> Assessment / Training / Review Engine
  -> MarketDataProvider
  -> Public Research Fetchers
  -> Compliance Guard
  -> Memory Writer
```

The frontend can keep three clear entry points:

```text
assessment 交易能力评估
training   行为训练
review     智能复盘
```

The backend treats those entries as routes into one shared system. The same profile, session memory, tool trace, compliance guard, and memory writer are used by all engines.

## 3. Backend Modules

| Module | Responsibility |
| --- | --- |
| `server.py` | Small HTTP API using Python standard library only. |
| `orchestrator.py` | Classifies intent, runs tools in order, writes memory, returns tool trace. |
| `engines.py` | Contains assessment, behavior training, and review heuristics. |
| `memory.py` | JSON-backed memory model for profiles, memories, tasks, and logs. |
| `compliance.py` | Rewrites or flags investment-advice language. |
| `research.py` | Research adapter that registers public fetchers into `MarketDataProvider`. |
| `src/MarketDataProvider/` | Provider facade, source registry, and fallback result envelope. |
| `questionnaire_store.py` | Loads the eight JSON questionnaire configs derived from `docs/problemlist.md`. |
| `questionnaire_engine.py` | Calls Kimi through an OpenAI-compatible endpoint, validates fixed profile JSON, and writes memory. |
| `llm_client.py` | Minimal OpenAI-compatible chat client using `OPENAI_BASE_URL`, `OPENAI_API_KEY`, and `OPENAI_MODEL`. |
| `models.py` | Shared data structures and response helpers. |

## 3.1 Search Engine Update

The repository now treats Miaoxiang as unavailable. The active instruction is:

```text
妙想相关接口当前不可用，可能需要联系供应商购买。不要安装或调用对应 skill；优先使用公开数据源和 src/MarketDataProvider/ 的 provider 降级链。
```

The backend therefore no longer calls vendor-only Miaoxiang skills for research search. The active path is:

```text
Orchestrator
  -> research.should_search
  -> research.broker_report_search
  -> MarketDataProvider.search_reports
  -> eastmoney_report fetcher
  -> DataResult envelope
```

The provider envelope keeps search failures visible without turning missing data into a trading signal:

```json
{
  "ok": false,
  "data": null,
  "source": "",
  "fallback": true,
  "errors": ["eastmoney_report: ..."],
  "metadata": {"attempted": ["eastmoney_report"]}
}
```

Search is triggered when the training payload contains a stock field, a 6-digit A-share code, or domain words such as 股票、行业、板块、研报、公告、政策.

## 4. Memory Model

The first implementation uses a JSON file so the demo can run without database setup:

```text
data/memory_store.json
```

Logical collections:

```text
user_profiles
session_memories
training_tasks
trade_records
assessment_results
review_reports
tool_call_logs
compliance_logs
research_reports
```

This maps directly to the future SQL tables in `docs/plan.md`. The API surface is intentionally database-shaped, so switching from JSON to SQLite/PostgreSQL later only requires replacing `MemoryStore`.

## 5. Orchestrator Flow

```text
1. classify_intent
2. validate_required_fields
3. user_profile_get
4. session_memory_query
5. broker_report_search through MarketDataProvider when a stock/theme query is present
6. call target engine
7. compliance_guard_check
8. user_profile_update when assessment changes profile
9. session_memory_write
10. tool_call_logs write
```

The response always includes:

```json
{
  "entry": "training",
  "intent": "add_position_training",
  "tool_trace": [],
  "report": {},
  "memory_written": true
}
```

## 6. Compliance Rules

The backend blocks or rewrites direct investment advice patterns, including:

```text
建议买入
建议卖出
可以买
跌破...卖出
目标价
稳赚
一定上涨
```

Allowed wording focuses on training:

```text
当前交易计划不完整
当前行为存在追涨风险
当前不满足训练规则
请明确最大可承受亏损
```

## 7. Backend E2E And CLI Gap

Current runnable checks:

```bash
python3 scripts/smoke_backend.py
python3 scripts/e2e_backend_cli.py
python3 scripts/e2e_questionnaire_kimi.py
```

`scripts/e2e_backend_cli.py` starts a local mock Eastmoney report API and then invokes the backend through the command-line interface:

```bash
python3 -m backend.app.cli research --query "300059 东方财富 研报" --limit 2
python3 -m backend.app.cli training --user-id cli_e2e --message "我今天买入300059，仓位30%，现在想加仓" --form-json '{...}'
```

This covers the important backend path:

```text
CLI -> Orchestrator -> MarketDataProvider -> mocked eastmoney_report -> training_engine -> memory write
```

Remaining gaps before a user-facing CLI is complete:

| Gap | Current state | Next work |
| --- | --- | --- |
| CLI ergonomics | JSON arguments are accepted, but still developer-oriented. | Add interactive prompts and examples for assessment/training/review. |
| Provider coverage | Only `eastmoney_report` has a concrete fetcher. | Add quote, announcement, news, and k-line fetchers behind the same registry. |
| Fallback depth | Registry defines fallback sources, but most fetchers are placeholders. | Implement `cninfo`, `tencent_qt`, `akshare` adapters and assert fallback order in e2e. |
| HTTP e2e | CLI e2e covers backend logic without real network. | Add a server-level e2e that starts `/api/*` and posts curl-equivalent requests. |
| Output contract | Reports are stable enough for demos. | Freeze JSON schema for frontend and CLI consumers. |
| Compliance coverage | Guard runs on generated reports. | Add regression tests with forbidden phrases and expected rewrites. |

## 8. Questionnaire Architecture

The questionnaire system is now config-driven. The eight configs live in:

```text
assets/questionnaires/
```

The active sets are:

```text
full_assessment
trading_cognition
analysis_framework
risk_control
position_management
trade_plan
emotion_discipline
review_ability
scenario_maturity
```

`full_assessment` is synthesized dynamically from the eight section configs and
contains all 40 questions. It is the correct entry point for a final user profile
and comprehensive score. The eight smaller questionnaires are partial diagnostic
views.

Frontend flow:

```text
GET  /api/questionnaires
GET  /api/questionnaires/{questionnaire_id}
POST /api/questionnaires/{questionnaire_id}/submit
```

Kimi is called through the OpenAI-compatible chat completions API:

```text
OPENAI_BASE_URL=https://api.moonshot.cn/v1
OPENAI_API_KEY=...
OPENAI_MODEL=moonshot-v1-8k
```

The LLM must return a fixed JSON object with:

```text
questionnaire_id
total_score
dimension_scores
trader_type
risk_level
weaknesses
risk_tags
profile_summary
evidence
next_training_focus
recommended_tasks
```

The backend then normalizes ranges, applies compliance checks, updates
`user_profiles`, stores `questionnaire_results`, and writes `session_memories`.

Submission contract:

```text
answers must contain every question_id in the selected questionnaire
answer may be an empty string when the user skips a question
missing, duplicate, or unknown question ids are rejected before calling Kimi
answers are reordered by questionnaire config and passed to Kimi with question_text
```
