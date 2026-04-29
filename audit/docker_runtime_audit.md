# Docker Runtime Audit

## Findings

- `Dockerfile` exists and installs the package.
- `docker-compose.yml` exists but serves original `tradingagents` CLI, not Alpaca daytrader commands.
- Runtime volumes are not mounted to `./logs`, `./reports`, `./data`, and `./audit` as requested.
- Tests service does not exist.
- TUI service does not exist.
- Container runs as non-root `appuser`, which is good.

## Risks

- `docker compose run --rm trader diagnostics` does not work with the current compose file.
- Alpaca runtime reports/logs may not persist in the requested host paths.

## Repair Status

- Dockerfile entrypoint now uses `python -m tradingagents.alpaca_daytrader`.
- Compose services now include `trader`, `trader-tui`, `trader-shadow`, and `tests`.
- Compose mounts `logs`, `reports`, `data`, `audit`, and `experiments`.
