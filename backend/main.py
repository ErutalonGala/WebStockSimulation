"""FastAPI entrypoint exposing stock history and training-session endpoints."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from backend.services.market_data import (
    DataSourceRateLimitError,
    DataSourceUnavailableError,
    InvalidSymbolError,
    MarketDataService,
)
from backend.services.training_session import (
    TrainingSessionCompleteError,
    TrainingSessionNotFoundError,
    TrainingSessionService,
)

app = FastAPI(title="codex_rp market data API")
market_data_service = MarketDataService()
training_session_service = TrainingSessionService(market_data_service=market_data_service)


class TrainingSessionCreate(BaseModel):
    """Request body for creating a training session."""

    symbol: str = Field(min_length=1, max_length=32)
    start_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    initial_cash: float = Field(gt=0)


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


@app.post("/api/sessions")
def create_training_session(payload: TrainingSessionCreate) -> dict[str, object]:
    """Create a training session starting at the next available trading day."""

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
    """Return the current state of a training session."""

    try:
        return training_session_service.get_session(session_id)
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
