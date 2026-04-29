"""Starter mathematical strategy sleeves for the ORIA pipeline."""

from __future__ import annotations

from typing import Protocol

import numpy as np

from tradingagents.alpaca_daytrader.quant.schemas import (
    MarketState,
    PortfolioState,
    QuantConfig,
    RawDesiredBook,
    StrategyDiagnostics,
)


class StrategySleeve(Protocol):
    name: str

    def generate_raw_book(
        self,
        market_state: MarketState,
        portfolio_state: PortfolioState,
        config: QuantConfig,
    ) -> RawDesiredBook:
        ...


def _closes(market_state: MarketState, symbol: str) -> np.ndarray:
    return np.array([bar.close for bar in market_state.bars.get(symbol, [])], dtype=float)


def _volumes(market_state: MarketState, symbol: str) -> np.ndarray:
    return np.array([bar.volume for bar in market_state.bars.get(symbol, [])], dtype=float)


def _normalize(weights: dict[str, float], allow_shorts: bool) -> dict[str, float]:
    if not allow_shorts:
        weights = {symbol: max(0.0, value) for symbol, value in weights.items()}
    gross = sum(abs(value) for value in weights.values())
    if gross <= 0:
        return {symbol: 0.0 for symbol in weights}
    return {symbol: value / gross for symbol, value in weights.items()}


