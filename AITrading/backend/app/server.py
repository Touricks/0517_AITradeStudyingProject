from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from .market import market_kline_response
from .memory import MemoryStore
from .orchestrator import Orchestrator
from .questionnaire_engine import QuestionnaireAnswerValidationError, run_questionnaire_assessment
from .questionnaire_store import QuestionnaireNotFound, get_questionnaire, list_questionnaires
from .research import broker_report_search
from .training_agent import run_training_check


class ApiHandler(BaseHTTPRequestHandler):
    orchestrator = Orchestrator(MemoryStore())

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._send_common_headers()
        self.end_headers()

    def do_GET(self) -> None:
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        if path == "/health":
            self._send(200, {"status": "ok"})
            return
        if path == "/api/market/kline":
            query = parse_qs(parsed_url.query)
            self._send(
                200,
                market_kline_response(
                    symbol=_first_query_value(query, "symbol"),
                    market=_first_query_value(query, "market") or "A",
                    limit=_int_query_value(query, "limit", default=120),
                ),
            )
            return
        if path == "/api/memory":
            self._send(200, self.orchestrator.store.snapshot())
            return
        if path == "/api/questionnaires":
            self._send(200, {"questionnaires": list_questionnaires()})
            return
        if path.startswith("/api/questionnaires/"):
            questionnaire_id = path.rsplit("/", 1)[-1]
            try:
                self._send(200, get_questionnaire(questionnaire_id))
            except QuestionnaireNotFound:
                self._send(404, {"error": "questionnaire_not_found", "questionnaire_id": questionnaire_id})
            return
        self._send(404, {"error": "not_found", "path": path})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        payload = self._read_json()
        routes = {
            "/api/orchestrate": self._orchestrate,
            "/api/assessment/run": lambda body: self._orchestrate({"entry": "assessment", **body}),
            "/api/assessment/full": self._assessment_full,
            "/api/training/check": self._training_check,
            "/api/review/run": lambda body: self._orchestrate({"entry": "review", **body}),
            "/api/research/search": self._research,
        }
        handler = routes.get(path)
        if handler is None and path.startswith("/api/questionnaires/") and path.endswith("/submit"):
            parts = [part for part in path.split("/") if part]
            if len(parts) == 4:
                handler = lambda body, questionnaire_id=parts[2]: self._questionnaire_submit(questionnaire_id, body)
        if not handler:
            self._send(404, {"error": "not_found", "path": path})
            return
        try:
            self._send(200, handler(payload))
        except QuestionnaireAnswerValidationError as exc:
            self._send(400, {"error": "invalid_questionnaire_answers", "detail": str(exc)})
        except Exception as exc:
            self._send(500, {"error": "internal_error", "detail": str(exc)})

    def _orchestrate(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.orchestrator.run(payload)

    def _training_check(self, payload: dict[str, Any]) -> dict[str, Any]:
        return run_training_check(self.orchestrator.store, {**payload, "entry": "training"})

    def _research(self, payload: dict[str, Any]) -> dict[str, Any]:
        return broker_report_search(payload.get("query") or "", limit=int(payload.get("limit", 5)))

    def _assessment_full(self, payload: dict[str, Any]) -> dict[str, Any]:
        questionnaire_id = payload.get("questionnaire_id") or "full_assessment"
        return self._questionnaire_submit(questionnaire_id, payload)

    def _questionnaire_submit(self, questionnaire_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return run_questionnaire_assessment(
            store=self.orchestrator.store,
            user_id=payload.get("user_id") or "demo_user",
            questionnaire_id=questionnaire_id,
            answers=payload.get("answers") or [],
            use_llm=payload.get("use_llm", True) is not False,
        )

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw) if raw else {}

    def _send(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self._send_common_headers()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_common_headers(self) -> None:
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Max-Age", "86400")

    def log_message(self, format: str, *args: Any) -> None:
        return


def _first_query_value(query: dict[str, list[str]], key: str) -> str:
    values = query.get(key) or []
    return values[0] if values else ""


def _int_query_value(query: dict[str, list[str]], key: str, default: int) -> int:
    try:
        return int(_first_query_value(query, key) or default)
    except ValueError:
        return default


def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), ApiHandler)
    print(f"AI Trading backend listening on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
