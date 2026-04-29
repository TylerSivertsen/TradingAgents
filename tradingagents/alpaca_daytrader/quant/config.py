"""Quant configuration loading from environment variables."""

from __future__ import annotations

import os

from tradingagents.alpaca_daytrader.config import DayTraderConfig
from tradingagents.alpaca_daytrader.quant.schemas import ExecutionConfig, QuantConfig, SleeveSettings


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _float(name: str, default: float) -> float:
    value = os.getenv(name)
    return default if value in (None, "") else float(value)


def _int(name: str, default: int) -> int:
    value = os.getenv(name)
    return default if value in (None, "") else int(value)


def _symbols(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name)
    if not raw:
        return default
    return [symbol.strip().upper() for symbol in raw.split(",") if symbol.strip()]


def load_quant_config(daytrader_config: DayTraderConfig | None = None) -> QuantConfig:
    default_symbols = daytrader_config.symbols if daytrader_config else ["AAPL", "MSFT", "NVDA", "SPY"]
    return QuantConfig(
        enabled=_bool("QUANT_ENABLED", True),
        symbols=_symbols("QUANT_SYMBOLS", default_symbols),
        allow_live_trading=_bool("ALLOW_LIVE_TRADING", False),
        dry_run_default=_bool("TRADING_DRY_RUN", True),
        allow_shorts=_bool("QUANT_ALLOW_SHORTS", False),
        max_gross_exposure=_float("QUANT_MAX_GROSS_EXPOSURE", 1.0),
        max_net_exposure=_float("QUANT_MAX_NET_EXPOSURE", 0.5),
        max_position_weight=_float("QUANT_MAX_POSITION_WEIGHT", 0.15),
        max_sleeve_weight=_float("QUANT_MAX_SLEEVE_WEIGHT", 0.35),
        min_cash_weight=_float("QUANT_MIN_CASH_WEIGHT", 0.10),
        target_volatility=_float("QUANT_TARGET_VOLATILITY", 0.15),
        max_daily_loss_pct=_float("QUANT_MAX_DAILY_LOSS_PCT", 0.02),
        max_drawdown_pct=_float("QUANT_MAX_DRAWDOWN_PCT", 0.05),
        max_turnover_per_day=_float("QUANT_MAX_TURNOVER_PER_DAY", 0.50),
        covariance_lookback_bars=_int("QUANT_COVARIANCE_LOOKBACK_BARS", 120),
        return_lookback_bars=_int("QUANT_RETURN_LOOKBACK_BARS", 60),
        enforce_market_neutral=_bool("QUANT_ENFORCE_MARKET_NEUTRAL", False),
        no_trade_symbols=_symbols("QUANT_NO_TRADE_SYMBOLS", []),
        execution=ExecutionConfig(
            max_participation_rate=_float("QUANT_MAX_PARTICIPATION_RATE", 0.05),
            max_spread_bps=_float("QUANT_MAX_SPREAD_BPS", 20.0),
            prefer_limit_orders=_bool("QUANT_PREFER_LIMIT_ORDERS", True),
            allow_market_orders=_bool("QUANT_ALLOW_MARKET_ORDERS", False),
            min_order_notional=_float("QUANT_MIN_ORDER_NOTIONAL", 25.0),
            max_order_notional=_float("QUANT_MAX_ORDER_NOTIONAL", 1_000.0),
            max_orders_per_cycle=_int("QUANT_MAX_ORDERS_PER_CYCLE", 10),
        ),
        momentum=SleeveSettings(
            enabled=_bool("QUANT_MOMENTUM_ENABLED", True),
            lookback_bars=_int("QUANT_MOMENTUM_LOOKBACK_BARS", 30),
        ),
        mean_reversion=SleeveSettings(
            enabled=_bool("QUANT_MEAN_REVERSION_ENABLED", True),
            lookback_bars=_int("QUANT_MEAN_REVERSION_LOOKBACK_BARS", 60),
            entry_z=_float("QUANT_MEAN_REVERSION_ENTRY_Z", 2.0),
            exit_z=_float("QUANT_MEAN_REVERSION_EXIT_Z", 0.5),
        ),
        volatility_breakout=SleeveSettings(
            enabled=_bool("QUANT_VOL_BREAKOUT_ENABLED", True),
            lookback_bars=_int("QUANT_VOL_BREAKOUT_LOOKBACK_BARS", 30),
            atr_lookback=_int("QUANT_VOL_BREAKOUT_ATR_LOOKBACK", 14),
        ),
        minimum_variance=SleeveSettings(enabled=_bool("QUANT_MIN_VAR_ENABLED", True)),
        cash=SleeveSettings(enabled=_bool("QUANT_CASH_ENABLED", True)),
    )
