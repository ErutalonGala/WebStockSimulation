# Market data API

This backend exposes daily stock history through FastAPI:

```bash
# 从仓库根目录启动
uvicorn app.main:app --reload

# 或从 backend 目录启动
cd backend
uvicorn app.main:app --reload
```

Endpoint:

```http
GET /api/stocks/{symbol}/history?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
```

The service accepts symbols such as `AAPL`, `TSLA`, and `600519.SS`, fetches daily history from Yahoo Finance from listing date to the current date, and caches full-symbol responses under `backend/.cache/market_data` by default. Set `MARKET_DATA_CACHE_DIR` to override the cache location.
