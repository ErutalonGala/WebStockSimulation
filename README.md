# 股票模拟交易训练平台

这是一个用于训练股票模拟交易与复盘能力的基础 Web 应用骨架。项目包含 React 前端、FastAPI 后端和 SQLite 数据库配置，后续可以继续接入真实行情供应商、策略回测、用户认证和更完整的交易风控逻辑。

## 项目结构

```text
.
├── backend/                 # FastAPI 后端服务
│   ├── app/
│   │   ├── main.py          # API 入口、健康检查、会话和交易接口
│   │   ├── db/              # SQLAlchemy 数据库连接
│   │   ├── models/          # 训练会话、交易、持仓、资金曲线模型
│   │   └── services/        # 行情数据与模拟交易引擎
│   └── requirements.txt     # Python 依赖
├── database/
│   └── schema.sql           # SQLite 初始表结构说明
├── frontend/                # Vite + React 前端应用
│   ├── src/
│   │   ├── main.jsx         # 训练会话与行情交互界面
│   │   └── styles.css       # 页面样式
│   └── package.json         # 前端依赖和脚本
└── README.md
```

## 核心模块

- **股票历史数据获取模块**：`backend/app/services/market_data.py` 提供确定性的示例历史收盘价接口，便于前端和训练流程联调。
- **模拟交易引擎**：`backend/app/services/trading_engine.py` 负责买入、卖出、现金余额、持仓均价和资金曲线写入。
- **训练会话管理**：`backend/app/main.py` 提供创建训练会话与提交交易的 API，并在会话创建时初始化资金曲线。
- **前端交互界面**：`frontend/src/main.jsx` 提供后端健康检查、创建 Demo 会话和查询股票历史数据的基础 UI。
- **数据库配置**：后端默认使用 SQLite，运行服务时会在 `database/trading_trainer.db` 自动创建数据表；`database/schema.sql` 也提供了表结构参考。

## 后端启动

> 建议使用 Python 3.11+。

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

后端启动后可访问：

- `GET http://localhost:8000/health`
- `GET http://localhost:8000/market-data/AAPL`
- `POST http://localhost:8000/sessions`
- `POST http://localhost:8000/sessions/{session_id}/trades`

## 前端启动

> 建议使用 Node.js 20+。

```bash
cd frontend
npm install
npm run dev
```

默认前端地址为 `http://localhost:5173`。如需修改后端地址，可设置环境变量：

```bash
VITE_API_BASE_URL=http://localhost:8000 npm run dev
```

## 数据库说明

当前默认数据库连接为：

```text
sqlite:///./database/trading_trainer.db
```

从仓库根目录启动后端时，SQLite 文件会生成在 `database/trading_trainer.db`。如果要切换到 PostgreSQL，可将 `backend/app/db/session.py` 中的 `DATABASE_URL` 替换为类似：

```text
postgresql+psycopg://user:password@localhost:5432/trading_trainer
```

并安装对应数据库驱动。
