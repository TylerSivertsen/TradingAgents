"""Logging and Markdown reporting for quant runs."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from tradingagents.alpaca_daytrader.quant.schemas import QuantRunReport


class QuantLogger:
    def __init__(self, log_root: Path = Path("logs"), report_root: Path = Path("reports")) -> None:
        self.base = log_root / "quant"
        self.report_root = report_root / "quant"
        self.backtest_root = self.report_root / "backtests"
        for path in (
            self.base / "raw_books",
            self.base / "orthogonalization",
            self.base / "allocation",
            self.base / "risk",
            self.base / "execution",
            self.report_root,
            self.backtest_root,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def log_stage(self, stage: str, payload: Any) -> Path:
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        path = self.base / stage / f"{day}.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(), "payload": self._jsonable(payload)}) + "\n")
        return path

    def write_report(self, report: QuantRunReport) -> Path:
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        path = self.report_root / f"{day}.md"
        path.write_text(render_markdown_report(report), encoding="utf-8")
        return path

    def latest_report(self) -> Path | None:
        reports = sorted(self.report_root.glob("*.md"))
        return reports[-1] if reports else None

    def write_backtest_report(self, metrics: dict[str, Any]) -> Path:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = self.backtest_root / f"{stamp}.md"
        lines = ["# ORIA Quant Backtest", "", "## Metrics", ""]
        for key, value in metrics.items():
            lines.append(f"- `{key}`: {value}")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def _jsonable(self, payload: Any) -> Any:
        if is_dataclass(payload):
            return self._jsonable(asdict(payload))
        if isinstance(payload, list):
            return [self._jsonable(item) for item in payload]
        if isinstance(payload, tuple):
            return [self._jsonable(item) for item in payload]
        if isinstance(payload, dict):
            return {key: self._jsonable(value) for key, value in payload.items()}
        if isinstance(payload, np.generic):
            return payload.item()
        return payload


def render_markdown_report(report: QuantRunReport) -> str:
    active = report.allocation.diagnostics.get("active_sleeves", [])
    focus_symbols = getattr(report.focus_list, "symbols", []) if report.focus_list else []
    regime_label = getattr(report.market_regime, "label", "unknown") if report.market_regime else "unknown"
    scanned_count = getattr(report.scan_result, "scanned_count", 0) if report.scan_result else 0
    rejected_count = getattr(report.scan_result, "rejected_count", 0) if report.scan_result else 0
    warnings = (
        report.orthogonalized.diagnostics.warnings
        + report.execution_plan.warnings
        + [violation.message for violation in report.risk.violations]
    )
    lines = [
        "# ORIA Quant Run Report",
        "",
        "Research and paper-trading only. Not financial advice.",
        "",
        "## Portfolio Summary",
        f"- Portfolio value: {report.portfolio_state.portfolio_value:.2f}",
        f"- Cash: {report.portfolio_state.cash:.2f}",
        f"- Market open: {report.market_state.market_open}",
        f"- Market regime: {regime_label}",
        f"- Symbols scanned: {scanned_count}",
        f"- Symbols rejected: {rejected_count}",
        f"- Focus list: {', '.join(focus_symbols) if focus_symbols else 'None'}",
        "",
        "## Active Sleeves",
        ", ".join(active) if active else "None",
        "",
        "## Raw Signals",
    ]
    for book in report.raw_books:
        lines.append(f"- `{book.strategy_name}` edge={book.expected_return:.4f} confidence={book.confidence:.2f}")
    lines.extend(
        [
            "",
            "## Orthogonalization Summary",
            f"- Removed exposure: {report.orthogonalized.diagnostics.removed_exposure}",
            "",
            "## Allocation Summary",
            f"- Cash allocation: {report.allocation.cash_weight:.2%}",
            f"- Sleeve budgets: {report.allocation.sleeve_budgets}",
            "",
            "## RiskBox Summary",
            f"- Approved: {report.risk.feasible_book.approved}",
            f"- Gross exposure: {report.risk.gross_exposure:.4f}",
            f"- Reason codes: {report.risk.reason_codes}",
            "",
            "## Stress Tests",
            f"- Passed: {getattr(report.stress_result, 'passed', 'unknown')}",
            f"- Warnings: {getattr(report.stress_result, 'warnings', [])}",
            "",
            "## Execution Summary",
            f"- Planned orders: {len(report.execution_plan.orders)}",
            f"- Dry run: {report.execution_plan.dry_run}",
            "",
            "## No-Trade Explanation",
            f"- {getattr(report.no_trade, 'reasons', [])}",
            "",
            "## Trade Explanations",
        ]
    )
    for explanation in report.trade_explanations:
        lines.append(
            f"- `{explanation.symbol}` {explanation.action}: {explanation.execution_choice}; "
            f"risk={explanation.main_risk}"
        )
    if not report.trade_explanations:
        lines.append("None")
    lines.extend(
        [
            "",
            "## Semantic Review",
            f"- {report.semantic_commentary}",
            "",
            "## Warnings",
        ]
    )
    lines.extend([f"- {warning}" for warning in warnings] or ["None"])
    lines.extend(["", "## Suggested Improvements", "- Add richer quote/spread inputs before paper execution."])
    return "\n".join(lines) + "\n"
