"""Typed schemas for the ORIA-inspired quant pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from tradingagents.alpaca_daytrader.models import MarketBar


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


OrderSide = Literal["buy", "sell"]
OrderType = Literal["market", "limit"]


@dataclass(frozen=True)
class ExecutionConfig:
    max_participation_rate: float = 0.05
    max_spread_bps: float = 20.0
    prefer_limit_orders: bool = True
    allow_market_orders: bool = False
    min_order_notional: float = 25.0
    max_order_notional: float = 1_000.0
    max_orders_per_cycle: int = 10
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None


@dataclass(frozen=True)
class SleeveSettings:
    enabled: bool = True
    lookback_bars: int = 30
    entry_z: float = 2.0
    exit_z: float = 0.5
    atr_lookback: int = 14


@dataclass(frozen=True)
class QuantConfig:
    enabled: bool = True
    symbols: list[str] = field(default_factory=lambda: ["AAPL", "MSFT", "NVDA", "SPY"])
    allow_live_trading: bool = False
    dry_run_default: bool = True
    allow_shorts: bool = False
    max_gross_exposure: float = 1.0
    max_net_exposure: float = 0.5
    max_position_weight: float = 0.15
    max_sleeve_weight: float = 0.35
    min_cash_weight: float = 0.10
    target_volatility: float = 0.15
    max_daily_loss_pct: float = 0.02
    max_drawdown_pct: float = 0.05
    max_turnover_per_day: float = 0.50
    covariance_lookback_bars: int = 120
    return_lookback_bars: int = 60
    enforce_market_neutral: bool = False
    no_trade_symbols: list[str] = field(default_factory=list)
    pairs: list[tuple[str, str]] = field(default_factory=list)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    momentum: SleeveSettings = field(default_factory=lambda: SleeveSettings(lookback_bars=30))
    mean_reversion: SleeveSettings = field(
        default_factory=lambda: SleeveSettings(lookback_bars=60, entry_z=2.0, exit_z=0.5)
    )
    volatility_breakout: SleeveSettings = field(
        default_factory=lambda: SleeveSettings(lookback_bars=30, atr_lookback=14)
    )
    minimum_variance: SleeveSettings = field(default_factory=SleeveSettings)
    cash: SleeveSettings = field(default_factory=SleeveSettings)


@dataclass
class MarketState:
    bars: dict[str, list[MarketBar]]
    market_open: bool
    spreads_bps: dict[str, float] = field(default_factory=dict)
    liquidity: dict[str, float] = field(default_factory=dict)
    timestamp: str = field(default_factory=utc_now_iso)

    def latest_price(self, symbol: str) -> float | None:
        bars = self.bars.get(symbol, [])
        return bars[-1].close if bars else None


@dataclass
class PortfolioState:
    cash: float
    portfolio_value: float
    positions: dict[str, float] = field(default_factory=dict)
    buying_power: float = 0.0
    daily_pnl: float = 0.0
    drawdown_pct: float = 0.0
    timestamp: str = field(default_factory=utc_now_iso)


@dataclass
class StrategyDiagnostics:
    warnings: list[str] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)


@dataclass
class RawDesiredBook:
    strategy_name: str
    symbols: list[str]
    target_weights: dict[str, float]
    expected_return: float
    confidence: float
    uncertainty: float
    holding_horizon: str
    turnover_estimate: float
    rationale: str
    diagnostics: StrategyDiagnostics = field(default_factory=StrategyDiagnostics)
    timestamp: str = field(default_factory=utc_now_iso)
    generated_at: str = field(default_factory=utc_now_iso)
    valid_until: str | None = None
    alpha_half_life_minutes: float = 30.0
    staleness_penalty: float = 0.0


@dataclass
class FactorExposure:
    symbols: list[str]
    exposures: dict[str, dict[str, float]]
    diagnostics: dict[str, Any] = field(default_factory=dict)


@dataclass
class FactorNeutralizationResult:
    weights: dict[str, float]
    before_exposure: dict[str, float]
    after_exposure: dict[str, float]
    removed_magnitude: float
    warnings: list[str] = field(default_factory=list)


@dataclass
class RiskMetric:
    symbols: list[str]
    covariance: list[list[float]]
    condition_number: float


@dataclass
class CovarianceEstimate:
    symbols: list[str]
    matrix: list[list[float]]
    method: str
    is_singular: bool = False
    warnings: list[str] = field(default_factory=list)


@dataclass
class OrthogonalizationDiagnostics:
    before_correlations: list[list[float]]
    after_correlations: list[list[float]]
    factor_exposures_before: dict[str, dict[str, float]]
    factor_exposures_after: dict[str, dict[str, float]]
    removed_exposure: dict[str, float]
    warnings: list[str] = field(default_factory=list)


@dataclass
class OrthogonalizedBook:
    strategy_name: str
    symbols: list[str]
    target_weights: dict[str, float]
    expected_return: float
    confidence: float
    uncertainty: float
    turnover_estimate: float
    active: bool
    removed_magnitude: float
    source_rationale: str


@dataclass
class OrthogonalizedBookSet:
    symbols: list[str]
    books: list[OrthogonalizedBook]
    diagnostics: OrthogonalizationDiagnostics


@dataclass
class SleeveUtility:
    strategy_name: str
    edge: float
    uncertainty_penalty: float
    cost_penalty: float
    turnover_penalty: float
    risk_penalty: float
    net_utility: float
    budget: float
    active: bool


@dataclass
class AllocationResult:
    sleeve_utilities: list[SleeveUtility]
    sleeve_budgets: dict[str, float]
    cash_weight: float
    total_risk_scalar: float
    combined_target_weights: dict[str, float]
    diagnostics: dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskConstraintViolation:
    code: str
    symbol: str | None
    message: str
    before: float | None = None
    after: float | None = None


@dataclass
class FeasibleBook:
    target_weights: dict[str, float]
    source_weights: dict[str, float]
    approved: bool
    source_sleeves: list[str] = field(default_factory=list)


@dataclass
class RiskBoxResult:
    feasible_book: FeasibleBook
    violations: list[RiskConstraintViolation]
    clipped_weights: dict[str, tuple[float, float]]
    risk_scalar: float
    volatility_estimate: float
    gross_exposure: float
    net_exposure: float
    concentration: dict[str, float]
    reason_codes: list[str]


@dataclass
class OrderPlan:
    symbol: str
    side: OrderSide
    quantity: int
    notional: float
    order_type: OrderType
    time_in_force: str
    limit_price: float | None
    stop_loss: float | None
    take_profit: float | None
    reason: str
    source_sleeves: list[str]
    risk_metadata: dict[str, Any]


@dataclass
class ExecutionPlan:
    orders: list[OrderPlan]
    dry_run: bool
    warnings: list[str] = field(default_factory=list)


@dataclass
class ExecutionResult:
    plan: ExecutionPlan
    submitted_order_ids: list[str]
    messages: list[str]


@dataclass
class QuantRunReport:
    market_state: MarketState
    portfolio_state: PortfolioState
    raw_books: list[RawDesiredBook]
    orthogonalized: OrthogonalizedBookSet
    allocation: AllocationResult
    risk: RiskBoxResult
    execution_plan: ExecutionPlan
    execution_result: ExecutionResult | None
    semantic_commentary: dict[str, Any]
    universe_selection: Any | None = None
    scan_result: Any | None = None
    focus_list: Any | None = None
    market_regime: Any | None = None
    stress_result: Any | None = None
    no_trade: Any | None = None
    trade_explanations: list[Any] = field(default_factory=list)
    timestamp: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
