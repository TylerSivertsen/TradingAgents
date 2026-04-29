"""Probability calibration for sleeve confidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CalibratedSignal:
    sleeve_name: str
    raw_confidence: float
    calibrated_confidence: float
    sample_size: int
    diagnostics: dict[str, Any] = field(default_factory=dict)


class SignalCalibrator:
    def calibrate(self, sleeve_name: str, raw_confidence: float, signal_context: dict) -> CalibratedSignal:
        sample_size = int(signal_context.get("sample_size", 0))
        realized_hit_rate = signal_context.get("hit_rate")
        if sample_size < 30 or realized_hit_rate is None:
            calibrated = 0.5 * raw_confidence + 0.25
        else:
            calibrated = 0.7 * float(realized_hit_rate) + 0.3 * raw_confidence
        return CalibratedSignal(sleeve_name, raw_confidence, max(0.0, min(1.0, calibrated)), sample_size)
