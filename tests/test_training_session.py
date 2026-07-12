from __future__ import annotations

import json
import sqlite3

import pytest

from backend.db.persistence import TrainingSessionRepository
from backend.models.training_session import TrainingSession
from backend.services.market_data import DailyBar
from backend.services.training_session import (
    TrainingSessionCompleteError,
    TrainingSessionService,
)


class FakeMarketDataService:
    def get_history(self, symbol, start_date=None, end_date=None):
        assert symbol == "AAPL"
        assert start_date == "2024-01-06"
        return [
            DailyBar(
                date="2024-01-08",
                open=100,
                high=110,
                low=99,
                close=105,
                adj_close=105,
                volume=1000,
            ),
            DailyBar(
                date="2024-01-09",
                open=106,
                high=112,
                low=104,
                close=111,
                adj_close=111,
                volume=1200,
            ),
        ]


def test_create_session_starts_on_next_valid_trading_day():
    service = TrainingSessionService(market_data_service=FakeMarketDataService())

    session = service.create_session("AAPL", "2024-01-06", 100000)

    assert session["current_trading_date"] == "2024-01-08"
    assert session["current_day_index"] == 0
    assert session["current_cash"] == 100000
    assert session["current_position_quantity"] == 0
    assert session["current_position_cost"] == 0
    assert session["daily_snapshots"][0]["total_assets"] == 100000


def test_next_day_advances_to_next_market_bar_only():
    service = TrainingSessionService(market_data_service=FakeMarketDataService())
    created = service.create_session("AAPL", "2024-01-06", 100000)

    advanced = service.next_day(created["id"])

    assert advanced["current_trading_date"] == "2024-01-09"
    assert advanced["current_day_index"] == 1
    assert advanced["is_complete"] is True
    assert len(advanced["daily_snapshots"]) == 2

    with pytest.raises(TrainingSessionCompleteError):
        service.next_day(created["id"])


def test_performance_metrics_and_snapshots_use_current_close():
    service = TrainingSessionService(market_data_service=FakeMarketDataService())
    created = service.create_session("AAPL", "2024-01-06", 100000)
    raw_session = service._get_session(created["id"])
    raw_session.current_cash = 89500
    raw_session.current_position_quantity = 100
    raw_session.current_position_cost = 100

    first_day = service.get_session(created["id"])

    assert first_day["market_value"] == 10500
    assert first_day["total_assets"] == 100000
    assert first_day["floating_pnl"] == 500
    assert first_day["floating_pnl_ratio"] == 0.05
    assert first_day["daily_pnl"] == 0
    assert first_day["cumulative_return"] == 0

    advanced = service.next_day(created["id"])

    assert advanced["market_value"] == 11100
    assert advanced["total_assets"] == 100600
    assert advanced["floating_pnl"] == 1100
    assert advanced["daily_pnl"] == 600
    assert advanced["cumulative_return"] == 0.006
    assert advanced["daily_snapshots"][-1]["cumulative_return"] == 0.006


def test_repository_migrates_legacy_training_sessions_without_symbol(tmp_path):
    database_path = tmp_path / "legacy.db"
    with sqlite3.connect(database_path) as conn:
        conn.execute("""
            CREATE TABLE training_sessions (
                id TEXT PRIMARY KEY,
                start_date TEXT NOT NULL,
                initial_cash REAL NOT NULL,
                current_day_index INTEGER NOT NULL DEFAULT 0,
                current_cash REAL NOT NULL,
                current_position_quantity INTEGER NOT NULL DEFAULT 0,
                current_position_cost REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """)

    repository = TrainingSessionRepository(database_path)
    session = TrainingSession(
        symbol="AAPL",
        start_date="2024-01-06",
        initial_cash=100000,
        market_data=[
            DailyBar(
                date="2024-01-08",
                open=100,
                high=110,
                low=99,
                close=105,
                adj_close=105,
                volume=1000,
            ),
        ],
    )

    repository.save_session(session)

    with sqlite3.connect(database_path) as conn:
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(training_sessions)")
        }
        saved = conn.execute(
            "SELECT symbol, current_positions FROM training_sessions WHERE id = ?",
            (session.id,),
        ).fetchone()

    assert "symbol" in columns
    assert "current_positions" in columns
    assert saved[0] == "AAPL"
    assert json.loads(saved[1])["AAPL"]["symbol"] == "AAPL"


