"""Market regime classification for risk-adaptive allocation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from tradingagents.alpaca_daytrader.quant.schemas import MarketState, PortfolioState, QuantConfig


@dataclass
class MarketRegime:
    label: str
    confidence: float
    volatility_state: str
    trend_state: str
    liquidity_state: str
    correlation_state: str
    event_risk_state: str
    recommended_sleeve_multipliers: dict[str, float]
    diagnostics: dict[str, Any] = field(default_factory=dict)


class MarketRegimeClassifier:
    """Rule-based classifier for trend, volatility, liquidity, and correlation regimes."""

    def classify(
        self,
        broad_market_state: MarketState,
        focus_market_state: MarketState,
        portfolio_state: PortfolioState,
        config: QuantConfig,
    ) -> MarketRegime:
        returns = []
        liquidities = []
        for symbol, bars in focus_market_state.bars.items():
            if len(bars) >= 20:
                closes = np.array([bar.close for bar in bars], dtype=float)
                returns.append(np.diff(closes[-60:]) / np.maximum(closes[-60:-1], 1e-12))
                liquidities.append(focus_market_state.liquidity.get(symbol, 0.0))
        if not returns:
            return MarketRegime("low_liquidity", 0.5, "unknown", "unknown", "low", "unknown", "normal", {"cash": 1.5, "minimum_variance": 1.2})
        min_len = min(len(item) for item in returns)
        matrix = np.column_stack([item[-min_len:] for item in returns if len(item) >= min_len])
        avg_return = float(np.nanmean(matrix))
        vol = float(np.nanstd(matrix))
        avg_liquidity = float(np.nanmean(liquidities)) if liquidities else 0.0
        corr = np.corrcoef(matrix, rowvar=False) if matrix.shape[1] > 1 else np.array([[1.0]])
        avg_corr = float(np.nanmean(np.nan_to_num(corr[np.triu_indices_from(corr, k=1)]))) if matrix.shape[1] > 1 else 0.0
        trend_state = "up" if avg_return > 0.0002 else "down" if avg_return < -0.0002 else "flat"
        volatility_state = "high" if vol > 0.01 else "low" if vol < 0.001 else "normal"
        liquidity_state = "low" if avg_liquidity < 100_000 else "normal"
        correlation_state = "concentrated" if avg_corr > 0.75 else "normal"
        label = "choppy"
        multipliers = {"momentum": 1.0, "mean_reversion": 1.0, "volatility_breakout": 1.0, "minimum_variance": 1.0, "cash": 1.0}
        if volatility_state == "high":
            label = "high_volatility"
            multipliers.update({"minimum_variance": 1.4, "cash": 1.3, "mean_reversion": 0.7})
        elif trend_state == "up":
            label = "trend_up"
            multipliers.update({"momentum": 1.3, "volatility_breakout": 1.2, "mean_reversion": 0.8})
        elif trend_state == "down":
            label = "risk_off"
            multipliers.update({"cash": 1.5, "minimum_variance": 1.3, "momentum": 0.7})
        if correlation_state == "concentrated":
            label = "correlation_breakdown"
            multipliers.update({"cash": max(multipliers["cash"], 1.4), "minimum_variance": 1.4})
        return MarketRegime(
            label=label,
            confidence=0.7,
            volatility_state=volatility_state,
            trend_state=trend_state,
            liquidity_state=liquidity_state,
            correlation_state=correlation_state,
            event_risk_state="normal",
            recommended_sleeve_multipliers=multipliers,
            diagnostics={"avg_return": avg_return, "volatility": vol, "avg_liquidity": avg_liquidity, "avg_correlation": avg_corr},
        )
