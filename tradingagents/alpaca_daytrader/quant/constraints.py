"""Constraint dataclasses for ORIA orthogonalization and risk stages."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class OrthogonalizationConstraints:
    enforce_market_neutral: bool = False
    neutralize_factors: list[str] = field(default_factory=list)
    min_book_norm: float = 1e-6
    max_condition_number: float = 1e8
