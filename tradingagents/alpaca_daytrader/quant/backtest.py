"""Basic deterministic backtesting for the ORIA quant layer."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import numpy as np

from tradingagents.alpaca_daytrader.models import MarketBar
from tradingagents.alpaca_daytrader.quant.orchestrator import QuantOrchestrator
from tradingagents.alpaca_daytrader.quant.schemas import MarketState, PortfolioState


class _BacktestAdapter:
    def __init__(self, symbols: list[str], bars: dict[str, list[MarketBar]], index: int) -> None:
        self.symbols = symbols
        self.bars = bars
        self.index = index
        self.portfolio = PortfolioState(cash=100_000.0, portfolio_value=100_000.0)

    def get_portfolio(self):
        from tradingagents.alpaca_daytrader.models import PortfolioSnapshot

        return PortfolioSnapshot(
            cash=self.portfolio.cash,
            portfolio_value=self.portfolio.portfolio_value,
            buying_power=self.portfolio.cash,
            positions=self.portfolio.positions,
        )

    def get_market_snapshot(self, symbols):
        from tradingagents.alpaca_daytrader.models import MarketSnapshot

        return MarketSnapshot(
            bars={symbol: self.bars[symbol][: self.index] for symbol in symbols},
            market_open=True,
        )

    def submit_order(self, symbol, side, qty):
        return {"id": f"backtest-{symbol}-{side}-{qty}"}


def synthetic_bars(symbols: list[str], periods: int = 180) -> dict[str, list[MarketBar]]:
    start = datetime.now(timezone.utc) - timedelta(minutes=periods)
    output: dict[str, list[MarketBar]] = {}
    for offset, symbol in enumerate(symbols):
        series: list[MarketBar] = []
        price = 100.0 + offset * 10.0
        for idx in range(periods):
            price = price * (1.0 + 0.0005 * np.sin(idx / 8.0 + offset) + 0.0002)
            series.append(
                MarketBar(
                    symbol=symbol,
                    timestamp=(start + timedelta(minutes=idx)).isoformat(),
                    open=price * 0.999,
                    high=price * 1.002,
                    low=price * 0.998,
                    close=price,
                    volume=10_000 + idx * 10,
                )
            )
        output[symbol] = series
    return output


class QuantBacktester:
    """Runs a simplified walk-forward backtest over generated or cached bars."""

    def run(self, orchestrator: QuantOrchestrator, periods: int = 180) -> dict[str, float | int]:
        symbols = orchestrator.quant_config.symbols
        bars = synthetic_bars(symbols, periods=periods)
        values: list[float] = [100_000.0]
        trades = 0
        turnover = 0.0
        start = max(80, min(periods - 2, orchestrator.quant_config.return_lookback_bars + 5))
        for index in range(start, periods):
            adapter = _BacktestAdapter(symbols, bars, index)
            test_orchestrator = QuantOrchestrator(
                orchestrator.daytrader_config,
                replace(orchestrator.quant_config, symbols=symbols),
                adapter=adapter,
                logger=orchestrator.logger,
            )
            report = test_orchestrator.once(dry_run=True)
            exposure = report.risk.gross_exposure
            next_return = np.mean([
                bars[symbol][index].close / bars[symbol][index - 1].close - 1.0
                for symbol in symbols
            ])
            cost = 0.0005 * len(report.execution_plan.orders)
            values.append(values[-1] * (1.0 + exposure * next_return - cost))
            trades += len(report.execution_plan.orders)
            turnover += exposure
        returns = np.diff(values) / np.maximum(values[:-1], 1e-12)
        peak = np.maximum.accumulate(values)
        drawdowns = (np.array(values) - peak) / np.maximum(peak, 1e-12)
        gains = returns[returns > 0]
        losses = returns[returns < 0]
        return {
            "total_return": float(values[-1] / values[0] - 1.0),
            "volatility": float(np.std(returns)) if len(returns) else 0.0,
            "max_drawdown": float(np.min(drawdowns)) if len(drawdowns) else 0.0,
            "sharpe_like": float(np.mean(returns) / np.std(returns)) if len(returns) and np.std(returns) > 0 else 0.0,
            "sortino_like": float(np.mean(returns) / np.std(losses)) if len(losses) and np.std(losses) > 0 else 0.0,
            "turnover": float(turnover),
            "number_of_trades": trades,
            "win_rate": float(len(gains) / len(returns)) if len(returns) else 0.0,
            "average_gain": float(np.mean(gains)) if len(gains) else 0.0,
            "average_loss": float(np.mean(losses)) if len(losses) else 0.0,
            "final_value": float(values[-1]),
        }
