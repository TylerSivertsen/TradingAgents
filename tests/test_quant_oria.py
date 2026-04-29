import pytest

from tradingagents.alpaca_daytrader.config import DayTraderConfig
from tradingagents.alpaca_daytrader.models import MarketBar, MarketSnapshot, PortfolioSnapshot
from tradingagents.alpaca_daytrader.quant.allocator import QuantAllocator
from tradingagents.alpaca_daytrader.quant.config import load_quant_config
from tradingagents.alpaca_daytrader.quant.constraints import OrthogonalizationConstraints
from tradingagents.alpaca_daytrader.quant.costs import CostModel
from tradingagents.alpaca_daytrader.quant.covariance import CovarianceEstimator
from tradingagents.alpaca_daytrader.quant.execution_governor import ExecutionGovernor
from tradingagents.alpaca_daytrader.quant.factors import FactorExposureModel
from tradingagents.alpaca_daytrader.quant.orchestrator import QuantOrchestrator
from tradingagents.alpaca_daytrader.quant.orthogonalization import Orthogonalizer
from tradingagents.alpaca_daytrader.quant.risk_box import RiskBox
from tradingagents.alpaca_daytrader.quant.schemas import (
    AllocationResult,
    ExecutionConfig,
    FeasibleBook,
    MarketState,
    OrthogonalizationDiagnostics,
    OrthogonalizedBook,
    OrthogonalizedBookSet,
    PortfolioState,
    QuantConfig,
    RawDesiredBook,
    RiskConstraintViolation,
    SleeveUtility,
)
from tradingagents.alpaca_daytrader.quant.strategy_sleeves import (
    CashSleeve,
    MeanReversionSleeve,
    MinimumVarianceSleeve,
    MomentumSleeve,
)


def _bars(symbol: str, prices: list[float]) -> list[MarketBar]:
    return [
        MarketBar(symbol=symbol, timestamp=str(idx), open=p, high=p * 1.01, low=p * 0.99, close=p, volume=10_000)
        for idx, p in enumerate(prices)
    ]


def _market(open_: bool = True) -> MarketState:
    prices_a = [100 + idx for idx in range(90)]
    prices_b = [100 - idx * 0.2 for idx in range(89)] + [70]
    bars = {"AAA": _bars("AAA", prices_a), "BBB": _bars("BBB", prices_b)}
    return MarketState(
        bars=bars,
        market_open=open_,
        spreads_bps={"AAA": 5, "BBB": 5},
        liquidity={"AAA": 1_000_000, "BBB": 1_000_000},
    )


def _config(**kwargs) -> QuantConfig:
    base = QuantConfig(symbols=["AAA", "BBB"], execution=ExecutionConfig(max_order_notional=500))
    return type(base)(**{**base.__dict__, **kwargs})


def test_strategy_sleeves_generate_sensible_books():
    market = _market()
    portfolio = PortfolioState(cash=100_000, portfolio_value=100_000)
    config = _config()

    momentum = MomentumSleeve().generate_raw_book(market, portfolio, config)
    mean_reversion = MeanReversionSleeve().generate_raw_book(market, portfolio, config)
    min_var = MinimumVarianceSleeve().generate_raw_book(market, portfolio, config)
    cash = CashSleeve().generate_raw_book(market, portfolio, config)

    assert momentum.target_weights["AAA"] > momentum.target_weights["BBB"]
    assert mean_reversion.target_weights["BBB"] > 0
    assert pytest.approx(sum(min_var.target_weights.values()), rel=1e-6) == 1.0
    assert all(value == 0 for value in cash.target_weights.values())


