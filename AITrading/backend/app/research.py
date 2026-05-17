from __future__ import annotations

import re
from typing import Any

from src.MarketDataProvider import MarketDataProvider, create_demo_provider


def should_search(form_data: dict[str, Any], message: str) -> bool:
    text = " ".join(str(value) for value in form_data.values()) + " " + message
    has_named_asset = any(key in form_data for key in ("stock", "symbol", "股票名称/代码"))
    has_stock_code = bool(_extract_stock_code(text))
    return has_named_asset or has_stock_code or any(key in text for key in ("股票", "代码", "行业", "板块", "研报", "公告", "政策"))


def build_query(form_data: dict[str, Any], message: str) -> str:
    stock = form_data.get("stock") or form_data.get("symbol") or form_data.get("股票名称/代码")
    topic = stock or message[:80] or "交易计划背景"
    return f"{topic} 研报 资讯 风险"


def broker_report_search(query: str, limit: int = 5) -> dict[str, Any]:
    provider = _build_provider()
    result = provider.search_reports(query=query, limit=limit)
    if not result.ok:
        return {
            "available": False,
            "reports": [],
            "message": "公开研报检索暂不可用，已跳过背景信息补充。",
            "provider": result.source,
            "fallback": result.fallback,
            "errors": result.errors,
            "metadata": result.metadata,
        }

    reports = result.data[:limit] if isinstance(result.data, list) else []
    return {
        "available": bool(reports),
        "reports": reports,
        "message": f"已检索到 {len(reports)} 条公开研报背景信息。" if reports else "未检索到匹配的公开研报背景信息。",
        "provider": result.source,
        "fallback": result.fallback,
        "errors": result.errors,
        "metadata": result.metadata,
    }


def _build_provider() -> MarketDataProvider:
    return create_demo_provider()


def _extract_stock_code(query: str) -> str:
    match = re.search(r"\b(\d{6})\b", query)
    return match.group(1) if match else ""
