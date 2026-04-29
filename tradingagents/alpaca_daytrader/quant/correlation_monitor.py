"""Correlation concentration monitoring."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from tradingagents.alpaca_daytrader.quant.schemas import CovarianceEstimate


@dataclass
class CorrelationBreakdownResult:
    breakdown_detected: bool
    avg_correlation: float
    first_pc_share: float
    recommended_gross_scale: float


class CorrelationMonitor:
    def inspect(self, covariance: CovarianceEstimate) -> CorrelationBreakdownResult:
        matrix = np.array(covariance.matrix, dtype=float)
        if matrix.size == 0:
            return CorrelationBreakdownResult(True, 1.0, 1.0, 0.5)
        diag = np.sqrt(np.maximum(np.diag(matrix), 1e-12))
        corr = matrix / np.maximum(np.outer(diag, diag), 1e-12)
        avg = float(np.nanmean(np.nan_to_num(corr[np.triu_indices_from(corr, k=1)]))) if corr.shape[0] > 1 else 0.0
        eig = np.linalg.eigvalsh(matrix)
        pc = float(max(eig) / max(sum(eig), 1e-12))
        detected = avg > 0.75 or pc > 0.8
        return CorrelationBreakdownResult(detected, avg, pc, 0.6 if detected else 1.0)
