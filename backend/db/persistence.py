"""SQLite persistence layer for market data and training sessions."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Iterable

from backend.models.order import Order
from backend.models.position import Position
from backend.models.training_session import AssetSnapshot, TrainingSession
from backend.services.market_data import DailyBar

DATABASE_PATH = Path(__file__).resolve().parents[2] / "database" / "trading_trainer.db"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "migrations" / "001_training_persistence.sql"


class TrainingSessionRepository:
    """Persist and restore training sessions, stock prices, orders, and snapshots."""

    def __init__(self, database_path: str | Path | None = None) -> None:
        self.database_path = Path(database_path or DATABASE_PATH)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def save_stock_prices(self, symbol: str, bars: Iterable[DailyBar]) -> None:
        normalized = symbol.strip().upper()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO stocks(symbol, name) VALUES(?, ?) "
                "ON CONFLICT(symbol) DO UPDATE SET updated_at = CURRENT_TIMESTAMP",
                (normalized, normalized),
            )
            conn.executemany(
                """
                INSERT INTO stock_prices(symbol, date, open, high, low, close, adj_close, volume, amount)
                VALUES(:symbol, :date, :open, :high, :low, :close, :adj_close, :volume, :amount)
                ON CONFLICT(symbol, date) DO UPDATE SET
                    open = excluded.open,
                    high = excluded.high,
                    low = excluded.low,
                    close = excluded.close,
                    adj_close = excluded.adj_close,
                    volume = excluded.volume,
                    amount = excluded.amount
                """,
                [{"symbol": normalized, **asdict(bar)} for bar in bars],
            )

    def save_session(self, session: TrainingSession) -> None:
        position_payload = {
            symbol: asdict(position) for symbol, position in self._positions(session).items()
        }
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO training_sessions(
                    id, symbol, start_date, initial_cash, current_day_index, current_cash,
                    current_position_quantity, current_position_cost, current_positions, created_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    symbol = excluded.symbol,
                    start_date = excluded.start_date,
                    initial_cash = excluded.initial_cash,
                    current_day_index = excluded.current_day_index,
                    current_cash = excluded.current_cash,
                    current_position_quantity = excluded.current_position_quantity,
                    current_position_cost = excluded.current_position_cost,
                    current_positions = excluded.current_positions
                """,
                (
                    session.id,
                    session.symbol,
                    session.start_date,
                    session.initial_cash,
                    session.current_day_index,
                    session.current_cash,
                    session.current_position_quantity,
                    session.current_position_cost,
                    json.dumps(position_payload, ensure_ascii=False),
                    session.created_at,
                ),
            )
            conn.execute("DELETE FROM portfolio_snapshots WHERE session_id = ?", (session.id,))
            conn.executemany(
                """
                INSERT INTO portfolio_snapshots(
                    session_id, date, cash, position_quantity, position_cost, close_price,
                    market_value, total_assets, floating_pnl, floating_pnl_ratio,
                    daily_pnl, cumulative_return
                ) VALUES(:session_id, :date, :cash, :position_quantity, :position_cost, :close_price,
                    :market_value, :total_assets, :floating_pnl, :floating_pnl_ratio,
                    :daily_pnl, :cumulative_return)
                """,
                [{"session_id": session.id, **asdict(snapshot)} for snapshot in session.daily_snapshots],
            )

    def save_order(self, order: Order, trade_date: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO orders(
                    id, session_id, symbol, date, side, price, quantity, fee, stamp_tax,
                    slippage, realized_pnl, cash_after, position_quantity_after,
                    position_cost_after, price_mode, executed_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id, session_id) DO UPDATE SET
                    date = excluded.date,
                    side = excluded.side,
                    price = excluded.price,
                    quantity = excluded.quantity,
                    fee = excluded.fee
                """,
                (
                    order.id, order.session_id, order.symbol, trade_date, order.side.value,
                    order.price, order.quantity, order.fee, order.stamp_tax, order.slippage,
                    order.realized_pnl, order.cash_after, order.position_quantity_after,
                    order.position_cost_after, order.price_mode.value, order.executed_at.isoformat(),
                ),
            )

    def list_sessions(self) -> list[dict[str, object]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, symbol, start_date, initial_cash, current_day_index, current_cash, "
                "current_position_quantity, current_position_cost, created_at "
                "FROM training_sessions ORDER BY created_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def load_session(self, session_id: str, market_data: list[DailyBar]) -> TrainingSession | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM training_sessions WHERE id = ?", (session_id,)).fetchone()
            if row is None:
                return None
            snapshots = conn.execute(
                "SELECT date, cash, position_quantity, position_cost, close_price, market_value, "
                "total_assets, floating_pnl, floating_pnl_ratio, daily_pnl, cumulative_return "
                "FROM portfolio_snapshots WHERE session_id = ? ORDER BY date",
                (session_id,),
            ).fetchall()
        session = TrainingSession(
            id=row["id"], symbol=row["symbol"], start_date=row["start_date"],
            initial_cash=row["initial_cash"], market_data=market_data,
            current_day_index=row["current_day_index"], current_cash=row["current_cash"],
            current_position_quantity=row["current_position_quantity"],
            current_position_cost=row["current_position_cost"], created_at=row["created_at"],
        )
        session.daily_snapshots = [AssetSnapshot(**dict(snapshot)) for snapshot in snapshots]
        return session

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
            self._migrate_existing_schema(conn)

    def _migrate_existing_schema(self, conn: sqlite3.Connection) -> None:
        """Bring older training session tables up to the current lightweight schema."""

        training_session_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(training_sessions)").fetchall()
        }
        expected_columns = {
            "symbol": "TEXT",
            "start_date": "TEXT",
            "initial_cash": "REAL NOT NULL DEFAULT 0",
            "current_day_index": "INTEGER NOT NULL DEFAULT 0",
            "current_cash": "REAL NOT NULL DEFAULT 0",
            "current_position_quantity": "INTEGER NOT NULL DEFAULT 0",
            "current_position_cost": "REAL NOT NULL DEFAULT 0",
            "current_positions": "TEXT NOT NULL DEFAULT '{}'",
            "created_at": "TEXT",
        }

        for column_name, column_definition in expected_columns.items():
            if column_name not in training_session_columns:
                conn.execute(
                    f"ALTER TABLE training_sessions ADD COLUMN {column_name} {column_definition}"
                )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @staticmethod
    def _positions(session: TrainingSession) -> dict[str, Position]:
        return {
            session.symbol: Position(
                symbol=session.symbol,
                quantity=session.current_position_quantity,
                average_cost=session.current_position_cost,
            )
        }
