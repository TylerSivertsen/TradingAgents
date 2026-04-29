# Alpaca Daytrader

The Alpaca daytrader module provides a safe research loop for portfolio state,
market data, semantic-agent decisions, risk review, dry-run execution, and
Alpaca paper order submission.

## Commands

Use Git Bash on Windows for the commands below.

Install the package in editable mode from the repo root:

```bash
pip install -e .
```

Create a local `.env` from `.env.example` and set only your own credentials:

```env
ALPACA_API_KEY=your_paper_key
ALPACA_SECRET_KEY=your_paper_secret
ALPACA_PAPER=true
TRADING_DRY_RUN=true
ALLOW_LIVE_TRADING=false
```

Keep `ALLOW_LIVE_TRADING=false`. The current Alpaca adapter is intended for
paper trading and initializes with `paper=True`.

## Safe First Run

Start with diagnostics and a universe scan. These commands do not submit
orders:

```bash
python -m tradingagents.alpaca_daytrader quant-diagnostics
python -m tradingagents.alpaca_daytrader universe-scan
python -m tradingagents.alpaca_daytrader universe-report
```

Then run a single dry-run quant pass:

```bash
python -m tradingagents.alpaca_daytrader quant-once --dry-run
python -m tradingagents.alpaca_daytrader quant-report
```

Read the generated reports before using review or execution modes:

- `reports/universe/YYYY-MM-DD.md`
- `reports/quant/YYYY-MM-DD.md`
- `logs/quant/*/YYYY-MM-DD.jsonl`

## Legacy Semantic Loop

```bash
python -m tradingagents.alpaca_daytrader once --dry-run
python -m tradingagents.alpaca_daytrader run --dry-run
python -m tradingagents.alpaca_daytrader run --execute
python -m tradingagents.alpaca_daytrader report
```

Dry-run is the default. Execution requires `ALPACA_API_KEY`,
`ALPACA_SECRET_KEY`, and `ALPACA_PAPER=true`.

Runtime logs are written under `logs/`, and reports are written under
`reports/`.

## Quant Modes

```bash
python -m tradingagents.alpaca_daytrader universe-scan
python -m tradingagents.alpaca_daytrader quant-once --dry-run
python -m tradingagents.alpaca_daytrader quant-once --review
python -m tradingagents.alpaca_daytrader quant-run --shadow
python -m tradingagents.alpaca_daytrader quant-once --execute
```

- `--dry-run`: generate analysis, plans, logs, and reports; submit nothing.
- `--review`: print proposed paper orders and ask for `y/N` approval.
- `--shadow`: continuously simulate proposed orders without submitting.
- `--execute`: submit approved orders to the Alpaca paper account.

For a bounded loop during testing:

```bash
python -m tradingagents.alpaca_daytrader quant-run --shadow --iterations 3
python -m tradingagents.alpaca_daytrader quant-run --dry-run --iterations 3
```

## Research Validation

Backtest and walk-forward commands can run without hardcoded symbols. They use
the dynamic universe flow unless `--symbols` is provided as an override.

```bash
python -m tradingagents.alpaca_daytrader quant-backtest --periods 180
python -m tradingagents.alpaca_daytrader quant-backtest --symbols SPY,QQQ --periods 180
python -m tradingagents.alpaca_daytrader quant-walkforward --train-days 60 --test-days 10
```

Experiment records are stored locally under `experiments/results/`:

```bash
python -m tradingagents.alpaca_daytrader experiment-list
python -m tradingagents.alpaca_daytrader experiment-show <id>
```

## Troubleshooting

- If the focus list is empty, inspect `reports/universe/YYYY-MM-DD.md`.
- If no orders are planned, inspect the no-trade section in the quant report.
- If execution is refused, check `ALPACA_PAPER=true`, credentials, market
  hours, data quality warnings, and RiskBox reason codes.
- If Git Bash cannot find the package, rerun `pip install -e .` from the repo
  root.
