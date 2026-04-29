# Alpaca Integration Audit

## Findings

- Credentials are loaded from `ALPACA_API_KEY` and `ALPACA_SECRET_KEY`.
- `TradingClient(api_key, secret_key, paper=True)` is used for the Alpaca adapter.
- Dry-run mode uses `DryRunAdapter` and does not require credentials.
- Paper execution validates credentials and `ALPACA_PAPER=true` through `DayTraderConfig.validate_for_execution`.
- Market clock is checked via Alpaca when using the real adapter.
- Market data is fetched through `StockHistoricalDataClient` when available, with dry-run synthetic bars otherwise.
- Cancel-all/flatten are paper-safe stubs unless a real adapter is passed.

## Risks

- No retry/timeout wrapper exists around Alpaca calls.
- Open orders are not currently reconciled before execution.
- Live trading is effectively refused by `paper=True`, but there is not yet an explicit `--execute-live` command.

## Repair Direction

- Centralize execution permission in `RuntimeMode` and `SafetyPolicy`.
- Keep live trading blocked by default.
- Make diagnostics report credential presence without printing secrets.
