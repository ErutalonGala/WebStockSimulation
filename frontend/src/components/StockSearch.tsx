import React from 'react';

type StockSearchProps = {
  symbol: string;
  startDate: string;
  initialCash: number | string;
  loading: boolean;
  onSymbolChange: (value: string) => void;
  onStartDateChange: (value: string) => void;
  onInitialCashChange: (value: string) => void;
  onSubmit: (event: React.FormEvent<HTMLFormElement>) => void;
};

export default function StockSearch({
  symbol,
  startDate,
  initialCash,
  loading,
  onSymbolChange,
  onStartDateChange,
  onInitialCashChange,
  onSubmit,
}: StockSearchProps) {
  return (
    <form onSubmit={onSubmit} className="form-stack simulator-form">
      <label>
        股票代码
        <input
          value={symbol}
          onChange={(event) => onSymbolChange(event.target.value.toUpperCase())}
          placeholder="AAPL"
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
