"""Command line entrypoint for python -m tradingagents.alpaca_daytrader."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from tradingagents.alpaca_daytrader.config import load_config
from tradingagents.alpaca_daytrader.experiments import ExperimentRegistry
from tradingagents.alpaca_daytrader.orchestrator import DayTraderOrchestrator
from tradingagents.alpaca_daytrader.risk.circuit_breakers import CircuitBreakerManager
from tradingagents.alpaca_daytrader.runtime import mode_by_name
from tradingagents.alpaca_daytrader.system_orchestrator import TradingSystemOrchestrator
from tradingagents.alpaca_daytrader.tui.app import run_tui
from tradingagents.alpaca_daytrader.universe.reporting import UniverseReporter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TradingAgents Alpaca daytrader runtime")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "once"):
        command = subparsers.add_parser(name)
        mode = command.add_mutually_exclusive_group()
        mode.add_argument("--dry-run", action="store_true", default=True)
        mode.add_argument("--execute", action="store_true")
        if name == "run":
            command.add_argument("--iterations", type=int, default=None)
    for name in ("quant-run", "quant-once"):
        command = subparsers.add_parser(name)
        mode = command.add_mutually_exclusive_group()
        mode.add_argument("--dry-run", action="store_true", default=True)
        mode.add_argument("--review", action="store_true")
        mode.add_argument("--execute", action="store_true")
        if name == "quant-run":
            mode.add_argument("--shadow", action="store_true")
            command.add_argument("--iterations", type=int, default=None)
    backtest = subparsers.add_parser("quant-backtest")
    backtest.add_argument("--symbols", default=None)
    backtest.add_argument("--start", default=None)
    backtest.add_argument("--end", default=None)
    backtest.add_argument("--periods", type=int, default=180)
    walk = subparsers.add_parser("quant-walkforward")
    walk.add_argument("--start", default=None)
    walk.add_argument("--end", default=None)
    walk.add_argument("--train-days", type=int, default=60)
    walk.add_argument("--test-days", type=int, default=10)
    subparsers.add_parser("diagnostics")
    subparsers.add_parser("dashboard")
    subparsers.add_parser("tui")
    subparsers.add_parser("test")
    subparsers.add_parser("report")
    subparsers.add_parser("quant-report")
    subparsers.add_parser("quant-diagnostics")
    subparsers.add_parser("universe-scan")
    subparsers.add_parser("universe-report")
    subparsers.add_parser("kill")
    subparsers.add_parser("cancel-all")
    flatten = subparsers.add_parser("flatten")
    flatten.add_argument("--paper-only", action="store_true", default=True)
    subparsers.add_parser("experiment-list")
    show = subparsers.add_parser("experiment-show")
    show.add_argument("experiment_id")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = load_config()
    system = TradingSystemOrchestrator(config)
    registry = ExperimentRegistry()
    if args.command in {"diagnostics", "quant-diagnostics"}:
        print(json.dumps(system.run_diagnostics(), indent=2, default=str))
        return
    if args.command in {"dashboard", "tui"}:
        run_tui()
        return
    if args.command == "test":
        raise SystemExit(system.run_tests())
    if args.command == "universe-scan":
        print(json.dumps(system.run_universe_scan(), indent=2, default=str))
        return
    if args.command == "universe-report":
        report = UniverseReporter(config.report_root).latest()
        print(report if report else "No universe reports found.")
        return
    if args.command == "kill":
        print(json.dumps(system.emergency_stop(), indent=2, default=str))
        return
    if args.command == "cancel-all":
        print(CircuitBreakerManager().cancel_all(None))
        return
    if args.command == "flatten":
        print(CircuitBreakerManager().flatten(None, paper_only=args.paper_only))
        return
    if args.command == "experiment-list":
        print(json.dumps(registry.list(), indent=2, default=str))
        return
    if args.command == "experiment-show":
        print(json.dumps(registry.show(args.experiment_id) or {"error": "experiment not found"}, indent=2, default=str))
        return
    if args.command == "quant-report":
        from tradingagents.alpaca_daytrader.quant.orchestrator import QuantOrchestrator
        from tradingagents.alpaca_daytrader.quant.config import load_quant_config
        from tradingagents.alpaca_daytrader.universe.config import load_universe_config

        report = QuantOrchestrator(config, load_quant_config(config), universe_config=load_universe_config()).latest_report()
        print(report if report else "No quant reports found.")
        return
    if args.command == "report":
        report = DayTraderOrchestrator(config).report()
        print(report if report else "No reports found.")
        return
    if args.command == "quant-backtest":
        symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()] if args.symbols else None
        print(json.dumps(system.run_backtest(periods=args.periods, symbols=symbols), indent=2, default=str))
        return
    if args.command == "quant-walkforward":
        print(json.dumps(system.run_walkforward(args.start, args.end, args.train_days, args.test_days), indent=2, default=str))
        return
    if args.command == "quant-once":
        mode = _quant_mode(args)
        result = system.run_once(mode)
        if mode.name == "review":
            _print_review(result)
            if input("Approve paper orders? [y/N] ").strip().lower() != "y":
                print("Review declined; no orders submitted.")
                return
            result = system.run_once(mode_by_name("paper_execute"))
        print(json.dumps(_run_summary(result), indent=2, default=str))
        return
    if args.command == "quant-run":
        mode = mode_by_name("shadow") if args.shadow else _quant_mode(args)
        system.run_loop(mode, iterations=args.iterations)
        return
    dry_run = not getattr(args, "execute", False)
    if args.command == "once":
        print(json.dumps(asdict(DayTraderOrchestrator(config).once(dry_run=dry_run)), indent=2, default=str))
        return
    DayTraderOrchestrator(config).run(dry_run=dry_run, iterations=args.iterations)


def _quant_mode(args: argparse.Namespace):
    if getattr(args, "review", False):
        return mode_by_name("review")
    if getattr(args, "execute", False):
        return mode_by_name("paper_execute")
    return mode_by_name("dry_run")


def _print_review(result) -> None:
    quant = result.quant_report
    orders = getattr(getattr(quant, "execution_plan", None), "orders", []) if quant else []
    print("Recommended trades:")
    if not orders:
        print("No orders recommended. Hold cash / maintain current book.")
        return
    for idx, order in enumerate(orders, start=1):
        action = "Buy" if order.side == "buy" else "Sell"
        print(f"{idx}. {action} ${order.notional:.2f} {order.symbol} via {order.order_type}")


def _run_summary(result) -> dict:
    quant = result.quant_report
    return {
        "runtime_mode": result.runtime_mode,
        "execution_allowed": result.execution_allowed,
        "semantic_veto": getattr(result.semantic_review, "veto", None),
        "focus_symbols": getattr(getattr(quant, "focus_list", None), "symbols", []) if quant else [],
        "planned_orders": len(getattr(getattr(quant, "execution_plan", None), "orders", [])) if quant else 0,
        "no_trade_reasons": result.no_trade_reasons,
        "warnings": result.warnings,
        "report_markdown": result.report_markdown,
        "report_json": result.report_json,
    }


if __name__ == "__main__":
    main()
