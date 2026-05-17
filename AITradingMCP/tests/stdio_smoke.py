from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src")
    proc = subprocess.Popen(
        [sys.executable, "-m", "aitrading_ability_mcp.server"],
        cwd=str(ROOT),
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert proc.stdin is not None
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "aitrading_extract_user_profile", "arguments": {"unexpected": "field"}},
        },
    ]
    payload = b"".join(_frame(message) for message in messages)
    stdout, stderr = proc.communicate(payload, timeout=5)
    if proc.returncode != 0:
        sys.stderr.write(stderr.decode("utf-8", errors="replace"))
        return proc.returncode or 1

    responses = _parse_frames(stdout)
    assert [item["id"] for item in responses] == [1, 2, 3]
    assert responses[0]["result"]["serverInfo"]["name"] == "aitrading-ability-mcp"
    names = [tool["name"] for tool in responses[1]["result"]["tools"]]
    assert "aitrading_extract_user_profile" in names
    assert "aitrading_get_user_profile_raw" in names
    assert "aitrading_check_behavior_plan" not in names
    assert responses[2]["result"]["isError"] is True
    error_text = responses[2]["result"]["content"][0]["text"]
    assert "validation_error" in error_text
    print(json.dumps({"ok": True, "tool_count": len(names)}, ensure_ascii=False))
    return 0


def _frame(message: dict[str, Any]) -> bytes:
    return json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"


def _parse_frames(raw: bytes) -> list[dict[str, Any]]:
    return [json.loads(line.decode("utf-8")) for line in raw.splitlines() if line.strip()]


if __name__ == "__main__":
    raise SystemExit(main())
