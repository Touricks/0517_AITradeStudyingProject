from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Case:
    name: str
    fn: Callable[[str, dict[str, str]], None]


def main() -> int:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    # Keep public research deterministic in local CLI tests. The training flow
    # should degrade gracefully when report search cannot connect.
    env["EASTMONEY_REPORT_BASE_URL"] = "http://127.0.0.1:9"
    env["EASTMONEY_PUSH2_BASE_URL"] = "http://127.0.0.1:9"
    env["EASTMONEY_PUSH2HIS_BASE_URL"] = "http://127.0.0.1:9"
    env["EASTMONEY_ANNOUNCEMENT_BASE_URL"] = "http://127.0.0.1:9"
    env["EASTMONEY_HSF10_BASE_URL"] = "http://127.0.0.1:9"
    env["DUCKDUCKGO_SEARCH_BASE_URL"] = "http://127.0.0.1:9"

    cases = [
        Case("assessment_normal", test_assessment_normal),
        Case("training_normal", test_training_normal),
        Case("training_minimal_pre_buy_fields", test_training_minimal_pre_buy_fields),
        Case("review_normal", test_review_normal),
        Case("review_table_normal", test_review_table_normal),
        Case("qa_questionnaire_normal", test_qa_questionnaire_normal),
        Case("qa_full_assessment_normal", test_qa_full_assessment_normal),
        Case("qa_missing_answers_rejected", test_qa_missing_answers_rejected),
        Case("qa_unknown_question_rejected", test_qa_unknown_question_rejected),
        Case("invalid_json_rejected", test_invalid_json_rejected),
    ]

    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmpdir:
        memory_path = str(Path(tmpdir) / "memory.json")
        for case in cases:
            try:
                case.fn(memory_path, env)
                print(f"PASS {case.name}")
            except Exception as exc:
                failures.append(f"{case.name}: {exc}")
                print(f"FAIL {case.name}: {exc}", file=sys.stderr)

    if failures:
        print("\nFailures:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print("\nAll CLI tests passed.")
    return 0


def test_assessment_normal(memory_path: str, env: dict[str, str]) -> None:
    result = run_json(
        [
            "--memory-path",
            memory_path,
            "assessment",
            "--user-id",
            "cli_core",
            "--answers-json",
            json.dumps(
                [
                    "我会先确定最大亏损和止损，再看盈亏比。",
                    "连续亏损后会暂停交易并复盘策略是否失效。",
                    "我记录每一笔交易并总结执行问题。",
                ],
                ensure_ascii=False,
            ),
        ],
        env,
    )
    assert_equal(result["intent"], "ability_assessment")
    assert_true(result["memory_written"])
    assert_between(result["report"]["total_score"], 0, 100)
    assert_trace_contains(result, "assessment_engine")
    assert_trace_contains(result, "session_memory_write")


def test_training_normal(memory_path: str, env: dict[str, str]) -> None:
    result = run_json(
        [
            "--memory-path",
            memory_path,
            "training",
            "--user-id",
            "cli_risk",
            "--scenario",
            "add",
            "--message",
            "我今天买入300059，仓位30%，现在想加仓",
            "--form-json",
            json.dumps(
                {
                    "stock": "300059",
                    "position": 30,
                    "reason": "最近三天涨得很强",
                    "holding_period": "短线",
                    "emotion": "担心踏空",
                },
                ensure_ascii=False,
            ),
        ],
        env,
    )
    assert_equal(result["intent"], "add_position_training")
    assert_true(result["memory_written"])
    assert_trace_contains(result, "stock_context_import")
    assert_trace_contains(result, "training_engine")
    assert_in("追涨", result["report"]["risk_tags"])
    assert_in("止损缺失", result["report"]["risk_tags"])


def test_training_minimal_pre_buy_fields(memory_path: str, env: dict[str, str]) -> None:
    result = run_json(
        [
            "--memory-path",
            memory_path,
            "training",
            "--user-id",
            "cli_minimal",
            "--scenario",
            "buy",
            "--message",
            "我准备买入300059，想先检查计划",
            "--form-json",
            json.dumps(
                {
                    "stock": "300059",
                    "reason": "AI 金融题材活跃，近期突破平台",
                    "risk_boundary": "跌回平台内或单笔亏损超过账户1%就停止本次计划",
                },
                ensure_ascii=False,
            ),
        ],
        env,
    )
    assert_equal(result["intent"], "pre_trade_training")
    assert_true(result["memory_written"])
    assert_equal(result["report"]["missing_fields"], [])
    assert_not_in("止损缺失", result["report"]["risk_tags"])


def test_review_normal(memory_path: str, env: dict[str, str]) -> None:
    result = run_json(
        [
            "--memory-path",
            memory_path,
            "review",
            "--user-id",
            "cli_core",
            "--message",
            "复盘一笔失败交易",
            "--self-reflection",
            "这次有点追涨，亏损后想补仓，原计划没有执行。",
            "--trade-json",
            json.dumps(
                {
                    "stock": "300059",
                    "buy_price": 18.6,
                    "sell_price": 17.2,
                    "position": 50,
                    "buy_reason": "短期上涨",
                    "followed_plan": "否",
                    "emotion": "害怕踏空",
                },
                ensure_ascii=False,
            ),
        ],
        env,
    )
    assert_equal(result["intent"], "trade_review")
    assert_true(result["memory_written"])
    assert_trace_contains(result, "review_engine")
    assert_in("追涨", result["report"]["mistake_types"])
    assert_in("计划缺失", result["report"]["mistake_types"])


def test_review_table_normal(memory_path: str, env: dict[str, str]) -> None:
    result = run_json(
        [
            "--memory-path",
            memory_path,
            "review",
            "--user-id",
            "cli_core",
            "--message",
            "复盘一笔表格提交的交易",
            "--self-reflection",
            "下跌后临时改变计划，没有执行原本纪律。",
            "--trade-table-json",
            json.dumps(
                [
                    {"field": "股票", "value": "300059"},
                    {"field": "买入价格", "value": "18.6"},
                    {"field": "卖出价格", "value": "17.2"},
                    {"field": "仓位比例", "value": "50"},
                    {"field": "买入理由", "value": "短期上涨"},
                    {"field": "原计划是否执行", "value": "否"},
                    {"field": "当时情绪状态", "value": "害怕"},
                ],
                ensure_ascii=False,
            ),
        ],
        env,
    )
    assert_equal(result["intent"], "trade_review")
    assert_equal(result["report"]["trade_document"]["stock"], "300059")
    assert_trace_contains(result, "review_engine")
    assert_true(result["memory_written"])


def test_qa_questionnaire_normal(memory_path: str, env: dict[str, str]) -> None:
    result = run_json(
        [
            "--memory-path",
            memory_path,
            "questionnaire",
            "submit",
            "--id",
            "risk_control",
            "--user-id",
            "cli_qa",
            "--no-llm",
            "--answers-json",
            risk_control_full_answers(),
        ],
        env,
    )
    assert_equal(result["intent"], "questionnaire_assessment")
    assert_equal(result["questionnaire"]["id"], "risk_control")
    assert_true(result["memory_written"])
    assert_trace_contains(result, "questionnaire_load")
    assert_trace_contains(result, "answer_validate")
    assert_trace_contains(result, "schema_validate")
    assert_between(result["report"]["total_score"], 0, 100)


def test_qa_full_assessment_normal(memory_path: str, env: dict[str, str]) -> None:
    questionnaire = run_json(["questionnaire", "show", "--id", "full_assessment"], env)
    answers = [
        {
            "question_id": question["id"],
            "answer": full_assessment_answer(question["id"]),
        }
        for question in questionnaire["questions"]
    ]
    result = run_json(
        [
            "--memory-path",
            memory_path,
            "questionnaire",
            "submit",
            "--id",
            "full_assessment",
            "--user-id",
            "cli_full",
            "--no-llm",
            "--answers-json",
            json.dumps(answers, ensure_ascii=False),
        ],
        env,
    )
    assert_equal(result["intent"], "questionnaire_assessment")
    assert_equal(result["questionnaire"]["id"], "full_assessment")
    assert_equal(len(questionnaire["questions"]), 40)
    assert_true(result["memory_written"])
    assert_trace_contains(result, "answer_validate")
    assert_between(result["report"]["total_score"], 0, 100)


def test_qa_missing_answers_rejected(memory_path: str, env: dict[str, str]) -> None:
    completed = run_raw(
        [
            "--memory-path",
            memory_path,
            "questionnaire",
            "submit",
            "--id",
            "risk_control",
            "--user-id",
            "cli_qa",
            "--no-llm",
            "--answers-json",
            json.dumps([{"question_id": "q11", "answer": "单笔最多亏损2%。"}], ensure_ascii=False),
        ],
        env,
    )
    assert_equal(completed.returncode, 2)
    assert_in("invalid_questionnaire_answers", completed.stderr)
    assert_in("missing_question_ids", completed.stderr)


def test_qa_unknown_question_rejected(memory_path: str, env: dict[str, str]) -> None:
    answers = json.loads(risk_control_full_answers())
    answers[-1]["question_id"] = "q999"
    completed = run_raw(
        [
            "--memory-path",
            memory_path,
            "questionnaire",
            "submit",
            "--id",
            "risk_control",
            "--user-id",
            "cli_qa",
            "--no-llm",
            "--answers-json",
            json.dumps(answers, ensure_ascii=False),
        ],
        env,
    )
    assert_equal(completed.returncode, 2)
    assert_in("invalid_questionnaire_answers", completed.stderr)
    assert_in("unknown_question_ids", completed.stderr)


def test_invalid_json_rejected(memory_path: str, env: dict[str, str]) -> None:
    completed = run_raw(
        [
            "--memory-path",
            memory_path,
            "training",
            "--user-id",
            "cli_core",
            "--message",
            "非法 JSON 测试",
            "--form-json",
            "{not-json",
        ],
        env,
    )
    assert_equal(completed.returncode, 1)
    assert_in("Invalid JSON", completed.stderr)


def risk_control_full_answers() -> str:
    return json.dumps(
        [
            {"question_id": "q11", "answer": "单笔最多亏损总资金的2%。"},
            {"question_id": "q12", "answer": "买入前设置止损，依据是交易计划失效条件。"},
            {"question_id": "q13", "answer": ""},
            {"question_id": "q14", "answer": ""},
            {"question_id": "q15", "answer": ""},
        ],
        ensure_ascii=False,
    )


def full_assessment_answer(question_id: str) -> str:
    answered = {
        "q1": "我认为最重要的是控制亏损和风险回报比，因为单次判断可能错，但风险必须先确定。",
        "q11": "单笔最多亏损总资金的2%。",
        "q12": "买入前设置止损，依据是交易计划失效条件。",
        "q16": "根据止损距离和最大亏损额度决定仓位。",
        "q21": "入场理由、买入价格、止损位置、仓位大小、持有周期、失效条件。",
        "q31": "记录每一笔交易，包括理由、仓位、止损、情绪、执行和复盘。",
        "s1": "不会因为三天上涨就直接追入，除非风险回报比和失效条件明确。",
    }
    return answered.get(question_id, "")


def run_json(args: list[str], env: dict[str, str]) -> dict[str, Any]:
    completed = run_raw(args, env)
    if completed.returncode != 0:
        raise AssertionError(f"CLI exited {completed.returncode}\nSTDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}")
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"stdout is not JSON: {exc}\n{completed.stdout}") from exc
    if not isinstance(parsed, dict):
        raise AssertionError("stdout JSON must be an object")
    return parsed


def run_raw(args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "backend.app.cli", *args],
        cwd=str(ROOT),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def assert_trace_contains(result: dict[str, Any], name: str) -> None:
    trace_names = [item["name"] for item in result.get("tool_trace", [])]
    assert_in(name, trace_names)


def assert_equal(actual: Any, expected: Any) -> None:
    if actual != expected:
        raise AssertionError(f"expected {expected!r}, got {actual!r}")


def assert_true(value: Any) -> None:
    if value is not True:
        raise AssertionError(f"expected True, got {value!r}")


def assert_in(needle: Any, haystack: Any) -> None:
    if needle not in haystack:
        raise AssertionError(f"expected {needle!r} in {haystack!r}")


def assert_not_in(needle: Any, haystack: Any) -> None:
    if needle in haystack:
        raise AssertionError(f"expected {needle!r} not in {haystack!r}")


def assert_between(value: int | float, low: int | float, high: int | float) -> None:
    if not (low <= value <= high):
        raise AssertionError(f"expected {value!r} between {low!r} and {high!r}")


if __name__ == "__main__":
    raise SystemExit(main())
