# CLI Runtime Audit

## Existing Commands

- Original TradingAgents CLI: `tradingagents`
- Alpaca semantic loop: `python -m tradingagents.alpaca_daytrader once|run|report`
- Quant commands: `quant-once`, `quant-run`, `quant-report`, `quant-backtest`, `quant-walkforward`, `quant-diagnostics`
- Universe commands: `universe-scan`, `universe-report`
- Paper-safe operational commands: `kill`, `cancel-all`, `flatten`
- Experiment commands: `experiment-list`, `experiment-show`

## Findings

- Alpaca commands mostly use orchestrators, but `universe-scan` builds discovery/scanner/focus directly in `__main__.py`.
- No single `diagnostics`, `dashboard`, `tui`, or `test` command exists yet.
- Runtime mode is inferred from flags instead of a strict mode object.
- Docker Compose does not expose the Alpaca commands as requested.
- Review mode correctly asks for human approval, but paper execution after approval still constructs a new quant orchestrator and should be guarded by a canonical runtime mode.

## Repair Status

- Added `RuntimeMode` and `TradingSystemOrchestrator`.
- Added top-level `diagnostics`, `dashboard`, `tui`, and `test` commands.
- Routed diagnostics, universe scan, quant run/backtest/walk-forward, test, and emergency stop through the system orchestrator.
- Updated Docker Compose service commands.
