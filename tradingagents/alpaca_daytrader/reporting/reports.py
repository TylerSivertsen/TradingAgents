"""Canonical run report writer."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from tradingagents.alpaca_daytrader.runtime import RuntimeMode


@dataclass
class TradingRunResult:
    runtime_mode: str
    safety: dict[str, Any]
    health: dict[str, Any] | None
    quant_report: Any | None
    semantic_review: Any | None
    execution_allowed: bool
    no_trade_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    report_markdown: str | None = None
    report_json: str | None = None


class RunReporter:
    def __init__(self, report_root: Path = Path("reports")) -> None:
        self.report_root = report_root

    def write(self, result: TradingRunResult) -> TradingRunResult:
        now = datetime.now(timezone.utc)
        day = now.strftime("%Y-%m-%d")
        stamp = now.strftime("%Y%m%dT%H%M%SZ")
        root = self.report_root / "runs" / day
        root.mkdir(parents=True, exist_ok=True)
        json_path = root / f"{stamp}_run.json"
        md_path = root / f"{stamp}_run.md"
        payload = self._jsonable(result)
        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        md_path.write_text(self._markdown(result), encoding="utf-8")
        result.report_json = str(json_path)
        result.report_markdown = str(md_path)
        json_path.write_text(json.dumps(self._jsonable(result), indent=2), encoding="utf-8")
        return result

    def _markdown(self, result: TradingRunResult) -> str:
        quant = result.quant_report
        focus = getattr(getattr(quant, "focus_list", None), "symbols", []) if quant else []
        regime = getattr(getattr(quant, "market_regime", None), "label", "unknown") if quant else "unknown"
        orders = getattr(getattr(quant, "execution_plan", None), "orders", []) if quant else []
        risk = getattr(quant, "risk", None) if quant else None
        semantic = result.semantic_review
        lines = [
            "# Trading System Run Report",
            "",
            f"- Runtime mode: `{result.runtime_mode}`",
            f"- Execution allowed: {result.execution_allowed}",
            f"- Safety: {result.safety}",
            "",
            "## Universe And Focus",
            f"- Focus list: {', '.join(focus) if focus else 'None'}",
            "",
            "## Market Regime",
            f"- {regime}",
            "",
            "## Risk",
            f"- Reason codes: {getattr(risk, 'reason_codes', [])}",
            f"- Gross exposure: {getattr(risk, 'gross_exposure', 0.0)}",
            "",
            "## Semantic Review",
            f"- Veto: {getattr(semantic, 'veto', None)}",
            f"- Explanation: {getattr(semantic, 'explanation', '')}",
            "",
            "## Execution",
            f"- Planned orders: {len(orders)}",
            "",
            "## No-Trade Reasons",
        ]
        lines.extend([f"- {reason}" for reason in result.no_trade_reasons] or ["None"])
        lines.extend(["", "## Warnings"])
        lines.extend([f"- {warning}" for warning in result.warnings] or ["None"])
        return "\n".join(lines) + "\n"

    def _jsonable(self, value: Any) -> Any:
        if is_dataclass(value):
            return self._jsonable(asdict(value))
        if isinstance(value, list):
            return [self._jsonable(item) for item in value]
        if isinstance(value, tuple):
            return [self._jsonable(item) for item in value]
        if isinstance(value, dict):
            return {key: self._jsonable(item) for key, item in value.items()}
        if isinstance(value, np.generic):
            return value.item()
        return value
