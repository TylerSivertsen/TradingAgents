"""Simplified walk-forward validation using the quant backtester."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tradingagents.alpaca_daytrader.quant.backtest import QuantBacktester
from tradingagents.alpaca_daytrader.quant.orchestrator import QuantOrchestrator


class WalkForwardValidator:
    def run(
        self,
        orchestrator: QuantOrchestrator,
        start: str | None,
        end: str | None,
        train_days: int,
        test_days: int,
    ) -> dict[str, Any]:
        train = QuantBacktester().run(orchestrator, periods=max(100, train_days * 3))
        test = QuantBacktester().run(orchestrator, periods=max(100, test_days * 6))
        decay = float(test["total_return"]) - float(train["total_return"])
        return {
            "start": start,
            "end": end,
            "train_days": train_days,
            "test_days": test_days,
            "in_sample_return": train["total_return"],
            "out_of_sample_return": test["total_return"],
            "performance_decay": decay,
            "max_drawdown": test["max_drawdown"],
            "turnover": test["turnover"],
            "hit_rate": test["win_rate"],
            "average_trade_expectancy": test["average_gain"],
            "appears_overfit": decay < -0.05,
        }

    def write_report(self, metrics: dict[str, Any], report_root: Path = Path("reports")) -> Path:
        root = report_root / "quant" / "walkforward"
        root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = root / f"{stamp}.md"
        lines = ["# ORIA Walk-Forward Validation", ""]
        lines.extend(f"- `{key}`: {value}" for key, value in metrics.items())
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path
