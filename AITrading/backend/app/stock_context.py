from __future__ import annotations

import re
from typing import Any

from src.MarketDataProvider import create_demo_provider


STOCK_CODE_PATTERN = re.compile(r"\b(\d{6})\b")


def build_stock_context_for_prompt(
    trade_plan: dict[str, Any],
    message: str = "",
    market: str = "A",
    report_limit: int = 3,
    news_limit: int = 5,
    announcement_limit: int = 5,
) -> dict[str, Any]:
    """Build compact stock context for LLM training prompts.

    The provider may return vendor-specific raw payloads. This module keeps the
    prompt surface small, descriptive, and explicitly non-advisory.
    """

    symbol = extract_stock_symbol(trade_plan, message)
    if not symbol:
        return {
            "available": False,
            "symbol": "",
            "market": market,
            "prompt_context": {
                "usage": "training_context_only",
                "reason": "未识别到 6 位股票代码，未拉取股票上下文。",
            },
            "raw_context": {},
        }

    provider = create_demo_provider()
    raw_context = provider.build_stock_context(
        symbol=symbol,
        market=market,
        report_limit=report_limit,
        news_limit=news_limit,
        announcement_limit=announcement_limit,
    )
    prompt_context = compact_stock_context(raw_context)
    return {
        "available": _has_any_success(raw_context),
        "symbol": symbol,
        "market": market,
        "prompt_context": prompt_context,
        "raw_context": raw_context,
        "reports": _items(raw_context.get("reports"), limit=report_limit),
    }


def extract_stock_symbol(trade_plan: dict[str, Any], message: str = "") -> str:
    candidates = [
        trade_plan.get("stock"),
        trade_plan.get("symbol"),
        trade_plan.get("股票名称/代码"),
        trade_plan.get("股票"),
        message,
        " ".join(str(value) for value in trade_plan.values()),
    ]
    for value in candidates:
        match = STOCK_CODE_PATTERN.search(str(value or ""))
        if match:
            return match.group(1)
    return ""


def compact_stock_context(raw_context: dict[str, Any]) -> dict[str, Any]:
    quote = _dict_data(raw_context.get("quote"))
    profile = _dict_data(raw_context.get("company_profile"))
    technical = raw_context.get("technical") if isinstance(raw_context.get("technical"), dict) else {}

    return {
        "usage": "training_context_only",
        "compliance_note": raw_context.get("compliance_note", "只用于交易能力训练背景，不构成投资建议。"),
        "symbol": raw_context.get("symbol", ""),
        "market": raw_context.get("market", "A"),
        "quote": _compact_quote(quote),
        "technical": _compact_technical(technical),
        "company_profile": _compact_profile(profile),
        "announcements": _compact_items(raw_context.get("announcements"), ("title", "date", "columns", "url"), limit=5),
        "news": _compact_items(raw_context.get("news"), ("title", "summary", "url"), limit=5),
        "reports": _compact_items(raw_context.get("reports"), ("title", "broker", "date", "summary", "type", "url"), limit=3),
        "source_status": _source_status(raw_context),
        "behavior_observation_hints": _behavior_observation_hints(quote, technical),
    }


def _compact_quote(quote: dict[str, Any]) -> dict[str, Any]:
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


def _compact_technical(technical: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "available",
        "as_of",
        "latest_close",
        "change_pct_3d",
        "change_pct_5d",
        "change_pct_20d",
        "volatility_20d",
        "consecutive_up_days",
        "distance_to_ma5_pct",
        "distance_to_ma20_pct",
        "distance_to_20d_high_pct",
        "distance_to_20d_low_pct",
    )
    return {key: technical.get(key) for key in keys if technical.get(key) not in (None, "")}


def _compact_profile(profile: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "symbol",
        "name",
        "org_name",
        "market",
        "security_type",
        "industry",
        "csrc_industry",
        "listing_date",
        "profile",
        "business_scope",
    )
    compacted = {key: profile.get(key) for key in keys if profile.get(key) not in (None, "")}
    for key in ("profile", "business_scope"):
        if isinstance(compacted.get(key), str) and len(compacted[key]) > 240:
            compacted[key] = compacted[key][:240] + "..."
    return compacted


def _compact_items(result_payload: Any, keys: tuple[str, ...], limit: int) -> dict[str, Any]:
    return {
        "ok": bool(isinstance(result_payload, dict) and result_payload.get("ok")),
        "source": result_payload.get("source", "") if isinstance(result_payload, dict) else "",
        "items": [_pick(item, keys) for item in _items(result_payload, limit=limit)],
        "errors": _errors(result_payload),
    }


def _items(result_payload: Any, limit: int) -> list[dict[str, Any]]:
    data = _data(result_payload)
    if not isinstance(data, list):
        return []
    return [item for item in data[:limit] if isinstance(item, dict)]


def _data(result_payload: Any) -> Any:
    if isinstance(result_payload, dict):
        return result_payload.get("data")
    return None


def _dict_data(result_payload: Any) -> dict[str, Any]:
    data = _data(result_payload)
    return data if isinstance(data, dict) else {}


def _errors(result_payload: Any) -> list[str]:
    if isinstance(result_payload, dict) and isinstance(result_payload.get("errors"), list):
        return [str(item) for item in result_payload["errors"][:3]]
    return []


def _source_status(raw_context: dict[str, Any]) -> dict[str, Any]:
    status = {}
    for key in ("quote", "kline", "announcements", "news", "company_profile", "reports"):
        payload = raw_context.get(key)
        if isinstance(payload, dict):
            status[key] = {
                "ok": bool(payload.get("ok")),
                "source": payload.get("source", ""),
                "fallback": bool(payload.get("fallback")),
                "errors": _errors(payload),
            }
    return status


def _behavior_observation_hints(quote: dict[str, Any], technical: dict[str, Any]) -> list[str]:
    hints = []
    change_3d = _as_float(technical.get("change_pct_3d"))
    change_5d = _as_float(technical.get("change_pct_5d"))
    consecutive_up_days = _as_float(technical.get("consecutive_up_days")) or 0
    quote_change = _as_float(quote.get("change_pct"))
    turnover = _as_float(quote.get("turnover_rate"))

    if (change_3d is not None and change_3d >= 8) or (change_5d is not None and change_5d >= 12) or consecutive_up_days >= 3:
        hints.append("近期涨幅或连续上涨较明显，需检查买入理由是否被追涨/FOMO驱动。")
    if quote_change is not None and abs(quote_change) >= 5:
        hints.append("当日波动较大，需确认计划中的风险边界是否足以覆盖波动。")
    if turnover is not None and turnover >= 8:
        hints.append("换手率偏高，需区分题材热度与可验证交易逻辑。")
    return hints


def _pick(item: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    picked = {key: item.get(key) for key in keys if item.get(key) not in (None, "", [])}
    for key in ("summary", "title"):
        if isinstance(picked.get(key), str) and len(picked[key]) > 180:
            picked[key] = picked[key][:180] + "..."
    return picked


def _has_any_success(raw_context: dict[str, Any]) -> bool:
    return any(
        isinstance(raw_context.get(key), dict) and raw_context[key].get("ok")
        for key in ("quote", "kline", "announcements", "news", "company_profile", "reports")
    )


def _as_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
