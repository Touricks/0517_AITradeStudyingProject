from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = "https://api.moonshot.cn/v1"
DEFAULT_MODEL = "moonshot-v1-8k"


class LLMError(RuntimeError):
    """Raised when the OpenAI-compatible LLM endpoint cannot return content."""


def load_env_file(path: str | Path = "config/.env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class OpenAICompatibleClient:
    def __init__(self) -> None:
        load_env_file()
        self.base_url = os.getenv("OPENAI_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
        self.temperature = float(os.getenv("OPENAI_TEMPERATURE", "0.2"))
        if not self.api_key:
            raise LLMError("OPENAI_API_KEY is not configured")

    def chat_json(self, messages: list[dict[str, str]], schema_name: str = "questionnaire_profile") -> dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "response_format": {"type": "json_object"},
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise LLMError(f"{schema_name} request failed: {exc}") from exc

        content = (
            raw.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        if not content:
            raise LLMError(f"{schema_name} response content is empty")
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMError(f"{schema_name} response is not valid JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise LLMError(f"{schema_name} response must be a JSON object")
        return parsed

