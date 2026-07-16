"""Stock market-data service with file-based caching.

The service fetches daily historical OHLCV bars from Yahoo Finance's chart API,
normalizes the response, and caches the full-symbol history locally so model
training and API calls do not repeatedly hit the remote provider.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
import json
import os
import re
from pathlib import Path
import time
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


class MarketDataError(Exception):
    """Base exception raised by the market-data service."""


class InvalidSymbolError(MarketDataError):
    """Raised when a symbol is unknown or the data source returns no prices."""


class DataSourceRateLimitError(MarketDataError):
    """Raised when the remote data source throttles requests."""


class DataSourceUnavailableError(MarketDataError):
    """Raised when the remote data source cannot be reached or parsed."""


@dataclass(frozen=True)
class DailyBar:
    """A normalized daily stock bar."""

    date: str
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    adj_close: float | None
    volume: int | None
    amount: float | None = None


class MarketDataService:
    """Fetch and cache daily historical stock data."""

    YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    EASTMONEY_SUGGEST_URL = "https://searchapi.eastmoney.com/api/suggest/get"
    EASTMONEY_TOKEN = "44c9d251add88e27b65ed86506f6e5da"
    CACHE_VERSION = 1
    A_SHARE_NAME_ALIASES = {
        "贵州茅台": "600519",
    }

    def __init__(
        self,
        cache_dir: str | Path | None = None,
        cache_ttl_seconds: int = 60 * 60 * 24,
        timeout_seconds: int = 20,
    ) -> None:
        self.cache_dir = Path(
            cache_dir
            or os.getenv("MARKET_DATA_CACHE_DIR")
            or Path(__file__).resolve().parents[1] / ".cache" / "market_data"
        )
        self.cache_ttl_seconds = cache_ttl_seconds
        self.timeout_seconds = timeout_seconds
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_history(
        self,
        symbol: str,
        start_date: str | date | None = None,
        end_date: str | date | None = None,
    ) -> list[DailyBar]:
        """Return daily history from listing date through today, optionally filtered.

        Args:
            symbol: Exchange ticker such as ``AAPL``, ``TSLA``, or ``600519.SS``.
            start_date: Inclusive lower bound in ``YYYY-MM-DD`` format.
            end_date: Inclusive upper bound in ``YYYY-MM-DD`` format.

        Raises:
            InvalidSymbolError: The symbol is empty, invalid, or has no daily bars.
            DataSourceRateLimitError: The upstream provider returns HTTP 429.
            DataSourceUnavailableError: Network, HTTP, or response parsing failure.
        """

        normalized_symbol = self.resolve_symbol(symbol)
        start = self._parse_date(start_date, "start_date") if start_date else None
        end = self._parse_date(end_date, "end_date") if end_date else None
        if start and end and start > end:
            raise ValueError("start_date must be earlier than or equal to end_date")

        bars = self._load_or_fetch(normalized_symbol)
        filtered = [bar for bar in bars if self._within_range(bar.date, start, end)]
        if not filtered:
            raise InvalidSymbolError(
                f"No historical daily data found for {normalized_symbol} in the requested date range"
            )
        return filtered

    def _load_or_fetch(self, symbol: str) -> list[DailyBar]:
        cached = self._read_cache(symbol)
        if cached is not None:
            return cached

        bars = self._fetch_from_yahoo(symbol)
        self._write_cache(symbol, bars)
        return bars

    def _fetch_from_yahoo(self, symbol: str) -> list[DailyBar]:
        encoded_symbol = quote(symbol, safe="")
        url = (
            self.YAHOO_CHART_URL.format(symbol=encoded_symbol)
            + "?period1=0&period2="
            + str(int(time.time()))
            + "&interval=1d&events=history&includeAdjustedClose=true"
        )
        request = Request(url, headers={"User-Agent": "codex-rp-market-data/1.0"})

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310 - trusted HTTPS endpoint.
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code == 404:
                raise InvalidSymbolError(f"Unknown stock symbol: {symbol}") from exc
            if exc.code == 429:
                raise DataSourceRateLimitError("Market data source rate limit exceeded") from exc
            raise DataSourceUnavailableError(f"Market data source returned HTTP {exc.code}") from exc
        except (URLError, TimeoutError) as exc:
            raise DataSourceUnavailableError("Market data source is unavailable") from exc
        except json.JSONDecodeError as exc:
            raise DataSourceUnavailableError("Market data source returned invalid JSON") from exc

        return self._parse_yahoo_response(symbol, payload)

    def _parse_yahoo_response(self, symbol: str, payload: dict[str, Any]) -> list[DailyBar]:
        chart = payload.get("chart") or {}
        error = chart.get("error")
        if error:
            code = error.get("code")
            description = error.get("description", "Unknown market data error")
            if code in {"Not Found", "No data found"}:
                raise InvalidSymbolError(f"Unknown stock symbol: {symbol}")
            raise DataSourceUnavailableError(description)

        results = chart.get("result") or []
        if not results:
            raise InvalidSymbolError(f"No historical daily data found for {symbol}")

        result = results[0]
        timestamps = result.get("timestamp") or []
        quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
        adjclose = ((result.get("indicators") or {}).get("adjclose") or [{}])[0].get("adjclose") or []

        bars: list[DailyBar] = []
        for index, ts in enumerate(timestamps):
            bar = DailyBar(
                date=datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat(),
                open=self._get_number(quote.get("open"), index),
                high=self._get_number(quote.get("high"), index),
                low=self._get_number(quote.get("low"), index),
                close=self._get_number(quote.get("close"), index),
                adj_close=self._get_number(adjclose, index),
                volume=self._get_int(quote.get("volume"), index),
                amount=None,
            )
            # Skip non-trading/suspended days or malformed rows where the data source
            # emits a timestamp but all price fields are missing.
            if any(value is not None for value in (bar.open, bar.high, bar.low, bar.close, bar.adj_close)):
                bars.append(bar)

        if not bars:
            raise InvalidSymbolError(f"No valid historical daily data found for {symbol}")
        return bars

    def _read_cache(self, symbol: str) -> list[DailyBar] | None:
        path = self._cache_path(symbol)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            generated_at = float(payload.get("generated_at", 0))
            if time.time() - generated_at > self.cache_ttl_seconds:
                return None
            if payload.get("version") != self.CACHE_VERSION:
                return None
            return [DailyBar(**item) for item in payload.get("data", [])]
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def _write_cache(self, symbol: str, bars: Iterable[DailyBar]) -> None:
        path = self._cache_path(symbol)
        tmp_path = path.with_suffix(".tmp")
        payload = {
            "version": self.CACHE_VERSION,
            "symbol": symbol,
            "generated_at": time.time(),
            "data": [asdict(bar) for bar in bars],
        }
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp_path.replace(path)

    def _cache_path(self, symbol: str) -> Path:
        safe_symbol = symbol.replace("/", "_").replace("\\", "_").upper()
        return self.cache_dir / f"{safe_symbol}.json"

    def resolve_symbol(self, symbol: str) -> str:
        """Return a Yahoo Finance compatible ticker for US or A-share input.

        US tickers are kept as uppercase symbols. A-share numeric codes are
        automatically suffixed with their exchange, and Chinese stock names are
        resolved through Eastmoney's suggestion API before requesting Yahoo
        Finance historical bars.
        """

        normalized = self._normalize_symbol(symbol)
        if self._is_chinese_query(normalized):
            return self._lookup_a_share_symbol(symbol.strip())
        if re.fullmatch(r"\d{6}", normalized):
            return self._suffix_a_share_code(normalized)
        return normalized

    def _lookup_a_share_symbol(self, query: str) -> str:
        alias_code = self.A_SHARE_NAME_ALIASES.get(query)
        if alias_code:
            return self._suffix_a_share_code(alias_code)

        params = urlencode({"input": query, "type": "14", "token": self.EASTMONEY_TOKEN})
        request = Request(
            f"{self.EASTMONEY_SUGGEST_URL}?{params}",
            headers={"User-Agent": "codex-rp-market-data/1.0"},
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310 - trusted HTTPS endpoint.
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError) as exc:
            raise DataSourceUnavailableError("A-share symbol search is unavailable") from exc
        except json.JSONDecodeError as exc:
            raise DataSourceUnavailableError("A-share symbol search returned invalid JSON") from exc

        suggestions = ((payload.get("QuotationCodeTable") or {}).get("Data") or [])
        for item in suggestions:
            code = str(item.get("Code") or "")
            security_type = str(item.get("SecurityTypeName") or item.get("SecurityType") or "")
            if re.fullmatch(r"\d{6}", code) and ("A股" in security_type or not security_type):
                return self._suffix_a_share_code(code)
        raise InvalidSymbolError(f"Unknown A-share stock name: {query}")

    @staticmethod
    def _suffix_a_share_code(code: str) -> str:
        if code.startswith("6"):
            return f"{code}.SS"
        if code.startswith(("0", "3")):
            return f"{code}.SZ"
        if code.startswith(("4", "8")):
            return f"{code}.BJ"
        raise InvalidSymbolError(f"Unsupported A-share stock code: {code}")

    @staticmethod
    def _is_chinese_query(value: str) -> bool:
        return any("\u4e00" <= char <= "\u9fff" for char in value)

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        if not symbol or not symbol.strip():
            raise InvalidSymbolError("Stock symbol is required")
        normalized = symbol.strip().upper()
        if len(normalized) > 32 or any(char.isspace() for char in normalized):
            raise InvalidSymbolError(f"Invalid stock symbol: {symbol}")
        return normalized

    @staticmethod
    def _parse_date(value: str | date, field_name: str) -> date:
        if isinstance(value, date):
            return value
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError(f"{field_name} must use YYYY-MM-DD format") from exc

    @staticmethod
    def _within_range(value: str, start: date | None, end: date | None) -> bool:
        current = datetime.strptime(value, "%Y-%m-%d").date()
        return (start is None or current >= start) and (end is None or current <= end)

    @staticmethod
    def _get_number(values: list[Any] | None, index: int) -> float | None:
        if not values or index >= len(values) or values[index] is None:
            return None
        return round(float(values[index]), 6)

    @staticmethod
    def _get_int(values: list[Any] | None, index: int) -> int | None:
        if not values or index >= len(values) or values[index] is None:
            return None
        return int(values[index])
