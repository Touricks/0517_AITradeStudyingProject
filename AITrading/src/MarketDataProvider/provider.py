"""Provider orchestration for market data.

Concrete fetchers live behind the same public methods so training, review, and
research engines can consume market background without knowing vendor URLs.
"""

from __future__ import annotations

from collections.abc import Callable
from statistics import pstdev
from typing import Any

from .registry import active_http_sources
from .types import Capability, DataResult, Market, ProviderError


Fetcher = Callable[..., Any]


class MarketDataProvider:
    """Unified market data facade with explicit fallback reporting."""

    def __init__(self) -> None:
        self._fetchers: dict[str, Fetcher] = {}

    def register_fetcher(self, source_id: str, fetcher: Fetcher) -> None:
        """Register a concrete fetcher for a source id from the registry."""

        self._fetchers[source_id] = fetcher

    def search_reports(
        self,
        query: str,
        brokers: list[str] | None = None,
        report_type: str | None = None,
        limit: int = 5,
    ) -> DataResult:
        return self._run_chain(
            "research",
            "A",
            query=query,
            brokers=brokers or [],
            report_type=report_type,
            limit=limit,
        )

    def get_quote(self, symbol: str, market: Market = "A") -> DataResult:
        return self._run_chain("quote", market, symbol=symbol, market=market)

    def get_kline(
        self,
        symbol: str,
        market: Market = "A",
        period: str = "daily",
        start: str | None = None,
        end: str | None = None,
    ) -> DataResult:
        return self._run_chain(
            "kline",
            market,
            symbol=symbol,
            market=market,
            period=period,
            start=start,
            end=end,
        )

    def get_announcements(self, symbol: str, market: Market = "A", limit: int = 10) -> DataResult:
        return self._run_chain("announcements", market, symbol=symbol, market=market, limit=limit)

    def get_news(self, query: str, market: Market = "A", limit: int = 10) -> DataResult:
        return self._run_chain("news", market, query=query, market=market, limit=limit)

    def get_company_profile(self, symbol: str, market: Market = "A") -> DataResult:
        return self._run_chain("company_profile", market, symbol=symbol, market=market)

    def build_stock_context(
        self,
        symbol: str,
        market: Market = "A",
        report_limit: int = 3,
        news_limit: int = 5,
        announcement_limit: int = 5,
    ) -> dict[str, Any]:
        """Collect demo stock context for training background.

        The result is intentionally descriptive. It must be treated as context
        for behavior training, never as a buy/sell/hold recommendation.
        """

        quote = self.get_quote(symbol, market=market)
        klines = self.get_kline(symbol, market=market)
        announcements = self.get_announcements(symbol, market=market, limit=announcement_limit)
        profile = self.get_company_profile(symbol, market=market)

        search_name = symbol
        if isinstance(quote.data, dict) and quote.data.get("name"):
            search_name = f"{quote.data['name']} {symbol}"

        news = self.get_news(f"{search_name} 股票 新闻 事件", market=market, limit=news_limit)
        reports = self.search_reports(f"{search_name} 研报 资讯 风险", limit=report_limit)

        return {
            "symbol": symbol,
            "market": market,
            "quote": _result_payload(quote),
            "kline": _result_payload(klines),
            "technical": _technical_summary(klines.data if klines.ok else []),
            "announcements": _result_payload(announcements),
            "news": _result_payload(news),
            "company_profile": _result_payload(profile),
            "reports": _result_payload(reports),
            "usage": "training_context_only",
            "compliance_note": "只用于交易能力训练背景，不输出买入、卖出、持有等投资建议。",
        }

    def _run_chain(self, capability: Capability, target_market: Market, **kwargs: Any) -> DataResult:
        errors: list[str] = []
        attempted = []

        for source in active_http_sources(capability, target_market):
            attempted.append(source.id)
            fetcher = self._fetchers.get(source.id)
            if fetcher is None:
                errors.append(f"{source.id}: no fetcher registered")
                continue

            try:
                data = fetcher(**kwargs)
            except ProviderError as exc:
                errors.append(f"{source.id}: {exc}")
                continue
            except Exception as exc:  # Keep provider failures from breaking training flows.
                errors.append(f"{source.id}: {type(exc).__name__}: {exc}")
                continue

            if data in (None, "", [], {}):
                errors.append(f"{source.id}: empty result")
                continue

            return DataResult(
                ok=True,
                data=data,
                source=source.id,
                fallback=len(errors) > 0,
                errors=errors,
                metadata={"attempted": attempted},
            )

        return DataResult(
            ok=False,
            data=None,
            source="",
            fallback=True,
            errors=errors,
            metadata={"attempted": attempted, "capability": capability, "market": target_market},
        )


def _result_payload(result: DataResult) -> dict[str, Any]:
    return {
        "ok": result.ok,
        "source": result.source,
        "fallback": result.fallback,
        "data": result.data if result.data is not None else {},
        "errors": result.errors,
        "metadata": result.metadata,
    }


def _technical_summary(rows: Any) -> dict[str, Any]:
    if not isinstance(rows, list) or not rows:
        return {"available": False}

    closes = [_as_float(row.get("close")) for row in rows if isinstance(row, dict)]
    closes = [value for value in closes if value is not None]
    if not closes:
        return {"available": False}

    latest_close = closes[-1]
    latest_row = rows[-1] if isinstance(rows[-1], dict) else {}

    summary = {
        "available": True,
        "as_of": latest_row.get("date"),
        "latest_close": latest_close,
        "change_pct_3d": _window_change_pct(closes, 3),
        "change_pct_5d": _window_change_pct(closes, 5),
        "change_pct_20d": _window_change_pct(closes, 20),
        "volatility_20d": _volatility(rows[-20:]),
        "consecutive_up_days": _consecutive_up_days(rows),
        "distance_to_ma5_pct": _distance_to_ma_pct(closes, 5),
        "distance_to_ma20_pct": _distance_to_ma_pct(closes, 20),
        "distance_to_20d_high_pct": _distance_to_range_pct(rows[-20:], "high", latest_close),
        "distance_to_20d_low_pct": _distance_to_range_pct(rows[-20:], "low", latest_close),
    }
    return summary


def _as_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _window_change_pct(values: list[float], days: int) -> float | None:
    if len(values) <= days:
        return None
    base = values[-days - 1]
    if base == 0:
        return None
    return round((values[-1] - base) / base * 100, 2)


def _volatility(rows: list[Any]) -> float | None:
    changes = [
        _as_float(row.get("change_pct"))
        for row in rows
        if isinstance(row, dict) and row.get("change_pct") not in (None, "")
    ]
    changes = [value for value in changes if value is not None]
    if len(changes) < 2:
        return None
    return round(pstdev(changes), 2)


def _consecutive_up_days(rows: list[Any]) -> int:
    count = 0
    for row in reversed(rows):
        if not isinstance(row, dict):
            break
        change = _as_float(row.get("change_pct"))
        if change is None or change <= 0:
            break
        count += 1
    return count


def _distance_to_ma_pct(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    ma = sum(values[-window:]) / window
    if ma == 0:
        return None
    return round((values[-1] - ma) / ma * 100, 2)


def _distance_to_range_pct(rows: list[Any], key: str, latest_close: float) -> float | None:
    values = [
        _as_float(row.get(key))
        for row in rows
        if isinstance(row, dict) and row.get(key) not in (None, "")
    ]
    values = [value for value in values if value is not None]
    if not values:
        return None
    target = max(values) if key == "high" else min(values)
    if target == 0:
        return None
    return round((latest_close - target) / target * 100, 2)
