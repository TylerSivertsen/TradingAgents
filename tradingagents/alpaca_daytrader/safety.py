"""Central safety policy and health checks."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tradingagents.alpaca_daytrader.config import DayTraderConfig
from tradingagents.alpaca_daytrader.runtime import RuntimeMode


@dataclass
class SafetyDecision:
    allowed: bool
    reasons: list[str] = field(default_factory=list)


class SafetyPolicy:
    """Authorizes runtime behavior before execution is attempted."""

    def validate(self, mode: RuntimeMode, config: DayTraderConfig) -> SafetyDecision:
        reasons: list[str] = []
        if mode.can_submit_orders:
            if mode.requires_paper_account and not config.paper:
                reasons.append("paper account required")
            if not config.api_key or not config.secret_key:
                reasons.append("Alpaca credentials required for execution")
        if mode.requires_live_override:
            if os.getenv("ALLOW_LIVE_TRADING", "false").lower() != "true":
                reasons.append("ALLOW_LIVE_TRADING=true required")
            reasons.append("live execution command is intentionally not implemented")
        return SafetyDecision(not reasons, reasons)


@dataclass
class SystemHealthReport:
    healthy: bool
    checks: dict[str, bool]
    warnings: list[str]
    diagnostics: dict[str, Any]


class SystemHealthCheck:
    def __init__(self, config: DayTraderConfig) -> None:
        self.config = config

    def run_all(self) -> SystemHealthReport:
        checks = {
            "package_importable": True,
            "paper_mode": self.config.paper,
            "live_trading_disabled": os.getenv("ALLOW_LIVE_TRADING", "false").lower() != "true",
            "logs_writable": self._writable(self.config.log_root),
            "reports_writable": self._writable(self.config.report_root),
            "data_writable": self._writable(Path("data")),
            "audit_writable": self._writable(Path("audit")),
        }
        warnings = []
        if not self.config.api_key or not self.config.secret_key:
            warnings.append("Alpaca credentials absent; dry-run/diagnostics only")
        if not self.config.paper:
            warnings.append("ALPACA_PAPER is false; paper execution will be refused")
        return SystemHealthReport(
            healthy=all(checks.values()),
            checks=checks,
            warnings=warnings,
            diagnostics={
                "alpaca_api_key_present": bool(self.config.api_key),
                "alpaca_secret_key_present": bool(self.config.secret_key),
                "paper": self.config.paper,
            },
        )

    def _writable(self, path: Path) -> bool:
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / ".write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return True
        except OSError:
            return False
