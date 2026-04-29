"""Configuration loading for the Alpaca daytrader."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    return default if value in (None, "") else float(value)


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    return default if value in (None, "") else int(value)


def _symbols_env() -> list[str]:
    raw = os.getenv("ALPACA_DAYTRADER_SYMBOLS", "SPY,QQQ")
    return [symbol.strip().upper() for symbol in raw.split(",") if symbol.strip()]


@dataclass(frozen=True)
class DayTraderConfig:
    """Runtime settings with conservative defaults."""

    api_key: str | None
    secret_key: str | None
    paper: bool = True
    symbols: list[str] = field(default_factory=lambda: ["SPY", "QQQ"])
    poll_seconds: int = 60
    max_notional_per_order: float = 1_000.0
    max_portfolio_exposure_pct: float = 0.20
    min_cash_reserve_pct: float = 0.05
    fast_window: int = 5
    slow_window: int = 20
    bar_timeframe: str = "5Min"
    log_root: Path = Path("logs")
    report_root: Path = Path("reports")

    def validate_for_execution(self) -> None:
        if not self.paper:
            raise ValueError("Only Alpaca paper trading is supported.")
        if not self.api_key or not self.secret_key:
            raise ValueError(
                "ALPACA_API_KEY and ALPACA_SECRET_KEY are required for --execute."
            )
        if self.max_notional_per_order <= 0:
            raise ValueError("ALPACA_DAYTRADER_MAX_NOTIONAL must be positive.")
        if not 0 < self.max_portfolio_exposure_pct <= 1:
            raise ValueError("ALPACA_DAYTRADER_MAX_EXPOSURE_PCT must be in (0, 1].")


def load_config() -> DayTraderConfig:
    return DayTraderConfig(
        api_key=os.getenv("ALPACA_API_KEY"),
        secret_key=os.getenv("ALPACA_SECRET_KEY"),
        paper=_bool_env("ALPACA_PAPER", True),
        symbols=_symbols_env(),
        poll_seconds=_int_env("ALPACA_DAYTRADER_POLL_SECONDS", 60),
        max_notional_per_order=_float_env("ALPACA_DAYTRADER_MAX_NOTIONAL", 1_000.0),
        max_portfolio_exposure_pct=_float_env(
            "ALPACA_DAYTRADER_MAX_EXPOSURE_PCT", 0.20
        ),
        min_cash_reserve_pct=_float_env("ALPACA_DAYTRADER_MIN_CASH_RESERVE_PCT", 0.05),
        fast_window=_int_env("ALPACA_DAYTRADER_FAST_WINDOW", 5),
        slow_window=_int_env("ALPACA_DAYTRADER_SLOW_WINDOW", 20),
        bar_timeframe=os.getenv("ALPACA_DAYTRADER_BAR_TIMEFRAME", "5Min"),
        log_root=Path(os.getenv("ALPACA_DAYTRADER_LOG_ROOT", "logs")),
        report_root=Path(os.getenv("ALPACA_DAYTRADER_REPORT_ROOT", "reports")),
    )
