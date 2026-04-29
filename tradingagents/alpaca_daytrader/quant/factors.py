"""Simple factor exposure model for ORIA-style risk deduplication."""

from __future__ import annotations

import numpy as np

from tradingagents.alpaca_daytrader.quant.covariance import returns_matrix
from tradingagents.alpaca_daytrader.quant.schemas import FactorExposure, MarketState, QuantConfig


class FactorExposureModel:
    """Computes approximate market, momentum, volatility, and liquidity exposures."""

    latest_exposures: FactorExposure | None = None

    def compute(
        self,
        market_state: MarketState,
        symbols: list[str],
        config: QuantConfig,
    ) -> FactorExposure:
        returns = returns_matrix(market_state, symbols, config.return_lookback_bars)
        market = self._market_beta(returns, symbols)
        exposures: dict[str, dict[str, float]] = {}
        for idx, symbol in enumerate(symbols):
            column = returns[:, idx] if returns.size else np.zeros(1)
            price = market_state.latest_price(symbol) or 1.0
            liquidity = market_state.liquidity.get(symbol)
            if liquidity is None:
                volumes = [bar.volume for bar in market_state.bars.get(symbol, [])]
                liquidity = float(np.nanmean(volumes[-20:])) if volumes else 0.0
            exposures[symbol] = {
                "market": float(market.get(symbol, 1.0)),
                "momentum": float(np.nanmean(column[-20:])) if len(column) else 0.0,
                "volatility": float(np.nanstd(column)) if len(column) else 0.0,
                "liquidity": float(np.log1p(max(liquidity, 0.0) * price)),
            }
        self.latest_exposures = FactorExposure(
            symbols=symbols,
            exposures=exposures,
            diagnostics={"fallback": "return_covariance" if "SPY" not in symbols else "spy_proxy"},
        )
        return self.latest_exposures

    def _market_beta(self, returns: np.ndarray, symbols: list[str]) -> dict[str, float]:
        if returns.size == 0:
            return {symbol: 1.0 for symbol in symbols}
        if "SPY" in symbols:
            proxy = returns[:, symbols.index("SPY")]
        else:
            proxy = np.nanmean(returns, axis=1)
        proxy_var = float(np.var(proxy))
        if proxy_var <= 1e-12:
            return {symbol: 1.0 for symbol in symbols}
        betas = {}
        for idx, symbol in enumerate(symbols):
            cov = float(np.cov(returns[:, idx], proxy)[0, 1])
            betas[symbol] = cov / proxy_var
        return betas
