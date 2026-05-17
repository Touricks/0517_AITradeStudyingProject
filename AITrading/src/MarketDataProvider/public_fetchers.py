"""No-key public fetchers for the demo market data provider."""

from __future__ import annotations

import gzip
import html
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from .provider import MarketDataProvider
from .types import Market, ProviderError


DEFAULT_REPORT_BASE_URL = "https://reportapi.eastmoney.com"
DEFAULT_PUSH2_BASE_URL = "https://push2.eastmoney.com"
DEFAULT_PUSH2HIS_BASE_URL = "http://push2his.eastmoney.com"
DEFAULT_TENCENT_KLINE_BASE_URL = "https://web.ifzq.gtimg.cn"
DEFAULT_ANNOUNCEMENT_BASE_URL = "https://np-anotice-stock.eastmoney.com"
DEFAULT_HSF10_BASE_URL = "https://emweb.securities.eastmoney.com"
DEFAULT_DUCKDUCKGO_BASE_URL = "https://duckduckgo.com"


def create_demo_provider() -> MarketDataProvider:
    """Return a provider wired to no-key public sources for demo use."""

    provider = MarketDataProvider()
    provider.register_fetcher("eastmoney_report", fetch_eastmoney_reports)
    provider.register_fetcher("eastmoney_push2", fetch_eastmoney_push2)
    provider.register_fetcher("tencent_fqkline", fetch_tencent_fqkline)
    provider.register_fetcher("eastmoney_announcements", fetch_eastmoney_announcements)
    provider.register_fetcher("eastmoney_profile", fetch_eastmoney_company_profile)
    provider.register_fetcher("duckduckgo", fetch_duckduckgo_news)
    return provider


def fetch_eastmoney_push2(
    symbol: str,
    market: Market = "A",
    period: str | None = None,
    start: str | None = None,
    end: str | None = None,
) -> dict[str, Any] | list[dict[str, Any]]:
    if period is not None or start is not None or end is not None:
        return fetch_eastmoney_kline(symbol=symbol, market=market, period=period or "daily", start=start, end=end)
    return fetch_eastmoney_quote(symbol=symbol, market=market)


def fetch_eastmoney_quote(symbol: str, market: Market = "A") -> dict[str, Any]:
    load_env_file()
    identity = normalize_a_share_symbol(symbol)
    base_url = os.getenv("EASTMONEY_PUSH2_BASE_URL", DEFAULT_PUSH2_BASE_URL).rstrip("/")
    fields = ",".join(
        [
            "f43",
            "f44",
            "f45",
            "f46",
            "f47",
            "f48",
            "f50",
            "f57",
            "f58",
            "f60",
            "f168",
            "f169",
            "f170",
        ]
    )
    url = f"{base_url}/api/qt/stock/get?{urllib.parse.urlencode({'secid': identity['secid'], 'fields': fields})}"
    payload = _read_json(url, referer="https://quote.eastmoney.com/")
    raw = payload.get("data")
    if not isinstance(raw, dict):
        raise ProviderError("eastmoney quote returned empty data")

    return {
        "symbol": raw.get("f57") or identity["code"],
        "name": raw.get("f58") or "",
        "market": market,
        "secid": identity["secid"],
        "price": _scaled(raw.get("f43")),
        "open": _scaled(raw.get("f46")),
        "high": _scaled(raw.get("f44")),
        "low": _scaled(raw.get("f45")),
        "previous_close": _scaled(raw.get("f60")),
        "change": _scaled(raw.get("f169")),
        "change_pct": _scaled(raw.get("f170")),
        "volume": raw.get("f47"),
        "amount": raw.get("f48"),
        "turnover_rate": _scaled(raw.get("f168")),
        "amplitude": _scaled(raw.get("f50")),
        "request_url": url,
    }


