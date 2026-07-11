from __future__ import annotations

import pytest

from backend.services.market_data import DailyBar
from backend.services.training_session import TrainingSessionCompleteError, TrainingSessionService


class FakeMarketDataService:
    def get_history(self, symbol, start_date=None, end_date=None):
        assert symbol == "AAPL"
        assert start_date == "2024-01-06"
        return [
            DailyBar(date="2024-01-08", open=100, high=110, low=99, close=105, adj_close=105, volume=1000),
            DailyBar(date="2024-01-09", open=106, high=112, low=104, close=111, adj_close=111, volume=1200),
        ]


def test_create_session_starts_on_next_valid_trading_day():
    service = TrainingSessionService(market_data_service=FakeMarketDataService())

    session = service.create_session("AAPL", "2024-01-06", 100000)

    assert session["current_trading_date"] == "2024-01-08"
    assert session["current_day_index"] == 0
    assert session["current_cash"] == 100000
    assert session["current_position_quantity"] == 0
    assert session["current_position_cost"] == 0
    assert session["daily_snapshots"][0]["total_assets"] == 100000


def test_next_day_advances_to_next_market_bar_only():
    service = TrainingSessionService(market_data_service=FakeMarketDataService())
    created = service.create_session("AAPL", "2024-01-06", 100000)

    advanced = service.next_day(created["id"])

    assert advanced["current_trading_date"] == "2024-01-09"
    assert advanced["current_day_index"] == 1
    assert advanced["is_complete"] is True
    assert len(advanced["daily_snapshots"]) == 2

    with pytest.raises(TrainingSessionCompleteError):
        service.next_day(created["id"])
