"""Small deterministic backtesting helper for the daytrader signal logic."""

from __future__ import annotations

from collections.abc import Sequence
from statistics import mean


def backtest_sma_cross(
    closes: Sequence[float],
    fast_window: int = 5,
    slow_window: int = 20,
    starting_cash: float = 10_000.0,
) -> dict[str, float | int]:
    if fast_window <= 0 or slow_window <= fast_window:
        raise ValueError("Require 0 < fast_window < slow_window.")
    if len(closes) < slow_window:
        raise ValueError("Not enough closes for the slow window.")
    cash = starting_cash
    shares = 0
    trades = 0
    for idx in range(slow_window, len(closes)):
        close = float(closes[idx])
        fast = mean(closes[idx - fast_window : idx])
        slow = mean(closes[idx - slow_window : idx])
        if fast > slow and shares == 0:
            shares = int(cash // close)
            cash -= shares * close
            trades += int(shares > 0)
        elif fast < slow and shares > 0:
            cash += shares * close
            shares = 0
            trades += 1
    final_value = cash + shares * float(closes[-1])
    return {
        "starting_cash": starting_cash,
        "final_value": final_value,
        "return_pct": (final_value - starting_cash) / starting_cash,
        "trades": trades,
        "shares": shares,
    }
