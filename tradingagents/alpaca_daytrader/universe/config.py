"""Universe configuration from environment variables."""

from __future__ import annotations

import os

from tradingagents.alpaca_daytrader.universe.schemas import UniverseConfig, UniverseRankingConfig


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    value = os.getenv(name)
    return default if value in (None, "") else int(value)


def _float(name: str, default: float) -> float:
    value = os.getenv(name)
    return default if value in (None, "") else float(value)


def _symbols(name: str) -> list[str]:
    raw = os.getenv(name, "")
    return [item.strip().upper() for item in raw.split(",") if item.strip()]


def load_universe_config() -> UniverseConfig:
    return UniverseConfig(
        enabled=_bool("UNIVERSE_ENABLED", True),
        source=os.getenv("UNIVERSE_SOURCE", "alpaca"),
        include_equities=_bool("UNIVERSE_INCLUDE_EQUITIES", True),
        include_etfs=_bool("UNIVERSE_INCLUDE_ETFS", True),
        max_scan_symbols=_int("UNIVERSE_MAX_SCAN_SYMBOLS", 3000),
        max_focus_symbols=_int("UNIVERSE_MAX_FOCUS_SYMBOLS", 25),
        cache_dir=os.getenv("UNIVERSE_CACHE_DIR", "data/universe"),
        seed_symbols=_symbols("UNIVERSE_SEED_SYMBOLS"),
        excluded_symbols=_symbols("UNIVERSE_EXCLUDED_SYMBOLS"),
        min_price=_float("UNIVERSE_MIN_PRICE", 2.0),
        max_price=_float("UNIVERSE_MAX_PRICE", 1000.0),
        min_avg_daily_volume=_float("UNIVERSE_MIN_AVG_DAILY_VOLUME", 1_000_000),
        min_intraday_volume=_float("UNIVERSE_MIN_INTRADAY_VOLUME", 100_000),
        max_spread_bps=_float("UNIVERSE_MAX_SPREAD_BPS", 30.0),
        min_atr_pct=_float("UNIVERSE_MIN_ATR_PCT", 0.005),
        max_atr_pct=_float("UNIVERSE_MAX_ATR_PCT", 0.12),
        ranking=UniverseRankingConfig(
            liquidity_weight=_float("UNIVERSE_RANK_LIQUIDITY_WEIGHT", 0.25),
            spread_weight=_float("UNIVERSE_RANK_SPREAD_WEIGHT", 0.20),
            volatility_weight=_float("UNIVERSE_RANK_VOLATILITY_WEIGHT", 0.15),
            momentum_weight=_float("UNIVERSE_RANK_MOMENTUM_WEIGHT", 0.15),
            mean_reversion_weight=_float("UNIVERSE_RANK_MEAN_REVERSION_WEIGHT", 0.10),
            news_event_weight=_float("UNIVERSE_RANK_NEWS_EVENT_WEIGHT", 0.10),
            execution_quality_weight=_float("UNIVERSE_RANK_EXECUTION_QUALITY_WEIGHT", 0.05),
        ),
    )
