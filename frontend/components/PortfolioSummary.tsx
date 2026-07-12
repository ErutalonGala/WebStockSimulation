import React from 'react';

function money(value: number | null | undefined) {
  return new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'USD' }).format(value || 0);
}

function percent(value: number | null | undefined) {
  return `${(((value || 0) as number) * 100).toFixed(2)}%`;
}

type PortfolioSummaryProps = {
  session: any;
  onNextDay: () => void;
  loading: boolean;
};

export default function PortfolioSummary({ session, onNextDay, loading }: PortfolioSummaryProps) {
  if (!session) {
    return <p className="muted">训练尚未开始。请先创建训练会话后查看账户统计。</p>;
  }

  if (!session.has_valid_market_data) {
    return <p className="muted">{session.performance_message || '当前日期没有有效行情数据，暂时无法计算账户统计。'}</p>;
  }

  return (
    <>
      <dl className="metrics">
        <div><dt>初始资金</dt><dd>{money(session.initial_cash)}</dd></div>
        <div><dt>当前现金</dt><dd>{money(session.current_cash)}</dd></div>
        <div><dt>当前持仓</dt><dd>{session.current_position_quantity}</dd></div>
        <div><dt>持仓成本</dt><dd>{money(session.current_position_cost)}</dd></div>
        <div><dt>持仓市值</dt><dd>{money(session.market_value)}</dd></div>
        <div><dt>总资产</dt><dd>{money(session.total_assets)}</dd></div>
        <div><dt>浮动盈亏</dt><dd className={session.floating_pnl >= 0 ? 'positive' : 'negative'}>{money(session.floating_pnl)}</dd></div>
        <div><dt>浮动盈亏比例</dt><dd className={session.floating_pnl_ratio >= 0 ? 'positive' : 'negative'}>{percent(session.floating_pnl_ratio)}</dd></div>
        <div><dt>当日盈亏</dt><dd className={session.daily_pnl >= 0 ? 'positive' : 'negative'}>{money(session.daily_pnl)}</dd></div>
        <div><dt>累计收益率</dt><dd className={session.cumulative_return >= 0 ? 'positive' : 'negative'}>{percent(session.cumulative_return)}</dd></div>
      </dl>
      <button onClick={onNextDay} disabled={loading || session.is_complete}>下一天</button>
      {session.is_complete && <p className="muted">已到达最后一个有效交易日。</p>}
    </>
  );
}
