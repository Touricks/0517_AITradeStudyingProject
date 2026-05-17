# CLI Test Components

Run all commands from the repository root:

```bash
cd /Users/carrick/Hackerson/AITrading
```

## 0. One-Command CLI Test Pack

Runs the first batch of CLI tests without real Kimi or persistent memory:

```bash
python3 tests/clitest/run_cli_tests.py
```

Expected result:

```text
PASS assessment_normal
PASS training_normal
PASS review_normal
PASS review_table_normal
PASS qa_questionnaire_normal
PASS qa_full_assessment_normal
PASS qa_missing_answers_rejected
PASS qa_unknown_question_rejected
PASS invalid_json_rejected

All CLI tests passed.
```

## 1. Core Function: Ability Assessment

Runs the legacy lightweight assessment engine:

```bash
python3 -m backend.app.cli assessment \
  --user-id cli_core \
  --answers-json '["我会先确定最大亏损和止损，再看盈亏比。","连续亏损后会暂停交易并复盘策略是否失效。","我记录每一笔交易并总结执行问题。"]'
```

Expected fields:

```text
intent = ability_assessment
tool_trace contains assessment_engine
report.total_score is 0-100
memory_written = true
```

## 2. Core Function: Behavior Training

Runs training plan inspection. The report-search step may degrade gracefully if the public report endpoint is unavailable.

```bash
EASTMONEY_REPORT_BASE_URL=http://127.0.0.1:9 \
python3 -m backend.app.cli training \
  --user-id cli_core \
  --scenario add \
  --message "我今天买入300059，仓位30%，现在想加仓" \
  --form-json '{"stock":"300059","position":30,"reason":"最近三天涨得很强","holding_period":"短线","emotion":"担心踏空"}'
```

Expected fields:

```text
intent = add_position_training
tool_trace contains broker_report_search
tool_trace contains training_engine
report.risk_tags contains 追涨
report.risk_tags contains 止损缺失
memory_written = true
```

## 3. Core Function: Trade Review

Runs intelligent trade review:

```bash
python3 -m backend.app.cli review \
  --user-id cli_core \
  --message "复盘一笔失败交易" \
  --self-reflection "这次有点追涨，亏损后想补仓，原计划没有执行。" \
  --trade-json '{"stock":"300059","buy_price":18.6,"sell_price":17.2,"position":50,"buy_reason":"短期上涨","followed_plan":"否","emotion":"害怕踏空"}'
```

Expected fields:

```text
intent = trade_review
tool_trace contains review_engine
report.mistake_types contains 追涨
report.mistake_types contains 计划缺失
memory_written = true
```

## 3.1 Core Function: Trade Review From Table Rows

Simulates frontend table submission. The backend converts rows into a JSON trade document before review:

```bash
python3 -m backend.app.cli review \
  --user-id cli_core \
  --message "复盘一笔表格提交的交易" \
  --self-reflection "下跌后临时改变计划，没有执行原本纪律。" \
  --trade-table-json '[{"field":"股票","value":"300059"},{"field":"买入价格","value":"18.6"},{"field":"卖出价格","value":"17.2"},{"field":"仓位比例","value":"50"},{"field":"买入理由","value":"短期上涨"},{"field":"原计划是否执行","value":"否"},{"field":"当时情绪状态","value":"害怕"}]'
```

Expected fields:

```text
intent = trade_review
report.trade_document.stock = 300059
tool_trace contains review_engine
memory_written = true
```

## 4. QA Function: List Questionnaires

Lists the full assessment and the eight configured questionnaire sets:

```bash
python3 -m backend.app.cli questionnaires
```

Expected questionnaire ids:

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

Use `full_assessment` for final user profile conclusions. The eight individual questionnaires are partial diagnostics only.

## 5. QA Function: Show One Questionnaire

Shows the full questionnaire config:

```bash
python3 -m backend.app.cli questionnaire show --id risk_control
```

Expected fields:

```text
id = risk_control
questions contains q11, q12, q13, q14, q15
```

## 6. QA Function: Submit Questionnaire Without Kimi

Uses local fallback scoring. This is the safest local test because it does not call Kimi:

```bash
python3 -m backend.app.cli questionnaire submit \
  --id risk_control \
  --user-id cli_qa \
  --no-llm \
  --answers-json '[{"question_id":"q11","answer":"单笔最多亏损总资金的2%。"},{"question_id":"q12","answer":"买入前设置止损，依据是交易计划失效条件。"},{"question_id":"q13","answer":""},{"question_id":"q14","answer":""},{"question_id":"q15","answer":""}]'
```

Expected fields:

```text
intent = questionnaire_assessment
tool_trace contains questionnaire_load
tool_trace contains answer_validate
tool_trace contains schema_validate
report.schema_version = questionnaire_profile.v1
memory_written = true
```

## 6.1 QA Function: Submit Full 40-Question Assessment Without Kimi

For the final user profile, submit `full_assessment`. It contains all 40 questions from the eight questionnaire sections. Every `question_id` must be present; answers may be empty strings.

Generate a complete empty answer payload:

