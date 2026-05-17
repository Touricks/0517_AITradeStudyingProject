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
from urllib import request
from urllib.error import HTTPError


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.memory import MemoryStore
from backend.app.orchestrator import Orchestrator
from backend.app.server import ApiHandler


def main() -> int:
    market_server = _start_market_mock()
    market_base_url = f"http://127.0.0.1:{market_server.server_port}"
    os.environ["EASTMONEY_REPORT_BASE_URL"] = market_base_url
    os.environ["EASTMONEY_PUSH2_BASE_URL"] = market_base_url
    os.environ["EASTMONEY_PUSH2HIS_BASE_URL"] = market_base_url
    os.environ["TENCENT_KLINE_BASE_URL"] = market_base_url
    os.environ["EASTMONEY_ANNOUNCEMENT_BASE_URL"] = market_base_url
    os.environ["EASTMONEY_HSF10_BASE_URL"] = market_base_url
    os.environ["DUCKDUCKGO_SEARCH_BASE_URL"] = market_base_url
    with tempfile.TemporaryDirectory() as tmpdir:
        server = _start_server(Path(tmpdir) / "memory.json")
        base_url = f"http://127.0.0.1:{server.server_port}"
        try:
            assert_json("GET", f"{base_url}/health", expected={"status": "ok"})
            cors = request.urlopen(request.Request(f"{base_url}/api/questionnaires", method="OPTIONS"), timeout=5)
            assert cors.status == 204, f"expected OPTIONS 204, got {cors.status}"
            assert cors.headers.get("Access-Control-Allow-Origin") == "*"

            questionnaires = assert_json("GET", f"{base_url}/api/questionnaires")
            ids = [item["id"] for item in questionnaires["questionnaires"]]
            assert "full_assessment" in ids, "full_assessment missing from questionnaire list"

            full = assert_json("GET", f"{base_url}/api/questionnaires/full_assessment")
            assert full["id"] == "full_assessment"
            assert len(full["questions"]) == 40, f"expected 40 questions, got {len(full['questions'])}"

            market = assert_json("GET", f"{base_url}/api/market/kline?symbol=300059&limit=4")
            assert market["available"] is True, "market kline should be available from mock provider"
            assert market["quote"]["symbol"] == "300059", "market quote symbol mismatch"
            assert len(market["kline"]) == 4, f"expected 4 kline rows, got {len(market['kline'])}"
            invalid_market = assert_json("GET", f"{base_url}/api/market/kline?symbol=abc")
            assert invalid_market["available"] is False, "invalid market symbol should not be available"

            answers = [{"question_id": item["id"], "answer": ""} for item in full["questions"]]
            answers[0]["answer"] = "我认为最重要的是控制亏损和风险回报比。"
            answers[10]["answer"] = "单笔最多亏损总资金的2%。"
            answers[11]["answer"] = "买入前设置止损，依据是计划失效条件。"
            assessment = assert_json(
                "POST",
                f"{base_url}/api/questionnaires/full_assessment/submit",
                {
                    "user_id": "http_smoke",
                    "use_llm": False,
                    "answers": answers,
                },
            )
            assert assessment["intent"] == "questionnaire_assessment"
            assert assessment["memory_written"] is True

            training = assert_json(
                "POST",
                f"{base_url}/api/training/check",
                {
                    "user_id": "http_smoke",
                    "scenario": "add",
                    "use_llm": False,
                    "message": "我今天买入300059，仓位30%，现在想加仓",
                    "trade_plan": {
                        "stock": "300059",
                        "position": 30,
                        "reason": "最近三天涨得很强",
                        "holding_period": "短线",
                        "emotion": "担心踏空",
                    },
                },
            )
            assert training["intent"] == "add_position_training"
            assert training["report"]["scenario"] == "add"

            review = assert_json(
                "POST",
                f"{base_url}/api/review/run",
                {
                    "user_id": "http_smoke",
                    "use_llm": False,
                    "self_reflection": "下跌后临时改变计划。",
                    "trade_table": [
                        {"field": "股票", "value": "300059"},
                        {"field": "买入价格", "value": "18.6"},
                        {"field": "卖出价格", "value": "17.2"},
                        {"field": "仓位比例", "value": "50"},
                        {"field": "买入理由", "value": "短期上涨"},
                        {"field": "原计划是否执行", "value": "否"},
                    ],
                },
            )
            assert review["intent"] == "trade_review"
            assert review["report"]["trade_document"]["stock"] == "300059"

            memory = assert_json("GET", f"{base_url}/api/memory")
            assert "http_smoke" in memory["user_profiles"], "profile was not written"
            assert len(memory["session_memories"]) >= 3, "expected memory writes from assessment/training/review"

            print("frontend HTTP contract smoke passed")
            print(json.dumps({"base_url": base_url, "questionnaire_count": len(ids)}, ensure_ascii=False, indent=2))
        finally:
            server.shutdown()
            server.server_close()
            market_server.shutdown()
            market_server.server_close()
    return 0


class MockMarketHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path.startswith("/api/qt/stock/get"):
            self._send_json(
                {
                    "rc": 0,
                    "data": {
                        "f43": 1973,
                        "f44": 2033,
                        "f45": 1967,
                        "f46": 2017,
                        "f47": 3695445,
                        "f48": 7371275659.34,
                        "f50": 93,
                        "f57": "300059",
                        "f58": "东方财富",
                        "f60": 2018,
                        "f168": 277,
                        "f169": -45,
                        "f170": -223,
                    },
                }
            )
            return
        if self.path.startswith("/api/qt/stock/kline/get"):
            self._send_json(
                {
                    "rc": 0,
                    "data": {
                        "code": "300059",
                        "klines": [
                            "2026-05-11,20.80,21.10,21.20,20.60,1000,2100000.00,2.88,1.44,0.30,1.10",
                            "2026-05-12,21.10,21.30,21.45,20.90,1100,2343000.00,2.61,0.95,0.20,1.20",
                            "2026-05-13,21.30,20.95,21.35,20.80,1200,2514000.00,2.58,-1.64,-0.35,1.30",
                            "2026-05-14,20.95,20.18,21.00,20.10,1300,2623400.00,4.30,-3.68,-0.77,1.40",
                            "2026-05-15,20.17,19.73,20.33,19.67,1400,2762200.00,3.27,-2.23,-0.45,1.50",
                        ],
                    },
                }
            )
            return
        if self.path.startswith("/appstock/app/fqkline/get"):
            self._send_json(
                {
                    "code": 0,
                    "msg": "",
                    "data": {
                        "sz300059": {
                            "qfqday": [
                                ["2026-05-11", "20.80", "21.10", "21.20", "20.60", "1000"],
                                ["2026-05-12", "21.10", "21.30", "21.45", "20.90", "1100"],
                                ["2026-05-13", "21.30", "20.95", "21.35", "20.80", "1200"],
                                ["2026-05-14", "20.95", "20.18", "21.00", "20.10", "1300"],
                                ["2026-05-15", "20.17", "19.73", "20.33", "19.67", "1400"],
                            ]
                        }
                    },
                }
            )
            return
        if self.path.startswith("/api/security/ann"):
            self._send_json({"data": {"list": []}, "success": 1})
            return
        if self.path.startswith("/PC_HSF10/CompanySurvey/PageAjax"):
            self._send_json(
                {
                    "jbzl": [
                        {
                            "SECURITY_CODE": "300059",
                            "SECURITY_NAME_ABBR": "东方财富",
                            "ORG_NAME": "东方财富信息股份有限公司",
                            "TRADE_MARKET": "深圳证券交易所",
                            "SECURITY_TYPE": "深交所创业板A股",
                            "EM2016": "互联网-互联网金融",
                            "INDUSTRYCSRC1": "金融业-资本市场服务",
                            "ORG_PROFILE": "公开资料，仅用于训练背景。",
                            "BUSINESS_SCOPE": "财经资讯、数据服务。",
                        }
                    ],
                    "fxxg": [{"LISTING_DATE": "2010-03-19 00:00:00"}],
                }
            )
            return
        if self.path.startswith("/html/"):
            body = '<html><body><a class="result__a" href="https://example.com/news">东方财富新闻</a><div class="result__snippet">公开新闻摘要。</div></body></html>'
            self._send_text(body)
            return
        if self.path.startswith("/report/list"):
            self._send_json({"data": []})
            return
        self._send_json({})

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send_json(self, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, text: str) -> None:
        body = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _start_market_mock() -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", _free_port()), MockMarketHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _start_server(memory_path: Path) -> ThreadingHTTPServer:
    class SmokeHandler(ApiHandler):
        orchestrator = Orchestrator(MemoryStore(memory_path))

    server = ThreadingHTTPServer(("127.0.0.1", _free_port()), SmokeHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def assert_json(method: str, url: str, payload: dict[str, Any] | None = None, expected: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with request.urlopen(req, timeout=10) as response:
            parsed = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8")
        raise AssertionError(f"{method} {url} failed: {exc.code} {body}") from exc
    if expected is not None and parsed != expected:
        raise AssertionError(f"{method} {url}: expected {expected!r}, got {parsed!r}")
    return parsed


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


if __name__ == "__main__":
    raise SystemExit(main())
