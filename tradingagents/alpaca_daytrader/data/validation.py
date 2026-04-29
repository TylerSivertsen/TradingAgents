"""Market data quality validation for safe trading decisions."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from typing import Any


@dataclass
class DataQualityReport:
    symbol: str
    action: str
    score: float
    reasons: list[str] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)


class DataQualityValidator:
    """Classifies symbol data as allow/warn/reduce/exclude/block."""

    def validate_symbol_data(self, symbol: str, bars: list[Any], quotes: Any, config: Any) -> DataQualityReport:
        reasons: list[str] = []
        if not bars:
            return DataQualityReport(symbol, "exclude_symbol", 0.0, ["missing_bars"])
        timestamps = [getattr(bar, "timestamp", None) for bar in bars]
        if len(set(timestamps)) != len(timestamps):
            reasons.append("duplicate_timestamps")
        prices = [getattr(bar, "close", None) for bar in bars]
        volumes = [getattr(bar, "volume", 0) for bar in bars]
        if any(price is None or not isfinite(float(price)) or float(price) <= 0 for price in prices):
            reasons.append("invalid_price")
        if sum(float(volume) for volume in volumes[-20:]) <= 0:
            reasons.append("zero_volume")
        jumps = []
        for left, right in zip(prices, prices[1:]):
            if left and right:
                jumps.append(abs(float(right) / float(left) - 1.0))
        if jumps and max(jumps) > 0.25:
            reasons.append("suspicious_price_jump")
        spread = getattr(quotes, "spread_bps", None) if quotes is not None else None
        max_spread = getattr(config, "max_spread_bps", 30.0)
        if spread is not None and spread > max_spread:
            reasons.append("abnormal_spread")
        score = max(0.0, 1.0 - 0.2 * len(reasons))
        if any(reason in reasons for reason in ("missing_bars", "invalid_price")):
            action = "exclude_symbol"
        elif "abnormal_spread" in reasons or "suspicious_price_jump" in reasons:
            action = "reduce_size"
        elif reasons:
            action = "warn"
        else:
            action = "allow"
        return DataQualityReport(symbol, action, score, reasons)
