"""Paper-safe circuit breakers and kill-switch helpers."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CircuitBreakerState:
    tripped: bool
    reasons: list[str] = field(default_factory=list)


class CircuitBreakerManager:
    def evaluate(self, context: dict) -> CircuitBreakerState:
        reasons: list[str] = []
        if context.get("daily_loss_exceeded"):
            reasons.append("daily_loss_exceeded")
        if context.get("market_data_stale"):
            reasons.append("market_data_stale")
        if context.get("unexpected_live_mode"):
            reasons.append("unexpected_live_mode")
        if context.get("focus_list_empty"):
            reasons.append("focus_list_empty")
        if context.get("covariance_failure"):
            reasons.append("covariance_failure")
        return CircuitBreakerState(bool(reasons), reasons)

    def kill(self) -> CircuitBreakerState:
        return CircuitBreakerState(True, ["manual_kill_switch"])

    def cancel_all(self, adapter: object | None = None) -> str:
        client = getattr(adapter, "trading_client", None)
        if client and hasattr(client, "cancel_orders"):
            client.cancel_orders()
            return "paper orders cancelled"
        return "cancel-all dry-run: no adapter action"

    def flatten(self, adapter: object | None = None, paper_only: bool = True) -> str:
        if not paper_only:
            raise ValueError("flatten refuses non-paper mode")
        return "flatten paper-only requested; submit close orders via reviewed execution path"
