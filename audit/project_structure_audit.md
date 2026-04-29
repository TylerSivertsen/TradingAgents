# Project Structure Audit

## Findings

- The original TradingAgents package and CLI remain intact under `tradingagents/`, `tradingagents/agents/`, `tradingagents/graph/`, and `cli/`.
- The Alpaca daytrader lives under `tradingagents/alpaca_daytrader/` with semantic loop modules, quant modules, universe modules, risk modules, execution quality, and explainability.
- The Alpaca adapter currently sits at `tradingagents/alpaca_daytrader/alpaca_adapter.py`, not under an `adapters/` package. This is acceptable but should be treated as the canonical adapter until a future move.
- Runtime artifacts exist under `logs/`, `reports/`, `data/universe/`, and `experiments/results/`; these are now ignored, but generated files may already exist locally.
- There are two command surfaces: original `tradingagents` script and `python -m tradingagents.alpaca_daytrader`. Docker currently uses the original script, not the Alpaca runtime.
- `requirements.txt` contains only `.`, while dependencies live in `pyproject.toml`. This is workable but should be documented as the canonical install path.
- `configs/quant.toml` exists, but runtime config currently loads mostly from env vars and defaults. Full file/env/CLI merge is not complete.

## Risks

- Docker entrypoint mismatch can make the integrated system appear unavailable.
- Implicit runtime booleans make execution safety harder to reason about.
- Some requested ideal package names differ from the current implementation. Avoid churn unless a move is required for safety.

## Repair Direction

- Add canonical runtime mode and system orchestrator inside `tradingagents/alpaca_daytrader/`.
- Route Alpaca daytrader CLI commands through the canonical system orchestrator.
- Update Docker to use the Alpaca daytrader module by default.
