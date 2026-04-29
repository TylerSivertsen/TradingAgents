"""Rule-based meta allocation adjustments."""

from __future__ import annotations

from dataclasses import replace

from tradingagents.alpaca_daytrader.quant.regime import MarketRegime
from tradingagents.alpaca_daytrader.quant.schemas import QuantConfig


class MetaAllocator:
    def adjust_config(self, config: QuantConfig, regime: MarketRegime, recent_drawdown: float = 0.0) -> QuantConfig:
        if regime.label == "high_volatility" or recent_drawdown > config.max_drawdown_pct / 2:
            return replace(
                config,
                max_gross_exposure=max(0.1, config.max_gross_exposure * 0.5),
                min_cash_weight=min(0.8, config.min_cash_weight + 0.2),
            )
        if regime.label == "trend_up":
            return replace(config, max_gross_exposure=min(1.0, config.max_gross_exposure * 1.1))
        return config
