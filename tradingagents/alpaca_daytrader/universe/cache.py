"""Local cache for universe metadata."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tradingagents.alpaca_daytrader.universe.schemas import AssetMetadata


class UniverseCache:
    def __init__(self, cache_dir: str) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.cache_dir / "assets.json"

    def load(self, max_age_hours: int = 24) -> list[AssetMetadata] | None:
        if not self.path.exists():
            return None
        stat = self.path.stat()
        age = datetime.now(timezone.utc) - datetime.fromtimestamp(stat.st_mtime, timezone.utc)
        if age > timedelta(hours=max_age_hours):
            return None
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return [AssetMetadata(**item) for item in payload]

    def save(self, assets: list[AssetMetadata]) -> None:
        self.path.write_text(json.dumps([asdict(asset) for asset in assets], indent=2), encoding="utf-8")
