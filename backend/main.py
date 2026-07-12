"""FastAPI entrypoint exposing stock history and persistent training-session endpoints."""

from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
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
from backend.services.training_session import (
    TrainingSessionCompleteError,
    TrainingSessionNotFoundError,
    TrainingSessionService,
)

app = FastAPI(title="codex_rp market data API")

def _get_cors_allow_origins() -> list[str]:
    """Return configured CORS origins, defaulting to local Vite dev servers."""

    configured_origins = os.getenv("CORS_ALLOW_ORIGINS")
    if configured_origins:
        return [origin.strip() for origin in configured_origins.split(",") if origin.strip()]
    return ["http://localhost:5173", "http://127.0.0.1:5173"]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_cors_allow_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)
market_data_service = MarketDataService()
training_session_service = TrainingSessionService(market_data_service=market_data_service)
trading_engine = TradingEngine()

# Backward-compatible in-memory account store for the order API tests and simple demos.
trading_sessions: dict[str, TradingSessionState] = {}


class TrainingSessionCreate(BaseModel):
    """Request body for creating a stock replay training session."""

    symbol: str = Field(min_length=1, max_length=32)
    start_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    initial_cash: float = Field(gt=0)


class DemoSessionCreate(BaseModel):
    """Request body for creating a simple order-training account."""

    initial_cash: float = Field(default=100000.0, gt=0)


class OrderCreate(BaseModel):
    """Request body for executing a simulated order."""

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

    training_session_service.repository.save_stock_prices(symbol, bars)
    return {
        "symbol": symbol.strip().upper(),
        "start_date": bars[0].date,
        "end_date": bars[-1].date,
        "count": len(bars),
        "data": [bar.__dict__ for bar in bars],
    }


@app.get("/api/sessions")
def list_training_sessions() -> dict[str, object]:
    """Return historical training records that can be resumed."""

    return {"sessions": training_session_service.list_sessions()}


@app.post("/api/sessions")
def create_training_session(payload: TrainingSessionCreate) -> dict[str, object]:
    """Create and persist a training session starting at the next available trading day."""

    try:
        return training_session_service.create_session(
            symbol=payload.symbol,
            start_date=payload.start_date,
            initial_cash=payload.initial_cash,
        )
    except InvalidSymbolError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DataSourceRateLimitError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except DataSourceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/sessions/{session_id}")
def get_training_session(session_id: str) -> dict[str, object]:
    """Return the current state of a training session, loading it from storage if needed."""

    try:
        return training_session_service.get_session(session_id)
    except TrainingSessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/sessions/{session_id}/continue")
def continue_training_session(session_id: str) -> dict[str, object]:
    """Resume a persisted training session for continued day-by-day training."""

    try:
        return training_session_service.continue_session(session_id)
    except TrainingSessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/sessions/{session_id}/next-day")
def advance_training_session(session_id: str) -> dict[str, object]:
    """Advance a training session to the next valid market-data trading day."""

    try:
        return training_session_service.next_day(session_id)
    except TrainingSessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TrainingSessionCompleteError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/sessions/{session_id}")
def create_demo_order_session(session_id: str, payload: DemoSessionCreate) -> dict[str, object]:
    """Create a simple account session for order execution practice."""

    session = TradingSessionState(
        session_id=session_id,
        initial_cash=payload.initial_cash,
        cash=payload.initial_cash,
    )
    trading_sessions[session_id] = session
    return session.to_dict()


@app.post("/api/sessions/{session_id}/orders")
def execute_order(session_id: str, payload: OrderCreate) -> dict[str, object]:
    """Execute a simulated order and persist it when it belongs to a stock replay session."""

    account = trading_sessions.get(session_id)
    replay_session = None
    if account is None:
        try:
            replay_session = training_session_service._get_session(session_id)
        except TrainingSessionNotFoundError as exc:
            raise HTTPException(status_code=404, detail="训练会话不存在") from exc
        account = TradingSessionState(
            session_id=replay_session.id,
            initial_cash=replay_session.initial_cash,
            cash=replay_session.current_cash,
        )
        if replay_session.current_position_quantity:
            from backend.models.position import Position

            account.positions[replay_session.symbol] = Position(
                symbol=replay_session.symbol,
                quantity=replay_session.current_position_quantity,
                average_cost=replay_session.current_position_cost,
            )

    try:
        result = trading_engine.execute_order(
            account,
            OrderCommand(
                symbol=payload.symbol,
                side=payload.side,
                quantity=payload.quantity,
                price_mode=payload.price_mode,
                close_price=payload.close_price,
                next_open_price=payload.next_open_price,
                custom_price=payload.custom_price,
                costs=TradingCostConfig(payload.fee_rate, payload.stamp_tax_rate, payload.slippage_rate),
            ),
        )
    except TradingRuleError as exc:
        raise HTTPException(status_code=400, detail={"error": str(exc)}) from exc

    if replay_session is not None:
        replay_session.current_cash = result.cash
        replay_session.current_position_quantity = result.position.quantity
        replay_session.current_position_cost = result.position.average_cost
        training_session_service.performance_service.capture_snapshot(replay_session)
        training_session_service.persist_order(replay_session, result.order)
    else:
        trading_sessions[session_id] = account

    return result.to_dict()
