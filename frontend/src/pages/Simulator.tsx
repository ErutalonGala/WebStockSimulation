import React, { useMemo, useState } from 'react';
import OrderPanel from '../components/OrderPanel';
import PortfolioSummary from '../components/PortfolioSummary';
import PriceChart from '../components/PriceChart';
import StockSearch, { type Market } from '../components/StockSearch';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

type MarketBar = {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

type Session = {
  id: string;
  symbol: string;
  current_trading_date: string;
  current_day_index: number;
  start_date: string;
  current_bar: MarketBar;
  market_data?: MarketBar[];
  current_cash: number;
  current_position_quantity: number;
  current_position_cost: number;
  is_complete: boolean;
  total_assets?: number;
};

const money = (value: number | null | undefined) =>
  new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'USD' }).format(value || 0);

const numberText = (value: number | null | undefined) => value?.toLocaleString('zh-CN') || '-';

function getChartStartDate(sessionStartDate: string) {
  const date = new Date(sessionStartDate);
  date.setUTCFullYear(date.getUTCFullYear() - 1);
  return date.toISOString().slice(0, 10);
}

async function request(path: string, options: RequestInit = {}) {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, options);
  } catch {
    throw new Error(`无法连接后端服务，请确认 API 地址 ${API_BASE_URL} 可访问，并检查 CORS/端口配置。`);
  }

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || '请求失败，请稍后重试。');
  }
  return data;
}