def fetch_eastmoney_kline(
    symbol: str,
    market: Market = "A",
    period: str = "daily",
    start: str | None = None,
    end: str | None = None,
) -> list[dict[str, Any]]:
    load_env_file()
    identity = normalize_a_share_symbol(symbol)
    base_url = os.getenv("EASTMONEY_PUSH2HIS_BASE_URL", DEFAULT_PUSH2HIS_BASE_URL).rstrip("/")
    today = date.today()
    begin = _compact_date(start) if start else (today - timedelta(days=420)).strftime("%Y%m%d")
    finish = _compact_date(end) if end else today.strftime("%Y%m%d")
    params = {
        "secid": identity["secid"],
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": {"daily": "101", "weekly": "102", "monthly": "103"}.get(period, "101"),
        "fqt": "1",
        "beg": begin,
        "end": finish,
    }
    url = f"{base_url}/api/qt/stock/kline/get?{urllib.parse.urlencode(params)}"
    payload = _read_json(url, referer="https://quote.eastmoney.com/")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ProviderError("eastmoney kline returned empty data")

    rows = []
    for item in data.get("klines") or []:
        parts = str(item).split(",")
        if len(parts) < 11:
            continue
        rows.append(
            {
                "date": parts[0],
                "open": _to_float(parts[1]),
                "close": _to_float(parts[2]),
                "high": _to_float(parts[3]),
                "low": _to_float(parts[4]),
                "volume": _to_float(parts[5]),
                "amount": _to_float(parts[6]),
                "amplitude": _to_float(parts[7]),
                "change_pct": _to_float(parts[8]),
                "change": _to_float(parts[9]),
                "turnover_rate": _to_float(parts[10]),
            }
        )
    if not rows:
        raise ProviderError("eastmoney kline returned no rows")
    return rows


def fetch_tencent_fqkline(
    symbol: str,
    market: Market = "A",
    period: str = "daily",
    start: str | None = None,
    end: str | None = None,
) -> list[dict[str, Any]]:
    load_env_file()
    if period not in ("daily", "day"):
        raise ProviderError("tencent fqkline demo fetcher only supports daily period")

    identity = normalize_a_share_symbol(symbol)
    base_url = os.getenv("TENCENT_KLINE_BASE_URL", DEFAULT_TENCENT_KLINE_BASE_URL).rstrip("/")
    stock_key = f"{identity['exchange'].lower()}{identity['code']}"
    params = f"{stock_key},day,,,{260},qfq"
    url = f"{base_url}/appstock/app/fqkline/get?{urllib.parse.urlencode({'param': params})}"
    payload = _read_json(url, referer="https://gu.qq.com/")
    container = payload.get("data")
    stock_data = container.get(stock_key) if isinstance(container, dict) else None
    if not isinstance(stock_data, dict):
        raise ProviderError("tencent fqkline returned empty data")

    raw_rows = stock_data.get("qfqday") or stock_data.get("day") or []
    if not isinstance(raw_rows, list):
        raise ProviderError("tencent fqkline returned non-list rows")

    begin = _compact_date(start) if start else ""
    finish = _compact_date(end) if end else ""
    rows = []
    previous_close: float | None = None
    for item in raw_rows:
        if not isinstance(item, list) or len(item) < 6:
            continue
        row_date = str(item[0])
        compact_row_date = _compact_date(row_date)
        if begin and compact_row_date < begin:
            continue
        if finish and compact_row_date > finish:
            continue
        open_price = _to_float(item[1])
        close_price = _to_float(item[2])
        high_price = _to_float(item[3])
        low_price = _to_float(item[4])
        if None in (open_price, close_price, high_price, low_price):
            continue
        change_pct = None
        if previous_close not in (None, 0):
            change_pct = round((close_price - previous_close) / previous_close * 100, 2)
        rows.append(
            {
                "date": row_date,
                "open": open_price,
                "close": close_price,
                "high": high_price,
                "low": low_price,
                "volume": _to_float(item[5]),
                "amount": None,
                "amplitude": None,
                "change_pct": change_pct,
                "change": round(close_price - previous_close, 4) if previous_close is not None else None,
                "turnover_rate": None,
                "request_url": url,
            }
        )
        previous_close = close_price

    if not rows:
        raise ProviderError("tencent fqkline returned no rows")
    return rows


