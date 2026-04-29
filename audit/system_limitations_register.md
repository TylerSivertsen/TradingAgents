# System Limitations Register

## LIM-001

Category: docker/runtime  
Severity: critical  
Description: Docker Compose points at the original `tradingagents` entrypoint instead of Alpaca daytrader runtime.  
Why it matters: Requested Docker commands cannot work reliably.  
Current behavior: `tradingagents` CLI starts original app.  
Desired behavior: `docker compose run --rm trader diagnostics` routes to Alpaca daytrader.  
Affected files: `Dockerfile`, `docker-compose.yml`  
Repair plan: Update entrypoint and Compose services.  
Test plan: Smoke CLI locally and document Docker commands.  
Status: repaired

## LIM-002

Category: risk controls  
Severity: critical  
Description: Runtime capabilities are implicit booleans rather than a strict mode model.  
Why it matters: Execution permission must be explicit and auditable.  
Current behavior: `dry_run = not args.execute`.  
Desired behavior: All execution checks use `RuntimeMode`.  
Affected files: `__main__.py`, quant orchestrator  
Repair plan: Add `runtime.py`, `safety.py`, canonical orchestrator.  
Test plan: Runtime mode and dry-run no-submit tests.  
Status: repaired

## LIM-003

Category: agent integration  
Severity: high  
Description: Semantic review is structured but not a formal execution gate.  
Why it matters: Unsafe semantic/quant disagreement should stop execution.  
Current behavior: Review commentary is logged and reported.  
Desired behavior: `SemanticReview.veto` blocks execution and produces no-trade.  
Affected files: `quant/semantic_review.py`, canonical orchestrator  
Repair plan: Add semantic schema and gate.  
Test plan: Mock veto stops execution.  
Status: repaired

## LIM-004

Category: reporting  
Severity: high  
Description: Reports are split by subsystem; no single canonical run report exists.  
Why it matters: Orders must be traceable to one decision record.  
Current behavior: `reports/quant`, `reports/universe`, JSONL logs.  
Desired behavior: `reports/runs/YYYY-MM-DD/<timestamp>_run.{md,json}`.  
Affected files: reporting modules  
Repair plan: Add run reporter.  
Test plan: Dry-run creates run report.  
Status: repaired

## LIM-005

Category: alpaca integration  
Severity: medium  
Description: Alpaca calls lack retry/timeout wrappers and open-order reconciliation.  
Why it matters: API failures should degrade safely.  
Current behavior: Exceptions can bubble.  
Desired behavior: Diagnostics/no-trade on unavailable Alpaca state.  
Affected files: `alpaca_adapter.py`  
Repair plan: Future adapter hardening.  
Test plan: Mock adapter failures.  
Status: open

## LIM-006

Category: universe discovery  
Severity: medium  
Description: Event/news/halt filters are scaffolds without real feeds.  
Why it matters: Event risk may be underestimated.  
Current behavior: Fallback scores event risk as safe.  
Desired behavior: Plug in real event providers when available.  
Affected files: `risk/events.py`, `universe/filters.py`  
Repair plan: Future provider integration.  
Test plan: Mock event blocks symbol.  
Status: open

## LIM-007

Category: configuration  
Severity: medium  
Description: Config file merge is partial; env/defaults dominate.  
Why it matters: Operators expect config file support.  
Current behavior: `configs/quant.toml` is documentation-like.  
Desired behavior: CLI flags > env vars > config file > defaults.  
Affected files: config loaders  
Repair plan: Add canonical config loader in a future pass.  
Test plan: Config precedence tests.  
Status: open

## LIM-008

Category: testing  
Severity: medium  
Description: Docker smoke tests are not automated.  
Why it matters: Docker regressions can slip.  
Current behavior: Local Git Bash tests pass.  
Desired behavior: CI or script exercises Docker commands.  
Affected files: tests/docker scripts  
Repair plan: Add documented Docker commands now; automate later.  
Test plan: Manual Docker smoke.  
Status: open
