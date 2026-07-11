"""Simulated trading engine with cash, position, cost, and P&L accounting."""

from __future__ import annotations

from dataclasses import dataclass

from backend.models.order import Order, OrderSide, PriceMode
from backend.models.position import Position, TradingSessionState


@dataclass(frozen=True)
class TradingCostConfig:
    """Configurable trading costs expressed as rates of trade notional."""

    fee_rate: float = 0.0003
    stamp_tax_rate: float = 0.001
    slippage_rate: float = 0.0


@dataclass(frozen=True)
class OrderCommand:
    """Input command for executing a simulated order."""

    symbol: str
    side: OrderSide
    quantity: int
    price_mode: PriceMode = PriceMode.CUSTOM
    close_price: float | None = None
    next_open_price: float | None = None
    custom_price: float | None = None
    costs: TradingCostConfig = TradingCostConfig()


@dataclass(frozen=True)
class TradeResult:
    """Successful execution result returned to callers."""

    order: Order
    cash: float
    position: Position
    realized_pnl: float
    session: TradingSessionState

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable API response payload."""

        return {
            "success": True,
            "order": self.order.to_dict(),
            "cash": self.cash,
            "position": self.position.to_dict(),
            "realized_pnl": self.realized_pnl,
            "session": self.session.to_dict(),
        }


class TradingRuleError(ValueError):
    """Raised when an order violates a trading rule."""


class TradingEngine:
    """Execute buy/sell orders against a mutable simulated account."""

    def execute_order(self, session: TradingSessionState, command: OrderCommand) -> TradeResult:
        """Validate and execute one order, updating account state in place."""

        symbol = self._normalize_symbol(command.symbol)
        side = OrderSide(command.side)
        price_mode = PriceMode(command.price_mode)
        quantity = self._validate_quantity(command.quantity)
        price = self._resolve_price(command)
        self._validate_costs(command.costs)

        position = session.positions.setdefault(symbol, Position(symbol=symbol))
        notional = round(quantity * price, 6)
        fee = round(notional * command.costs.fee_rate, 6)
        slippage = round(notional * command.costs.slippage_rate, 6)
        stamp_tax = round(notional * command.costs.stamp_tax_rate, 6) if side == OrderSide.SELL else 0.0
        total_cost = notional + fee + slippage
        realized_delta = 0.0

        if side == OrderSide.BUY:
            if total_cost > session.cash:
                raise TradingRuleError("买入金额不能超过可用现金")
            new_cost = position.average_cost * position.quantity + total_cost
            position.quantity += quantity
            position.average_cost = round(new_cost / position.quantity, 6)
            session.cash = round(session.cash - total_cost, 6)
        else:
            if position.quantity < quantity:
                raise TradingRuleError("卖出数量不能超过当前持仓")
            sale_proceeds = notional - fee - stamp_tax - slippage
            cost_basis = position.average_cost * quantity
            realized_delta = round(sale_proceeds - cost_basis, 6)
            position.quantity -= quantity
            position.realized_pnl = round(position.realized_pnl + realized_delta, 6)
            if position.quantity == 0:
                position.average_cost = 0.0
            session.cash = round(session.cash + sale_proceeds, 6)

        order = Order(
            id=len(session.orders) + 1,
            session_id=session.session_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            price_mode=price_mode,
            notional=notional,
            fee=fee,
            stamp_tax=stamp_tax,
            slippage=slippage,
            realized_pnl=realized_delta,
            cash_after=session.cash,
            position_quantity_after=position.quantity,
            position_cost_after=position.average_cost,
        )
        session.orders.append(order)
        return TradeResult(
            order=order,
            cash=round(session.cash, 6),
            position=position,
            realized_pnl=round(session.realized_pnl, 6),
            session=session,
        )

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        if not symbol or not symbol.strip():
            raise TradingRuleError("股票代码不能为空")
        normalized = symbol.strip().upper()
        if len(normalized) > 32 or any(char.isspace() for char in normalized):
            raise TradingRuleError("股票代码格式无效")
        return normalized

    @staticmethod
    def _validate_quantity(quantity: int) -> int:
        if quantity <= 0:
            raise TradingRuleError("数量必须为正数")
        return quantity

    @staticmethod
    def _validate_costs(costs: TradingCostConfig) -> None:
        for name, value in {
            "手续费率": costs.fee_rate,
            "印花税率": costs.stamp_tax_rate,
            "滑点率": costs.slippage_rate,
        }.items():
            if value < 0:
                raise TradingRuleError(f"{name}不能为负数")

    @staticmethod
    def _resolve_price(command: OrderCommand) -> float:
        price_map = {
            PriceMode.CLOSE: command.close_price,
            PriceMode.NEXT_OPEN: command.next_open_price,
            PriceMode.CUSTOM: command.custom_price,
        }
        price = price_map[PriceMode(command.price_mode)]
        if price is None:
            raise TradingRuleError("缺少所选价格模式对应的成交价")
        if price <= 0:
            raise TradingRuleError("成交价必须为正数")
        return round(price, 6)
