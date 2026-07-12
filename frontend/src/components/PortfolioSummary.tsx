import React from 'react';

const money = (value: number | null | undefined) =>
  new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'USD' }).format(value || 0);

type PortfolioSummaryProps = {
  cash: number;
  positionQuantity: number;
  positionCost: number;
  marketValue: number;
  floatingPnl: number;
  dailyPnl: number;
  totalAssets: number;
};

export default function PortfolioSummary({
  cash,
  positionQuantity,
  positionCost,
  marketValue,
  floatingPnl,
  dailyPnl,
  totalAssets,
}: PortfolioSummaryProps) {
  return (
    <dl className="metrics">
      <div><dt>当前现金</dt><dd>{money(cash)}</dd></div>
      <div><dt>持仓数量</dt><dd>{positionQuantity}</dd></div>
      <div><dt>持仓成本</dt><dd>{money(positionCost)}</dd></div>
      <div><dt>当前市值</dt><dd>{money(marketValue)}</dd></div>
      <div><dt>浮盈</dt><dd className={floatingPnl >= 0 ? 'positive' : 'negative'}>{money(floatingPnl)}</dd></div>
      <div><dt>当日盈亏</dt><dd className={dailyPnl >= 0 ? 'positive' : 'negative'}>{money(dailyPnl)}</dd></div>
      <div><dt>总资产</dt><dd>{money(totalAssets)}</dd></div>
    </dl>
  );
}
