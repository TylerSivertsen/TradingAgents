from pathlib import Path

import pytest

from tradingagents.alpaca_daytrader.agents import RiskManagerAgent
from tradingagents.alpaca_daytrader.backtesting import backtest_sma_cross
from tradingagents.alpaca_daytrader.config import DayTraderConfig
from tradingagents.alpaca_daytrader.models import (
    MarketSnapshot,
    PortfolioSnapshot,
    TechnicalSnapshot,
    TradeDecision,
)
from tradingagents.alpaca_daytrader.orchestrator import DayTraderOrchestrator


def test_config_rejects_non_paper_execution():
    config = DayTraderConfig(api_key="key", secret_key="secret", paper=False)

    with pytest.raises(ValueError, match="paper trading"):
        config.validate_for_execution()


def test_dry_run_once_logs_and_does_not_submit(tmp_path: Path):
    config = DayTraderConfig(
        api_key=None,
        secret_key=None,
        symbols=["SPY"],
        log_root=tmp_path / "logs",
        report_root=tmp_path / "reports",
    )
    orchestrator = DayTraderOrchestrator(config)

    result = orchestrator.once(dry_run=True)

    assert result.decisions
    assert all(order.dry_run for order in result.orders)
    assert all(not order.submitted for order in result.orders)
    assert (tmp_path / "logs" / "decisions" / "decisions.jsonl").exists()
    assert list((tmp_path / "reports").glob("alpaca_daytrader_*.json"))


def test_risk_manager_rejects_closed_market_and_insufficient_funds():
    config = DayTraderConfig(api_key=None, secret_key=None, max_notional_per_order=1_000)
    portfolio = PortfolioSnapshot(cash=100, portfolio_value=1_000, buying_power=100)
    market = MarketSnapshot(bars={}, market_open=False)
    technicals = {
        "SPY": TechnicalSnapshot(
            symbol="SPY",
            close=100,
            fast_sma=101,
            slow_sma=99,
            momentum=1,
            status="ok",
        )
    }
    decisions = [TradeDecision(symbol="SPY", action="buy", qty=10, notional=1_000)]

    reviewed = RiskManagerAgent().review(
        decisions,
        portfolio,
        market,
        technicals,
        config,
        dry_run=True,
    )

    assert not reviewed[0].approved
    assert "market closed" in reviewed[0].rejections
    assert "insufficient funds after cash reserve" in reviewed[0].rejections


def test_backtest_sma_cross_returns_metrics():
    closes = [float(value) for value in range(1, 40)]

    result = backtest_sma_cross(closes, fast_window=3, slow_window=5)

    assert result["final_value"] > 0
    assert result["trades"] >= 1
