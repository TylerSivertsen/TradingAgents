"""Risk-adjusted candidate ranking for market scans."""

from __future__ import annotations

from tradingagents.alpaca_daytrader.universe.schemas import SymbolCandidateScore, UniverseRankingConfig


def weighted_total(
    candidate: SymbolCandidateScore,
    ranking: UniverseRankingConfig,
) -> float:
    return (
        ranking.liquidity_weight * candidate.liquidity_score
        + ranking.spread_weight * candidate.spread_score
        + ranking.volatility_weight * candidate.volatility_score
        + ranking.momentum_weight * candidate.momentum_score
        + ranking.mean_reversion_weight * candidate.mean_reversion_score
        + ranking.news_event_weight * candidate.event_risk_score
        + ranking.execution_quality_weight * candidate.execution_quality_score
    ) * candidate.data_quality_score
