"""Training-session domain models for day-by-day market simulation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from backend.services.market_data import DailyBar


@dataclass
class TradeRecord:
    """A historical trade attached to a training session."""

    symbol: str
    side: str
    quantity: int
    price: float
    trade_date: str
    executed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class AssetSnapshot:
    """Daily portfolio snapshot captured for a training session."""

    date: str
    cash: float
    position_quantity: int
    position_cost: float
    close_price: float
    market_value: float
    total_assets: float
    floating_pnl: float = 0.0
    floating_pnl_ratio: float = 0.0
    daily_pnl: float = 0.0
    cumulative_return: float = 0.0


@dataclass
class TrainingSession:
    """State for one stock training simulation."""

    symbol: str
    start_date: str
    initial_cash: float
    market_data: list[DailyBar]
    id: str = field(default_factory=lambda: uuid4().hex)
    current_day_index: int = 0
    current_cash: float = 0.0
    current_position_quantity: int = 0
    current_position_cost: float = 0.0
    trade_history: list[TradeRecord] = field(default_factory=list)
    daily_snapshots: list[AssetSnapshot] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self) -> None:
        if not self.current_cash:
            self.current_cash = self.initial_cash

    @property
    def current_bar(self) -> DailyBar:
        return self.market_data[self.current_day_index]

