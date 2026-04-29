"""JSONL logging helpers for decisions, orders, portfolio, and reports."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class DecisionLogger:
    def __init__(self, log_root: Path, report_root: Path) -> None:
        self.log_root = log_root
        self.report_root = report_root
        self.decision_dir = log_root / "decisions"
        self.order_dir = log_root / "orders"
        self.portfolio_dir = log_root / "portfolio"
        for path in (
            self.decision_dir,
            self.order_dir,
            self.portfolio_dir,
            self.report_root,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def log_decisions(self, payload: Any) -> Path:
        return self._append(self.decision_dir / "decisions.jsonl", payload)

    def log_orders(self, payload: Any) -> Path:
        return self._append(self.order_dir / "orders.jsonl", payload)

    def log_portfolio(self, payload: Any) -> Path:
        return self._append(self.portfolio_dir / "portfolio.jsonl", payload)

    def write_report(self, payload: Any) -> Path:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = self.report_root / f"alpaca_daytrader_{stamp}.json"
        path.write_text(json.dumps(self._jsonable(payload), indent=2), encoding="utf-8")
        return path

    def latest_report(self) -> Path | None:
        reports = sorted(self.report_root.glob("alpaca_daytrader_*.json"))
        return reports[-1] if reports else None

    def _append(self, path: Path, payload: Any) -> Path:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": self._jsonable(payload),
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")
        return path

    def _jsonable(self, payload: Any) -> Any:
        if is_dataclass(payload):
            return asdict(payload)
        if isinstance(payload, list):
            return [self._jsonable(item) for item in payload]
        if isinstance(payload, dict):
            return {key: self._jsonable(value) for key, value in payload.items()}
        return payload
