"""Command line entrypoint for python -m tradingagents.alpaca_daytrader."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, replace

from tradingagents.alpaca_daytrader.config import load_config
from tradingagents.alpaca_daytrader.orchestrator import DayTraderOrchestrator
from tradingagents.alpaca_daytrader.quant.backtest import QuantBacktester
from tradingagents.alpaca_daytrader.quant.config import load_quant_config
from tradingagents.alpaca_daytrader.quant.orchestrator import QuantOrchestrator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Alpaca orchestrated daytrader")
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
        mode.add_argument("--execute", action="store_true")
        if name == "quant-run":
            command.add_argument("--iterations", type=int, default=None)
    backtest = subparsers.add_parser("quant-backtest")
    backtest.add_argument("--symbols", default=None)
    backtest.add_argument("--start", default=None)
    backtest.add_argument("--end", default=None)
    backtest.add_argument("--periods", type=int, default=180)
    subparsers.add_parser("report")
    subparsers.add_parser("quant-report")
    subparsers.add_parser("quant-diagnostics")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = load_config()
    quant_config = load_quant_config(config)
    orchestrator = DayTraderOrchestrator(config)
    quant_orchestrator = QuantOrchestrator(config, quant_config)
    if args.command == "report":
        report = orchestrator.report()
        print(report if report else "No reports found.")
        return
    if args.command == "quant-report":
        report = quant_orchestrator.latest_report()
        print(report if report else "No quant reports found.")
        return
    if args.command == "quant-diagnostics":
        print(json.dumps(quant_orchestrator.diagnostics(), indent=2))
        return
    if args.command == "quant-backtest":
        if args.symbols:
            quant_orchestrator.quant_config = replace(
                quant_orchestrator.quant_config,
                symbols=[s.strip().upper() for s in args.symbols.split(",") if s.strip()],
            )
        metrics = QuantBacktester().run(quant_orchestrator, periods=args.periods)
        path = quant_orchestrator.logger.write_backtest_report(metrics)
        print(json.dumps({"metrics": metrics, "report": str(path)}, indent=2))
        return
    dry_run = not args.execute
    if args.command == "quant-once":
        result = quant_orchestrator.once(dry_run=dry_run)
        print(json.dumps(asdict(result), indent=2))
        return
    if args.command == "quant-run":
        quant_orchestrator.run(dry_run=dry_run, iterations=args.iterations)
        return
    if args.command == "once":
        result = orchestrator.once(dry_run=dry_run)
        print(json.dumps(asdict(result), indent=2))
        return
    orchestrator.run(dry_run=dry_run, iterations=args.iterations)


if __name__ == "__main__":
    main()
