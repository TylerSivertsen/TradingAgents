"""Strict runtime modes for the Alpaca daytrader."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeMode:
    name: str
    can_read_account: bool
    can_read_market_data: bool
    can_generate_orders: bool
    can_submit_orders: bool
    requires_human_approval: bool
    requires_paper_account: bool
    requires_live_override: bool = False
    writes_logs: bool = True
    writes_reports: bool = True


RUNTIME_MODES = {
    "diagnostics": RuntimeMode("diagnostics", False, False, False, False, False, False),
    "dry_run": RuntimeMode("dry_run", True, True, True, False, False, False),
    "review": RuntimeMode("review", True, True, True, False, True, True),
    "shadow": RuntimeMode("shadow", True, True, True, False, False, False),
    "paper_execute": RuntimeMode("paper_execute", True, True, True, True, False, True),
    "live_execute_blocked_by_default": RuntimeMode(
        "live_execute_blocked_by_default",
        True,
        True,
        True,
        True,
        True,
        False,
        requires_live_override=True,
    ),
    "backtest": RuntimeMode("backtest", False, True, True, False, False, False),
    "walkforward": RuntimeMode("walkforward", False, True, True, False, False, False),
}


def mode_by_name(name: str) -> RuntimeMode:
    try:
        return RUNTIME_MODES[name]
    except KeyError as exc:
        raise ValueError(f"Unknown runtime mode: {name}") from exc
