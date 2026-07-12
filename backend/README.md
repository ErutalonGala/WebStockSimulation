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

## SQLite 本地数据库 schema 变更处理

后端默认使用的 SQLite 数据库路径定义在 `backend/db/persistence.py` 的 `DATABASE_PATH`，当前为仓库根目录下的 `database/trading_trainer.db`。

项目已提供版本化迁移，迁移脚本位于 `backend/migrations/`，应用启动或初始化 `TrainingSessionRepository` 时会自动执行尚未应用的迁移。遇到 schema 变更时，请优先直接启动应用让自动迁移完成，而不是立即删除数据库。

如果本地运行时报错 `table training_sessions has no column named symbol`，通常表示本地 `database/trading_trainer.db` 中的表结构落后于当前代码。建议按以下安全步骤处理：

1. 先停止正在运行的后端服务。
2. 备份现有数据库，例如：
   ```bash
   cp database/trading_trainer.db database/trading_trainer.db.bak
   ```
3. 重新启动应用，让版本化迁移自动补齐缺失列。
4. 如果自动迁移仍无法修复，并且可以接受丢弃本地数据，再删除旧库后重新启动应用：
   ```bash
   rm database/trading_trainer.db
   ```

注意：删除 `database/trading_trainer.db` 会清空本地训练会话、订单记录和资产快照数据；只有在已备份且确认不再需要这些本地数据时才执行删除。
