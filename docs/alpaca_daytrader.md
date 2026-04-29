# Alpaca Orchestrated Daytrader

This module adds a research-only Alpaca paper-trading loop under
`tradingagents.alpaca_daytrader`. It analyzes a portfolio and recent market
bars, runs simple multi-agent decision stages, applies hard risk checks, logs
each action, and can submit approved paper orders through `alpaca-py`.

This is not financial advice. The default mode is dry-run.

## Configuration

Set credentials through environment variables. Do not commit real keys.

```bash
ALPACA_API_KEY=
ALPACA_SECRET_KEY=
ALPACA_PAPER=true
ALPACA_DAYTRADER_SYMBOLS=SPY,QQQ
```

Useful risk settings:

```bash
ALPACA_DAYTRADER_MAX_NOTIONAL=1000
ALPACA_DAYTRADER_MAX_EXPOSURE_PCT=0.20
ALPACA_DAYTRADER_MIN_CASH_RESERVE_PCT=0.05
```

`ALPACA_PAPER=false` is rejected. The integration initializes Alpaca execution
with `TradingClient(api_key, secret_key, paper=True)`.

## Commands

```bash
python -m tradingagents.alpaca_daytrader once --dry-run
python -m tradingagents.alpaca_daytrader run --dry-run
python -m tradingagents.alpaca_daytrader run --execute
python -m tradingagents.alpaca_daytrader report
```

`--dry-run` is the default. Use `--execute` only with Alpaca paper credentials.

## Agent Flow

- `PortfolioStateAgent` reads cash, buying power, and positions.
- `MarketDataAgent` fetches recent bars and market status.
- `TechnicalAnalysisAgent` computes fast and slow moving averages.
- `SentimentAgent` provides a neutral placeholder score.
- `StrategyAgent` proposes buy, sell, or hold decisions.
- `RiskManagerAgent` rejects trades if risk limits fail, the market is closed,
  data is missing, or funds/positions are insufficient.
- `ExecutionAgent` skips orders in dry-run and submits approved paper orders
  only in execute mode.
- `ReflectionAgent` summarizes the cycle.

## Output

Runtime output is written to:

- `logs/decisions/decisions.jsonl`
- `logs/orders/orders.jsonl`
- `logs/portfolio/portfolio.jsonl`
- `reports/alpaca_daytrader_*.json`

These directories are ignored by git because they contain local run history.
