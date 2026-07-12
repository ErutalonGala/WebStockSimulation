import React from 'react';

type EquityCurveProps = {
  snapshots?: Array<{ date: string; total_assets: number }>;
};

export default function EquityCurve({ snapshots = [] }: EquityCurveProps) {
  if (snapshots.length === 0) {
    return <p className="muted">训练尚未开始，暂无每日资产快照。</p>;
  }

  const width = 720;
  const height = 220;
  const padding = 28;
  const totals = snapshots.map((snapshot) => snapshot.total_assets);
  const min = Math.min(...totals);
  const max = Math.max(...totals);
  const span = max - min || 1;
  const points = snapshots.map((snapshot, index) => {
    const x = snapshots.length === 1 ? width / 2 : padding + (index * (width - padding * 2)) / (snapshots.length - 1);
    const y = height - padding - ((snapshot.total_assets - min) * (height - padding * 2)) / span;
    return { ...snapshot, x, y };
  });
  const path = points.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`).join(' ');

  return (
    <div className="equity-curve">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="账户总资产曲线">
        <path className="equity-line" d={path} />
        {points.map((point) => <circle key={point.date} cx={point.x} cy={point.y} r="4" />)}
      </svg>
      <div className="curve-caption">
        <span>{snapshots[0].date}</span>
        <span>{snapshots[snapshots.length - 1].date}</span>
      </div>
    </div>
  );
}
