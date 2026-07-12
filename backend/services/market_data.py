"""Stock market-data service with file-based caching.

The service fetches daily historical OHLCV bars from Yahoo Finance's chart API,
normalizes the response, and caches the full-symbol history locally so model
training and API calls do not repeatedly hit the remote provider.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
import csv
import io
import json
import os
from pathlib import Path
import time
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
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
    CACHE_VERSION = 1

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

        normalized_symbol = self._normalize_symbol(symbol)
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

        bars = self._fetch_with_fallbacks(symbol)
        self._write_cache(symbol, bars)
        return bars

    def _fetch_with_fallbacks(self, symbol: str) -> list[DailyBar]:
        errors: list[str] = []
        invalid_symbol_errors: list[str] = []
        for provider_name, fetcher in (
            ("Yahoo Finance", self._fetch_from_yahoo),
            ("Stooq", self._fetch_from_stooq),
        ):
            try:
                return fetcher(symbol)
            except InvalidSymbolError as exc:
                invalid_symbol_errors.append(f"{provider_name}: {exc}")
            except DataSourceRateLimitError:
                errors.append(f"{provider_name}: rate limited")
            except DataSourceUnavailableError as exc:
                errors.append(f"{provider_name}: {exc}")

        if invalid_symbol_errors and not errors:
            raise InvalidSymbolError(
                f"No historical daily data found for {symbol}"
                + f" ({'; '.join(invalid_symbol_errors)})"
            )
        raise DataSourceUnavailableError(
            "All market data providers are unavailable"
            + (f" ({'; '.join(errors + invalid_symbol_errors)})" if errors or invalid_symbol_errors else "")
        )

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

    def _fetch_from_stooq(self, symbol: str) -> list[DailyBar]:
        stooq_symbol = self._to_stooq_symbol(symbol)
        url = f"https://stooq.com/q/d/l/?s={quote(stooq_symbol, safe='')}&i=d"
        request = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; codex-rp-market-data/1.0)"})

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310 - trusted HTTPS endpoint.
                payload = response.read().decode("utf-8")
        except HTTPError as exc:
            if exc.code == 429:
                raise DataSourceRateLimitError("Stooq market data source rate limit exceeded") from exc
            raise DataSourceUnavailableError(f"Stooq returned HTTP {exc.code}") from exc
        except (URLError, TimeoutError) as exc:
            raise DataSourceUnavailableError("Stooq market data source is unavailable") from exc

        return self._parse_stooq_response(symbol, payload)

    def _parse_stooq_response(self, symbol: str, payload: str) -> list[DailyBar]:
        if not payload.strip() or payload.strip().lower() == "no data":
            raise InvalidSymbolError(f"No historical daily data found for {symbol}")

        reader = csv.DictReader(io.StringIO(payload))
        required_columns = {"Date", "Open", "High", "Low", "Close", "Volume"}
        if not reader.fieldnames or not required_columns.issubset(reader.fieldnames):
            raise InvalidSymbolError(f"No historical daily data found for {symbol}")

        bars: list[DailyBar] = []
        for row in reader:
            try:
                bar_date = self._parse_date(row["Date"], "Date").isoformat()
            except ValueError:
                continue
            bar = DailyBar(
                date=bar_date,
                open=self._parse_optional_number(row.get("Open")),
                high=self._parse_optional_number(row.get("High")),
                low=self._parse_optional_number(row.get("Low")),
                close=self._parse_optional_number(row.get("Close")),
                # Stooq close prices are adjusted for splits in its historical CSV,
                # but it does not expose a separate adjusted-close column.
                adj_close=None,
                volume=self._parse_optional_int(row.get("Volume")),
                amount=None,
            )
            if any(value is not None for value in (bar.open, bar.high, bar.low, bar.close, bar.adj_close)):
                bars.append(bar)

        if not bars:
            raise InvalidSymbolError(f"No valid historical daily data found for {symbol}")
        return bars

    @staticmethod
    def _to_stooq_symbol(symbol: str) -> str:
        lower_symbol = symbol.lower()
        if lower_symbol.endswith(".ss") or lower_symbol.endswith(".sz"):
            return lower_symbol[:-3] + ".cn"
        if "." not in lower_symbol:
            return lower_symbol + ".us"
        return lower_symbol

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
    def _parse_optional_number(value: Any) -> float | None:
        if value in (None, "", "N/A", "null"):
            return None
        return round(float(value), 6)

    @staticmethod
    def _parse_optional_int(value: Any) -> int | None:
        if value in (None, "", "N/A", "null"):
            return None
        return int(float(value))

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