```bash
python3 - <<'PY'
import json
from backend.app.questionnaire_store import get_questionnaire

q = get_questionnaire("full_assessment")
answers = [{"question_id": item["id"], "answer": ""} for item in q["questions"]]
print(json.dumps(answers, ensure_ascii=False))
PY
```

Submit the full assessment with local fallback scoring:

```bash
python3 -m backend.app.cli questionnaire submit \
  --id full_assessment \
  --user-id cli_full \
  --no-llm \
  --answers-json "$(python3 - <<'PY'
import json
from backend.app.questionnaire_store import get_questionnaire

q = get_questionnaire("full_assessment")
answers = [{"question_id": item["id"], "answer": ""} for item in q["questions"]]
answers[0]["answer"] = "我认为最重要的是控制亏损和风险回报比，因为单次判断可能错，但风险必须先确定。"
answers[10]["answer"] = "单笔最多亏损总资金的2%。"
answers[11]["answer"] = "买入前设置止损，依据是交易计划失效条件。"
print(json.dumps(answers, ensure_ascii=False))
PY
)"
```

Expected fields:

```text
questionnaire.id = full_assessment
tool_trace contains answer_validate
report.schema_version = questionnaire_profile.v1
memory_written = true
```

## 7. QA Function: Submit Full Assessment With Kimi

Uses the OpenAI-compatible Kimi configuration in `config/.env`:

```bash
python3 -m backend.app.cli questionnaire submit \
  --id full_assessment \
  --user-id cli_qa \
  --answers-json "$(python3 - <<'PY'
import json
from backend.app.questionnaire_store import get_questionnaire

q = get_questionnaire("full_assessment")
answers = [{"question_id": item["id"], "answer": ""} for item in q["questions"]]
answers[0]["answer"] = "我认为最重要的是控制亏损和风险回报比，因为单次判断可能错，但风险必须先确定。"
answers[10]["answer"] = "单笔最多亏损总资金的2%。"
answers[11]["answer"] = "买入前设置止损，依据是交易计划失效条件。"
answers[20]["answer"] = "交易前必须明确入场理由、止损位置、仓位大小、持有周期和失效条件。"
answers[30]["answer"] = "我记录每一笔交易，包括理由、仓位、止损、情绪、执行和复盘。"
print(json.dumps(answers, ensure_ascii=False))
PY
)"
```

Required env names:

```text
OPENAI_BASE_URL
OPENAI_API_KEY
OPENAI_MODEL
OPENAI_TEMPERATURE
```

Expected fields:

```text
tool_trace contains kimi_profile_generate
report.schema_version = questionnaire_profile.v1
report.total_score is 0-100
memory_written = true
```

## 8. Combined Function: Unified Orchestrator

Runs the merged backend entry point:

```bash
EASTMONEY_REPORT_BASE_URL=http://127.0.0.1:9 \
python3 -m backend.app.cli orchestrate \
  --payload '{"user_id":"cli_combined","entry":"training","message":"我今天买入300059，仓位30%，现在想加仓","form_data":{"stock":"300059","position":30,"reason":"最近三天涨得很强","holding_period":"短线","emotion":"担心踏空"}}'
```

Expected fields:

```text
entry = training
intent = add_position_training
tool_trace contains classify_intent
tool_trace contains user_profile_get
tool_trace contains session_memory_query
tool_trace contains training_engine
memory_written = true
```

## 9. Corner Case: Missing Questionnaire Answers Must Be Rejected

Questionnaire submissions must include every question id. Empty answers are allowed, missing ids are not.

```bash
python3 -m backend.app.cli questionnaire submit \
  --id risk_control \
  --user-id cli_qa \
  --no-llm \
  --answers-json '[{"question_id":"q11","answer":"单笔最多亏损2%。"}]'
```

Expected result:

```text
exit code = 2
stderr contains invalid_questionnaire_answers
stderr contains missing_question_ids
```

## 10. Corner Case: Unknown Questionnaire Question Must Be Rejected

```bash
python3 -m backend.app.cli questionnaire submit \
  --id risk_control \
  --user-id cli_qa \
  --no-llm \
  --answers-json '[{"question_id":"q11","answer":"单笔最多亏损2%。"},{"question_id":"q12","answer":""},{"question_id":"q13","answer":""},{"question_id":"q14","answer":""},{"question_id":"q999","answer":""}]'
```

Expected result:

```text
exit code = 2
stderr contains invalid_questionnaire_answers
stderr contains unknown_question_ids
```

## 11. Corner Case: Invalid JSON Must Be Rejected

```bash
python3 -m backend.app.cli training \
  --user-id cli_core \
  --message "非法 JSON 测试" \
  --form-json '{not-json'
```

Expected result:

```text
exit code = 1
stderr contains Invalid JSON
```

## 12. Mock E2E Components

Mock Kimi/OpenAI-compatible questionnaire e2e:

```bash
python3 scripts/e2e_questionnaire_kimi.py
```

Mock public research + training e2e:

```bash
python3 scripts/e2e_backend_cli.py
```

Legacy smoke for assessment/training/review:

```bash
MX_APIKEY= EASTMONEY_REPORT_BASE_URL=http://127.0.0.1:9 python3 scripts/smoke_backend.py
```
