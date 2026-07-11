import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.models.trading import EquityCurvePoint, TrainingSession
from app.services.trading_engine import TradingEngine


class TradingEngineTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        self.session = TrainingSession(user_name="tester", initial_cash=1000.0, cash_balance=1000.0)
        self.db.add(self.session)
        self.db.commit()
        self.db.refresh(self.session)

    def tearDown(self):
        self.db.close()

    def test_equity_curve_includes_all_open_positions_after_cross_symbol_trade(self):
        engine = TradingEngine(self.db)

        engine.execute_trade(self.session, "AAPL", "BUY", 2, 100.0)
        engine.execute_trade(self.session, "MSFT", "BUY", 3, 50.0)

        latest_equity = (
            self.db.query(EquityCurvePoint)
            .filter_by(session_id=self.session.id)
            .order_by(EquityCurvePoint.id.desc())
            .first()
            .equity
        )

        self.assertEqual(latest_equity, 1000.0)

    def test_equity_curve_keeps_other_positions_when_selling_one_symbol(self):
        engine = TradingEngine(self.db)

        engine.execute_trade(self.session, "AAPL", "BUY", 2, 100.0)
        engine.execute_trade(self.session, "MSFT", "BUY", 3, 50.0)
        engine.execute_trade(self.session, "MSFT", "SELL", 1, 60.0)

        latest_equity = (
            self.db.query(EquityCurvePoint)
            .filter_by(session_id=self.session.id)
            .order_by(EquityCurvePoint.id.desc())
            .first()
            .equity
        )

        self.assertEqual(latest_equity, 1030.0)

    def test_equity_uses_latest_price_for_previously_traded_symbols(self):
        engine = TradingEngine(self.db)

        engine.execute_trade(self.session, "AAPL", "BUY", 1, 100.0)
        engine.execute_trade(self.session, "AAPL", "BUY", 1, 120.0)
        engine.execute_trade(self.session, "MSFT", "BUY", 3, 50.0)

        latest_equity = (
            self.db.query(EquityCurvePoint)
            .filter_by(session_id=self.session.id)
            .order_by(EquityCurvePoint.id.desc())
            .first()
            .equity
        )

        self.assertEqual(latest_equity, 1020.0)


if __name__ == "__main__":
    unittest.main()
