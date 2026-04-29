# Risk Controls

This project is research and paper-trading oriented. It defaults to dry-run,
uses Alpaca paper trading, refuses live trading unless explicitly allowed, and
keeps hard risk constraints in deterministic code.

## Layers

- Data quality validation excludes invalid prices, missing bars, zero volume,
  abnormal spreads, duplicate timestamps, and suspicious jumps.
- Universe filters reject symbols that are too illiquid, too wide, too quiet,
  too volatile, or event-risk blocked.
- Regime classification adjusts sleeve budgets for trend, risk-off,
  high-volatility, low-liquidity, and correlation-concentration regimes.
- RiskBox enforces max gross/net exposure, max position size, market hours,
  daily loss, drawdown, spread, liquidity, no-trade symbols, and cash reserve.
- Stress tests estimate losses under market drops, largest-position shocks,
  doubled spreads, and liquidity cuts.
- ExecutionGovernor stages limit-first paper orders and rejects orders below
  minimum size or outside execution policy.
- Circuit breakers expose paper-safe `kill`, `cancel-all`, and `flatten`
  commands.

## Commands

```bash
python -m tradingagents.alpaca_daytrader kill
python -m tradingagents.alpaca_daytrader cancel-all
python -m tradingagents.alpaca_daytrader flatten --paper-only
```

These commands are safe by default in this implementation. Real order
cancellation/flattening should be wired only after account-state reconciliation
and human review are in place.