def test_repository_rebuilds_legacy_integer_session_ids(tmp_path):
    database_path = tmp_path / "legacy_integer_id.db"
    with sqlite3.connect(database_path) as conn:
        conn.execute("""
            CREATE TABLE training_sessions (
                id INTEGER PRIMARY KEY,
                start_date TEXT NOT NULL,
                initial_cash REAL NOT NULL,
                current_day_index INTEGER NOT NULL DEFAULT 0,
                current_cash REAL NOT NULL,
                current_position_quantity INTEGER NOT NULL DEFAULT 0,
                current_position_cost REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """)

    repository = TrainingSessionRepository(database_path)
    session = TrainingSession(
        symbol="AAPL",
        start_date="2024-01-06",
        initial_cash=100000,
        market_data=[
            DailyBar(
                date="2024-01-08",
                open=100,
                high=110,
                low=99,
                close=105,
                adj_close=105,
                volume=1000,
            ),
        ],
    )

    repository.save_session(session)

    with sqlite3.connect(database_path) as conn:
        id_column = next(
            row
            for row in conn.execute("PRAGMA table_info(training_sessions)")
            if row[1] == "id"
        )
        saved = conn.execute(
            "SELECT id, symbol FROM training_sessions WHERE id = ?",
            (session.id,),
        ).fetchone()

    assert id_column[2].upper() == "TEXT"
    assert saved == (session.id, "AAPL")


def _migration_versions(database_path):
    with sqlite3.connect(database_path) as conn:
        return [
            row[0]
            for row in conn.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            ).fetchall()
        ]


def test_repository_initializes_empty_database_with_migration_versions(tmp_path):
    database_path = tmp_path / "empty.db"

    TrainingSessionRepository(database_path)

    with sqlite3.connect(database_path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        training_session_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(training_sessions)")
        }

    assert "schema_migrations" in tables
    assert "training_sessions" in tables
    assert "symbol" in training_session_columns
    assert _migration_versions(database_path) == [
        "001_training_persistence",
        "002_training_sessions_symbol",
    ]


def test_repository_skips_previously_applied_001_migration(tmp_path):
    database_path = tmp_path / "applied_001.db"
    with sqlite3.connect(database_path) as conn:
        conn.executescript("""
            CREATE TABLE schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            INSERT INTO schema_migrations(version) VALUES('001_training_persistence');
            CREATE TABLE training_sessions (
                id TEXT PRIMARY KEY,
                start_date TEXT NOT NULL,
                initial_cash REAL NOT NULL,
                current_day_index INTEGER NOT NULL DEFAULT 0,
                current_cash REAL NOT NULL,
                current_position_quantity INTEGER NOT NULL DEFAULT 0,
                current_position_cost REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """)

    TrainingSessionRepository(database_path)

    with sqlite3.connect(database_path) as conn:
        training_session_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(training_sessions)")
        }

    assert "symbol" in training_session_columns
    assert "current_positions" in training_session_columns
    assert _migration_versions(database_path) == [
        "001_training_persistence",
        "002_training_sessions_symbol",
    ]


class WeekFakeMarketDataService:
    def get_history(self, symbol, start_date=None, end_date=None):
        assert symbol == "AAPL"
        assert start_date == "2024-01-02"
        return [
            DailyBar(
                date=f"2024-01-{day:02d}",
                open=100 + day,
                high=101 + day,
                low=99 + day,
                close=100 + day,
                adj_close=100 + day,
                volume=1000 + day,
            )
            for day in range(2, 10)
        ]


def test_next_week_advances_five_market_bars(tmp_path):
    repository = TrainingSessionRepository(tmp_path / "week.db")
    service = TrainingSessionService(
        market_data_service=WeekFakeMarketDataService(), repository=repository
    )
    created = service.create_session("AAPL", "2024-01-02", 100000)

    advanced = service.next_week(created["id"])

    assert advanced["current_trading_date"] == "2024-01-07"
    assert advanced["current_day_index"] == 5
    assert advanced["is_complete"] is False
    assert len(advanced["daily_snapshots"]) == 2


def test_next_week_stops_at_final_market_bar_when_less_than_five_days_remain(tmp_path):
    repository = TrainingSessionRepository(tmp_path / "partial_week.db")
    service = TrainingSessionService(
        market_data_service=WeekFakeMarketDataService(), repository=repository
    )
    created = service.create_session("AAPL", "2024-01-02", 100000)

    service.next_week(created["id"])
    advanced = service.next_week(created["id"])

    assert advanced["current_trading_date"] == "2024-01-09"
    assert advanced["current_day_index"] == 7
    assert advanced["is_complete"] is True
    assert len(advanced["daily_snapshots"]) == 3

    with pytest.raises(TrainingSessionCompleteError):
        service.next_week(created["id"])


def test_next_week_api_route_advances_session(monkeypatch, tmp_path):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    import backend.main as main

    repository = TrainingSessionRepository(tmp_path / "api_week.db")
    service = TrainingSessionService(
        market_data_service=WeekFakeMarketDataService(), repository=repository
    )
    created = service.create_session("AAPL", "2024-01-02", 100000)
    monkeypatch.setattr(main, "training_session_service", service)

    client = TestClient(main.app)
    response = client.post(f"/api/sessions/{created['id']}/next-week")

    assert response.status_code == 200
    payload = response.json()
    assert payload["current_day_index"] == 5
    assert payload["current_trading_date"] == "2024-01-07"
