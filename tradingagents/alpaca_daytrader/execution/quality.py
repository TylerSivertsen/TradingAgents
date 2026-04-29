"""Execution quality feedback records."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class ExecutionQualityRecord:
    symbol: str
    decision_price: float
    submitted_price: float | None
    fill_price: float | None
    mid_price: float | None
    spread_paid_bps: float
    slippage_bps: float
    implementation_shortfall_bps: float
    time_to_fill_seconds: float | None
    status: str


class ExecutionQualityTracker:
    def __init__(self, path: Path = Path("logs/quant/execution_quality.jsonl")) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, record: ExecutionQualityRecord) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(record)) + "\n")

    def symbol_penalty(self, symbol: str) -> float:
        if not self.path.exists():
            return 0.0
        penalties = []
        for line in self.path.read_text(encoding="utf-8").splitlines()[-500:]:
            item = json.loads(line)
            if item.get("symbol") == symbol:
                penalties.append(max(0.0, float(item.get("implementation_shortfall_bps", 0.0))) / 10_000.0)
        return sum(penalties) / len(penalties) if penalties else 0.0
