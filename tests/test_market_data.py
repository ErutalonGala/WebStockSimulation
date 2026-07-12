from __future__ import annotations

import json
import time

import pytest

from backend.services.market_data import InvalidSymbolError, MarketDataService


def test_get_history_uses_cache_and_filters_dates(tmp_path):
    service = MarketDataService(cache_dir=tmp_path)
    payload = {
        "version": service.CACHE_VERSION,
        "symbol": "AAPL",
        "generated_at": time.time(),
        "data": [
            {"date": "2024-01-02", "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "adj_close": 1.4, "volume": 100, "amount": None},
            {"date": "2024-01-03", "open": 2.0, "high": 3.0, "low": 1.5, "close": 2.5, "adj_close": 2.4, "volume": 200, "amount": None},
        ],
    }
    (tmp_path / "AAPL.json").write_text(json.dumps(payload), encoding="utf-8")

    bars = service.get_history("aapl", start_date="2024-01-03", end_date="2024-01-03")

    assert len(bars) == 1
    assert bars[0].date == "2024-01-03"
    assert bars[0].adj_close == 2.4


def test_parse_yahoo_response_skips_missing_suspended_rows(tmp_path):
    service = MarketDataService(cache_dir=tmp_path)
    payload = {
        "chart": {
            "result": [
                {
                    "timestamp": [1704153600, 1704240000],
                    "indicators": {
                        "quote": [
                            {
                                "open": [None, 10.0],
                                "high": [None, 11.0],
                                "low": [None, 9.5],
                                "close": [None, 10.5],
                                "volume": [None, 12345],
                            }
                        ],
                        "adjclose": [{"adjclose": [None, 10.4]}],
                    },
                }
            ],
            "error": None,
        }
    }

    bars = service._parse_yahoo_response("TSLA", payload)

    assert len(bars) == 1
    assert bars[0].close == 10.5
    assert bars[0].volume == 12345


def test_invalid_symbol_rejected(tmp_path):
    service = MarketDataService(cache_dir=tmp_path)

    with pytest.raises(InvalidSymbolError):
        service.get_history("bad symbol")


def test_invalid_date_range_rejected(tmp_path):
    service = MarketDataService(cache_dir=tmp_path)

    with pytest.raises(ValueError):
        service.get_history("AAPL", start_date="2024-02-01", end_date="2024-01-01")


def test_fetch_with_fallbacks_uses_stooq_when_yahoo_unavailable(tmp_path, monkeypatch):
    service = MarketDataService(cache_dir=tmp_path)

    def yahoo_down(symbol):
        from backend.services.market_data import DataSourceUnavailableError
        raise DataSourceUnavailableError("blocked")

    monkeypatch.setattr(service, "_fetch_from_yahoo", yahoo_down)
    monkeypatch.setattr(
        service,
        "_fetch_from_stooq",
        lambda symbol: service._parse_stooq_response(
            symbol, "Date,Open,High,Low,Close,Volume\n2024-01-02,1,2,0.5,1.5,100\n"
        ),
    )

    bars = service.get_history("AAPL")

    assert len(bars) == 1
    assert bars[0].date == "2024-01-02"
    assert bars[0].close == 1.5


def test_stooq_symbol_mapping_supports_common_inputs(tmp_path):
    service = MarketDataService(cache_dir=tmp_path)

    assert service._to_stooq_symbol("AAPL") == "aapl.us"
    assert service._to_stooq_symbol("600519.SS") == "600519.cn"
    assert service._to_stooq_symbol("000001.SZ") == "000001.cn"


def test_fetch_with_fallbacks_tries_stooq_after_yahoo_invalid_symbol(tmp_path, monkeypatch):
    service = MarketDataService(cache_dir=tmp_path)

    def yahoo_no_data(symbol):
        raise InvalidSymbolError("no yahoo data")

    monkeypatch.setattr(service, "_fetch_from_yahoo", yahoo_no_data)
    monkeypatch.setattr(
        service,
        "_fetch_from_stooq",
        lambda symbol: service._parse_stooq_response(
            symbol, "Date,Open,High,Low,Close,Volume\n2024-01-03,2,3,1.5,2.5,200\n"
        ),
    )

    bars = service.get_history("600519.SS")

    assert len(bars) == 1
    assert bars[0].close == 2.5
