"""Universe scan reporting."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from tradingagents.alpaca_daytrader.universe.schemas import FocusList, MarketScanResult, UniverseSelectionResult


class UniverseReporter:
    def __init__(self, report_root: Path = Path("reports")) -> None:
        self.root = report_root / "universe"
        self.root.mkdir(parents=True, exist_ok=True)

    def write(
        self,
        selection: UniverseSelectionResult,
        scan: MarketScanResult,
        focus: FocusList,
    ) -> Path:
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        path = self.root / f"{day}.md"
        breakdown: dict[str, int] = {}
        for reasons in scan.rejected.values():
            for reason in reasons:
                breakdown[reason] = breakdown.get(reason, 0) + 1
        top = sorted(scan.candidates, key=lambda item: (-item.total_score, item.symbol))[:25]
        lines = [
            "# Market Universe Report",
            "",
            f"- Assets discovered: {selection.discovered_count}",
            f"- Symbols scanned: {scan.scanned_count}",
            f"- Symbols rejected: {scan.rejected_count}",
            f"- Cache hit: {selection.cache_hit}",
            "",
            "## Rejection Breakdown",
        ]
        lines.extend([f"- `{key}`: {value}" for key, value in sorted(breakdown.items())] or ["None"])
        lines.extend(["", "## Top Ranked Candidates"])
        for candidate in top:
            lines.append(f"- `{candidate.symbol}` score={candidate.total_score:.3f} valid={candidate.is_valid} reasons={candidate.rejection_reasons}")
        lines.extend(["", "## Final Focus List", ", ".join(focus.symbols) if focus.symbols else "None"])
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def latest(self) -> Path | None:
        reports = sorted(self.root.glob("*.md"))
        return reports[-1] if reports else None
