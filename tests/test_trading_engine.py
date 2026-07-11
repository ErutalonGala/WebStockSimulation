from __future__ import annotations

import pytest

from backend.models.order import OrderSide, PriceMode
from backend.models.position import TradingSessionState
from backend.services.trading_engine import OrderCommand, TradingCostConfig, TradingEngine, TradingRuleError


def test_buy_and_sell_updates_cash_position_cost_pnl_and_records():
    session = TradingSessionState(session_id="unit", initial_cash=10_000, cash=10_000)
    engine = TradingEngine()

    buy = engine.execute_order(
        session,
        OrderCommand(
            symbol="aapl",
            side=OrderSide.BUY,
            quantity=100,
            price_mode=PriceMode.CUSTOM,
            custom_price=10,
            costs=TradingCostConfig(fee_rate=0.001, stamp_tax_rate=0.001, slippage_rate=0.001),
        ),
    )
    sell = engine.execute_order(
        session,
        OrderCommand(
            symbol="AAPL",
            side=OrderSide.SELL,
            quantity=40,
            price_mode=PriceMode.CLOSE,
            close_price=12,
            costs=TradingCostConfig(fee_rate=0.001, stamp_tax_rate=0.001, slippage_rate=0.001),
        ),
    )

    assert buy.cash == 8998
    assert buy.position.quantity == 60
    assert sell.position.average_cost == 10.02
    assert sell.realized_pnl == pytest.approx(77.76)
    assert len(session.orders) == 2


def test_rejects_insufficient_cash_and_position():
    session = TradingSessionState(session_id="unit", initial_cash=100, cash=100)
    engine = TradingEngine()

    with pytest.raises(TradingRuleError, match="买入金额不能超过可用现金"):
        engine.execute_order(
            session,
            OrderCommand(symbol="MSFT", side=OrderSide.BUY, quantity=2, custom_price=100),
        )

    with pytest.raises(TradingRuleError, match="卖出数量不能超过当前持仓"):
        engine.execute_order(
            session,
            OrderCommand(symbol="MSFT", side=OrderSide.SELL, quantity=1, custom_price=100),
        )


def test_orders_api_returns_result_and_validation_errors():
    fastapi = pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from backend.main import app, trading_sessions

    client = TestClient(app)
    trading_sessions.clear()

    created = client.post("/api/sessions/demo", json={"initial_cash": 1000})
    assert created.status_code == 200

    bought = client.post(
        "/api/sessions/demo/orders",
        json={"symbol": "TSLA", "side": "BUY", "quantity": 5, "price_mode": "next_open", "next_open_price": 20},
    )
    assert bought.status_code == 200
    payload = bought.json()
    assert payload["success"] is True
    assert payload["cash"] == 899.97
    assert payload["position"]["quantity"] == 5
    assert payload["order"]["price_mode"] == "next_open"

    rejected = client.post(
        "/api/sessions/demo/orders",
        json={"symbol": "TSLA", "side": "SELL", "quantity": 6, "custom_price": 20},
    )
    assert rejected.status_code == 400
    assert rejected.json()["detail"]["error"] == "卖出数量不能超过当前持仓"
