import React from 'react';

type PriceBar = { date: string; close?: number | null };

type PriceChartProps = { bars: PriceBar[]; currentIndex: number };

export default function PriceChart({ bars, currentIndex }: PriceChartProps) {
  const visibleBars = bars.slice(0, currentIndex + 1).filter((bar) => typeof bar.close === 'number');
  if (visibleBars.length === 0) {
    return <p className="muted">暂无可绘制行情数据。</p>;
  }

  const width = 760;
  const height = 260;
  const padding = 32;
  const prices = visibleBars.map((bar) => bar.close as number);
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const span = max - min || 1;
  const points = visibleBars.map((bar, index) => {
    const x = visibleBars.length === 1 ? width / 2 : padding + (index * (width - padding * 2)) / (visibleBars.length - 1);
    const y = height - padding - (((bar.close as number) - min) * (height - padding * 2)) / span;
    return { ...bar, x, y };
  });
  const path = points.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`).join(' ');

  return (
    <div className="price-chart">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="收盘价折线图">
        <path className="chart-line" d={path} />
        {points.map((point) => <circle key={point.date} cx={point.x} cy={point.y} r="4" />)}
      </svg>
      <div className="curve-caption">
        <span>{visibleBars[0].date}</span>
        <span>{visibleBars[visibleBars.length - 1].date}</span>
      </div>
    </div>
  );
}
