# Test Coverage Audit

## Findings

- Focused tests exist for Alpaca daytrader, ORIA quant, and market auditing.
- Tests use mock/dry-run adapters and do not require real Alpaca credentials.
- Existing broader TradingAgents tests remain.
- Git Bash focused suite has passed locally.

## Gaps

- Docker command smoke tests are documented but not automated in pytest.
- Semantic veto integration needs a test.
- Runtime mode safety needs explicit tests.
- Canonical orchestrator dry-run integration needs a test.

## Repair Direction

- Add tests for runtime modes, system orchestrator dry-run, semantic veto, and dry-run no-submit safety.
