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


def test_numeric_a_share_code_resolves_to_yahoo_exchange_suffix(tmp_path):
    service = MarketDataService(cache_dir=tmp_path)

    assert service.resolve_symbol("600519") == "600519.SS"
    assert service.resolve_symbol("000001") == "000001.SZ"


def test_common_chinese_a_share_name_resolves_without_remote_lookup(monkeypatch, tmp_path):
    def fail_urlopen(request, timeout):
        raise AssertionError("common A-share alias should not call remote search")

    monkeypatch.setattr("backend.services.market_data.urlopen", fail_urlopen)
    service = MarketDataService(cache_dir=tmp_path)

    assert service.resolve_symbol("贵州茅台") == "600519.SS"


def test_chinese_a_share_name_resolves_from_suggestions(monkeypatch, tmp_path):
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return json.dumps({
                "QuotationCodeTable": {
                    "Data": [{"Code": "600036", "SecurityTypeName": "沪深A股"}]
                }
            }).encode("utf-8")

    def fake_urlopen(request, timeout):
        assert "%E6%8B%9B%E5%95%86%E9%93%B6%E8%A1%8C" in request.full_url
        return FakeResponse()

    monkeypatch.setattr("backend.services.market_data.urlopen", fake_urlopen)
    service = MarketDataService(cache_dir=tmp_path)

    assert service.resolve_symbol("招商银行") == "600036.SS"