def fetch_eastmoney_announcements(symbol: str, market: Market = "A", limit: int = 10) -> list[dict[str, Any]]:
    load_env_file()
    identity = normalize_a_share_symbol(symbol)
    base_url = os.getenv("EASTMONEY_ANNOUNCEMENT_BASE_URL", DEFAULT_ANNOUNCEMENT_BASE_URL).rstrip("/")
    params = {
        "sr": "-1",
        "page_size": str(max(limit, 1)),
        "page_index": "1",
        "ann_type": "A",
        "client_source": "web",
        "stock_list": identity["code"],
        "f_node": "0",
        "s_node": "0",
    }
    url = f"{base_url}/api/security/ann?{urllib.parse.urlencode(params)}"
    payload = _read_json(url, referer=f"https://data.eastmoney.com/notices/stock/{identity['code']}.html")
    data = payload.get("data")
    items = data.get("list") if isinstance(data, dict) else []
    if not isinstance(items, list):
        raise ProviderError("eastmoney announcements returned non-list data")

    announcements = []
    for item in items[:limit]:
        if not isinstance(item, dict):
            continue
        code = identity["code"]
        art_code = str(item.get("art_code") or "")
        announcements.append(
            {
                "title": item.get("title_ch") or item.get("title") or "",
                "date": str(item.get("notice_date") or item.get("display_time") or "").split(" ")[0],
                "columns": [column.get("column_name") for column in item.get("columns", []) if isinstance(column, dict)],
                "art_code": art_code,
                "stock": _first_code_value(item, "short_name"),
                "stock_code": _first_code_value(item, "stock_code") or code,
                "url": f"https://data.eastmoney.com/notices/detail/{code}/{art_code}.html" if art_code else "",
            }
        )
    return announcements


def fetch_eastmoney_company_profile(symbol: str, market: Market = "A") -> dict[str, Any]:
    load_env_file()
    identity = normalize_a_share_symbol(symbol)
    base_url = os.getenv("EASTMONEY_HSF10_BASE_URL", DEFAULT_HSF10_BASE_URL).rstrip("/")
    eastmoney_code = f"{identity['exchange']}{identity['code']}"
    url = f"{base_url}/PC_HSF10/CompanySurvey/PageAjax?{urllib.parse.urlencode({'code': eastmoney_code})}"
    payload = _read_json(
        url,
        referer=f"{base_url}/PC_HSF10/CompanySurvey/Index?type=web&code={eastmoney_code}",
    )
    basics = _first_list_item(payload.get("jbzl"))
    listing = _first_list_item(payload.get("fxxg"))
    if not basics:
        raise ProviderError("eastmoney company profile returned no basics")

    return {
        "symbol": basics.get("SECURITY_CODE") or identity["code"],
        "name": basics.get("SECURITY_NAME_ABBR") or "",
        "org_name": basics.get("ORG_NAME") or "",
        "market": basics.get("TRADE_MARKET") or "",
        "security_type": basics.get("SECURITY_TYPE") or "",
        "industry": basics.get("EM2016") or "",
        "csrc_industry": basics.get("INDUSTRYCSRC1") or "",
        "chairman": basics.get("CHAIRMAN") or "",
        "employees": basics.get("EMP_NUM"),
        "website": basics.get("ORG_WEB") or "",
        "profile": _collapse_text(basics.get("ORG_PROFILE") or ""),
        "business_scope": _collapse_text(basics.get("BUSINESS_SCOPE") or ""),
        "listing_date": str(listing.get("LISTING_DATE") or "").split(" ")[0] if listing else "",
        "request_url": url,
    }


