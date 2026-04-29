from pathlib import Path

from tradingagents.alpaca_daytrader.config import DayTraderConfig
from tradingagents.alpaca_daytrader.runtime import mode_by_name
from tradingagents.alpaca_daytrader.safety import SafetyPolicy
from tradingagents.alpaca_daytrader.system_orchestrator import TradingSystemOrchestrator


def test_runtime_modes_block_submission_in_dry_run(tmp_path: Path):
    config = DayTraderConfig(
        api_key=None,
        secret_key=None,
        log_root=tmp_path / "logs",
        report_root=tmp_path / "reports",
    )
    mode = mode_by_name("dry_run")

    decision = SafetyPolicy().validate(mode, config)

    assert decision.allowed
    assert not mode.can_submit_orders


def test_paper_execute_requires_credentials(tmp_path: Path):
    config = DayTraderConfig(
        api_key=None,
        secret_key=None,
        log_root=tmp_path / "logs",
        report_root=tmp_path / "reports",
    )

    decision = SafetyPolicy().validate(mode_by_name("paper_execute"), config)

    assert not decision.allowed
    assert "Alpaca credentials required for execution" in decision.reasons


def test_system_orchestrator_dry_run_creates_canonical_report(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("UNIVERSE_CACHE_DIR", str(tmp_path / "universe"))
    monkeypatch.setenv("UNIVERSE_MAX_SCAN_SYMBOLS", "10")
    monkeypatch.setenv("UNIVERSE_MAX_FOCUS_SYMBOLS", "5")
    config = DayTraderConfig(
        api_key=None,
        secret_key=None,
        log_root=tmp_path / "logs",
        report_root=tmp_path / "reports",
    )

    result = TradingSystemOrchestrator(config).run_once(mode_by_name("dry_run"))

    assert result.runtime_mode == "dry_run"
    assert not result.execution_allowed
    assert result.quant_report is not None
    assert result.report_markdown is not None
    assert Path(result.report_markdown).exists()


def test_semantic_veto_prevents_execution_when_market_closed(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("UNIVERSE_CACHE_DIR", str(tmp_path / "universe"))
    config = DayTraderConfig(
        api_key=None,
        secret_key=None,
        log_root=tmp_path / "logs",
        report_root=tmp_path / "reports",
    )
    orchestrator = TradingSystemOrchestrator(config)

    result = orchestrator.run_once(mode_by_name("dry_run"))

    assert result.semantic_review is not None
    assert result.quant_report.execution_plan.dry_run
