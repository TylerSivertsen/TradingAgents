# Alpaca Daytrader

The Alpaca daytrader module provides a safe research loop for portfolio state,
market data, semantic-agent decisions, risk review, dry-run execution, and
Alpaca paper order submission.

## Commands

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

The quant extension adds dynamic universe scanning:

```bash
python -m tradingagents.alpaca_daytrader universe-scan
python -m tradingagents.alpaca_daytrader quant-once --dry-run
python -m tradingagents.alpaca_daytrader quant-once --review
python -m tradingagents.alpaca_daytrader quant-run --shadow
```
