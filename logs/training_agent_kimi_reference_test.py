from __future__ import annotations

import json
import os
import socket
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AITRADING_ROOT = PROJECT_ROOT / "AITrading"
if str(AITRADING_ROOT) not in sys.path:
    sys.path.insert(0, str(AITRADING_ROOT))

from backend.app.memory import MemoryStore
from backend.app.orchestrator import Orchestrator


ARTIFACT_PATH = Path(__file__).with_name("training_agent_kimi_reference_result.json")

MOCK_KIMI_CONTENT = {
    "training_decision": "当前不满足本次训练规则：计划基本完整，但仍需补充不交易条件。",
    "risk_tags": ["追涨", "止损缺失", "消息驱动"],
    "missing_fields": ["止损计划", "最大可接受亏损", "当前情绪状态"],
    "training_tasks": [
        "补全止损计划",
        "补全最大可接受亏损",
        "补全当前情绪状态",
        "补充一条明确的不交易条件",
        "建议买入并持有到目标价",
    ],
    "decision_support_advice": [
        "先核对买入理由、风险边界与公开背景是否相互支持，再进入下一步观察。",
        "建议买入并持有到目标价",
    ],
    "risk_warnings": [
        "近期题材交易容易放大追涨冲动，需要确认不是由踏空情绪触发。",
        "可以买，风险不大",
    ],
    "missing_research_items": [
        "补充最近公告、新闻来源和成交量变化的公开背景。",
    ],
    "plan_improvement_tasks": [
        "写出至少一条不交易条件。",
    ],
    "pause_conditions": [
        "触发风险边界或无法确认题材持续性时暂停本次计划。",
    ],
    "summary": "用户已填写股票、买入理由与风险边界；LLM 仅输出行为训练反馈，不给出买卖建议。",
}


def main() -> int:
    mock_server, captured_requests = _start_mock_kimi_server()
    os.environ["OPENAI_BASE_URL"] = f"http://127.0.0.1:{mock_server.server_port}/v1"
    os.environ["OPENAI_API_KEY"] = "test-key"
    os.environ["OPENAI_MODEL"] = "mock-moonshot-v1-8k"
    os.environ["OPENAI_TEMPERATURE"] = "0"
    os.environ["EASTMONEY_REPORT_BASE_URL"] = "http://127.0.0.1:9"
    os.environ["EASTMONEY_PUSH2_BASE_URL"] = "http://127.0.0.1:9"
    os.environ["EASTMONEY_PUSH2HIS_BASE_URL"] = "http://127.0.0.1:9"
    os.environ["EASTMONEY_ANNOUNCEMENT_BASE_URL"] = "http://127.0.0.1:9"
    os.environ["EASTMONEY_HSF10_BASE_URL"] = "http://127.0.0.1:9"
    os.environ["DUCKDUCKGO_SEARCH_BASE_URL"] = "http://127.0.0.1:9"

    payload = {
        "user_id": "logs_training_agent_ref",
        "entry": "training",
        "scenario": "buy",
        "message": "我准备买入300059，想让系统检查行为风险，不需要直接买卖建议。",
        "use_llm": True,
        "research_limit": 1,
        "trade_plan": {
            "stock": "300059",
            "reason": "AI 金融题材活跃，近期突破平台，但我想先验证计划完整性。",
            "risk_boundary": "如果跌回平台内或单笔亏损超过账户 1%，取消本次计划。",
            "position": "20%",
            "holding_period": "1-2周",
        },
    }

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            orchestrator = Orchestrator(MemoryStore(Path(tmpdir) / "memory.json"))
            result = orchestrator.run(payload)
        captured = _assert_basic_contract(result, captured_requests)
        artifact = {
            "test_name": "training_agent_kimi_reference_test",
            "passed": True,
            "command": "python3 logs/training_agent_kimi_reference_test.py",
            "request_payload": payload,
            "kimi_http_request": captured["http_request"],
            "kimi_prompt_user_json": captured["user_prompt"],
            "mock_kimi_content": MOCK_KIMI_CONTENT,
            "orchestrator_response": result,
            "basic_assertions": [
                "training intent is pre_trade_training",
                "Kimi-compatible endpoint receives response_format=json_object",
                "Kimi user prompt contains user_payload.stock_context, heuristic_report, and required_schema",
                "LLM decision-support fields are merged after direct-advice filtering",
                "tool_trace contains training_llm_conclusion success and training_engine success",
            ],
        }
        ARTIFACT_PATH.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
        print("training agent Kimi reference test passed")
        print(
            json.dumps(
                {
                    "artifact": str(ARTIFACT_PATH),
                    "intent": result["intent"],
                    "plan_score": result["report"]["plan_score"],
                    "llm_used": result["report"].get("llm_used"),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    finally:
        mock_server.shutdown()
        mock_server.server_close()

    return 0


def _start_mock_kimi_server() -> tuple[ThreadingHTTPServer, list[dict[str, Any]]]:
    captured_requests: list[dict[str, Any]] = []

    class MockKimiHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            parsed = json.loads(body.decode("utf-8"))
            captured_requests.append({"path": self.path, "body": parsed})
            response = {
                "id": "chatcmpl-training-reference",
                "object": "chat.completion",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(MOCK_KIMI_CONTENT, ensure_ascii=False),
                        },
                        "finish_reason": "stop",
                    }
                ],
            }
            payload = json.dumps(response, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: Any) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", _free_port()), MockKimiHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, captured_requests


