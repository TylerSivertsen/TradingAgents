"""Simple Rich-based TUI entrypoint."""

from __future__ import annotations

from tradingagents.alpaca_daytrader.config import load_config
from tradingagents.alpaca_daytrader.reporting.dashboard import Dashboard
from tradingagents.alpaca_daytrader.safety import SystemHealthCheck


def run_tui() -> None:
    config = load_config()
    health = SystemHealthCheck(config).run_all()
    Dashboard().render_diagnostics(config, health)
