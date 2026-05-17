from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    backend_url: str = "http://127.0.0.1:8000"
    timeout_seconds: float = 20.0
    enable_write_tools: bool = False


def load_settings() -> Settings:
    return Settings(
        backend_url=os.getenv("AITRADING_BACKEND_URL", "http://127.0.0.1:8000").rstrip("/"),
        timeout_seconds=float(os.getenv("AITRADING_MCP_TIMEOUT", "20")),
        enable_write_tools=_truthy(os.getenv("AITRADING_MCP_ENABLE_WRITE_TOOLS", "")),
    )


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}
