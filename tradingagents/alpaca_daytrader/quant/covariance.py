"""Covariance estimation for risk-aware orthogonalization."""

from __future__ import annotations

import numpy as np

from tradingagents.alpaca_daytrader.quant.schemas import CovarianceEstimate, MarketState


def returns_matrix(market_state: MarketState, symbols: list[str], lookback: int) -> np.ndarray:
    columns: list[np.ndarray] = []
    min_len: int | None = None
    for symbol in symbols:
        closes = np.array([bar.close for bar in market_state.bars.get(symbol, [])], dtype=float)
        if len(closes) < 2:
            returns = np.zeros(1)
        else:
            returns = np.diff(closes[-lookback:]) / np.maximum(closes[-lookback:-1], 1e-12)
        min_len = len(returns) if min_len is None else min(min_len, len(returns))
        columns.append(returns)
    if min_len is None or min_len <= 0:
        return np.zeros((1, len(symbols)))
    return np.column_stack([col[-min_len:] for col in columns])


class CovarianceEstimator:
    """Estimates rolling or exponentially weighted covariance with safe fallbacks."""

    def estimate(
        self,
        market_state: MarketState,
        symbols: list[str],
        lookback: int,
        method: str = "ewm",
        shrinkage: float = 0.10,
    ) -> CovarianceEstimate:
        warnings: list[str] = []
        returns = returns_matrix(market_state, symbols, lookback)
        if returns.shape[0] < 2:
            warnings.append("insufficient returns; using diagonal fallback")
            matrix = np.eye(len(symbols)) * 1e-4
            return CovarianceEstimate(symbols, matrix.tolist(), "diagonal", False, warnings)
        returns = np.nan_to_num(returns)
        if method == "ewm":
            decay = 0.94
            weights = np.array([decay ** i for i in range(returns.shape[0] - 1, -1, -1)], dtype=float)
            weights = weights / weights.sum()
            centered = returns - np.average(returns, axis=0, weights=weights)
            matrix = (centered * weights[:, None]).T @ centered
        else:
            matrix = np.cov(returns, rowvar=False)
        if matrix.ndim == 0:
            matrix = np.array([[float(matrix)]])
        diag = np.diag(np.diag(matrix))
        matrix = (1.0 - shrinkage) * matrix + shrinkage * diag
        matrix = np.nan_to_num(matrix)
        matrix += np.eye(len(symbols)) * 1e-8
        singular = False
        try:
            condition = np.linalg.cond(matrix)
        except np.linalg.LinAlgError:
            condition = float("inf")
        if not np.isfinite(condition) or condition > 1e10:
            singular = True
            warnings.append("covariance unstable; using diagonal fallback")
            matrix = np.diag(np.maximum(np.diag(matrix), 1e-6))
        return CovarianceEstimate(symbols, matrix.tolist(), method, singular, warnings)
