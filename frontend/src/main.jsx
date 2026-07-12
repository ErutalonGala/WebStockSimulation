import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';
import PortfolioSummary from '../components/PortfolioSummary';
import EquityCurve from '../components/EquityCurve';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function money(value) {
  return new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'USD' }).format(value || 0);
}

function App() {
  const [symbol, setSymbol] = useState('AAPL');
  const [startDate, setStartDate] = useState('2024-01-02');
  const [initialCash, setInitialCash] = useState(100000);
  const [session, setSession] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function request(path, options = {}) {
    const response = await fetch(`${API_BASE_URL}${path}`, options);
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || '请求失败');
    }
    return data;
  }

  async function createSession(event) {
    event.preventDefault();
    setLoading(true);
    setError('');
    try {
      const data = await request('/api/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol, start_date: startDate, initial_cash: Number(initialCash) })
      });
      setSession(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function nextDay() {
    if (!session) return;
    setLoading(true);
    setError('');
    try {
      setSession(await request(`/api/sessions/${session.id}/next-day`, { method: 'POST' }));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const bar = session?.current_bar;

  return (
    <main className="app-shell">
      <section className="hero">
        <div>
          <p className="eyebrow">Trading Trainer</p>
          <h1>股票模拟交易训练平台</h1>
          <p>创建训练会话后，点击“下一天”会沿历史行情中的有效交易日推进，自动跳过周末、节假日和无行情日期。</p>
        </div>
        <div className="status-card">
          <span>当前训练日</span>
          <strong>{session ? session.current_trading_date : '未开始'}</strong>
        </div>
      </section>

      <section className="grid">
        <article className="card">
          <h2>创建训练会话</h2>
          <form onSubmit={createSession} className="form-stack">
            <label>
              股票代码
              <input value={symbol} onChange={(event) => setSymbol(event.target.value.toUpperCase())} placeholder="AAPL" />
            </label>
            <label>
              开始日期
              <input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
            </label>
            <label>
              初始资金
              <input type="number" min="1" value={initialCash} onChange={(event) => setInitialCash(event.target.value)} />
            </label>
            <button disabled={loading}>{loading ? '处理中...' : '创建会话'}</button>
          </form>
          {error && <p className="error">{error}</p>}
        </article>

        <article className="card">
          <h2>会话资产</h2>
          <PortfolioSummary session={session} onNextDay={nextDay} loading={loading} />
        </article>
      </section>

      <section className="card market-card">
        <h2>资产曲线</h2>
        <EquityCurve snapshots={session?.daily_snapshots} />
      </section>

      {bar && (
        <section className="card market-card">
          <h2>当日行情</h2>
          <dl className="metrics market-metrics">
            <div><dt>日期</dt><dd>{bar.date}</dd></div>
            <div><dt>开盘</dt><dd>{money(bar.open)}</dd></div>
            <div><dt>最高</dt><dd>{money(bar.high)}</dd></div>
            <div><dt>最低</dt><dd>{money(bar.low)}</dd></div>
            <div><dt>收盘</dt><dd>{money(bar.close)}</dd></div>
            <div><dt>成交量</dt><dd>{bar.volume?.toLocaleString() || '-'}</dd></div>
          </dl>
        </section>
      )}
    </main>
  );
}

createRoot(document.getElementById('root')).render(<App />);
