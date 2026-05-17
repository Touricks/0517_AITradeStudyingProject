"""Shared types for market data providers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


Market = Literal["A", "H", "U"]
Capability = Literal[
    "quote",
    "kline",
    "financials",
    "research",
    "announcements",
    "news",
    "company_profile",
    "sentiment",
]
AccessMethod = Literal["http", "akshare", "browser", "search"]
Health = Literal["known_good", "flaky", "blocked_often", "needs_key", "disabled"]


class ProviderError(RuntimeError):
    """Raised when a provider cannot fulfill a request."""


@dataclass(frozen=True)
class DataSource:
    """Static source metadata used to build fallback chains."""

    id: str
    name: str
    base_url: str
    markets: tuple[Market, ...]
    capabilities: tuple[Capability, ...]
    tier: int
    access: AccessMethod
    health: Health
    notes: str = ""


@dataclass
class DataResult:
    """Normalized provider response envelope.

    Business logic should inspect ``ok`` and ``data`` instead of assuming that a
    missing source means a weak trading signal. ``errors`` keeps failed fallback
    attempts visible for diagnostics.
    """

    ok: bool
    data: Any = None
    source: str = ""
    fallback: bool = False
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
