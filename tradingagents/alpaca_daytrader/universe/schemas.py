"""Schemas for dynamic market universe discovery and scanning."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class UniverseRankingConfig:
    liquidity_weight: float = 0.25
    spread_weight: float = 0.20
    volatility_weight: float = 0.15
    momentum_weight: float = 0.15
    mean_reversion_weight: float = 0.10
    news_event_weight: float = 0.10
    execution_quality_weight: float = 0.05


@dataclass(frozen=True)
class UniverseConfig:
    enabled: bool = True
    source: str = "alpaca"
    include_equities: bool = True
    include_etfs: bool = True
    include_crypto: bool = False
    include_options: bool = False
    max_scan_symbols: int = 3000
    max_focus_symbols: int = 25
    refresh_assets_daily: bool = True
    cache_dir: str = "data/universe"
    seed_symbols: list[str] = field(default_factory=list)
    excluded_symbols: list[str] = field(default_factory=list)
    allow_fractional_only: bool = False
    require_tradable: bool = True
    require_marginable: bool = False
    min_price: float = 2.0
    max_price: float = 1000.0
    min_avg_daily_volume: float = 1_000_000
    min_intraday_volume: float = 100_000
    max_spread_bps: float = 30.0
    min_atr_pct: float = 0.005
    max_atr_pct: float = 0.12
    block_earnings_today: bool = True
    block_recent_halts: bool = True
    ranking: UniverseRankingConfig = field(default_factory=UniverseRankingConfig)


@dataclass
class AssetMetadata:
    symbol: str
    name: str = ""
    asset_class: str = "us_equity"
    exchange: str = ""
    status: str = "active"
    tradable: bool = True
    marginable: bool = False
    fractionable: bool = False
    shortable: bool = False
    easy_to_borrow: bool = False
    diagnostics: dict[str, Any] = field(default_factory=dict)


@dataclass
class TradableUniverse:
    assets: list[AssetMetadata]
    source: str
    timestamp: str = field(default_factory=utc_now_iso)

    @property
    def symbols(self) -> list[str]:
        return [asset.symbol for asset in self.assets]


@dataclass
class UniverseSelectionResult:
    universe: TradableUniverse
    discovered_count: int
    selected_count: int
    rejected: dict[str, list[str]]
    cache_hit: bool
    diagnostics: dict[str, Any] = field(default_factory=dict)


@dataclass
class SymbolCandidateScore:
    symbol: str
    is_valid: bool
    total_score: float
    liquidity_score: float
    spread_score: float
    volatility_score: float
    momentum_score: float
    mean_reversion_score: float
    breakout_score: float
    event_risk_score: float
    data_quality_score: float
    execution_quality_score: float
    rejection_reasons: list[str] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)


@dataclass
class MarketScanResult:
    candidates: list[SymbolCandidateScore]
    rejected: dict[str, list[str]]
    focus_symbols: list[str]
    scanned_count: int
    rejected_count: int
    timestamp: str = field(default_factory=utc_now_iso)


@dataclass
class FocusList:
    symbols: list[str]
    reasons: dict[str, list[str]]
    rejected: dict[str, list[str]]
    timestamp: str = field(default_factory=utc_now_iso)
