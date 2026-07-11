"""FastAPI entrypoint exposing stock history endpoints."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query

from backend.services.market_data import (
    DataSourceRateLimitError,
    DataSourceUnavailableError,
    InvalidSymbolError,
    MarketDataService,
)

app = FastAPI(title="codex_rp market data API")
market_data_service = MarketDataService()


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
