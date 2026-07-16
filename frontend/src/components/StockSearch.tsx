import React from 'react';

export type Market = 'us' | 'cn';

type StockSearchProps = {
  market: Market;
  symbol: string;
  startDate: string;
  initialCash: number | string;
  loading: boolean;
  onMarketChange: (value: Market) => void;
  onSymbolChange: (value: string) => void;
  onStartDateChange: (value: string) => void;
  onInitialCashChange: (value: string) => void;
  onSubmit: (event: React.FormEvent<HTMLFormElement>) => void;
};

export default function StockSearch({
  market,
  symbol,
  startDate,
  initialCash,
  loading,
  onMarketChange,
  onSymbolChange,
  onStartDateChange,
  onInitialCashChange,
  onSubmit,
}: StockSearchProps) {
  const isAshare = market === 'cn';

  function handleMarketChange(nextMarket: Market) {
    onMarketChange(nextMarket);
    onSymbolChange(nextMarket === 'cn' ? '贵州茅台' : 'AAPL');
  }

  function handleSymbolChange(value: string) {
    onSymbolChange(isAshare ? value.trim() : value.toUpperCase().trim());
  }

  return (
    <form onSubmit={onSubmit} className="form-stack simulator-form">
      <fieldset className="market-toggle" aria-label="选择股票市场">
        <legend>市场</legend>
        <button type="button" className={market === 'us' ? 'active' : ''} onClick={() => handleMarketChange('us')}>
          美股
        </button>
        <button type="button" className={market === 'cn' ? 'active' : ''} onClick={() => handleMarketChange('cn')}>
          A股
        </button>
      </fieldset>
      <label>
        {isAshare ? '股票代码 / 中文名称' : '股票代码'}
        <input
          value={symbol}
          onChange={(event) => handleSymbolChange(event.target.value)}
          placeholder={isAshare ? '600519 或 贵州茅台' : 'AAPL'}
          required
        />
      </label>
      <label>
        开始日期
        <input type="date" value={startDate} onChange={(event) => onStartDateChange(event.target.value)} required />
      </label>
      <label>
        初始资金
        <input
          type="number"
          min="1"
          step="1"
          value={initialCash}
          onChange={(event) => onInitialCashChange(event.target.value)}
          required
        />
      </label>
      <button disabled={loading}>{loading ? '训练初始化中...' : '开始训练'}</button>
    </form>
  );
}
