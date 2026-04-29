"""ORIA-style factor neutralization and risk-metric decorrelation."""

from __future__ import annotations

import numpy as np

from tradingagents.alpaca_daytrader.quant.constraints import OrthogonalizationConstraints
from tradingagents.alpaca_daytrader.quant.factors import FactorExposureModel
from tradingagents.alpaca_daytrader.quant.schemas import (
    CovarianceEstimate,
    FactorNeutralizationResult,
    OrthogonalizationDiagnostics,
    OrthogonalizedBook,
    OrthogonalizedBookSet,
    RawDesiredBook,
)


def _vector(book: RawDesiredBook, symbols: list[str]) -> np.ndarray:
    return np.array([book.target_weights.get(symbol, 0.0) for symbol in symbols], dtype=float)


def _dict(symbols: list[str], vector: np.ndarray) -> dict[str, float]:
    return {symbol: float(value) for symbol, value in zip(symbols, vector)}


def _safe_corr(matrix: np.ndarray) -> list[list[float]]:
    if matrix.shape[0] <= 1:
        return [[1.0]]
    if matrix.shape[1] == 0:
        return []
    row_std = np.std(matrix, axis=1)
    if np.any(row_std <= 1e-12):
        size = matrix.shape[0]
        corr = np.eye(size)
        for i in range(size):
            for j in range(size):
                if i != j and row_std[i] > 1e-12 and row_std[j] > 1e-12:
                    corr[i, j] = float(np.corrcoef(matrix[i], matrix[j])[0, 1])
        return np.nan_to_num(corr).tolist()
    corr = np.corrcoef(matrix)
    return np.nan_to_num(corr).tolist()