def _confidence(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(max(0.0, min(1.0, np.nanmean(np.abs(values)))))


class MomentumSleeve:
    name = "momentum"

    def generate_raw_book(
        self,
        market_state: MarketState,
        portfolio_state: PortfolioState,
        config: QuantConfig,
    ) -> RawDesiredBook:
        lookback = config.momentum.lookback_bars
        raw: dict[str, float] = {}
        warnings: list[str] = []
        signals: list[float] = []
        for symbol in config.symbols:
            closes = _closes(market_state, symbol)
            if len(closes) <= lookback:
                warnings.append(f"{symbol}: insufficient momentum history")
                raw[symbol] = 0.0
                continue
            ret = closes[-1] / closes[-lookback] - 1.0
            raw[symbol] = float(ret)
            signals.append(float(ret))
        weights = _normalize(raw, config.allow_shorts)
        return RawDesiredBook(
            strategy_name=self.name,
            symbols=config.symbols,
            target_weights=weights,
            expected_return=float(np.nanmean(signals)) if signals else 0.0,
            confidence=_confidence(signals),
            uncertainty=float(np.nanstd(signals)) if signals else 1.0,
            holding_horizon="intraday",
            turnover_estimate=sum(abs(value) for value in weights.values()),
            rationale="Ranks assets by recent intraday return momentum.",
            diagnostics=StrategyDiagnostics(warnings=warnings, metrics={"lookback": lookback}),
        )


class MeanReversionSleeve:
    name = "mean_reversion"

    def generate_raw_book(
        self,
        market_state: MarketState,
        portfolio_state: PortfolioState,
        config: QuantConfig,
    ) -> RawDesiredBook:
        lookback = config.mean_reversion.lookback_bars
        entry_z = config.mean_reversion.entry_z
        raw: dict[str, float] = {}
        warnings: list[str] = []
        zscores: list[float] = []
        for symbol in config.symbols:
            closes = _closes(market_state, symbol)
            if len(closes) <= lookback:
                warnings.append(f"{symbol}: insufficient mean-reversion history")
                raw[symbol] = 0.0
                continue
            window = closes[-lookback:]
            sigma = float(np.std(window))
            if sigma <= 1e-12:
                raw[symbol] = 0.0
                continue
            z = float((closes[-1] - np.mean(window)) / sigma)
            zscores.append(z)
            if abs(z) >= entry_z:
                raw[symbol] = -z
            else:
                raw[symbol] = 0.0
        weights = _normalize(raw, config.allow_shorts)
        return RawDesiredBook(
            strategy_name=self.name,
            symbols=config.symbols,
            target_weights=weights,
            expected_return=float(np.nanmean(np.abs(zscores))) / 100.0 if zscores else 0.0,
            confidence=min(1.0, float(np.nanmean(np.abs(zscores))) / max(entry_z, 1.0)) if zscores else 0.0,
            uncertainty=float(np.nanstd(zscores)) if zscores else 1.0,
            holding_horizon="intraday",
            turnover_estimate=sum(abs(value) for value in weights.values()),
            rationale="Fades large z-score deviations from recent mean.",
            diagnostics=StrategyDiagnostics(
                warnings=warnings,
                metrics={"lookback": lookback, "entry_z": entry_z},
            ),
        )


class VolatilityBreakoutSleeve:
    name = "volatility_breakout"

    def generate_raw_book(
        self,
        market_state: MarketState,
        portfolio_state: PortfolioState,
        config: QuantConfig,
    ) -> RawDesiredBook:
        lookback = config.volatility_breakout.lookback_bars
        raw: dict[str, float] = {}
        warnings: list[str] = []
        scores: list[float] = []
        for symbol in config.symbols:
            bars = market_state.bars.get(symbol, [])
            if len(bars) <= lookback:
                warnings.append(f"{symbol}: insufficient breakout history")
                raw[symbol] = 0.0
                continue
            ranges = np.array([bar.high - bar.low for bar in bars[-lookback:]], dtype=float)
            avg_range = float(np.mean(ranges))
            latest_range = float(bars[-1].high - bars[-1].low)
            close_break = bars[-1].close / bars[-lookback].close - 1.0
            spread_penalty = max(0.0, market_state.spreads_bps.get(symbol, 5.0) / 100.0)
            score = max(0.0, (latest_range / max(avg_range, 1e-12) - 1.0) * np.sign(close_break))
            score = float(score / (1.0 + spread_penalty))
            raw[symbol] = score
            scores.append(score)
        weights = _normalize(raw, config.allow_shorts)
        return RawDesiredBook(
            strategy_name=self.name,
            symbols=config.symbols,
            target_weights=weights,
            expected_return=float(np.nanmean(scores)) if scores else 0.0,
            confidence=_confidence(scores),
            uncertainty=float(np.nanstd(scores)) if scores else 1.0,
            holding_horizon="intraday",
            turnover_estimate=sum(abs(value) for value in weights.values()),
            rationale="Follows range expansion when price confirms the breakout direction.",
            diagnostics=StrategyDiagnostics(warnings=warnings, metrics={"lookback": lookback}),
        )


class PairSpreadSleeve:
    name = "pair_spread"

    def generate_raw_book(
        self,
        market_state: MarketState,
        portfolio_state: PortfolioState,
        config: QuantConfig,
    ) -> RawDesiredBook:
        raw = {symbol: 0.0 for symbol in config.symbols}
        warnings: list[str] = []
        zscores: list[float] = []
        for left, right in config.pairs:
            if left not in raw or right not in raw:
                continue
            left_closes = _closes(market_state, left)
            right_closes = _closes(market_state, right)
            n = min(len(left_closes), len(right_closes), config.return_lookback_bars)
            if n < 20:
                warnings.append(f"{left}/{right}: insufficient pair history")
                continue
            spread = np.log(left_closes[-n:]) - np.log(right_closes[-n:])
            sigma = float(np.std(spread))
            if sigma <= 1e-12:
                continue
            z = float((spread[-1] - np.mean(spread)) / sigma)
            zscores.append(z)
            if abs(z) >= config.mean_reversion.entry_z:
                raw[left] += -z
                raw[right] += z
        weights = _normalize(raw, config.allow_shorts)
        return RawDesiredBook(
            strategy_name=self.name,
            symbols=config.symbols,
            target_weights=weights,
            expected_return=float(np.nanmean(np.abs(zscores))) / 100.0 if zscores else 0.0,
            confidence=min(1.0, float(np.nanmean(np.abs(zscores))) / 3.0) if zscores else 0.0,
            uncertainty=float(np.nanstd(zscores)) if zscores else 1.0,
            holding_horizon="intraday",
            turnover_estimate=sum(abs(value) for value in weights.values()),
            rationale="Trades relative spread z-scores for configured pairs.",
            diagnostics=StrategyDiagnostics(warnings=warnings, metrics={"pairs": float(len(config.pairs))}),
        )


class MinimumVarianceSleeve:
    name = "minimum_variance"

    def generate_raw_book(
        self,
        market_state: MarketState,
        portfolio_state: PortfolioState,
        config: QuantConfig,
    ) -> RawDesiredBook:
        raw: dict[str, float] = {}
        vols: list[float] = []
        warnings: list[str] = []
        for symbol in config.symbols:
            closes = _closes(market_state, symbol)
            if len(closes) < 3:
                warnings.append(f"{symbol}: insufficient volatility history")
                raw[symbol] = 0.0
                continue
            returns = np.diff(closes[-config.return_lookback_bars :]) / closes[-config.return_lookback_bars : -1]
            vol = float(np.std(returns)) if len(returns) else 0.0
            vols.append(vol)
            raw[symbol] = 1.0 / max(vol, 1e-6)
        weights = _normalize(raw, allow_shorts=False)
        return RawDesiredBook(
            strategy_name=self.name,
            symbols=config.symbols,
            target_weights=weights,
            expected_return=0.001,
            confidence=0.5 if any(weights.values()) else 0.0,
            uncertainty=float(np.nanmean(vols)) if vols else 1.0,
            holding_horizon="intraday",
            turnover_estimate=sum(abs(value) for value in weights.values()),
            rationale="Defensive inverse-volatility allocation.",
            diagnostics=StrategyDiagnostics(warnings=warnings),
        )


class CashSleeve:
    name = "cash"

    def generate_raw_book(
        self,
        market_state: MarketState,
        portfolio_state: PortfolioState,
        config: QuantConfig,
    ) -> RawDesiredBook:
        return RawDesiredBook(
            strategy_name=self.name,
            symbols=config.symbols,
            target_weights={symbol: 0.0 for symbol in config.symbols},
            expected_return=0.0,
            confidence=1.0,
            uncertainty=0.0,
            holding_horizon="cash",
            turnover_estimate=0.0,
            rationale="Explicit no-trade/cash alternative.",
        )


def default_sleeves(config: QuantConfig) -> list[StrategySleeve]:
    sleeves: list[StrategySleeve] = []
    if config.momentum.enabled:
        sleeves.append(MomentumSleeve())
    if config.mean_reversion.enabled:
        sleeves.append(MeanReversionSleeve())
    if config.volatility_breakout.enabled:
        sleeves.append(VolatilityBreakoutSleeve())
    if config.pairs:
        sleeves.append(PairSpreadSleeve())
    if config.minimum_variance.enabled:
        sleeves.append(MinimumVarianceSleeve())
    if config.cash.enabled:
        sleeves.append(CashSleeve())
    return sleeves
