"""Service for creating and advancing stock training sessions."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime

from backend.models.training_session import TrainingSession
from backend.services.market_data import DailyBar, MarketDataService
from backend.services.performance import PerformanceService


class TrainingSessionNotFoundError(Exception):
    """Raised when a requested training session does not exist."""


class TrainingSessionCompleteError(Exception):
    """Raised when a session cannot advance past the final trading day."""


class TrainingSessionService:
    """Coordinates training sessions against valid market trading days."""

    def __init__(self, market_data_service: MarketDataService | None = None) -> None:
        self.market_data_service = market_data_service or MarketDataService()
        self.performance_service = PerformanceService()
        self._sessions: dict[str, TrainingSession] = {}

    def create_session(self, symbol: str, start_date: str | date, initial_cash: float) -> dict[str, object]:
        normalized_start = self._normalize_date(start_date)
        bars = self.market_data_service.get_history(symbol, start_date=normalized_start)
        tradable_bars = [bar for bar in bars if self._has_price(bar)]
        if not tradable_bars:
            raise ValueError("No valid trading days found for the requested session")

        session = TrainingSession(
            symbol=symbol.strip().upper(),
            start_date=normalized_start,
            initial_cash=initial_cash,
            current_cash=initial_cash,
            market_data=tradable_bars,
        )
        self.performance_service.capture_snapshot(session)
        self._sessions[session.id] = session
        return self.serialize(session)

    def get_session(self, session_id: str) -> dict[str, object]:
        return self.serialize(self._get_session(session_id))

    def next_day(self, session_id: str) -> dict[str, object]:
        session = self._get_session(session_id)
        if session.current_day_index >= len(session.market_data) - 1:
            raise TrainingSessionCompleteError("训练会话已经到达最后一个有效交易日")
        session.current_day_index += 1
        self.performance_service.capture_snapshot(session)
        return self.serialize(session)

    def serialize(self, session: TrainingSession) -> dict[str, object]:
        current_bar = session.current_bar
        performance = self.performance_service.calculate(session)
        return {
            "id": session.id,
            "symbol": session.symbol,
            "start_date": session.start_date,
            "current_trading_date": current_bar.date,
            "current_day_index": session.current_day_index,
            "initial_cash": performance.initial_cash,
            "current_cash": performance.current_cash,
            "current_position_quantity": performance.current_position_quantity,
            "current_position_cost": performance.current_position_cost,
            "market_value": performance.market_value,
            "total_assets": performance.total_assets,
            "floating_pnl": performance.floating_pnl,
            "floating_pnl_ratio": performance.floating_pnl_ratio,
            "daily_pnl": performance.daily_pnl,
            "cumulative_return": performance.cumulative_return,
            "has_valid_market_data": performance.has_valid_market_data,
            "performance_message": performance.message,
            "performance": performance.to_dict(),
            "current_bar": asdict(current_bar),
            "trade_history": [asdict(trade) for trade in session.trade_history],
            "daily_snapshots": [asdict(snapshot) for snapshot in session.daily_snapshots],
            "created_at": session.created_at,
            "is_complete": session.current_day_index >= len(session.market_data) - 1,
        }

    def _get_session(self, session_id: str) -> TrainingSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise TrainingSessionNotFoundError("训练会话不存在")
        return session

    @staticmethod
    def _normalize_date(value: str | date) -> str:
        if isinstance(value, date):
            return value.isoformat()
        try:
            return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
        except ValueError as exc:
            raise ValueError("start_date must use YYYY-MM-DD format") from exc

    @staticmethod
    def _has_price(bar: DailyBar) -> bool:
        return bar.close is not None or bar.adj_close is not None
