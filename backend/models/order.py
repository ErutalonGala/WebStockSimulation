"""Order domain models for the simulated trading engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum


class OrderSide(StrEnum):
    """Supported order directions."""

    BUY = "BUY"
    SELL = "SELL"


class PriceMode(StrEnum):
    """Supported execution price sources for buy orders."""

    CLOSE = "close"
    NEXT_OPEN = "next_open"
    CUSTOM = "custom"


@dataclass(frozen=True)
class Order:
    """A persisted execution record for a simulated trade."""

    id: int
    session_id: str
    symbol: str
    side: OrderSide
    quantity: int
    price: float
    price_mode: PriceMode
    notional: float
    fee: float
    stamp_tax: float
    slippage: float
    realized_pnl: float
    cash_after: float
    position_quantity_after: int
    position_cost_after: float
    executed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation for API responses."""

        return {
            "id": self.id,
            "session_id": self.session_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "quantity": self.quantity,
            "price": self.price,
            "price_mode": self.price_mode.value,
            "notional": self.notional,
            "fee": self.fee,
            "stamp_tax": self.stamp_tax,
            "slippage": self.slippage,
            "realized_pnl": self.realized_pnl,
            "cash_after": self.cash_after,
            "position_quantity_after": self.position_quantity_after,
            "position_cost_after": self.position_cost_after,
            "executed_at": self.executed_at.isoformat(),
        }