export default function Simulator() {
  const [market, setMarket] = useState<Market>('us');
  const [symbol, setSymbol] = useState('AAPL');
  const [startDate, setStartDate] = useState('2024-01-02');
  const [initialCash, setInitialCash] = useState<number | string>(100000);
  const [session, setSession] = useState<Session | null>(null);
  const [history, setHistory] = useState<MarketBar[]>([]);
  const [cash, setCash] = useState(0);
  const [positionQuantity, setPositionQuantity] = useState(0);
  const [positionCost, setPositionCost] = useState(0);
  const [previousTotalAssets, setPreviousTotalAssets] = useState(0);
  const [buyQuantity, setBuyQuantity] = useState<number | string>(100);
  const [sellQuantity, setSellQuantity] = useState<number | string>(100);
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [tradeMessage, setTradeMessage] = useState('');
  const [dataMessage, setDataMessage] = useState('');

  const currentBar = session?.current_bar;
  const closePrice = currentBar?.close || 0;
  const marketValue = positionQuantity * closePrice;
  const totalCost = positionQuantity * positionCost;
  const floatingPnl = marketValue - totalCost;
  const totalAssets = cash + marketValue;
  const dailyPnl = session ? totalAssets - previousTotalAssets : 0;
  const controlsDisabled = !session || !currentBar;

  const chartBars = useMemo(() => {
    if (history.length > 0) return history;
    return currentBar ? [currentBar] : [];
  }, [currentBar, history]);

  async function startTraining(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setErrorMessage('');
    setTradeMessage('');
    setDataMessage('');
    try {
      const created = await request('/api/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol, start_date: startDate, initial_cash: Number(initialCash) }),
      });
      setSession(created);
      setCash(Number(created.current_cash));
      setPositionQuantity(Number(created.current_position_quantity || 0));
      setPositionCost(Number(created.current_position_cost || 0));
      setPreviousTotalAssets(Number(created.total_assets || created.current_cash));

      try {
        const chartStartDate = getChartStartDate(created.start_date);
        const encodedSymbol = encodeURIComponent(created.symbol);
        const historyPayload = await request(`/api/stocks/${encodedSymbol}/history?start_date=${chartStartDate}`);
        setHistory(historyPayload.data || [created.current_bar]);
      } catch (historyError) {
        setHistory([created.current_bar]);
        setDataMessage(`数据加载失败：${(historyError as Error).message} 已仅显示当前交易日行情。`);
      }
    } catch (error) {
      setSession(null);
      setErrorMessage(`数据加载失败：${(error as Error).message}`);
    } finally {
      setLoading(false);
    }
  }

  function executeBuy(quantity: number) {
    if (!currentBar) return;
    const cost = quantity * currentBar.close;
    if (!Number.isInteger(quantity) || quantity <= 0) {
      setTradeMessage('交易失败：买入数量必须为正整数。');
      return;
    }
    if (cost > cash) {
      setTradeMessage('交易失败：买入金额不能超过当前现金。');
      return;
    }
    const newQuantity = positionQuantity + quantity;
    setPositionCost((positionCost * positionQuantity + cost) / newQuantity);
    setPositionQuantity(newQuantity);
    setCash(cash - cost);
    setTradeMessage(`买入成功：以收盘价 ${money(currentBar.close)} 买入 ${quantity} 股。`);
  }

  function buy() {
    executeBuy(Number(buyQuantity));
  }

  function setBuyPositionFraction(fraction: number) {
    if (!currentBar) return;
    const quantity = Math.floor((cash * fraction) / currentBar.close);
    setBuyQuantity(quantity);
    setTradeMessage(`已填入买入数量：${quantity} 股。请点击买入确认交易。`);
  }

  function setSellPositionFraction(fraction: number) {
    const quantity = Math.floor(positionQuantity * fraction);
    setSellQuantity(quantity);
    setTradeMessage(`已填入卖出数量：${quantity} 股。请点击卖出确认交易。`);
  }

  function sell() {
    if (!currentBar) return;
    const quantity = Number(sellQuantity);
    if (!Number.isInteger(quantity) || quantity <= 0) {
      setTradeMessage('交易失败：卖出数量必须为正整数。');
      return;
    }
    if (quantity > positionQuantity) {
      setTradeMessage('交易失败：卖出数量不能超过当前持仓。');
      return;
    }
    const remaining = positionQuantity - quantity;
    setPositionQuantity(remaining);
    setPositionCost(remaining === 0 ? 0 : positionCost);
    setCash(cash + quantity * currentBar.close);
    setTradeMessage(`卖出成功：以收盘价 ${money(currentBar.close)} 卖出 ${quantity} 股。`);
  }

  async function nextDay() {
    if (!session) return;
    setLoading(true);
    setErrorMessage('');
    setTradeMessage('');
    setPreviousTotalAssets(totalAssets);
    try {
      setSession(await request(`/api/sessions/${session.id}/next-day`, { method: 'POST' }));
    } catch (error) {
      setErrorMessage(`训练结束：${(error as Error).message}`);
    } finally {
      setLoading(false);
    }
  }

  async function nextWeek() {
    if (!session) return;
    setLoading(true);
    setErrorMessage('');
    setTradeMessage('');
    setPreviousTotalAssets(totalAssets);
    try {
      setSession(await request(`/api/sessions/${session.id}/next-week`, { method: 'POST' }));
    } catch (error) {
      setErrorMessage(`训练结束：${(error as Error).message}`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="app-shell">
      <section className="hero">
        <div>
          <p className="eyebrow">Trading Simulator</p>
          <h1>前端模拟交易训练</h1>
          <p>选择股票、开始日期和初始资金后，按历史交易日推进训练，并使用当日收盘价进行模拟买卖。</p>
        </div>
        <div className="status-card">
          <span>当前日期</span>
          <strong>{session ? session.current_trading_date : '未开始'}</strong>
          {session?.is_complete && <p className="warning">训练结束：已到达最后一个有效交易日。</p>}
        </div>
      </section>

      <section className="card setup-card">
        <h2>训练初始化</h2>
        <StockSearch
          market={market}
          symbol={symbol}
          startDate={startDate}
          initialCash={initialCash}
          loading={loading}
          onMarketChange={setMarket}
          onSymbolChange={setSymbol}
          onStartDateChange={setStartDate}
          onInitialCashChange={setInitialCash}
          onSubmit={startTraining}
        />
        {errorMessage && <p className="error">{errorMessage}</p>}
        {dataMessage && <p className="warning">{dataMessage}</p>}
      </section>

      <section className="simulator-workspace" aria-label="模拟交易工作区">
        <article className="card chart-card">
          <h2>股价曲线</h2>
          {currentBar ? (
            <PriceChart bars={chartBars} currentDate={session.current_trading_date} />
          ) : (
            <p className="muted">训练尚未开始，暂无行情数据。</p>
          )}
        </article>

        <aside className="side-panel">
          <article className="card trade-card">
            <h2>买入 / 卖出</h2>
            <OrderPanel
              buyQuantity={buyQuantity}
              sellQuantity={sellQuantity}
              loading={loading}
              disabled={controlsDisabled}
              isComplete={Boolean(session?.is_complete)}
              onBuyQuantityChange={setBuyQuantity}
              onSellQuantityChange={setSellQuantity}
              onBuy={buy}
              onSell={sell}
              onBuyPositionFraction={setBuyPositionFraction}
              onSellPositionFraction={setSellPositionFraction}
              onNextDay={nextDay}
              onNextWeek={nextWeek}
            />
            {tradeMessage && <p className={tradeMessage.startsWith('交易失败') ? 'error' : 'success'}>{tradeMessage}</p>}
          </article>

          <article className="card data-card">
            <h2>账户与行情数据</h2>
            {currentBar ? (
              <dl className="metrics market-metrics">
                <div><dt>当前日期</dt><dd>{currentBar.date}</dd></div>
                <div><dt>开盘价</dt><dd>{money(currentBar.open)}</dd></div>
                <div><dt>最高价</dt><dd>{money(currentBar.high)}</dd></div>
                <div><dt>最低价</dt><dd>{money(currentBar.low)}</dd></div>
                <div><dt>收盘价</dt><dd>{money(currentBar.close)}</dd></div>
                <div><dt>成交量</dt><dd>{numberText(currentBar.volume)}</dd></div>
              </dl>
            ) : (
              <p className="muted">训练尚未开始，暂无行情数据。</p>
            )}
            {session ? (
              <PortfolioSummary
                cash={cash}
                positionQuantity={positionQuantity}
                positionCost={positionCost}
                marketValue={marketValue}
                floatingPnl={floatingPnl}
                dailyPnl={dailyPnl}
                totalAssets={totalAssets}
              />
            ) : (
              <p className="muted">训练尚未开始，请先创建训练会话。</p>
            )}
          </article>
        </aside>
      </section>
    </main>
  );
}
