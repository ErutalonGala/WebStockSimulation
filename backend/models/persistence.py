"""Database-facing model definitions for persistent training data."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StockRecord:
    """A tradable stock tracked by the training database."""

    symbol: str
    name: str | None = None
    exchange: str | None = None
    currency: str | None = None


@dataclass(frozen=True)
class StockPriceRecord:
    """One daily OHLCV price row for a stock."""

    symbol: str
    date: str
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    adj_close: float | None
    volume: int | None
    amount: float | None = None


@dataclass(frozen=True)
class TrainingSessionRecord:
    """Persistent summary state needed to resume a training session."""

    id: str
    symbol: str
    start_date: str
    initial_cash: float
    current_day_index: int
    current_cash: float
    current_position_quantity: int
    current_position_cost: float
    created_at: str


@dataclass(frozen=True)
class OrderRecord:
    """Persistent execution record for a simulated order."""

    id: int
    session_id: str
    symbol: str
    date: str
    side: str
    price: float
    quantity: int
    fee: float


@dataclass(frozen=True)
class PortfolioSnapshotRecord:
    """Daily account performance snapshot."""

    session_id: str
    date: str
    cash: float
    market_value: float
    total_assets: float
    daily_pnl: float
    cumulative_return: float