def test_orthogonalizer_aligns_symbols_and_reduces_duplicate_correlation():
    market = _market()
    config = _config(allow_shorts=True)
    factor_model = FactorExposureModel()
    factor_model.compute(market, config.symbols, config)
    covariance = CovarianceEstimator().estimate(market, config.symbols, 60)
    books = [
        RawDesiredBook("a", ["AAA", "BBB"], {"AAA": 0.5, "BBB": -0.5}, 0.1, 1, 0, "day", 0.1, "a"),
        RawDesiredBook("b", ["AAA", "BBB"], {"AAA": 0.5, "BBB": -0.5}, 0.1, 1, 0, "day", 0.1, "b"),
    ]

    result = Orthogonalizer().orthogonalize(
        books,
        factor_model,
        covariance,
        OrthogonalizationConstraints(neutralize_factors=[]),
    )

    assert result.symbols == ["AAA", "BBB"]
    assert result.books[0].active
    assert not result.books[1].active


def test_allocator_prefers_high_utility_and_cash_when_negative():
    market = _market()
    portfolio = PortfolioState(cash=100_000, portfolio_value=100_000)
    diagnostics = OrthogonalizationDiagnostics([], [], {}, {}, {})
    bookset = OrthogonalizedBookSet(
        symbols=["AAA"],
        books=[
            OrthogonalizedBook("good", ["AAA"], {"AAA": 1.0}, 0.2, 1.0, 0.01, 0.1, True, 0, "good"),
            OrthogonalizedBook("bad", ["AAA"], {"AAA": 1.0}, -0.2, 1.0, 1.0, 0.1, True, 0, "bad"),
        ],
        diagnostics=diagnostics,
    )

    allocation = QuantAllocator().allocate(bookset, market, portfolio, CostModel(), _config())

    assert allocation.sleeve_budgets["good"] > allocation.sleeve_budgets["bad"]
    assert allocation.sleeve_budgets["good"] <= _config().max_sleeve_weight
    assert allocation.cash_weight >= _config().min_cash_weight


def test_risk_box_clips_and_rejects_closed_market_or_liquidity():
    config = _config(max_position_weight=0.10)
    portfolio = PortfolioState(cash=100_000, portfolio_value=100_000)
    allocation = AllocationResult(
        sleeve_utilities=[SleeveUtility("x", 1, 0, 0, 0, 0, 1, 0.5, True)],
        sleeve_budgets={"x": 0.5},
        cash_weight=0.5,
        total_risk_scalar=0.5,
        combined_target_weights={"AAA": 0.5, "BBB": 0.2},
    )
    market = _market(open_=False)
    market.liquidity["BBB"] = 0

    result = RiskBox().apply(allocation, market, portfolio, config)

    assert "MARKET_CLOSED" in result.reason_codes
    assert result.feasible_book.target_weights["AAA"] == 0


def test_execution_governor_stages_limit_orders_and_dry_run_flag():
    config = _config(
        execution=ExecutionConfig(
            prefer_limit_orders=True,
            allow_market_orders=False,
            max_order_notional=500,
            min_order_notional=25,
            max_orders_per_cycle=3,
        )
    )
    market = _market()
    portfolio = PortfolioState(cash=100_000, portfolio_value=100_000)
    feasible = FeasibleBook({"AAA": 0.04}, {}, True, ["good"])

    plan = ExecutionGovernor().generate_orders(feasible, portfolio, market, config, dry_run=True)

    assert plan.dry_run
    assert 1 <= len(plan.orders) <= 3
    assert all(order.order_type == "limit" for order in plan.orders)


def test_quant_once_dry_run_does_not_submit(tmp_path):
    class Adapter:
        def get_portfolio(self):
            return PortfolioSnapshot(100_000, 100_000, 100_000, {})

        def get_market_snapshot(self, symbols):
            bars = {symbol: _bars(symbol, [100 + idx for idx in range(150)]) for symbol in symbols}
            return MarketSnapshot(bars, True)

        def submit_order(self, symbol, side, qty):
            raise AssertionError("dry-run must not submit")

    day = DayTraderConfig(None, None, symbols=["AAA", "BBB"], log_root=tmp_path / "logs", report_root=tmp_path / "reports")
    quant = _config(symbols=["AAA", "BBB"])
    report = QuantOrchestrator(day, quant, adapter=Adapter()).once(dry_run=True)

    assert report.raw_books
    assert report.allocation.combined_target_weights
    assert report.execution_plan.dry_run
    assert list((tmp_path / "reports" / "quant").glob("*.md"))
