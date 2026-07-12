"""FastAPI entrypoint exposing stock history endpoints."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from backend.services.market_data import (
    DataSourceRateLimitError,
    DataSourceUnavailableError,
    InvalidSymbolError,
    MarketDataService,
)

app = FastAPI(title="codex_rp market data API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)
market_data_service = MarketDataService()


@app.get("/api/stocks/search")
def search_stocks(query: str = Query(min_length=1, max_length=32)) -> dict[str, object]:
    """Return a normalized exact-symbol candidate for clients with a search box."""

    symbol = query.strip().upper()
    if not symbol or any(char.isspace() for char in symbol):
        raise HTTPException(status_code=400, detail="query must be a stock symbol without spaces")
    return {"query": query, "count": 1, "data": [{"symbol": symbol}]}


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
