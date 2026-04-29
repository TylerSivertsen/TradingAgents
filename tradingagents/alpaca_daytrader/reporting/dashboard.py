"""Rich terminal dashboard rendering."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from tradingagents.alpaca_daytrader.config import DayTraderConfig
from tradingagents.alpaca_daytrader.safety import SystemHealthReport


class Dashboard:
    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()

    def render_diagnostics(self, config: DayTraderConfig, health: SystemHealthReport) -> None:
        table = Table(title="TradingAgents Alpaca Runtime")
        table.add_column("Check")
        table.add_column("Status")
        for key, value in health.checks.items():
            table.add_row(key, "ok" if value else "fail")
        self.console.print(Panel.fit("Alpaca/ORIA Trading Research Platform", title="Dashboard"))
        self.console.print(table)
        self.console.print(f"Paper mode: {config.paper}")
        self.console.print(f"API key present: {bool(config.api_key)}")
        self.console.print(f"Reports: {Path(config.report_root).resolve()}")
        if health.warnings:
            self.console.print(Panel("\n".join(health.warnings), title="Warnings"))
