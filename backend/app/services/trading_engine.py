from sqlalchemy.orm import Session

from app.models.trading import EquityCurvePoint, Position, Trade, TrainingSession


class TradingEngine:
    def __init__(self, db: Session):
        self.db = db

    def execute_trade(self, session: TrainingSession, symbol: str, side: str, quantity: int, price: float) -> Trade:
        symbol = symbol.upper()
        notional = quantity * price
        if side == "BUY" and session.cash_balance < notional:
            raise ValueError("现金余额不足")

        position = self._get_or_create_position(session.id, symbol)
        if side == "BUY":
            total_cost = position.average_cost * position.quantity + notional
            position.quantity += quantity
            position.average_cost = total_cost / position.quantity
            session.cash_balance -= notional
        elif side == "SELL":
            if position.quantity < quantity:
                raise ValueError("持仓数量不足")
            position.quantity -= quantity
            session.cash_balance += notional
        else:
            raise ValueError("side 必须为 BUY 或 SELL")

        trade = Trade(session_id=session.id, symbol=symbol, side=side, quantity=quantity, price=price)
        self.db.add(trade)
        self.db.flush()

        self.db.add(EquityCurvePoint(session_id=session.id, equity=self._calculate_equity(session, trade)))
        self.db.commit()
        self.db.refresh(trade)
        return trade

    def _get_or_create_position(self, session_id: int, symbol: str) -> Position:
        position = self.db.query(Position).filter_by(session_id=session_id, symbol=symbol).one_or_none()
        if position is None:
            position = Position(session_id=session_id, symbol=symbol)
            self.db.add(position)
            self.db.flush()
        return position

    def _calculate_equity(self, session: TrainingSession, latest_trade: Trade) -> float:
        """Compute cash plus every open position marked to the latest known price."""
        latest_prices = self._latest_prices_by_symbol(session.id, latest_trade)
        positions_value = 0.0
        for position in self.db.query(Position).filter(Position.session_id == session.id, Position.quantity > 0):
            mark_price = latest_prices.get(position.symbol, position.average_cost)
            positions_value += position.quantity * mark_price

        return session.cash_balance + positions_value

    def _latest_prices_by_symbol(self, session_id: int, latest_trade: Trade) -> dict[str, float]:
        prices = {latest_trade.symbol: latest_trade.price}
        for trade in (
            self.db.query(Trade)
            .filter(Trade.session_id == session_id, Trade.symbol != latest_trade.symbol)
            .order_by(Trade.executed_at.desc(), Trade.id.desc())
        ):
            prices.setdefault(trade.symbol, trade.price)
        return prices
