# Market data API

This backend exposes daily stock history through FastAPI:

```bash
uvicorn backend.main:app --reload
```

Endpoints:

```http
GET /api/stocks/search?query=AAPL
GET /api/stocks/{symbol}/history?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
```

The service accepts symbols such as `AAPL`, `TSLA`, and `600519.SS`, fetches daily history from Yahoo Finance with a Stooq CSV fallback, and caches full-symbol responses under `backend/.cache/market_data` by default. Set `MARKET_DATA_CACHE_DIR` to override the cache location.

If both remote providers are blocked by the runtime environment or rate-limited upstream, the history endpoint returns a `503` with provider diagnostics instead of an empty dataset.
