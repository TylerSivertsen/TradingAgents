"""Thin Alpaca adapter with imports isolated from dry-run tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from tradingagents.alpaca_daytrader.config import DayTraderConfig
from tradingagents.alpaca_daytrader.models import MarketBar, MarketSnapshot, PortfolioSnapshot


class AlpacaAdapter:
    """Adapter around alpaca-py clients.

    The trading client is initialized exactly as required by the integration
    contract: TradingClient(api_key, secret_key, paper=True).
    """

    def __init__(self, config: DayTraderConfig) -> None:
        self.config = config
        try:
            from alpaca.trading.client import TradingClient
        except ImportError as exc:
            raise ImportError("Install alpaca-py to use Alpaca execution.") from exc
        if not config.api_key or not config.secret_key:
            raise ValueError("Alpaca API credentials are required.")
        self.trading_client = TradingClient(
            config.api_key,
            config.secret_key,
            paper=True,
        )
        self.data_client = self._build_data_client(config)

    def get_portfolio(self) -> PortfolioSnapshot:
        account = self.trading_client.get_account()
        positions = {
            position.symbol: float(position.qty)
            for position in self.trading_client.get_all_positions()
        }
        return PortfolioSnapshot(
            cash=float(account.cash),
            portfolio_value=float(account.portfolio_value),
            buying_power=float(account.buying_power),
            positions=positions,
        )

    def is_market_open(self) -> bool:
        clock = self.trading_client.get_clock()
        return bool(clock.is_open)

    def get_market_snapshot(self, symbols: list[str]) -> MarketSnapshot:
        bars = self._get_bars(symbols)
        return MarketSnapshot(bars=bars, market_open=self.is_market_open())

    def submit_order(self, symbol: str, side: str, qty: int) -> Any:
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest

        request = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
        )
        return self.trading_client.submit_order(order_data=request)

    def _build_data_client(self, config: DayTraderConfig) -> Any:
        try:
            from alpaca.data.historical import StockHistoricalDataClient
        except ImportError:
            return None
        return StockHistoricalDataClient(config.api_key, config.secret_key)

    def _get_bars(self, symbols: list[str]) -> dict[str, list[MarketBar]]:
        if self.data_client is None:
            return {symbol: [] for symbol in symbols}
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        timeframe = TimeFrame.Minute
        start = datetime.now(timezone.utc) - timedelta(days=5)
        request = StockBarsRequest(symbol_or_symbols=symbols, timeframe=timeframe, start=start)
        response = self.data_client.get_stock_bars(request)
        rows = response.df.reset_index().to_dict("records")
        bars: dict[str, list[MarketBar]] = {symbol: [] for symbol in symbols}
        for row in rows:
            symbol = str(row["symbol"]).upper()
            bars.setdefault(symbol, []).append(
                MarketBar(
                    symbol=symbol,
                    timestamp=str(row["timestamp"]),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["volume"]),
                )
            )
        return bars


class DryRunAdapter:
    """Deterministic local adapter used when no Alpaca calls should happen."""

    def __init__(self, market_open: bool = True) -> None:
        self.market_open = market_open

    def get_portfolio(self) -> PortfolioSnapshot:
        return PortfolioSnapshot(
            cash=100_000.0,
            portfolio_value=100_000.0,
            buying_power=100_000.0,
            positions={},
        )

    def is_market_open(self) -> bool:
        return self.market_open

    def get_market_snapshot(self, symbols: list[str]) -> MarketSnapshot:
        bars: dict[str, list[MarketBar]] = {}
        for symbol in symbols:
            series: list[MarketBar] = []
            for idx in range(150):
                close = 100.0 + idx * 0.25
                series.append(
                    MarketBar(
                        symbol=symbol,
                        timestamp=(
                            datetime.now(timezone.utc) - timedelta(minutes=150 - idx)
                        ).isoformat(),
                        open=close - 0.1,
                        high=close + 0.2,
                        low=close - 0.2,
                        close=close,
                        volume=1_000 + idx,
                    )
                )
            bars[symbol] = series
        return MarketSnapshot(bars=bars, market_open=self.market_open)

    def submit_order(self, symbol: str, side: str, qty: int) -> Any:
        return {"id": f"dry-{symbol}-{side}-{qty}"}