def fetch_eastmoney_reports(
    query: str,
    brokers: list[str] | None = None,
    report_type: str | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    load_env_file()
    base_url = os.getenv("EASTMONEY_REPORT_BASE_URL", DEFAULT_REPORT_BASE_URL).rstrip("/")
    today = date.today()
    begin = today - timedelta(days=365)
    params = {
        "pageSize": str(max(limit * 4, 20)),
        "beginTime": begin.strftime("%Y-%m-%d"),
        "endTime": today.strftime("%Y-%m-%d"),
        "pageNo": "1",
        "qType": "0",
        "industryCode": "*",
        "industry": "*",
        "rating": "*",
        "ratingChange": "*",
        "orgCode": "",
        "code": _extract_stock_code(query) or "*",
        "rcode": "",
    }
    url = f"{base_url}/report/list?{urllib.parse.urlencode(params)}"
    payload = _read_json(url, referer="https://data.eastmoney.com/report/")
    items = payload.get("data") if isinstance(payload.get("data"), list) else []
    items = _filter_reports(items, query, brokers or [], report_type)

    reports = []
    for item in items[:limit]:
        reports.append(
            {
                "title": item.get("title", "无标题"),
                "broker": item.get("orgSName") or item.get("orgName", ""),
                "date": str(item.get("publishDate", "")).split(" ")[0],
                "summary": item.get("summary") or item.get("indvInduName") or "",
                "type": item.get("emRatingName") or item.get("rating", ""),
                "stock": item.get("stockName", ""),
                "stock_code": item.get("stockCode", ""),
                "url": _build_report_pdf_url(item),
                "request_url": url,
            }
        )
    return reports


def fetch_duckduckgo_news(query: str, market: Market = "A", limit: int = 10) -> list[dict[str, Any]]:
    load_env_file()
    base_url = os.getenv("DUCKDUCKGO_SEARCH_BASE_URL", DEFAULT_DUCKDUCKGO_BASE_URL).rstrip("/")
    url = f"{base_url}/html/?{urllib.parse.urlencode({'q': query})}"
    text = _read_text(url, referer="https://duckduckgo.com/")
    parser = _DuckDuckGoParser()
    parser.feed(text)
    return parser.results[:limit]


def load_env_file(path: str | Path = "config/.env") -> None:
    for env_path in _candidate_env_paths(Path(path)):
        if not env_path.exists():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
        return


def normalize_a_share_symbol(symbol: str) -> dict[str, str]:
    text = str(symbol or "").strip()
    match = re.search(r"(\d{6})", text)
    if not match:
        raise ProviderError(f"cannot extract 6-digit A-share code from symbol: {symbol!r}")
    code = match.group(1)
    upper = text.upper()
    if upper.startswith("SH") or code.startswith(("5", "6", "9")):
        exchange = "SH"
        market_id = "1"
    else:
        exchange = "SZ"
        market_id = "0"
    return {"code": code, "exchange": exchange, "secid": f"{market_id}.{code}"}


def _candidate_env_paths(path: Path) -> list[Path]:
    cwd = Path.cwd()
    package_root = Path(__file__).resolve().parents[2]
    repo_root = package_root.parent
    return [path, cwd / path, package_root / path, repo_root / "AITrading" / path]


def _read_json(url: str, referer: str = "") -> dict[str, Any]:
    text = _read_text(url, referer=referer)
    stripped = text.strip()
    if stripped.startswith("{"):
        parsed = json.loads(stripped)
    else:
        start = stripped.find("(")
        end = stripped.rfind(")")
        if start < 0 or end < start:
            raise ProviderError("response is not JSON or JSONP")
        parsed = json.loads(stripped[start + 1 : end])
    if not isinstance(parsed, dict):
        raise ProviderError("response JSON is not an object")
    return parsed


def _read_text(url: str, referer: str = "") -> str:
    headers = {
        "Accept": "application/json,text/html,text/plain,*/*",
        "Accept-Encoding": "gzip",
        "User-Agent": "Mozilla/5.0",
    }
    if referer:
        headers["Referer"] = referer
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            raw = response.read()
            encoding = response.headers.get("Content-Encoding", "")
            content_type = response.headers.get("Content-Type", "")
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ProviderError(f"request failed: {exc}") from exc

    if encoding == "gzip" or raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    charset = "utf-8"
    match = re.search(r"charset=([\w-]+)", content_type, flags=re.IGNORECASE)
    if match:
        charset = match.group(1)
    try:
        return raw.decode(charset)
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="replace")


