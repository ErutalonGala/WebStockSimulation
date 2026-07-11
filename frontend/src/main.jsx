import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function App() {
  const [health, setHealth] = useState('检查中...');
  const [session, setSession] = useState(null);
  const [symbol, setSymbol] = useState('AAPL');
  const [prices, setPrices] = useState([]);

  useEffect(() => {
    fetch(`${API_BASE_URL}/health`)
      .then((res) => res.json())
      .then((data) => setHealth(data.status))
      .catch(() => setHealth('后端未连接'));
  }, []);

  async function createSession() {
    const response = await fetch(`${API_BASE_URL}/sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_name: 'demo-user', initial_cash: 100000 })
    });
    setSession(await response.json());
  }

  async function loadPrices() {
    const response = await fetch(`${API_BASE_URL}/market-data/${symbol}`);
    const data = await response.json();
    setPrices(data.prices);
  }

  return (
    <main className="app-shell">
      <section className="hero">
        <div>
          <p className="eyebrow">Trading Trainer</p>
          <h1>股票模拟交易训练平台</h1>
          <p>集成历史行情、模拟交易引擎、训练会话和资金曲线记录，帮助用户复盘并训练交易策略。</p>
        </div>
        <div className="status-card">
          <span>后端状态</span>
          <strong>{health}</strong>
        </div>
      </section>

      <section className="grid">
        <article className="card">
          <h2>训练会话</h2>
          <p>创建一段独立训练，后端会初始化现金、持仓和资金曲线。</p>
          <button onClick={createSession}>创建 Demo 会话</button>
          {session && <pre>{JSON.stringify(session, null, 2)}</pre>}
        </article>

        <article className="card">
          <h2>股票历史数据</h2>
          <p>输入股票代码，加载后端示例行情模块返回的历史价格。</p>
          <div className="row">
            <input value={symbol} onChange={(event) => setSymbol(event.target.value.toUpperCase())} />
            <button onClick={loadPrices}>获取数据</button>
          </div>
          <ul className="price-list">
            {prices.map((price) => (
              <li key={price.date}>{price.date}: ${price.close}</li>
            ))}
          </ul>
        </article>
      </section>
    </main>
  );
}

createRoot(document.getElementById('root')).render(<App />);
