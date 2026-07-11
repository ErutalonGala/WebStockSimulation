"""FastAPI entrypoint exposing stock history endpoints."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from backend.models.order import OrderSide, PriceMode
from backend.models.position import TradingSessionState
from backend.services.market_data import (
    DataSourceRateLimitError,
    DataSourceUnavailableError,
    InvalidSymbolError,
    MarketDataService,
)
from backend.services.trading_engine import OrderCommand, TradingCostConfig, TradingEngine, TradingRuleError

app = FastAPI(title="codex_rp market data API")
market_data_service = MarketDataService()
trading_engine = TradingEngine()
trading_sessions: dict[str, TradingSessionState] = {}


class TradingSessionCreate(BaseModel):
    """Request body for creating or resetting a trading session."""

    initial_cash: float = Field(default=100000.0, gt=0)


class OrderCreate(BaseModel):
    """Request body for executing an order in a trading session."""

    symbol: str = Field(min_length=1, max_length=32)
    side: OrderSide
    quantity: int = Field(gt=0)
    price_mode: PriceMode = PriceMode.CUSTOM
    close_price: float | None = Field(default=None, gt=0)
    next_open_price: float | None = Field(default=None, gt=0)
    custom_price: float | None = Field(default=None, gt=0)
    fee_rate: float = Field(default=0.0003, ge=0)
    stamp_tax_rate: float = Field(default=0.001, ge=0)
    slippage_rate: float = Field(default=0.0, ge=0)


@app.get("/api/stocks/{symbol}/history")
def get_stock_history(
    symbol: str,
    start_date: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    end_date: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
) -> dict[str, object]:
    """Return cached daily history for a stock symbol."""

    try:
        bars = market_data_service.get_history(symbol, start_date=start_date, end_date=end_date)
    except InvalidSymbolError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DataSourceRateLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except DataSourceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        "symbol": symbol.strip().upper(),
        "start_date": bars[0].date,
        "end_date": bars[-1].date,
        "count": len(bars),
        "data": [bar.__dict__ for bar in bars],
    }


@app.post("/api/sessions/{session_id}")
def create_trading_session(session_id: str, payload: TradingSessionCreate) -> dict[str, object]:
    """Create or reset a simulated trading session with an initial cash balance."""

    session = TradingSessionState(
        session_id=session_id,
        initial_cash=payload.initial_cash,
        cash=payload.initial_cash,
    )
    trading_sessions[session_id] = session
    return {"success": True, "session": session.to_dict()}


@app.post("/api/sessions/{session_id}/orders")
def create_order(session_id: str, payload: OrderCreate) -> dict[str, object]:
    """Execute a buy or sell order and return updated cash, position, P&L, and records."""

    session = trading_sessions.setdefault(
        session_id,
        TradingSessionState(session_id=session_id, initial_cash=100000.0, cash=100000.0),
    )
    try:
        result = trading_engine.execute_order(
            session,
            OrderCommand(
                symbol=payload.symbol,
                side=payload.side,
                quantity=payload.quantity,
                price_mode=payload.price_mode,
                close_price=payload.close_price,
                next_open_price=payload.next_open_price,
                custom_price=payload.custom_price,
                costs=TradingCostConfig(
                    fee_rate=payload.fee_rate,
                    stamp_tax_rate=payload.stamp_tax_rate,
                    slippage_rate=payload.slippage_rate,
                ),
            ),
        )
    except TradingRuleError as exc:
        raise HTTPException(status_code=400, detail={"success": False, "error": str(exc)}) from exc
    return result.to_dict()
