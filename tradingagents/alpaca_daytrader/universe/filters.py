"""Market-wide scanning and focus-list construction."""

from __future__ import annotations

import numpy as np

from tradingagents.alpaca_daytrader.data.validation import DataQualityValidator
from tradingagents.alpaca_daytrader.quant.schemas import PortfolioState
from tradingagents.alpaca_daytrader.universe.ranking import weighted_total
from tradingagents.alpaca_daytrader.universe.schemas import (
    FocusList,
    MarketScanResult,
    SymbolCandidateScore,
    TradableUniverse,
    UniverseConfig,
)


def _clip01(value: float) -> float:
    return float(max(0.0, min(1.0, value)))


class MarketScanner:
    """Scores a broad universe and rejects symbols unsuitable for intraday focus."""

    def __init__(self) -> None:
        self.validator = DataQualityValidator()

    def scan(
        self,
        universe: TradableUniverse,
        market_state_provider: object,
        config: UniverseConfig,
    ) -> MarketScanResult:
        symbols = universe.symbols[: config.max_scan_symbols]
        snapshot = market_state_provider.get_market_snapshot(symbols)
        candidates: list[SymbolCandidateScore] = []
        rejected: dict[str, list[str]] = {}
        for symbol in symbols:
            bars = snapshot.bars.get(symbol, [])
            quality = self.validator.validate_symbol_data(symbol, bars, None, config)
            candidate = self._score_symbol(symbol, bars, quality.score, config)
            candidate.rejection_reasons.extend(quality.reasons)
            if quality.action in {"exclude_symbol", "block_execution"}:
                candidate.is_valid = False
            if candidate.rejection_reasons:
                rejected[symbol] = list(candidate.rejection_reasons)
            candidate.total_score = weighted_total(candidate, config.ranking)
            candidates.append(candidate)
        valid = sorted(
            [candidate for candidate in candidates if candidate.is_valid],
            key=lambda item: (-item.total_score, item.symbol),
        )
        focus = [candidate.symbol for candidate in valid[: config.max_focus_symbols]]
        return MarketScanResult(
            candidates=candidates,
            rejected=rejected,
            focus_symbols=focus,
            scanned_count=len(candidates),
            rejected_count=len(rejected),
        )

    def _score_symbol(
        self,
        symbol: str,
        bars: list[object],
        data_quality_score: float,
        config: UniverseConfig,
    ) -> SymbolCandidateScore:
        reasons: list[str] = []
        if len(bars) < 20:
            return SymbolCandidateScore(symbol, False, 0.0, 0, 0, 0, 0, 0, 0, 1, data_quality_score, 0, ["insufficient_history"])
        closes = np.array([float(bar.close) for bar in bars], dtype=float)
        highs = np.array([float(bar.high) for bar in bars], dtype=float)
        lows = np.array([float(bar.low) for bar in bars], dtype=float)
        volumes = np.array([float(bar.volume) for bar in bars], dtype=float)
        price = float(closes[-1])
        recent_volume = float(np.sum(volumes[-20:]))
        avg_volume = float(np.mean(volumes[-60:])) if len(volumes) >= 60 else float(np.mean(volumes))
        spread_bps = 5.0
        returns = np.diff(closes) / np.maximum(closes[:-1], 1e-12)
        atr_pct = float(np.mean(highs[-14:] - lows[-14:]) / max(price, 1e-12))
        momentum = float(closes[-1] / closes[-20] - 1.0)
        mean = float(np.mean(closes[-60:])) if len(closes) >= 60 else float(np.mean(closes))
        std = float(np.std(closes[-60:])) if len(closes) >= 60 else float(np.std(closes))
        z = (price - mean) / max(std, 1e-12)
        breakout = float((highs[-1] - lows[-1]) / max(np.mean(highs[-20:] - lows[-20:]), 1e-12) - 1.0)
        if price < config.min_price or price > config.max_price:
            reasons.append("price_out_of_range")
        if recent_volume < config.min_intraday_volume or avg_volume < config.min_avg_daily_volume / 390:
            reasons.append("low_liquidity")
        if spread_bps > config.max_spread_bps:
            reasons.append("wide_spread")
        if atr_pct < config.min_atr_pct:
            reasons.append("too_quiet")
        if atr_pct > config.max_atr_pct:
            reasons.append("too_volatile")
        return SymbolCandidateScore(
            symbol=symbol,
            is_valid=not reasons and data_quality_score > 0,
            total_score=0.0,
            liquidity_score=_clip01(np.log1p(recent_volume) / np.log1p(max(config.min_intraday_volume * 20, 1))),
            spread_score=_clip01(1.0 - spread_bps / max(config.max_spread_bps, 1.0)),
            volatility_score=_clip01(1.0 - abs(atr_pct - 0.03) / 0.09),
            momentum_score=_clip01(abs(momentum) * 20),
            mean_reversion_score=_clip01(abs(z) / 3.0),
            breakout_score=_clip01(max(0.0, breakout)),
            event_risk_score=1.0,
            data_quality_score=data_quality_score,
            execution_quality_score=_clip01(1.0 - spread_bps / max(config.max_spread_bps, 1.0)),
            rejection_reasons=reasons,
            diagnostics={
                "price": price,
                "recent_volume": recent_volume,
                "avg_volume": avg_volume,
                "spread_bps": spread_bps,
                "atr_pct": atr_pct,
                "momentum": momentum,
                "zscore": z,
                "breakout": breakout,
            },
        )


class FocusListManager:
    """Builds the final dynamic focus list sent to ORIA."""

    def build_focus_list(
        self,
        scan_result: MarketScanResult,
        portfolio_state: PortfolioState,
        config: UniverseConfig,
        semantic_symbols: list[str] | None = None,
    ) -> FocusList:
        reasons: dict[str, list[str]] = {}
        rejected = dict(scan_result.rejected)
        ranked_valid = [
            candidate.symbol
            for candidate in sorted(scan_result.candidates, key=lambda c: (-c.total_score, c.symbol))
            if candidate.is_valid
        ]
        selected: list[str] = []
        for symbol in list(portfolio_state.positions) + config.seed_symbols + (semantic_symbols or []) + ranked_valid:
            symbol = symbol.upper()
            if symbol in selected:
                continue
            if symbol in rejected and symbol not in portfolio_state.positions:
                continue
            selected.append(symbol)
            reasons.setdefault(symbol, []).append("holding" if symbol in portfolio_state.positions else "ranked_or_seed")
            if len(selected) >= config.max_focus_symbols:
                break
        if not selected:
            rejected["__focus__"] = ["no_valid_focus_symbols"]
        return FocusList(symbols=selected, reasons=reasons, rejected=rejected)
