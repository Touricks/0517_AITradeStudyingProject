from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


KIMI_PROFILE = {
    "questionnaire_id": "risk_control",
    "total_score": 76,
    "dimension_scores": {
        "market_understanding": 13,
        "analysis_framework": 12,
        "risk_control": 18,
        "execution_discipline": 16,
        "review_ability": 17
    },
    "trader_type": "成熟交易者",
    "risk_level": "medium",
    "weaknesses": ["连续亏损后的暂停机制仍需细化"],
    "risk_tags": ["止损执行待验证"],
    "profile_summary": "用户具备较清晰的单笔风险预算意识，但需要把连续亏损后的暂停和复盘动作写成固定规则。",
    "evidence": [
        {"question_id": "q11", "finding": "用户明确给出单笔最大亏损比例。"},
        {"question_id": "q12", "finding": "用户提到买入前设置止损。"}
    ],
    "next_training_focus": ["止损执行训练", "连续亏损暂停机制"],
    "recommended_tasks": ["未来3笔交易记录止损依据。", "连续亏损2次后暂停并复盘。"]
}


class MockKimiHandler(BaseHTTPRequestHandler):
    calls = 0

    def do_POST(self) -> None:
        MockKimiHandler.calls += 1
        body = json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(KIMI_PROFILE, ensure_ascii=False)
                        }
                    }
                ]
            },
            ensure_ascii=False,
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        return


def main() -> int:
    mock_server = ThreadingHTTPServer(("127.0.0.1", _free_port()), MockKimiHandler)
    thread = threading.Thread(target=mock_server.serve_forever, daemon=True)
    thread.start()

    env = os.environ.copy()
    env["OPENAI_BASE_URL"] = f"http://127.0.0.1:{mock_server.server_port}/v1"
    env["OPENAI_API_KEY"] = "test-key"
    env["OPENAI_MODEL"] = "moonshot-mock"
    env["PYTHONPATH"] = str(ROOT)

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            memory_path = str(Path(tmpdir) / "memory.json")
            result = _run_cli(
                env,
                [
                    "--memory-path",
                    memory_path,
                    "questionnaire",
                    "submit",
                    "--id",
                    "risk_control",
                    "--user-id",
                    "kimi_e2e",
                    "--answers-json",
                    json.dumps(
                        [
                            {"question_id": "q11", "answer": "单笔最多亏损总资金的2%。"},
                            {"question_id": "q12", "answer": "买入前设置止损，依据是计划失效条件。"},
                            {"question_id": "q13", "answer": ""},
                            {"question_id": "q14", "answer": ""},
                            {"question_id": "q15", "answer": ""}
                        ],
                        ensure_ascii=False,
                    ),
                ],
            )

            trace_names = [item["name"] for item in result["tool_trace"]]
            _assert(MockKimiHandler.calls == 1, "Kimi-compatible endpoint should be called once")
            _assert("kimi_profile_generate" in trace_names, "trace should include kimi_profile_generate")
            _assert(result["report"]["total_score"] == 76, "score should come from mocked Kimi response")
            _assert(result["report"]["schema_version"] == "questionnaire_profile.v1", "schema version should be set")
            _assert(result["memory_written"] is True, "questionnaire should write memory")

            failed = _run_cli_failure(
                env,
                [
                    "--memory-path",
                    memory_path,
                    "questionnaire",
                    "submit",
                    "--id",
                    "risk_control",
                    "--user-id",
                    "kimi_e2e",
                    "--answers-json",
                    json.dumps(
                        [
                            {"question_id": "q11", "answer": "单笔最多亏损总资金的2%。"}
                        ],
                        ensure_ascii=False,
                    ),
                ],
            )
            _assert(failed.returncode == 2, "missing questionnaire answers should fail validation")
            _assert("missing_question_ids" in failed.stderr, "failure should report missing ids")

            print("questionnaire Kimi e2e passed")
            print(
                json.dumps(
                    {
                        "questionnaire_id": result["questionnaire"]["id"],
                        "score": result["report"]["total_score"],
                        "trace": trace_names,
                        "memory_path": memory_path,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
    finally:
        mock_server.shutdown()
        mock_server.server_close()
    return 0


def _run_cli(env: dict[str, str], args: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, "-m", "backend.app.cli", *args],
        cwd=str(ROOT),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"CLI failed:\nSTDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}")
    return json.loads(completed.stdout)


def _run_cli_failure(env: dict[str, str], args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "backend.app.cli", *args],
        cwd=str(ROOT),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    raise SystemExit(main())
