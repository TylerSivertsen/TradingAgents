"""Shared data models for the daytrader pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

DecisionAction = Literal["buy", "sell", "hold"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PortfolioSnapshot:
    cash: float
    portfolio_value: float
    buying_power: float
    positions: dict[str, float] = field(default_factory=dict)
    timestamp: str = field(default_factory=utc_now_iso)


@dataclass
class MarketBar:
    symbol: str
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class MarketSnapshot:
    bars: dict[str, list[MarketBar]]
    market_open: bool
    timestamp: str = field(default_factory=utc_now_iso)


@dataclass
class TechnicalSnapshot:
    symbol: str
    close: float | None
    fast_sma: float | None
    slow_sma: float | None
    momentum: float | None
    status: str


@dataclass
class TradeDecision:
    symbol: str
    action: DecisionAction
    qty: int = 0
    notional: float = 0.0
    reason: str = ""
    approved: bool = False
    rejections: list[str] = field(default_factory=list)
    dry_run: bool = True


@dataclass
class OrderResult:
    symbol: str
    action: DecisionAction
    submitted: bool
    dry_run: bool
    message: str
    order_id: str | None = None


@dataclass
class OrchestratorResult:
    portfolio: PortfolioSnapshot
    market: MarketSnapshot
    technicals: dict[str, TechnicalSnapshot]
    decisions: list[TradeDecision]
    orders: list[OrderResult]
    reflection: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
