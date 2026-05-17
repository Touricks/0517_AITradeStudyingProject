# Backend

Zero-dependency Python backend for the AI Trading Ability Training Workspace.

## Run

```bash
python3 -m backend.app
```

For frontend integration, prefer:

```bash
python3 scripts/dev_server.py
```

Default URL:

```text
http://127.0.0.1:8000
```

## Endpoints

```text
GET  /health
GET  /api/memory
POST /api/orchestrate
POST /api/assessment/run
POST /api/training/check
POST /api/review/run
POST /api/research/search
GET  /api/questionnaires
GET  /api/questionnaires/{questionnaire_id}
POST /api/questionnaires/{questionnaire_id}/submit
POST /api/assessment/full
```

## CLI

The same backend can be called without starting the HTTP server:

```bash
python3 -m backend.app.cli research --query "300059 东方财富 研报" --limit 2

python3 -m backend.app.cli training \
  --user-id cli_user \
  --scenario add \
  --message "我今天买入300059，仓位30%，现在想加仓" \
  --form-json '{"stock":"300059","position":30,"reason":"最近三天涨得很强","holding_period":"短线","emotion":"担心踏空"}'
```

The CLI is intentionally JSON-first for now so it can share the same request
contract as `/api/orchestrate`.

Questionnaires can be listed, inspected, and submitted from CLI:

```bash
python3 -m backend.app.cli questionnaires
python3 -m backend.app.cli questionnaire show --id full_assessment
python3 -m backend.app.cli questionnaire show --id risk_control
python3 -m backend.app.cli questionnaire submit \
  --id risk_control \
  --user-id cli_user \
  --answers-json '[{"question_id":"q11","answer":"单笔最多亏损总资金的2%。"},{"question_id":"q12","answer":"买入前设置止损。"},{"question_id":"q13","answer":""},{"question_id":"q14","answer":""},{"question_id":"q15","answer":""}]'
```

By default questionnaire submission calls the configured OpenAI-compatible Kimi
endpoint through `OPENAI_BASE_URL`, `OPENAI_API_KEY`, and `OPENAI_MODEL`.
Use `--no-llm` for local fallback scoring.

Questionnaire submissions must include every `question_id` from the selected
questionnaire. Empty answers are valid, but missing question ids are rejected so
Kimi receives the full questionnaire shape.

Use `full_assessment` for final user profile conclusions. It dynamically merges
the eight questionnaire sections into one 40-question questionnaire. Individual
questionnaire ids such as `risk_control` are partial diagnostics.

Questionnaire configs are stored as static JSON assets under
`assets/questionnaires/`; the backend loads them from there.

## E2E

```bash
python3 scripts/e2e_backend_cli.py
python3 scripts/http_smoke_frontend_contract.py
```

This starts a local mock public Eastmoney report API, invokes the CLI, verifies
that `MarketDataProvider` is used, and checks that behavior training writes
memory after consuming research context.

Sync the backend OpenAPI contract to the sibling frontend repo:

```bash
bash scripts/sync_openapi.sh
```

## Demo Request

```bash
curl -s http://127.0.0.1:8000/api/orchestrate \
  -H 'Content-Type: application/json' \
  -d '{
    "user_id": "u_001",
    "entry": "training",
    "message": "我今天买入某股票，仓位30%，现在想加仓",
    "form_data": {
      "stock": "某股票",
      "position": 30,
      "reason": "最近三天涨得很强",
      "holding_period": "短线",
      "emotion": "担心踏空"
    }
  }'
```
