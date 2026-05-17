from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


class BackendError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None, details: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details


@dataclass
class AITradingClient:
    base_url: str
    timeout_seconds: float = 20.0

    def get(self, path: str) -> dict[str, Any]:
        return self._request("GET", path)

    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", path, payload)

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        url = urllib.parse.urljoin(f"{self.base_url}/", path.lstrip("/"))
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            detail = _safe_read_error(exc)
            raise BackendError(f"Backend returned HTTP {exc.code}", exc.code, detail) from exc
        except urllib.error.URLError as exc:
            raise BackendError(f"Backend unavailable: {exc.reason}") from exc
        except TimeoutError as exc:
            raise BackendError("Backend request timed out") from exc
        except json.JSONDecodeError as exc:
            raise BackendError(f"Backend returned invalid JSON: {exc}") from exc


def _safe_read_error(exc: urllib.error.HTTPError) -> Any:
    try:
        raw = exc.read().decode("utf-8")
    except Exception:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw

