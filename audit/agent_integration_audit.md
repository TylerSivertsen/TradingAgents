# Agent Integration Audit

## Findings

- Original semantic TradingAgents agents remain separate from Alpaca ORIA.
- The Alpaca daytrader has lightweight semantic-style agents in `agents.py` and structured quant review in `quant/semantic_review.py`.
- Semantic review is advisory and structured, but it does not yet produce a formal `SemanticReview` object with veto semantics.
- Quant output is deterministic and RiskBox-gated. Semantic agents do not directly submit orders.
- Current semantic review is used before final report generation, but not as a formal gate before execution.

## Risks

- Semantic and quant disagreement is not yet represented as a first-class veto condition.
- Some original semantic agents return free-form LLM outputs and are not adapted to the quant schemas.

## Repair Direction

- Add canonical `SemanticReview` schema and gate execution through it.
- Keep semantic agents in an audit/explain/veto role only.
- Preserve RiskBox as mandatory deterministic enforcement.
