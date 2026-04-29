"""Simple multi-timeframe signal fusion helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TimeframeSignal:
    symbol: str
    one_minute: float
    five_minute: float
    fifteen_minute: float
    daily: float

    @property
    def fused_score(self) -> float:
        return 0.2 * self.one_minute + 0.35 * self.five_minute + 0.3 * self.fifteen_minute + 0.15 * self.daily
