from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .models import UserProfile, new_id, profile_from_dict, utc_now


COLLECTIONS = (
    "user_profiles",
    "session_memories",
    "training_tasks",
    "trade_records",
    "assessment_results",
    "questionnaire_results",
    "review_reports",
    "tool_call_logs",
    "compliance_logs",
    "research_reports",
)


class MemoryStore:
    def __init__(self, path: str | Path | None = None):
        root = Path(__file__).resolve().parents[2]
        self.path = Path(path) if path else root / "data" / "memory_store.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({name: {} if name == "user_profiles" else [] for name in COLLECTIONS})

    def _read(self) -> dict[str, Any]:
        with self.path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        for name in COLLECTIONS:
            data.setdefault(name, {} if name == "user_profiles" else [])
        return data

    def _write(self, data: dict[str, Any]) -> None:
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)

    def snapshot(self) -> dict[str, Any]:
        return deepcopy(self._read())

    def get_profile(self, user_id: str) -> UserProfile:
        data = self._read()
        return profile_from_dict(data["user_profiles"].get(user_id, {}), user_id)

    def update_profile(self, profile: UserProfile | dict[str, Any]) -> dict[str, Any]:
        data = self._read()
        payload = profile.to_dict() if isinstance(profile, UserProfile) else profile
        payload["updated_at"] = utc_now()
        data["user_profiles"][payload["user_id"]] = payload
        self._write(data)
        return payload

    def query_memories(self, user_id: str, query: str = "", limit: int = 5) -> list[dict[str, Any]]:
        data = self._read()
        tokens = [token for token in query.replace(",", " ").replace("，", " ").split() if token]
        memories = [item for item in data["session_memories"] if item.get("user_id") == user_id]
        if tokens:
            def score(item: dict[str, Any]) -> int:
                haystack = " ".join(
                    [
                        item.get("summary", ""),
                        item.get("decision_pattern", ""),
                        " ".join(item.get("tags", [])),
                    ]
                )
                return sum(1 for token in tokens if token in haystack)

            memories = sorted(memories, key=score, reverse=True)
            memories = [item for item in memories if score(item) > 0] or memories
        return memories[:limit]

    def write_memory(
        self,
        user_id: str,
        session_type: str,
        summary: str,
        decision_pattern: str,
        tags: list[str],
        report_id: str | None = None,
    ) -> dict[str, Any]:
        data = self._read()
        memory = {
            "memory_id": new_id("mem"),
            "user_id": user_id,
            "session_type": session_type,
            "summary": summary,
            "decision_pattern": decision_pattern,
            "tags": tags,
            "report_id": report_id,
            "created_at": utc_now(),
        }
        data["session_memories"].insert(0, memory)
        self._write(data)
        return memory

    def add_record(self, collection: str, payload: dict[str, Any]) -> dict[str, Any]:
        if collection not in COLLECTIONS or collection == "user_profiles":
            raise ValueError(f"Unsupported collection: {collection}")
        data = self._read()
        data[collection].insert(0, payload)
        self._write(data)
        return payload
