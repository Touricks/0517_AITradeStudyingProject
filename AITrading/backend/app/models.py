from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


COMPLIANCE_NOTICE = "本系统仅用于投资教育与交易能力训练，不构成任何投资建议、个股推荐或买卖信号。"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


@dataclass
class ToolTrace:
    name: str
    status: str
    detail: str = ""
    input_summary: dict[str, Any] = field(default_factory=dict)
    output_summary: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class UserProfile:
    user_id: str
    trader_type: str = "经验型散户"
    total_score: int = 50
    dimension_scores: dict[str, int] = field(
        default_factory=lambda: {
            "market_understanding": 10,
            "analysis_framework": 10,
            "risk_control": 10,
            "execution_discipline": 10,
            "review_ability": 10,
        }
    )
    risk_tags: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    training_stage: str = "foundation"
    risk_level: str = "medium"
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def profile_from_dict(raw: dict[str, Any], user_id: str) -> UserProfile:
    if not raw:
        return UserProfile(user_id=user_id)
    base = UserProfile(user_id=user_id).to_dict()
    base.update(raw)
    base["user_id"] = user_id
    return UserProfile(**base)


def clamp(value: int, low: int = 0, high: int = 20) -> int:
    return max(low, min(high, value))


def normalize_entry(entry: str | None, message: str = "") -> str:
    if entry in {"assessment", "training", "review", "demo"}:
        return entry
    text = message or ""
    if any(word in text for word in ("复盘", "卖出", "亏损后", "总结")):
        return "review"
    if any(word in text for word in ("评估", "水平", "能力", "题单")):
        return "assessment"
    return "training"