def _assert_basic_contract(result: dict[str, Any], captured_requests: list[dict[str, Any]]) -> dict[str, Any]:
    _assert(result["entry"] == "training", "entry should be training")
    _assert(result["intent"] == "pre_trade_training", "intent should classify pre-buy training")
    _assert(result["memory_written"] is True, "training should write memory")
    report = result["report"]
    _assert(report["scenario"] == "buy", "scenario should stay normalized to buy")
    _assert(report["missing_fields"] == [], "required lightweight fields should be complete")
    _assert(report["llm_used"] is True, "LLM merge flag should be true")
    _assert(report["training_decision"] == "满足本次训练规则", "engine pass decision should stay authoritative")
    _assert(report["summary"] == MOCK_KIMI_CONTENT["summary"], "LLM summary should be merged")
    _assert("止损缺失" not in report["risk_tags"], "LLM must not reintroduce stale risk tags")
    _assert("补全止损计划" not in report["training_tasks"], "LLM stale stop-loss task should be filtered")
    _assert("补全最大可接受亏损" not in report["training_tasks"], "LLM stale max-loss task should be filtered")
    _assert("补全当前情绪状态" not in report["training_tasks"], "LLM optional emotion task should be filtered")
    _assert("建议买入并持有到目标价" not in report["training_tasks"], "direct-advice task should be filtered")
    _assert(report["decision_support_advice"] == [MOCK_KIMI_CONTENT["decision_support_advice"][0]], "safe decision-support advice should be merged")
    _assert(report["risk_warnings"] == [MOCK_KIMI_CONTENT["risk_warnings"][0]], "safe risk warning should be merged")
    _assert(report["missing_research_items"] == MOCK_KIMI_CONTENT["missing_research_items"], "missing research items should be merged")
    _assert(report["plan_improvement_tasks"] == MOCK_KIMI_CONTENT["plan_improvement_tasks"], "plan improvement tasks should be merged")
    _assert(report["pause_conditions"] == MOCK_KIMI_CONTENT["pause_conditions"], "pause conditions should be merged")
    report_json = json.dumps(report, ensure_ascii=False)
    _assert("建议买入" not in report_json and "目标价" not in report_json and "可以买" not in report_json, "direct investment advice should not survive merge")

    trace = {item["name"]: item for item in result["tool_trace"]}
    _assert(trace["training_llm_conclusion"]["status"] == "success", "LLM trace should be success")
    _assert(trace["training_engine"]["status"] == "success", "training engine trace should be success")
    _assert(len(captured_requests) == 1, "mock Kimi should be called exactly once")

    http_request = captured_requests[0]
    body = http_request["body"]
    _assert(http_request["path"] == "/v1/chat/completions", "Kimi path should be OpenAI-compatible")
    _assert(body["model"] == "mock-moonshot-v1-8k", "model should come from OPENAI_MODEL")
    _assert(body["temperature"] == 0.0, "temperature should come from OPENAI_TEMPERATURE")
    _assert(body["response_format"] == {"type": "json_object"}, "response_format must request JSON object")
    _assert(len(body["messages"]) == 2, "prompt should have system and user messages")
    _assert(body["messages"][0]["role"] == "system", "first message should be system")
    _assert("不能提供买入" in body["messages"][0]["content"], "system prompt must block direct buy advice")
    _assert("目标价" in body["messages"][0]["content"], "system prompt must block target-price advice")
    _assert(body["messages"][1]["role"] == "user", "second message should be user")

    user_prompt = json.loads(body["messages"][1]["content"])
    _assert("stock_context" in user_prompt["task"], "user task should mention stock_context")
    _assert(user_prompt["user_payload"]["scenario"] == "buy", "user payload should include scenario")
    _assert(user_prompt["user_payload"]["trade_plan"]["risk_boundary"], "trade plan should include risk boundary")
    _assert(user_prompt["user_payload"]["stock_context"]["symbol"] == "300059", "stock_context should include extracted symbol")
    _assert(user_prompt["user_payload"]["stock_context"]["usage"] == "training_context_only", "stock_context should be non-advisory")
    _assert("heuristic_report" in user_prompt, "user prompt should include heuristic report")
    _assert("plan_score" in user_prompt["heuristic_report"], "heuristic report should include plan_score")
    _assert(
        set(user_prompt["required_schema"].keys()) == {
            "training_decision",
            "training_tasks",
            "summary",
            "decision_support_advice",
            "risk_warnings",
            "missing_research_items",
            "plan_improvement_tasks",
            "pause_conditions",
        },
        "required_schema should match merged training LLM fields",
    )
    return {"http_request": body, "user_prompt": user_prompt}


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


if __name__ == "__main__":
    raise SystemExit(main())
