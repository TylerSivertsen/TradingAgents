# Universe Scanner Audit

## Findings

- Universe discovery uses Alpaca assets when available and a fallback universe for dry-run/offline operation.
- Metadata is cached under `data/universe/assets.json`.
- Scan size and focus size are configurable by environment variables.
- Scanner computes data quality, liquidity, spread, volatility, momentum, mean reversion, breakout, event risk, and execution quality scores.
- Focus list includes current holdings and ranked valid candidates.
- Rejected symbols carry rejection reasons and are reported in Markdown.

## Limitations

- ETF/equity classification is simple and depends on Alpaca metadata when available.
- Paid quote data is not required; spread is currently a conservative fallback in dry-run.
- Cache invalidation is mtime-based and simple.
- Event risk is scaffolded but not connected to a real earnings/news/halt feed.

## Repair Direction

- Keep universe failures as no-trade, not crashes.
- Surface universe health in diagnostics and dashboard.
