from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import Base, engine, get_db
from app.models.trading import EquityCurvePoint, TrainingSession
from app.services.market_data import get_historical_prices
from app.services.trading_engine import TradingEngine

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Trading Trainer API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SessionCreate(BaseModel):
    user_name: str = Field(default="demo-user", min_length=1)
    initial_cash: float = Field(default=100000.0, gt=0)


class TradeCreate(BaseModel):
    symbol: str = Field(min_length=1, max_length=16)
    side: str = Field(pattern="^(BUY|SELL)$")
    quantity: int = Field(gt=0)
    price: float = Field(gt=0)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/market-data/{symbol}")
def historical_market_data(symbol: str) -> dict[str, object]:
    return {"symbol": symbol.upper(), "prices": get_historical_prices(symbol)}


@app.post("/sessions")
def create_training_session(payload: SessionCreate, db: Session = Depends(get_db)) -> dict[str, object]:
    session = TrainingSession(
        user_name=payload.user_name,
        initial_cash=payload.initial_cash,
        cash_balance=payload.initial_cash,
    )
    db.add(session)
    db.flush()
    db.add(EquityCurvePoint(session_id=session.id, equity=payload.initial_cash))
    db.commit()
    db.refresh(session)
    return {
        "id": session.id,
        "user_name": session.user_name,
        "initial_cash": session.initial_cash,
        "cash_balance": session.cash_balance,
        "created_at": session.created_at.isoformat(),
    }


@app.post("/sessions/{session_id}/trades")
def execute_trade(session_id: int, payload: TradeCreate, db: Session = Depends(get_db)) -> dict[str, object]:
    session = db.get(TrainingSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="训练会话不存在")
    try:
        trade = TradingEngine(db).execute_trade(
            session=session,
            symbol=payload.symbol,
            side=payload.side,
            quantity=payload.quantity,
            price=payload.price,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "id": trade.id,
        "session_id": trade.session_id,
        "symbol": trade.symbol,
        "side": trade.side,
        "quantity": trade.quantity,
        "price": trade.price,
        "executed_at": trade.executed_at.isoformat(),
    }
