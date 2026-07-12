import React from 'react';

type OrderPanelProps = {
  buyQuantity: number | string;
  sellQuantity: number | string;
  loading: boolean;
  disabled: boolean;
  isComplete: boolean;
  onBuyQuantityChange: (value: string) => void;
  onSellQuantityChange: (value: string) => void;
  onBuy: () => void;
  onSell: () => void;
  onBuyPositionFraction: (fraction: number) => void;
  onNextDay: () => void;
  onNextWeek: () => void;
};

export default function OrderPanel({
  buyQuantity,
  sellQuantity,
  loading,
  disabled,
  isComplete,
  onBuyQuantityChange,
  onSellQuantityChange,
  onBuy,
  onSell,
  onBuyPositionFraction,
  onNextDay,
  onNextWeek,
}: OrderPanelProps) {
  return (
    <div className="form-stack">
      <label>
        买入数量
        <input
          type="number"
          min="1"
          step="1"
          value={buyQuantity}
          onChange={(event) => onBuyQuantityChange(event.target.value)}
          disabled={disabled}
        />
      </label>
      <button type="button" onClick={onBuy} disabled={disabled || loading}>买入</button>
      <label>
        卖出数量
        <input
          type="number"
          min="1"
          step="1"
          value={sellQuantity}
          onChange={(event) => onSellQuantityChange(event.target.value)}
          disabled={disabled}
        />
      </label>
      <button type="button" onClick={onSell} disabled={disabled || loading}>卖出</button>
      <div className="quick-position-group" aria-label="快速买入仓位">
        <span>快速买入仓位</span>
        <div className="button-row">
          <button type="button" className="secondary-button" onClick={() => onBuyPositionFraction(1 / 4)} disabled={disabled || loading}>
            1/4 仓
          </button>
          <button type="button" className="secondary-button" onClick={() => onBuyPositionFraction(1 / 3)} disabled={disabled || loading}>
            1/3 仓
          </button>
          <button type="button" className="secondary-button" onClick={() => onBuyPositionFraction(2 / 3)} disabled={disabled || loading}>
            2/3 仓
          </button>
        </div>
      </div>
      <div className="button-row">
        <button type="button" className="secondary-button" onClick={onNextDay} disabled={disabled || loading || isComplete}>
          下一交易日
        </button>
        <button type="button" className="secondary-button" onClick={onNextWeek} disabled={disabled || loading || isComplete}>
          下一周
        </button>
      </div>
    </div>
  );
}