def _scaled(value: Any) -> float | None:
    number = _to_float(value)
    if number is None:
        return None
    return round(number / 100, 4)


def _to_float(value: Any) -> float | None:
    try:
        if value in (None, "", "-"):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _compact_date(value: str | None) -> str:
    return str(value or "").replace("-", "")[:8]


def _extract_stock_code(query: str) -> str:
    match = re.search(r"\b(\d{6})\b", query)
    return match.group(1) if match else ""


def _filter_reports(
    items: list[Any],
    query: str,
    brokers: list[str] | None = None,
    report_type: str | None = None,
) -> list[dict[str, Any]]:
    terms = [part for part in re.split(r"[\s,，]+", query.strip()) if part]
    filtered = []
    for item in items:
        if not isinstance(item, dict):
            continue
        haystack = " ".join(
            str(item.get(key, ""))
            for key in ("title", "stockName", "stockCode", "orgName", "orgSName", "indvInduName")
        )
        broker_ok = not brokers or any(broker in haystack for broker in brokers)
        type_ok = not report_type or report_type in {"all", "*"} or report_type in haystack
        term_ok = not terms or any(term in haystack for term in terms)
        if broker_ok and type_ok and term_ok:
            filtered.append(item)
    return filtered or [item for item in items if isinstance(item, dict)]


def _build_report_pdf_url(item: dict[str, Any]) -> str:
    info_code = str(item.get("infoCode") or "")
    encode_url = str(item.get("encodeUrl") or "")
    if not info_code or not encode_url:
        return ""
    token = encode_url.split("=", 1)[0]
    return f"https://pdf.dfcfw.com/pdf/H3_{info_code}_1.pdf?{token}.pdf"


def _first_code_value(item: dict[str, Any], key: str) -> str:
    codes = item.get("codes")
    if isinstance(codes, list) and codes and isinstance(codes[0], dict):
        return str(codes[0].get(key) or "")
    return ""


def _first_list_item(value: Any) -> dict[str, Any]:
    if isinstance(value, list) and value and isinstance(value[0], dict):
        return value[0]
    return {}


def _collapse_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


class _DuckDuckGoParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._active: dict[str, str] | None = None
        self._field = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key: value or "" for key, value in attrs}
        classes = attrs_dict.get("class", "")
        if tag == "a" and "result__a" in classes:
            self._active = {"title": "", "url": self._clean_url(attrs_dict.get("href", "")), "summary": ""}
            self._field = "title"
        elif self._active is not None and "result__snippet" in classes:
            self._field = "summary"

    def handle_data(self, data: str) -> None:
        if self._active is not None and self._field:
            self._active[self._field] = (self._active.get(self._field, "") + " " + html.unescape(data)).strip()

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._active is not None and self._field == "title":
            self._field = ""
        elif tag == "div" and self._active is not None and self._active.get("title"):
            self.results.append(self._active)
            self._active = None
            self._field = ""

    def _clean_url(self, href: str) -> str:
        href = html.unescape(href)
        if href.startswith("//"):
            href = f"https:{href}"
        parsed = urllib.parse.urlparse(href)
        query = urllib.parse.parse_qs(parsed.query)
        if "uddg" in query and query["uddg"]:
            return query["uddg"][0]
        return href
