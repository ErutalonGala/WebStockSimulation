"""Position domain models for the simulated trading engine."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.models.order import Order


@dataclass
class Position:
    """Current position state for one symbol in a training session."""

    symbol: str
    quantity: int = 0
    average_cost: float = 0.0
    realized_pnl: float = 0.0

    @property
    def market_value_at_cost(self) -> float:
        """Return the position value using average cost."""

        return self.quantity * self.average_cost

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation for API responses."""

        return {
            "symbol": self.symbol,
            "quantity": self.quantity,
            "average_cost": self.average_cost,
            "realized_pnl": self.realized_pnl,
            "market_value_at_cost": self.market_value_at_cost,
        }


@dataclass
class TradingSessionState:
    """Mutable simulated account state for a training session."""

    session_id: str
    initial_cash: float = 100000.0
    cash: float = 100000.0
    positions: dict[str, Position] = field(default_factory=dict)
    orders: list[Order] = field(default_factory=list)

    @property
    def realized_pnl(self) -> float:
        """Return aggregate realized P&L across all symbols."""

        return sum(position.realized_pnl for position in self.positions.values())

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable account snapshot."""

        return {
            "session_id": self.session_id,
            "initial_cash": self.initial_cash,
            "cash": self.cash,
            "realized_pnl": self.realized_pnl,
            "positions": {symbol: position.to_dict() for symbol, position in self.positions.items()},
            "orders": [order.to_dict() for order in self.orders],
        }
