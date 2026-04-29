"""Dynamic universe discovery from Alpaca assets with cache fallback."""

from __future__ import annotations

from tradingagents.alpaca_daytrader.universe.cache import UniverseCache
from tradingagents.alpaca_daytrader.universe.schemas import (
    AssetMetadata,
    TradableUniverse,
    UniverseConfig,
    UniverseSelectionResult,
)


class UniverseDiscoveryEngine:
    """Discovers tradable assets without requiring a hardcoded ticker list."""

    FALLBACK_SYMBOLS = [
        "SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "XLE", "XLV", "XLY", "XLI",
        "SMH", "TLT", "GLD", "AAPL", "MSFT", "NVDA", "AMD", "META", "AMZN", "TSLA",
        "GOOGL", "JPM", "BAC", "AVGO", "NFLX", "COST", "CRM", "ORCL", "INTC", "UBER",
    ]

    def discover(
        self,
        market_data_adapter: object,
        alpaca_adapter: object,
        config: UniverseConfig,
    ) -> UniverseSelectionResult:
        cache = UniverseCache(config.cache_dir)
        cache_hit = False
        assets = cache.load() if config.refresh_assets_daily else None
        if assets is not None:
            cache_hit = True
        else:
            assets = self._load_assets(alpaca_adapter, config)
            cache.save(assets)
        rejected: dict[str, list[str]] = {}
        selected: list[AssetMetadata] = []
        seed = {symbol.upper() for symbol in config.seed_symbols}
        excluded = {symbol.upper() for symbol in config.excluded_symbols}
        for asset in assets:
            reasons = self._asset_rejections(asset, config, excluded)
            if reasons and asset.symbol not in seed:
                rejected[asset.symbol] = reasons
                continue
            selected.append(asset)
            if len(selected) >= config.max_scan_symbols:
                break
        for symbol in seed:
            if symbol not in {asset.symbol for asset in selected} and symbol not in excluded:
                selected.append(AssetMetadata(symbol=symbol, name="seed", diagnostics={"source": "seed"}))
        universe = TradableUniverse(selected, source=config.source)
        return UniverseSelectionResult(
            universe=universe,
            discovered_count=len(assets),
            selected_count=len(selected),
            rejected=rejected,
            cache_hit=cache_hit,
            diagnostics={"max_scan_symbols": config.max_scan_symbols},
        )

    def _load_assets(self, adapter: object, config: UniverseConfig) -> list[AssetMetadata]:
        client = getattr(adapter, "trading_client", None)
        if client is not None and hasattr(client, "get_all_assets"):
            try:
                return [self._from_alpaca(asset) for asset in client.get_all_assets()]
            except Exception:
                pass
        return [AssetMetadata(symbol=symbol, name="fallback") for symbol in self.FALLBACK_SYMBOLS]

    def _from_alpaca(self, asset: object) -> AssetMetadata:
        return AssetMetadata(
            symbol=str(getattr(asset, "symbol", "")).upper(),
            name=str(getattr(asset, "name", "")),
            asset_class=str(getattr(asset, "asset_class", "us_equity")),
            exchange=str(getattr(asset, "exchange", "")),
            status=str(getattr(asset, "status", "active")),
            tradable=bool(getattr(asset, "tradable", True)),
            marginable=bool(getattr(asset, "marginable", False)),
            fractionable=bool(getattr(asset, "fractionable", False)),
            shortable=bool(getattr(asset, "shortable", False)),
            easy_to_borrow=bool(getattr(asset, "easy_to_borrow", False)),
        )

    def _asset_rejections(self, asset: AssetMetadata, config: UniverseConfig, excluded: set[str]) -> list[str]:
        reasons: list[str] = []
        if asset.symbol in excluded:
            reasons.append("excluded")
        if config.require_tradable and not asset.tradable:
            reasons.append("not_tradable")
        if config.require_marginable and not asset.marginable:
            reasons.append("not_marginable")
        if asset.status.lower() != "active":
            reasons.append("inactive")
        if not config.allow_fractional_only and asset.fractionable and not asset.tradable:
            reasons.append("fractional_only")
        return reasons
