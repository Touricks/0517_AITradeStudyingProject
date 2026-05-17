from __future__ import annotations

import re
from statistics import pstdev
from typing import Any

from src.MarketDataProvider import create_demo_provider


STOCK_CODE_PATTERN = re.compile(r"(?<!\d)(\d{6})(?!\d)")
COMPLIANCE_NOTE = "公开行情只作为交易能力训练背景，不构成买入、卖出、持有或加仓建议。"


def market_kline_response(symbol: str, market: str = "A", limit: int = 120) -> dict[str, Any]:
    code = _extract_stock_code(symbol)
    if not code:
        return _unavailable(symbol=symbol, market=market, errors=["symbol must contain a 6-digit A-share code"])
    if market != "A":
        return _unavailable(symbol=code, market=market, errors=["only A-share market is supported in demo mode"])

    limit = max(1, min(int(limit or 120), 260))
    provider = create_demo_provider()
    quote_result = provider.get_quote(code, market="A")
    kline_result = provider.get_kline(code, market="A")

    rows = _compact_kline(kline_result.data if kline_result.ok else [], limit=limit)
    errors = [*quote_result.errors, *kline_result.errors]
    return {
        "available": bool(rows),
        "symbol": code,
        "market": "A",
        "source": kline_result.source,
        "fallback": bool(quote_result.fallback or kline_result.fallback),
        "errors": errors,
        "quote": _compact_quote(quote_result.data if quote_result.ok else {}),
        "kline": rows,
        "technical": _technical_summary(rows),
        "compliance_note": COMPLIANCE_NOTE,
    }


def _unavailable(symbol: str, market: str, errors: list[str]) -> dict[str, Any]:
    return {
        "available": False,
        "symbol": symbol,
        "market": market,
        "source": "",
        "fallback": False,
        "errors": errors,
        "quote": {},
        "kline": [],
        "technical": {"available": False},
        "compliance_note": COMPLIANCE_NOTE,
    }


def _extract_stock_code(symbol: str) -> str:
    match = STOCK_CODE_PATTERN.search(str(symbol or ""))
    return match.group(1) if match else ""


def _compact_quote(quote: Any) -> dict[str, Any]:
    if not isinstance(quote, dict):
        return {}
    keys = (
        "symbol",
        "name",
        "price",
        "change",
        "change_pct",
        "turnover_rate",
        "amplitude",
        "amount",
        "volume",
    )
    return {key: quote.get(key) for key in keys if quote.get(key) not in (None, "")}


def _compact_kline(rows: Any, limit: int) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    compacted = []
    for row in rows[-limit:]:
        if not isinstance(row, dict):
            continue
        compacted.append(
            {
                "date": row.get("date"),
                "open": _as_float(row.get("open")),
                "close": _as_float(row.get("close")),
                "high": _as_float(row.get("high")),
                "low": _as_float(row.get("low")),
                "volume": _as_float(row.get("volume")),
                "amount": _as_float(row.get("amount")),
                "change_pct": _as_float(row.get("change_pct")),
                "turnover_rate": _as_float(row.get("turnover_rate")),
            }
        )
    return [
        row
        for row in compacted
        if row.get("date") and all(row.get(key) is not None for key in ("open", "close", "high", "low"))
    ]


def _technical_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    closes = [row["close"] for row in rows if row.get("close") is not None]
    if not closes:
        return {"available": False}
    latest_close = closes[-1]
    return {
        "available": True,
        "as_of": rows[-1].get("date") if rows else "",
        "latest_close": latest_close,
        "change_pct_3d": _window_change_pct(closes, 3),
        "change_pct_5d": _window_change_pct(closes, 5),
        "change_pct_20d": _window_change_pct(closes, 20),
        "volatility_20d": _volatility(rows[-20:]),
    }


def _window_change_pct(values: list[float], days: int) -> float | None:
    if len(values) <= days:
        return None
    base = values[-days - 1]
    if base == 0:
        return None
    return round((values[-1] - base) / base * 100, 2)


def _volatility(rows: list[dict[str, Any]]) -> float | None:
    changes = [row.get("change_pct") for row in rows if row.get("change_pct") is not None]
    if len(changes) < 2:
        return None
    return round(pstdev(changes), 2)


def _as_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
