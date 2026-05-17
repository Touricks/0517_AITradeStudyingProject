from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

from .client import AITradingClient
from .config import load_settings
from .tools import COMPLIANCE_NOTICE, call_tool, list_tools


PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "aitrading-ability-mcp"
SERVER_VERSION = "0.1.0"

SERVER_INSTRUCTIONS = (
    "This MCP server is a read-only profile extraction adapter for the AITrading investment education backend by default. "
    "Use it to extract the user capability profile generated after the user has already completed frontend assessment/testing, "
    "including questionnaire profile, compact profile, evidence, and profile-related memories. "
    "Agents may omit user_id in a single-user local setup; the server resolves it from AITRADING_MCP_DEFAULT_USER_ID or the only user in memory. "
    "If multiple users are found, ask the user which candidate profile to use. "
    "By default it is not a testing, questionnaire submission, training, review, or CLI workflow. "
    "Write/admin tools are hidden unless AITRADING_MCP_ENABLE_WRITE_TOOLS=true. "
    "Never use it to provide stock picks, buy/sell points, trade execution, price targets, or trading signals. "
    f"Compliance notice: {COMPLIANCE_NOTICE}"
)


def main() -> None:
    settings = load_settings()
    client = AITradingClient(settings.backend_url, settings.timeout_seconds)
    server = StdioMCPServer(client)
    server.run()


class StdioMCPServer:
    def __init__(self, client: AITradingClient):
        self.client = client
        self.reader = sys.stdin.buffer
        self.writer = sys.stdout.buffer

    def run(self) -> None:
        self._debug("server_start")
        while True:
            message = self._read_message()
            if message is None:
                self._debug("stdin_eof")
                return
            response = self._handle_message(message)
            if response is not None:
                self._write_message(response)

    def _handle_message(self, message: dict[str, Any]) -> dict[str, Any] | None:
        request_id = message.get("id")
        method = message.get("method")
        params = message.get("params") or {}
        self._debug("request", {"id": request_id, "method": method})

        try:
            if method == "initialize":
                requested_protocol_version = params.get("protocolVersion") or PROTOCOL_VERSION
                return self._result(
                    request_id,
                    {
                        "protocolVersion": requested_protocol_version,
                        "capabilities": {"tools": {"listChanged": False}},
                        "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                        "instructions": SERVER_INSTRUCTIONS,
                    },
                )
            if method == "notifications/initialized":
                return None
            if method == "ping":
                return self._result(request_id, {})
            if method == "tools/list":
                return self._result(request_id, {"tools": list_tools()})
            if method == "tools/call":
                name = params.get("name")
                arguments = params.get("arguments") or {}
                is_error, payload = call_tool(self.client, name, arguments)
                return self._result(
                    request_id,
                    {
                        "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, indent=2)}],
                        "isError": is_error,
                    },
                )
            if request_id is None:
                return None
            return self._error(request_id, -32601, f"Method not found: {method}")
        except Exception as exc:
            self._debug("exception", {"method": method, "error": f"{type(exc).__name__}: {exc}"})
            if request_id is None:
                return None
            return self._error(request_id, -32603, f"Internal error: {type(exc).__name__}: {exc}")

    def _read_message(self) -> dict[str, Any] | None:
        line = self.reader.readline()
        if line == b"":
            return None
        stripped = line.strip()
        if not stripped:
            return self._read_message()
        if stripped.startswith(b"{"):
            message = json.loads(stripped.decode("utf-8"))
            if not isinstance(message, dict):
                raise ValueError("JSON-RPC message must be an object")
            return message

        headers: dict[str, str] = {}
        text = line.decode("ascii").strip()
        if ":" in text:
            key, value = text.split(":", 1)
            headers[key.lower()] = value.strip()
        while True:
            line = self.reader.readline()
            if line == b"":
                return None
            if line in (b"\r\n", b"\n"):
                break
            text = line.decode("ascii").strip()
            if ":" in text:
                key, value = text.split(":", 1)
                headers[key.lower()] = value.strip()

        length_raw = headers.get("content-length")
        if not length_raw:
            raise ValueError("Missing Content-Length header")
        length = int(length_raw)
        body = self.reader.read(length)
        if len(body) != length:
            raise ValueError("Unexpected EOF while reading message body")
        message = json.loads(body.decode("utf-8"))
        if not isinstance(message, dict):
            raise ValueError("JSON-RPC message must be an object")
        return message

    def _write_message(self, message: dict[str, Any]) -> None:
        body = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.writer.write(body)
        self.writer.write(b"\n")
        self.writer.flush()
        self._debug("response", {"id": message.get("id"), "has_error": "error" in message})

    def _result(self, request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    def _error(self, request_id: Any, code: int, message: str, data: Any = None) -> dict[str, Any]:
        error = {"code": code, "message": message}
        if data is not None:
            error["data"] = data
        return {"jsonrpc": "2.0", "id": request_id, "error": error}

    def _debug(self, event: str, data: dict[str, Any] | None = None) -> None:
        path = os.getenv("AITRADING_MCP_DEBUG_LOG")
        if not path:
            return
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "data": data or {},
        }
        try:
            with open(path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
        except Exception:
            return


if __name__ == "__main__":
    main()
