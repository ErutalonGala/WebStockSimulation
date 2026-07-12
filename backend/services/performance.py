"""Portfolio performance calculations for training sessions."""

from __future__ import annotations

from dataclasses import dataclass

from backend.models.training_session import AssetSnapshot, TrainingSession
from backend.services.market_data import DailyBar


@dataclass(frozen=True)
class PortfolioPerformance:
    """Computed account statistics for the current trading day."""

    date: str
    initial_cash: float
    current_cash: float
    current_position_quantity: int
    current_position_cost: float
    close_price: float
    market_value: float
    total_assets: float
    floating_pnl: float
    floating_pnl_ratio: float
    daily_pnl: float
    cumulative_return: float
    has_valid_market_data: bool
    message: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return {
            "date": self.date,
            "initial_cash": self.initial_cash,
            "current_cash": self.current_cash,
            "current_position_quantity": self.current_position_quantity,
            "current_position_cost": self.current_position_cost,
            "close_price": self.close_price,
            "market_value": self.market_value,
            "total_assets": self.total_assets,
            "floating_pnl": self.floating_pnl,
            "floating_pnl_ratio": self.floating_pnl_ratio,
            "daily_pnl": self.daily_pnl,
            "cumulative_return": self.cumulative_return,
            "has_valid_market_data": self.has_valid_market_data,
            "message": self.message,
        }


class PerformanceService:
    """Calculate portfolio statistics and persist daily account snapshots."""

    NO_MARKET_DATA_MESSAGE = "当前日期没有有效行情数据，暂时无法计算账户统计。"

    def calculate(self, session: TrainingSession) -> PortfolioPerformance:
        """Calculate current-day portfolio performance from the closing price."""

        bar = session.current_bar
        close_price = self._close_price(bar)
        has_valid_market_data = close_price is not None and close_price > 0
        effective_close = close_price if has_valid_market_data else 0.0
        market_value = round(session.current_position_quantity * effective_close, 2)
        total_assets = round(session.current_cash + market_value, 2)
        position_cost_basis = round(session.current_position_quantity * session.current_position_cost, 6)
        floating_pnl = round(market_value - position_cost_basis, 2)
        floating_pnl_ratio = round(floating_pnl / position_cost_basis, 6) if position_cost_basis > 0 else 0.0
        previous_total_assets = self._previous_total_assets(session)
        daily_pnl = round(total_assets - previous_total_assets, 2) if previous_total_assets is not None else 0.0
        cumulative_return = round((total_assets - session.initial_cash) / session.initial_cash, 6)

        return PortfolioPerformance(
            date=bar.date,
            initial_cash=round(session.initial_cash, 2),
            current_cash=round(session.current_cash, 2),
            current_position_quantity=session.current_position_quantity,
            current_position_cost=round(session.current_position_cost, 6),
            close_price=round(effective_close, 6),
            market_value=market_value,
            total_assets=total_assets,
            floating_pnl=floating_pnl,
            floating_pnl_ratio=floating_pnl_ratio,
            daily_pnl=daily_pnl,
            cumulative_return=cumulative_return,
            has_valid_market_data=has_valid_market_data,
            message=None if has_valid_market_data else self.NO_MARKET_DATA_MESSAGE,
        )

    def capture_snapshot(self, session: TrainingSession) -> AssetSnapshot:
        """Save or replace the current trading day's asset snapshot."""

        performance = self.calculate(session)
        snapshot = AssetSnapshot(
            date=performance.date,
            cash=performance.current_cash,
            position_quantity=performance.current_position_quantity,
            position_cost=performance.current_position_cost,
            close_price=performance.close_price,
            market_value=performance.market_value,
            total_assets=performance.total_assets,
            floating_pnl=performance.floating_pnl,
            floating_pnl_ratio=performance.floating_pnl_ratio,
            daily_pnl=performance.daily_pnl,
            cumulative_return=performance.cumulative_return,
        )
        session.daily_snapshots = [item for item in session.daily_snapshots if item.date != snapshot.date]
        session.daily_snapshots.append(snapshot)
        return snapshot

    @staticmethod
    def _close_price(bar: DailyBar) -> float | None:
        return bar.close if bar.close is not None else bar.adj_close

    @staticmethod
    def _previous_total_assets(session: TrainingSession) -> float | None:
        current_date = session.current_bar.date
        previous_snapshots = [snapshot for snapshot in session.daily_snapshots if snapshot.date != current_date]
        if not previous_snapshots:
            return None
        return previous_snapshots[-1].total_assets
