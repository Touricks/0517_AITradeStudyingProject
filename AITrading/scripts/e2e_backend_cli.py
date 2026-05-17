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


MOCK_REPORTS = {
    "data": [
        {
            "title": "东方财富交易行为训练相关公开研报",
            "orgSName": "国泰海通",
            "orgName": "国泰海通证券",
            "publishDate": "2026-05-14 00:00:00",
            "summary": "公开研报摘要，仅用于训练背景，不构成投资建议。",
            "emRatingName": "行业",
            "stockName": "东方财富",
            "stockCode": "300059",
            "infoCode": "AP202605140001",
            "encodeUrl": "mocktoken=1",
        }
    ]
}


class MockEastmoneyHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = json.dumps(MOCK_REPORTS, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        return


def main() -> int:
    mock_server = ThreadingHTTPServer(("127.0.0.1", _free_port()), MockEastmoneyHandler)
    thread = threading.Thread(target=mock_server.serve_forever, daemon=True)
    thread.start()

    env = os.environ.copy()
    mock_base_url = f"http://127.0.0.1:{mock_server.server_port}"
    env["EASTMONEY_REPORT_BASE_URL"] = mock_base_url
    env["EASTMONEY_PUSH2_BASE_URL"] = mock_base_url
    env["EASTMONEY_PUSH2HIS_BASE_URL"] = mock_base_url
    env["EASTMONEY_ANNOUNCEMENT_BASE_URL"] = mock_base_url
    env["EASTMONEY_HSF10_BASE_URL"] = mock_base_url
    env["DUCKDUCKGO_SEARCH_BASE_URL"] = mock_base_url
    env["PYTHONPATH"] = str(ROOT)

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            memory_path = str(Path(tmpdir) / "memory.json")
            research = _run_cli(
                env,
                [
                    "--memory-path",
                    memory_path,
                    "research",
                    "--query",
                    "300059 东方财富 研报",
                    "--limit",
                    "2",
                ],
            )
            _assert(research["available"] is True, "research should be available")
            _assert(research["provider"] == "eastmoney_report", "research should use provider facade")
            _assert(len(research["reports"]) == 1, "research should return one mocked report")

            training = _run_cli(
                env,
                [
                    "--memory-path",
                    memory_path,
                    "training",
                    "--user-id",
                    "cli_e2e",
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
            )
            trace_names = [item["name"] for item in training["tool_trace"]]
            _assert(training["intent"] == "add_position_training", "training intent should classify add-position")
            _assert("stock_context_import" in trace_names, "training should invoke stock context import")
            _assert(training["report"]["research_context_used"] == 1, "training should consume mocked research context")
            _assert(training["memory_written"] is True, "training should write memory")

            print("backend CLI e2e passed")
            print(
                json.dumps(
                    {
                        "research_provider": research["provider"],
                        "training_intent": training["intent"],
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


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    raise SystemExit(main())
