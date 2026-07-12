-- Persistent training schema for stock replay sessions.
CREATE TABLE IF NOT EXISTS stocks (
  symbol TEXT PRIMARY KEY,
  name TEXT,
  exchange TEXT,
  currency TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS stock_prices (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  symbol TEXT NOT NULL REFERENCES stocks(symbol) ON DELETE CASCADE,
  date TEXT NOT NULL,
  open REAL,
  high REAL,
  low REAL,
  close REAL,
  adj_close REAL,
  volume INTEGER,
  amount REAL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(symbol, date)
);

CREATE TABLE IF NOT EXISTS training_sessions (
  id TEXT PRIMARY KEY,
  symbol TEXT NOT NULL REFERENCES stocks(symbol),
  start_date TEXT NOT NULL,
  initial_cash REAL NOT NULL,
  current_day_index INTEGER NOT NULL DEFAULT 0,
  current_cash REAL NOT NULL,
  current_position_quantity INTEGER NOT NULL DEFAULT 0,
  current_position_cost REAL NOT NULL DEFAULT 0,
  current_positions TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS orders (
  id INTEGER NOT NULL,
  session_id TEXT NOT NULL REFERENCES training_sessions(id) ON DELETE CASCADE,
  symbol TEXT NOT NULL,
  date TEXT NOT NULL,
  side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
  price REAL NOT NULL,
  quantity INTEGER NOT NULL CHECK (quantity > 0),
  fee REAL NOT NULL DEFAULT 0,
  stamp_tax REAL NOT NULL DEFAULT 0,
  slippage REAL NOT NULL DEFAULT 0,
  realized_pnl REAL NOT NULL DEFAULT 0,
  cash_after REAL NOT NULL,
  position_quantity_after INTEGER NOT NULL,
  position_cost_after REAL NOT NULL,
  price_mode TEXT NOT NULL DEFAULT 'custom',
  executed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(id, session_id)
);

CREATE TABLE IF NOT EXISTS portfolio_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT NOT NULL REFERENCES training_sessions(id) ON DELETE CASCADE,
  date TEXT NOT NULL,
  cash REAL NOT NULL,
  position_quantity INTEGER NOT NULL,
  position_cost REAL NOT NULL,
  close_price REAL NOT NULL,
  market_value REAL NOT NULL,
  total_assets REAL NOT NULL,
  floating_pnl REAL NOT NULL DEFAULT 0,
  floating_pnl_ratio REAL NOT NULL DEFAULT 0,
  daily_pnl REAL NOT NULL DEFAULT 0,
  cumulative_return REAL NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(session_id, date)
);