class Orthogonalizer:
    """Deduplicates sleeve risk before capital allocation."""

    def orthogonalize(
        self,
        raw_books: list[RawDesiredBook],
        factor_model: FactorExposureModel,
        covariance: CovarianceEstimate,
        constraints: OrthogonalizationConstraints,
    ) -> OrthogonalizedBookSet:
        if not raw_books:
            diagnostics = OrthogonalizationDiagnostics([], [], {}, {}, {}, ["no raw books"])
            return OrthogonalizedBookSet([], [], diagnostics)
        symbols = sorted({symbol for book in raw_books for symbol in book.symbols})
        cov = self._aligned_covariance(covariance, symbols)
        warnings = list(covariance.warnings)
        matrix = np.vstack([_vector(book, symbols) for book in raw_books])
        factor_exposure = factor_model.compute_from_symbols(symbols) if hasattr(factor_model, "compute_from_symbols") else None
        neutralized: list[np.ndarray] = []
        before_exp: dict[str, dict[str, float]] = {}
        after_exp: dict[str, dict[str, float]] = {}
        removed: dict[str, float] = {}
        factors = self._factor_matrix(factor_model, symbols)
        for book, row in zip(raw_books, matrix):
            result = self._neutralize(row, symbols, factors, constraints)
            neutralized.append(np.array(list(result.weights.values()), dtype=float))
            before_exp[book.strategy_name] = result.before_exposure
            after_exp[book.strategy_name] = result.after_exposure
            removed[book.strategy_name] = result.removed_magnitude
            warnings.extend(result.warnings)
        ortho = self._gram_schmidt(neutralized, cov, constraints, warnings)
        books: list[OrthogonalizedBook] = []
        for raw, vector, removed_mag in zip(raw_books, ortho, [removed[b.strategy_name] for b in raw_books]):
            norm = self._risk_norm(vector, cov)
            active = bool(norm >= constraints.min_book_norm and np.any(np.abs(vector) > constraints.min_book_norm))
            normalized = vector / norm if active and norm > 0 else np.zeros_like(vector)
            gross = float(np.sum(np.abs(normalized)))
            if gross > 0:
                normalized = normalized / gross
            books.append(
                OrthogonalizedBook(
                    strategy_name=raw.strategy_name,
                    symbols=symbols,
                    target_weights=_dict(symbols, normalized),
                    expected_return=raw.expected_return,
                    confidence=raw.confidence,
                    uncertainty=raw.uncertainty,
                    turnover_estimate=raw.turnover_estimate,
                    active=active,
                    removed_magnitude=removed_mag,
                    source_rationale=raw.rationale,
                )
            )
            if not active:
                warnings.append(f"{raw.strategy_name}: collapsed after orthogonalization")
        after_matrix = np.vstack([np.array(list(book.target_weights.values())) for book in books]) if books else np.zeros((0, 0))
        diagnostics = OrthogonalizationDiagnostics(
            before_correlations=_safe_corr(matrix),
            after_correlations=_safe_corr(after_matrix),
            factor_exposures_before=before_exp,
            factor_exposures_after=after_exp,
            removed_exposure=removed,
            warnings=warnings,
        )
        return OrthogonalizedBookSet(symbols=symbols, books=books, diagnostics=diagnostics)

    def _factor_matrix(self, factor_model: FactorExposureModel, symbols: list[str]) -> np.ndarray:
        exposures = getattr(factor_model, "latest_exposures", None)
        if exposures is None:
            return np.ones((len(symbols), 1))
        factor_names = sorted({name for item in exposures.exposures.values() for name in item})
        if not factor_names:
            return np.ones((len(symbols), 1))
        return np.array(
            [[exposures.exposures.get(symbol, {}).get(name, 0.0) for name in factor_names] for symbol in symbols],
            dtype=float,
        )

    def _neutralize(
        self,
        weights: np.ndarray,
        symbols: list[str],
        factors: np.ndarray,
        constraints: OrthogonalizationConstraints,
    ) -> FactorNeutralizationResult:
        warnings: list[str] = []
        before = self._exposure_summary(weights, factors)
        neutralized = weights.copy()
        if constraints.enforce_market_neutral or constraints.neutralize_factors:
            try:
                projection = factors @ np.linalg.pinv(factors) @ weights
                neutralized = weights - projection
            except np.linalg.LinAlgError:
                warnings.append("factor neutralization failed; kept raw weights")
        after = self._exposure_summary(neutralized, factors)
        return FactorNeutralizationResult(
            weights=_dict(symbols, neutralized),
            before_exposure=before,
            after_exposure=after,
            removed_magnitude=float(np.linalg.norm(weights - neutralized)),
            warnings=warnings,
        )

    def _exposure_summary(self, weights: np.ndarray, factors: np.ndarray) -> dict[str, float]:
        values = factors.T @ weights if factors.size else np.array([])
        return {f"factor_{idx}": float(value) for idx, value in enumerate(values)}

    def _gram_schmidt(
        self,
        vectors: list[np.ndarray],
        cov: np.ndarray,
        constraints: OrthogonalizationConstraints,
        warnings: list[str],
    ) -> list[np.ndarray]:
        output: list[np.ndarray] = []
        for vector in vectors:
            current = vector.astype(float).copy()
            for basis in output:
                denom = float(basis.T @ cov @ basis)
                if abs(denom) <= constraints.min_book_norm:
                    continue
                current = current - (float(current.T @ cov @ basis) / denom) * basis
            if self._risk_norm(current, cov) <= constraints.min_book_norm:
                warnings.append("degenerate sleeve vector under risk metric")
            output.append(current)
        return output

    def _risk_norm(self, vector: np.ndarray, cov: np.ndarray) -> float:
        value = float(vector.T @ cov @ vector)
        return float(np.sqrt(max(value, 0.0)))

    def _aligned_covariance(self, covariance: CovarianceEstimate, symbols: list[str]) -> np.ndarray:
        source = np.array(covariance.matrix, dtype=float)
        if source.shape == (len(symbols), len(symbols)) and covariance.symbols == symbols:
            return source
        result = np.eye(len(symbols)) * 1e-4
        index = {symbol: idx for idx, symbol in enumerate(covariance.symbols)}
        for i, left in enumerate(symbols):
            for j, right in enumerate(symbols):
                if left in index and right in index:
                    result[i, j] = source[index[left], index[right]]
        return result
