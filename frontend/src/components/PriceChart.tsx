import React, { useState } from 'react';

type PriceBar = { date: string; close?: number | null };

type PriceChartProps = { bars: PriceBar[]; currentDate: string };

type ChartPoint = PriceBar & { close: number; x: number; y: number };

type MovingAveragePoint = { date: string; value: number; x: number; y: number };

const priceFormatter = new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'USD' });

const buildPath = (points: Array<{ x: number; y: number }>) => points.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`).join(' ');

const calculateMovingAverage = (bars: Array<PriceBar & { close: number }>, windowSize: number) => bars.reduce<Array<{ date: string; value: number; index: number }>>((averages, bar, index) => {
  if (index + 1 < windowSize) {
    return averages;
  }

  const windowBars = bars.slice(index + 1 - windowSize, index + 1);
  const value = windowBars.reduce((sum, windowBar) => sum + windowBar.close, 0) / windowSize;
  averages.push({ date: bar.date, value, index });
  return averages;
}, []);

export default function PriceChart({ bars, currentDate }: PriceChartProps) {
  const [showMa5, setShowMa5] = useState(true);
  const [showMa10, setShowMa10] = useState(true);
  const [showMa30, setShowMa30] = useState(true);
  const [hoveredPoint, setHoveredPoint] = useState<ChartPoint | null>(null);

  const currentBarIndex = bars.findIndex((bar) => bar.date === currentDate);
  const visibleBars = bars
    .slice(0, currentBarIndex >= 0 ? currentBarIndex + 1 : bars.length)
    .filter((bar): bar is PriceBar & { close: number } => typeof bar.close === 'number');
  if (visibleBars.length === 0) {
    return <p className="muted">暂无可绘制行情数据。</p>;
  }

  const width = 760;
  const height = 260;
  const padding = 32;
  const ma5 = calculateMovingAverage(visibleBars, 5);
  const ma10 = calculateMovingAverage(visibleBars, 10);
  const ma30 = calculateMovingAverage(visibleBars, 30);
  const enabledMovingAverageValues = [
    ...(showMa5 ? ma5.map((point) => point.value) : []),
    ...(showMa10 ? ma10.map((point) => point.value) : []),
    ...(showMa30 ? ma30.map((point) => point.value) : []),
  ];
  const prices = visibleBars.map((bar) => bar.close);
  const yValues = [...prices, ...enabledMovingAverageValues];
  const min = Math.min(...yValues);
  const max = Math.max(...yValues);
  const span = max - min || 1;
  const getX = (index: number) => (visibleBars.length === 1 ? width / 2 : padding + (index * (width - padding * 2)) / (visibleBars.length - 1));
  const getY = (value: number) => height - padding - ((value - min) * (height - padding * 2)) / span;
  const points: ChartPoint[] = visibleBars.map((bar, index) => ({ ...bar, x: getX(index), y: getY(bar.close) }));
  const path = buildPath(points);
  const mapMovingAveragePoints = (averages: Array<{ date: string; value: number; index: number }>): MovingAveragePoint[] => averages.map((point) => ({
    date: point.date,
    value: point.value,
    x: getX(point.index),
    y: getY(point.value),
  }));
  const ma5Path = buildPath(mapMovingAveragePoints(ma5));
  const ma10Path = buildPath(mapMovingAveragePoints(ma10));
  const ma30Path = buildPath(mapMovingAveragePoints(ma30));
  const tooltipWidth = 132;
  const tooltipHeight = 54;
  const tooltipX = hoveredPoint ? Math.min(hoveredPoint.x + 12, width - padding - tooltipWidth) : 0;
  const tooltipY = hoveredPoint ? Math.max(padding / 2, hoveredPoint.y - tooltipHeight - 12) : 0;

  return (
    <div className="price-chart">
      <div className="ma-controls" aria-label="移动均线显示设置">
        <label>
          <input type="checkbox" checked={showMa5} onChange={(event) => setShowMa5(event.target.checked)} />
          5日均线
        </label>
        <label>
          <input type="checkbox" checked={showMa10} onChange={(event) => setShowMa10(event.target.checked)} />
          10日均线
        </label>
        <label>
          <input type="checkbox" checked={showMa30} onChange={(event) => setShowMa30(event.target.checked)} />
          30日均线
        </label>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="收盘价与移动均线折线图">
        <path className="chart-line" d={path} />
        {showMa5 && ma5Path && <path className="ma-line ma5" d={ma5Path} />}
        {showMa10 && ma10Path && <path className="ma-line ma10" d={ma10Path} />}
        {showMa30 && ma30Path && <path className="ma-line ma30" d={ma30Path} />}
        {points.map((point) => (
          <circle
            key={point.date}
            cx={point.x}
            cy={point.y}
            r="4"
            tabIndex={0}
            aria-label={`${point.date} 收盘价 ${priceFormatter.format(point.close)}`}
            onMouseEnter={() => setHoveredPoint(point)}
            onMouseLeave={() => setHoveredPoint(null)}
            onFocus={() => setHoveredPoint(point)}
            onBlur={() => setHoveredPoint(null)}
          >
            <title>{`${point.date} 收盘价 ${priceFormatter.format(point.close)}`}</title>
          </circle>
        ))}
        {hoveredPoint && (
          <g className="chart-tooltip" pointerEvents="none">
            <line className="chart-hover-line" x1={hoveredPoint.x} x2={hoveredPoint.x} y1={padding} y2={height - padding} />
            <rect className="chart-tooltip-bg" x={tooltipX} y={tooltipY} width={tooltipWidth} height={tooltipHeight} rx="8" />
            <text className="chart-tooltip-text" x={tooltipX + 10} y={tooltipY + 21}>
              {hoveredPoint.date}
            </text>
            <text className="chart-tooltip-text chart-tooltip-price" x={tooltipX + 10} y={tooltipY + 40}>
              {priceFormatter.format(hoveredPoint.close)}
            </text>
          </g>
        )}
      </svg>
      <div className="curve-caption">
        <span>{visibleBars[0].date}</span>
        <span>{visibleBars[visibleBars.length - 1].date}</span>
      </div>
    </div>
  );
}
