import React, { useState } from 'react';

type PriceBar = { date: string; close?: number | null; volume?: number | null };

type TradeMarker = {
  id: string;
  date: string;
  type: 'buy' | 'sell';
  price: number;
  quantity: number;
  pnl?: number;
};

type PriceChartProps = { bars: PriceBar[]; currentDate: string; tradeMarkers?: TradeMarker[] };

type ChartPoint = PriceBar & { close: number; x: number; y: number };

type MovingAveragePoint = { date: string; value: number; x: number; y: number };

type VisibleTradeMarker = TradeMarker & { x: number; y: number; offsetIndex: number };

const priceFormatter = new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'USD' });
const compactNumberFormatter = new Intl.NumberFormat('zh-CN', { notation: 'compact', maximumFractionDigits: 2 });
const pnlFormatter = new Intl.NumberFormat('zh-CN', {
  style: 'currency',
  currency: 'USD',
  signDisplay: 'always',
  maximumFractionDigits: 2,
});

const buildPath = (points: Array<{ x: number; y: number }>) => points.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`).join(' ');

const normalizeIndicatorSpan = (minValue: number, maxValue: number) => {
  if (minValue === maxValue) {
    const fallback = Math.abs(minValue) || 1;
    return { min: minValue - fallback, max: maxValue + fallback };
  }
  return { min: minValue, max: maxValue };
};

const calculateEmaSeries = (bars: Array<PriceBar & { close: number }>, period: number) => {
  const multiplier = 2 / (period + 1);
  return bars.reduce<number[]>((values, bar, index) => {
    const previous = values[index - 1] ?? bar.close;
    values.push(index === 0 ? bar.close : (bar.close - previous) * multiplier + previous);
    return values;
  }, []);
};

const calculateMacd = (bars: Array<PriceBar & { close: number }>) => {
  const ema12 = calculateEmaSeries(bars, 12);
  const ema26 = calculateEmaSeries(bars, 26);
  const difValues = bars.map((_, index) => ema12[index] - ema26[index]);
  const deaValues = difValues.reduce<number[]>((values, dif, index) => {
    const previous = values[index - 1] ?? dif;
    values.push(index === 0 ? dif : (dif - previous) * (2 / (9 + 1)) + previous);
    return values;
  }, []);

  return bars.map((bar, index) => ({
    date: bar.date,
    index,
    dif: difValues[index],
    dea: deaValues[index],
    histogram: (difValues[index] - deaValues[index]) * 2,
  }));
};

const calculateMovingAverage = (bars: Array<PriceBar & { close: number }>, windowSize: number) => bars.reduce<Array<{ date: string; value: number; index: number }>>((averages, bar, index) => {
  if (index + 1 < windowSize) {
    return averages;
  }

  const windowBars = bars.slice(index + 1 - windowSize, index + 1);
  const value = windowBars.reduce((sum, windowBar) => sum + windowBar.close, 0) / windowSize;
  averages.push({ date: bar.date, value, index });
  return averages;
}, []);

export default function PriceChart({ bars, currentDate, tradeMarkers = [] }: PriceChartProps) {
  const [showClosePrice, setShowClosePrice] = useState(true);
  const [showMa5, setShowMa5] = useState(true);
  const [showMa10, setShowMa10] = useState(true);
  const [showMa30, setShowMa30] = useState(true);
  const [zoomLevel, setZoomLevel] = useState(1);
  const [hoveredPoint, setHoveredPoint] = useState<ChartPoint | null>(null);

  const currentBarIndex = bars.findIndex((bar) => bar.date === currentDate);
  const availableBars = bars
    .slice(0, currentBarIndex >= 0 ? currentBarIndex + 1 : bars.length)
    .filter((bar): bar is PriceBar & { close: number } => typeof bar.close === 'number');
  if (availableBars.length === 0) {
    return <p className="muted">暂无可绘制行情数据。</p>;
  }

  const visibleCount = Math.max(2, Math.ceil(availableBars.length / zoomLevel));
  const visibleBars = availableBars.slice(-visibleCount);
  const visibleOffset = availableBars.length - visibleBars.length;
  const width = 1120;
  const height = 720;
  const padding = 48;
  const priceChartHeight = 420;
  const indicatorGap = 28;
  const volumeTop = priceChartHeight + indicatorGap;
  const volumeHeight = 104;
  const macdTop = volumeTop + volumeHeight + indicatorGap;
  const macdHeight = 120;
  const ma5 = calculateMovingAverage(availableBars, 5).filter((point) => point.index >= visibleOffset);
  const ma10 = calculateMovingAverage(availableBars, 10).filter((point) => point.index >= visibleOffset);
  const ma30 = calculateMovingAverage(availableBars, 30).filter((point) => point.index >= visibleOffset);
  const enabledMovingAverageValues = [
    ...(showMa5 ? ma5.map((point) => point.value) : []),
    ...(showMa10 ? ma10.map((point) => point.value) : []),
    ...(showMa30 ? ma30.map((point) => point.value) : []),
  ];
  const prices = visibleBars.map((bar) => bar.close);
  const yValues = [...(showClosePrice ? prices : []), ...enabledMovingAverageValues];
  const safeYValues = yValues.length > 0 ? yValues : prices;
  const min = Math.min(...safeYValues);
  const max = Math.max(...safeYValues);
  const span = max - min || 1;
  const getX = (index: number) => (visibleBars.length === 1 ? width / 2 : padding + (index * (width - padding * 2)) / (visibleBars.length - 1));
  const getY = (value: number) => priceChartHeight - padding - ((value - min) * (priceChartHeight - padding * 2)) / span;
  const points: ChartPoint[] = visibleBars.map((bar, index) => ({ ...bar, x: getX(index), y: getY(bar.close) }));
  const path = buildPath(points);
  const mapMovingAveragePoints = (averages: Array<{ date: string; value: number; index: number }>): MovingAveragePoint[] => averages.map((point) => ({
    date: point.date,
    value: point.value,
    x: getX(point.index - visibleOffset),
    y: getY(point.value),
  }));
  const ma5Path = buildPath(mapMovingAveragePoints(ma5));
  const ma10Path = buildPath(mapMovingAveragePoints(ma10));
  const ma30Path = buildPath(mapMovingAveragePoints(ma30));
  const volumeAmounts = visibleBars.map((bar) => (bar.volume || 0) * bar.close);
  const maxVolumeAmount = Math.max(...volumeAmounts, 1);
  const volumeBars = visibleBars.map((bar, index) => {
    const amount = (bar.volume || 0) * bar.close;
    const barSlotWidth = (width - padding * 2) / Math.max(visibleBars.length, 1);
    return {
      date: bar.date,
      amount,
      x: getX(index),
      y: volumeTop + volumeHeight - (amount / maxVolumeAmount) * volumeHeight,
      width: Math.max(2, Math.min(12, barSlotWidth * 0.68)),
      height: (amount / maxVolumeAmount) * volumeHeight,
    };
  });
  const macd = calculateMacd(availableBars).filter((point) => point.index >= visibleOffset);
  const macdValues = macd.flatMap((point) => [point.dif, point.dea, point.histogram, 0]);
  const { min: macdMin, max: macdMax } = normalizeIndicatorSpan(Math.min(...macdValues), Math.max(...macdValues));
  const macdSpan = macdMax - macdMin || 1;
  const getMacdY = (value: number) => macdTop + macdHeight - ((value - macdMin) * macdHeight) / macdSpan;
  const macdZeroY = getMacdY(0);
  const macdDifPath = buildPath(macd.map((point) => ({ x: getX(point.index - visibleOffset), y: getMacdY(point.dif) })));
  const macdDeaPath = buildPath(macd.map((point) => ({ x: getX(point.index - visibleOffset), y: getMacdY(point.dea) })));
  const visibleIndexByDate = new Map(visibleBars.map((bar, index) => [bar.date, index]));
  const markerCountByDate = new Map<string, number>();
  const visibleTradeMarkers: VisibleTradeMarker[] = tradeMarkers.reduce<VisibleTradeMarker[]>((markers, marker) => {
    const index = visibleIndexByDate.get(marker.date);
    if (index === undefined) return markers;

    const sameDateCount = markerCountByDate.get(marker.date) || 0;
    markerCountByDate.set(marker.date, sameDateCount + 1);
    markers.push({
      ...marker,
      x: getX(index),
      y: getY(marker.price),
      offsetIndex: sameDateCount,
    });
    return markers;
  }, []);
  const tooltipWidth = 148;
  const tooltipHeight = 58;
  const tooltipX = hoveredPoint ? Math.min(hoveredPoint.x + 12, width - padding - tooltipWidth) : 0;
  const tooltipY = hoveredPoint ? Math.max(padding / 2, hoveredPoint.y - tooltipHeight - 12) : 0;

  return (
    <div className="price-chart">
      <div className="chart-toolbar" aria-label="股价图表设置">
        <div className="ma-controls" aria-label="行情曲线显示设置">
          <label>
            <input type="checkbox" checked={showClosePrice} onChange={(event) => setShowClosePrice(event.target.checked)} />
            <span className="legend-text legend-current">当前股价</span>
          </label>
          <label>
            <input type="checkbox" checked={showMa5} onChange={(event) => setShowMa5(event.target.checked)} />
            <span className="legend-text legend-ma5">5日均线</span>
          </label>
          <label>
            <input type="checkbox" checked={showMa10} onChange={(event) => setShowMa10(event.target.checked)} />
            <span className="legend-text legend-ma10">10日均线</span>
          </label>
          <label>
            <input type="checkbox" checked={showMa30} onChange={(event) => setShowMa30(event.target.checked)} />
            <span className="legend-text legend-ma30">30日均线</span>
          </label>
          <span className="legend-text trade-legend-buy">买入点</span>
          <span className="legend-text trade-legend-sell">卖出点 / 做T盈亏</span>
          <span className="legend-text volume-legend">成交额</span>
          <span className="legend-text macd-legend-dif">DIF</span>
          <span className="legend-text macd-legend-dea">DEA</span>
        </div>
        <label className="zoom-control">
          缩放
          <input
            type="range"
            min="1"
            max="6"
            step="0.5"
            value={zoomLevel}
            onChange={(event) => setZoomLevel(Number(event.target.value))}
            aria-label="股价曲线缩放"
          />
          <span>{zoomLevel.toFixed(1)}x</span>
        </label>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="收盘价、成交额、MACD 与买卖点同步走势图">
        {showClosePrice && <path className="chart-line" d={path} />}
        {showMa5 && ma5Path && <path className="ma-line ma5" d={ma5Path} />}
        {showMa10 && ma10Path && <path className="ma-line ma10" d={ma10Path} />}
        {showMa30 && ma30Path && <path className="ma-line ma30" d={ma30Path} />}
        {showClosePrice && points.map((point) => (
          <circle
            key={point.date}
            className="price-point"
            cx={point.x}
            cy={point.y}
            r="2.5"
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
        {visibleTradeMarkers.map((marker) => {
          const labelY = marker.y - 14 - marker.offsetIndex * 20;
          const safeLabelY = Math.max(18, labelY);
          return (
            <g key={marker.id} className={`trade-marker trade-marker-${marker.type}`}>
              <circle
                cx={marker.x}
                cy={marker.y}
                r="6"
                aria-label={`${marker.date} ${marker.type === 'buy' ? '买入' : '卖出'} ${marker.quantity} 股，价格 ${priceFormatter.format(marker.price)}${marker.type === 'sell' && typeof marker.pnl === 'number' ? `，做T盈亏 ${pnlFormatter.format(marker.pnl)}` : ''}`}
              >
                <title>{`${marker.date} ${marker.type === 'buy' ? '买入' : '卖出'} ${marker.quantity} 股 @ ${priceFormatter.format(marker.price)}${marker.type === 'sell' && typeof marker.pnl === 'number' ? `，做T盈亏 ${pnlFormatter.format(marker.pnl)}` : ''}`}</title>
              </circle>
              {marker.type === 'sell' && typeof marker.pnl === 'number' && (
                <text className="trade-pnl-label" x={marker.x + 8} y={safeLabelY}>
                  {pnlFormatter.format(marker.pnl)}
                </text>
              )}
            </g>
          );
        })}

        <line className="indicator-axis" x1={padding} x2={width - padding} y1={volumeTop + volumeHeight} y2={volumeTop + volumeHeight} />
        <text className="indicator-label" x={padding} y={volumeTop - 8}>成交额</text>
        <text className="indicator-value-label" x={width - padding} y={volumeTop - 8} textAnchor="end">{compactNumberFormatter.format(maxVolumeAmount)}</text>
        {volumeBars.map((bar) => (
          <rect
            key={`volume-${bar.date}`}
            className="volume-amount-bar"
            x={bar.x - bar.width / 2}
            y={bar.y}
            width={bar.width}
            height={Math.max(1, bar.height)}
          >
            <title>{`${bar.date} 成交额 ${priceFormatter.format(bar.amount)}`}</title>
          </rect>
        ))}
        <line className="indicator-axis" x1={padding} x2={width - padding} y1={macdZeroY} y2={macdZeroY} />
        <text className="indicator-label" x={padding} y={macdTop - 8}>MACD(12,26,9)</text>
        {macd.map((point) => {
          const x = getX(point.index - visibleOffset);
          const barWidth = Math.max(2, Math.min(10, (width - padding * 2) / Math.max(visibleBars.length, 1) * 0.58));
          const histogramY = getMacdY(point.histogram);
          return (
            <rect
              key={`macd-bar-${point.date}`}
              className={`macd-histogram ${point.histogram >= 0 ? 'positive' : 'negative'}`}
              x={x - barWidth / 2}
              y={Math.min(histogramY, macdZeroY)}
              width={barWidth}
              height={Math.max(1, Math.abs(histogramY - macdZeroY))}
            >
              <title>{`${point.date} MACD ${point.histogram.toFixed(3)} DIF ${point.dif.toFixed(3)} DEA ${point.dea.toFixed(3)}`}</title>
            </rect>
          );
        })}
        {macdDifPath && <path className="macd-line dif" d={macdDifPath} />}
        {macdDeaPath && <path className="macd-line dea" d={macdDeaPath} />}
        {showClosePrice && hoveredPoint && (
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
