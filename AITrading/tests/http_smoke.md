# Frontend HTTP Contract Smoke

Run from the backend repository root:

```bash
cd /Users/carrick/Hackerson/AITrading
python3 scripts/http_smoke_frontend_contract.py
```

The smoke test starts a temporary backend server on a free local port and covers:

- `OPTIONS /api/questionnaires` CORS preflight
- `GET /health`
- `GET /api/questionnaires`
- `GET /api/questionnaires/full_assessment`
- `POST /api/questionnaires/full_assessment/submit`
- `POST /api/training/check`
- `POST /api/review/run`
- `GET /api/memory`

It uses `use_llm=false` for questionnaire submission and disables live research
by pointing `EASTMONEY_REPORT_BASE_URL` at an unreachable local port. It should
not call real Kimi or external market data providers.

Expected output:

```text
frontend HTTP contract smoke passed
```

