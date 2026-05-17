"""Market data source registry.

This mirrors the reference project's registry pattern: source metadata is pure
configuration, while fetchers report actual runtime success or failure.
"""

from __future__ import annotations

from .types import Capability, DataSource, Market


SOURCES: list[DataSource] = [
    DataSource(
        id="eastmoney_report",
        name="东方财富研报",
        base_url="https://reportapi.eastmoney.com",
        markets=("A",),
        capabilities=("research",),
        tier=1,
        access="http",
        health="known_good",
        notes="Primary source for broker research search planned in docs/plan.md.",
    ),
    DataSource(
        id="cninfo",
        name="巨潮资讯",
        base_url="http://www.cninfo.com.cn",
        markets=("A",),
        capabilities=("announcements", "financials", "company_profile"),
        tier=1,
        access="http",
        health="known_good",
        notes="Legal disclosure source for A-share announcements.",
    ),
    DataSource(
        id="eastmoney_announcements",
        name="东方财富公告",
        base_url="https://np-anotice-stock.eastmoney.com",
        markets=("A",),
        capabilities=("announcements",),
        tier=0,
        access="http",
        health="known_good",
        notes="No-key announcement source for demo stock context.",
    ),
    DataSource(
        id="eastmoney_profile",
        name="东方财富 F10 公司资料",
        base_url="https://emweb.securities.eastmoney.com",
        markets=("A",),
        capabilities=("company_profile",),
        tier=0,
        access="http",
        health="known_good",
        notes="No-key company profile source for demo stock context.",
    ),
    DataSource(
        id="akshare",
        name="AkShare",
        base_url="https://akshare.akfamily.xyz",
        markets=("A", "H", "U"),
        capabilities=("kline", "financials", "announcements", "news"),
        tier=1,
        access="akshare",
        health="known_good",
        notes="Free Python data engine; install dependency before enabling.",
    ),
    DataSource(
        id="eastmoney_push2",
        name="东方财富 push2",
        base_url="https://push2.eastmoney.com/api/qt/stock/get",
        markets=("A", "H", "U"),
        capabilities=("quote", "kline"),
        tier=0,
        access="http",
        health="blocked_often",
        notes="Useful but often blocked; always keep a fallback after it.",
    ),
    DataSource(
        id="tencent_fqkline",
        name="腾讯前复权 K 线",
        base_url="https://web.ifzq.gtimg.cn/appstock/app/fqkline/get",
        markets=("A",),
        capabilities=("kline",),
        tier=0,
        access="http",
        health="known_good",
        notes="No-key daily K-line fallback for demo chart rendering.",
    ),
    DataSource(
        id="tencent_qt",
        name="腾讯行情 qt",
        base_url="http://qt.gtimg.cn",
        markets=("A", "H", "U"),
        capabilities=("quote",),
        tier=1,
        access="http",
        health="known_good",
        notes="No-key quote fallback used by the reference project.",
    ),
    DataSource(
        id="sina_quote",
        name="新浪财经行情",
        base_url="http://hq.sinajs.cn",
        markets=("A", "H", "U"),
        capabilities=("quote",),
        tier=1,
        access="http",
        health="flaky",
        notes="Secondary quote fallback.",
    ),
    DataSource(
        id="xueqiu",
        name="雪球",
        base_url="https://stock.xueqiu.com",
        markets=("A", "H"),
        capabilities=("quote", "company_profile", "sentiment"),
        tier=2,
        access="browser",
        health="needs_key",
        notes="Some endpoints need login/cookies; keep opt-in.",
    ),
    DataSource(
        id="duckduckgo",
        name="DuckDuckGo Search",
        base_url="https://duckduckgo.com",
        markets=("A", "H", "U"),
        capabilities=("news", "sentiment"),
        tier=0,
        access="search",
        health="flaky",
        notes="Use for event background only; filter aggressively.",
    ),
]


def by_capability(capability: Capability, market: Market | None = None) -> list[DataSource]:
    """Return sources that can support a capability, ordered by tier."""

    candidates = [
        source
        for source in SOURCES
        if capability in source.capabilities and (market is None or market in source.markets)
    ]
    return sorted(candidates, key=lambda source: source.tier)


def active_http_sources(capability: Capability, market: Market | None = None) -> list[DataSource]:
    """Return non-disabled HTTP-style sources suitable for first-pass fetchers."""

    return [
        source
        for source in by_capability(capability, market)
        if source.health != "disabled" and source.access in {"http", "akshare", "search"}
    ]
