"""Persistent sleeve performance scoreboard."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SleevePerformanceStats:
    sleeve_name: str
    lookback_days: int = 20
    realized_pnl: float = 0.0
    hit_rate: float = 0.5
    avg_return: float = 0.0
    max_drawdown: float = 0.0
    turnover: float = 0.0
    cost_drag: float = 0.0
    regime_breakdown: dict[str, Any] = field(default_factory=dict)
    reliability_score: float = 0.5
    current_status: str = "active"


class StrategyScoreboard:
    def __init__(self, path: Path = Path("logs/quant/scoreboard.json")) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict[str, SleevePerformanceStats]:
        if not self.path.exists():
            return {}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return {name: SleevePerformanceStats(**stats) for name, stats in payload.items()}

    def reliability_multiplier(self, sleeve_name: str) -> float:
        stats = self.load().get(sleeve_name)
        if stats is None:
            return 1.0
        if stats.current_status == "disabled":
            return 0.0
        if stats.current_status == "probation":
            return 0.5
        if stats.current_status == "reduced":
            return 0.75
        return max(0.25, min(1.5, 0.5 + stats.reliability_score))

    def save(self, stats: dict[str, SleevePerformanceStats]) -> None:
        self.path.write_text(json.dumps({k: asdict(v) for k, v in stats.items()}, indent=2), encoding="utf-8")
