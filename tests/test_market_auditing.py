from pathlib import Path

from tradingagents.alpaca_daytrader.config import DayTraderConfig
from tradingagents.alpaca_daytrader.data.validation import DataQualityValidator
from tradingagents.alpaca_daytrader.models import MarketBar, MarketSnapshot, PortfolioSnapshot
from tradingagents.alpaca_daytrader.quant.orchestrator import QuantOrchestrator
from tradingagents.alpaca_daytrader.quant.schemas import QuantConfig
from tradingagents.alpaca_daytrader.risk.circuit_breakers import CircuitBreakerManager
from tradingagents.alpaca_daytrader.universe.discovery import UniverseDiscoveryEngine
from tradingagents.alpaca_daytrader.universe.filters import FocusListManager, MarketScanner
from tradingagents.alpaca_daytrader.universe.schemas import AssetMetadata, UniverseConfig


def _bars(symbol: str, count: int = 120, price: float = 100.0, volume: float = 20_000) -> list[MarketBar]:
    return [
        MarketBar(
            symbol=symbol,
            timestamp=str(idx),
            open=price + idx * 0.05,
            high=price + idx * 0.05 + 1.0,
            low=price + idx * 0.05 - 1.0,
            close=price + idx * 0.05,
            volume=volume,
        )
        for idx in range(count)
    ]


class Adapter:
    def __init__(self, bars=None):
        self.bars = bars or {"AAA": _bars("AAA"), "BBB": _bars("BBB", price=50)}

    def get_portfolio(self):
        return PortfolioSnapshot(cash=100_000, portfolio_value=100_000, buying_power=100_000, positions={})

    def get_market_snapshot(self, symbols):
        return MarketSnapshot({symbol: self.bars.get(symbol, []) for symbol in symbols}, True)

    def submit_order(self, symbol, side, qty):
        raise AssertionError("dry-run should not submit")


def test_universe_discovery_uses_assets_filters_and_seeds(tmp_path: Path):
    config = UniverseConfig(
        cache_dir=str(tmp_path),
        seed_symbols=["SEED"],
        excluded_symbols=["BAD"],
        max_scan_symbols=10,
    )
    engine = UniverseDiscoveryEngine()
    engine._load_assets = lambda adapter, cfg: [
        AssetMetadata("AAA"),
        AssetMetadata("BAD"),
        AssetMetadata("HALT", status="inactive"),
    ]

    result = engine.discover(None, None, config)

    assert "AAA" in result.universe.symbols
    assert "SEED" in result.universe.symbols
    assert "BAD" in result.rejected
    assert "HALT" in result.rejected


def test_market_scanner_ranks_valid_symbols_and_focus_list_includes_holdings():
    config = UniverseConfig(
        max_focus_symbols=2,
        min_intraday_volume=1,
        min_avg_daily_volume=1,
        min_atr_pct=0,
    )
    universe = type("Universe", (), {"symbols": ["AAA", "BBB"]})()
    scan = MarketScanner().scan(universe, Adapter(), config)
    portfolio = type("Portfolio", (), {"positions": {"HELD": 5}})()
    focus = FocusListManager().build_focus_list(scan, portfolio, config)

    assert scan.scanned_count == 2
    assert scan.focus_symbols
    assert "HELD" in focus.symbols


def test_data_quality_validator_excludes_nan_negative_and_zero_volume():
    bars = [
        MarketBar("BAD", "1", 1, 1, 1, 100, 0),
        MarketBar("BAD", "1", 1, 1, 1, -1, 0),
    ]
    report = DataQualityValidator().validate_symbol_data("BAD", bars, None, UniverseConfig())

    assert report.action == "exclude_symbol"
    assert "invalid_price" in report.reasons


def test_quant_orchestrator_dynamic_universe_no_trade_on_bad_focus(tmp_path: Path):
    day = DayTraderConfig(None, None, log_root=tmp_path / "logs", report_root=tmp_path / "reports")
    quant = QuantConfig(symbols=[])
    universe = UniverseConfig(
        seed_symbols=[],
        max_scan_symbols=2,
        max_focus_symbols=2,
        min_intraday_volume=10_000_000,
        min_avg_daily_volume=10_000_000,
        min_atr_pct=0,
        cache_dir=str(tmp_path / "universe"),
    )
    report = QuantOrchestrator(day, quant, adapter=Adapter({"AAA": _bars("AAA", volume=1)}), universe_config=universe).once(dry_run=True)

    assert report.focus_list is not None
    assert report.no_trade.no_trade
    assert "universe scan found no valid candidates" in report.no_trade.reasons
    assert not report.execution_plan.orders


def test_circuit_breakers_trip_safely():
    state = CircuitBreakerManager().evaluate({"daily_loss_exceeded": True, "focus_list_empty": True})

    assert state.tripped
    assert "daily_loss_exceeded" in state.reasons
