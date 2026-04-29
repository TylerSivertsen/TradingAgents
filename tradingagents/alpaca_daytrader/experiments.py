"""Local experiment registry for reproducible research runs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ExperimentRegistry:
    def __init__(self, root: Path = Path("experiments/results")) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def register(self, payload: dict[str, Any]) -> Path:
        exp_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = self.root / f"{exp_id}.json"
        path.write_text(json.dumps({"id": exp_id, **payload}, indent=2), encoding="utf-8")
        return path

    def list(self) -> list[str]:
        return [path.stem for path in sorted(self.root.glob("*.json"))]

    def show(self, exp_id: str) -> dict[str, Any] | None:
        path = self.root / f"{exp_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
