from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Literal

from backend.config import load_config
from backend.data.data_sync import DataSync
from backend.db import get_session, get_system_meta, init_db, table_counts
from backend.engine.auction_runner import AuctionRunner
from backend.engine.daily_runner import DailyRunner
from backend.engine.intraday_runner import IntradayRunner
from backend.engine.trade_day_runner import TradeDayRunner
from backend.strategy.signal_eval_strategy import SignalEval


Mode = Literal["sync", "daily", "auction", "intraday", "trade_day", "detail", "eval", "status"]


def configure_logging(level: str) -> None:
    """Configure process logging from config."""
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO), format="%(asctime)s %(levelname)s %(message)s")


def print_status() -> None:
    """Print table row counts and selected system metadata."""
    with get_session() as session:
        counts = table_counts(session)
        meta = get_system_meta(session)

    print("System status")
    print("-------------")
    for table_name, row_count in counts.items():
        print(f"{table_name}: {row_count}")

    print("\nSystem meta")
    print("-----------")
    watched_keys = (
        "last_daily_update",
        "data_source_status",
        "degradation_log",
        "trade_day.last_phase",
        "trade_day.last_message",
        "trade_day.last_detail",
        "trade_day.last_run_at",
    )
    for key in watched_keys:
        print(f"{key}: {meta.get(key, '')}")


def run_mode(mode: Mode, days: int = 60, interval: int = 30, phase: str = "auto", daemon: bool = False) -> None:
    """Run the selected command mode."""
    logger = logging.getLogger(__name__)
    logger.info("run_mode started: %s", mode)
    init_db()
    if mode == "status":
        print_status()
        return
    if mode == "sync":
        result = DataSync().sync_all()
        if result.skipped:
            print("数据已是最新，跳过")
        print(
            "SyncResult("
            f"success_count={result.success_count}, "
            f"fail_count={result.fail_count}, "
            f"degradation_count={result.degradation_count}, "
            f"skipped={result.skipped}"
            ")"
        )
        return
    if mode == "daily":
        result = DailyRunner().run()
        print(result.terminal_report)
        print(f"\nOutput dir: {result.output_dir}")
        return
    if mode == "eval":
        results = SignalEval().evaluate(days)
        print_eval_results(results, days)
        return
    if mode == "auction":
        result = AuctionRunner().run()
        print_auction_result(result)
        return
    if mode == "intraday":
        IntradayRunner().run_loop(interval)
        return
    if mode == "trade_day":
        runner = TradeDayRunner()
        if daemon:
            runner.run_daemon(interval)
            return
        result = runner.run_phase(phase)  # type: ignore[arg-type]
        print_trade_day_result(result)
        return
    logger.info("mode %s is not implemented in Task 00", mode)
    print(f"mode {mode} initialized database; implementation will be added in later tasks")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="主线龙头交易系统")
    parser.add_argument("--mode", choices=["sync", "daily", "auction", "intraday", "trade_day", "detail", "eval", "status"], default="status")
    parser.add_argument("-s", "--symbol", default="", help="symbol for detail mode")
    parser.add_argument("-i", "--interval", type=int, default=30, help="intraday loop interval in seconds")
    parser.add_argument("--days", type=int, default=60, help="evaluation window in days")
    parser.add_argument("--phase", choices=["auto", "opening", "intraday", "review"], default="auto", help="trade_day phase")
    parser.add_argument("--daemon", action="store_true", help="keep trade_day scheduler running")
    return parser.parse_args()


def print_mainlines(results: list[object]) -> None:
    """Print a compact Top mainline table for Phase 2 daily mode."""
    print("\nTop mainlines")
    print("-------------")
    if not results:
        print("No mainline results")
        return
    print("rank | sector | score | status")
    for result in results:
        print(f"{result.rank} | {result.sector_name} | {result.mainline_score:.2f} | {result.mainline_status}")


def print_roles(role_results: dict[str, object]) -> None:
    """Print compact role assignment output."""
    print("\nRole assignments")
    print("----------------")
    if not role_results:
        print("No role assignments")
        return
    print("symbol | role | sector | score")
    for result in sorted(role_results.values(), key=lambda item: (item.sector_name, item.role, -item.score)):
        print(f"{result.symbol} | {result.role} | {result.sector_name} | {result.score:.2f}")


def print_eval_results(results: list[object], days: int) -> None:
    """Print signal evaluation summary."""
    print(f"Signal evaluation: last {days} days")
    print("--------------------------------")
    if not results:
        print("历史买入信号不足（少于 5 条），已生成空报告 output/signal_eval_report.csv")
        print_stage_eval_results()
        return
    print("strategy | total | win1 | win3 | win5 | avg1 | avg3 | avg5 | mdd5 | stop")
    for item in results:
        print(
            f"{item.strategy_name} | {item.total_signals} | "
            f"{item.win_rate_1d:.2%} | {item.win_rate_3d:.2%} | {item.win_rate_5d:.2%} | "
            f"{item.avg_return_1d:.2%} | {item.avg_return_3d:.2%} | {item.avg_return_5d:.2%} | "
            f"{item.max_drawdown_5d:.2%} | {item.hit_stop_loss_rate:.2%}"
        )
    print_stage_eval_results()


def print_stage_eval_results() -> None:
    """Print stage-grouped signal evaluation when available."""
    path = Path("output") / "signal_eval_by_stage.csv"
    if not path.exists():
        return
    import csv

    with path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    if not rows:
        print("\n信号验证（按阶段）")
        print("----------------")
        print("暂无可评估阶段样本，已生成 output/signal_eval_by_stage.csv")
        return
    print("\n信号验证（按阶段）")
    print("----------------")
    print("stage | total | blocked | win1 | win3 | win5 | avg5 | mdd5")
    for row in rows:
        print(
            f"{row['stage']} | {row['total_signals']} | {row['blocked_signals']} | "
            f"{float(row['win_rate_1d']):.2%} | {float(row['win_rate_3d']):.2%} | {float(row['win_rate_5d']):.2%} | "
            f"{float(row['avg_return_5d']):.2%} | {float(row['max_drawdown_5d']):.2%}"
        )
    blocked = [row for row in rows if int(float(row["blocked_signals"])) > 0]
    if blocked:
        total_blocked = sum(int(float(row["blocked_signals"])) for row in blocked)
        avg5 = sum(float(row["avg_return_5d"]) * int(float(row["blocked_signals"])) for row in blocked) / max(total_blocked, 1)
        mdd5 = min(float(row["max_drawdown_5d"]) for row in blocked)
        print("\n门控效果")
        print("--------")
        print(f"被阶段拦截的信号假设表现：平均 5 日收益 {avg5:.2%}，最大回撤 {mdd5:.2%}")


def print_auction_result(result: object) -> None:
    """Print auction runner summary."""
    print("Auction run")
    print("-----------")
    print(result.message)
    print(f"snapshot_count: {result.snapshot_count}")
    print(f"skipped: {result.skipped}")
    if not result.signals:
        return
    print("symbol | confidence | action_text")
    for signal in result.signals:
        print(f"{signal.symbol} | {signal.confidence:.2f} | {signal.action_text}")


def print_trade_day_result(result: object) -> None:
    """Print compact trade-day coordinator output."""
    print("Trade day runner")
    print("----------------")
    print(f"phase: {result.phase}")
    print(f"skipped: {result.skipped}")
    print(result.message)
    if result.detail:
        print(result.detail)


def main() -> None:
    """Program entrypoint."""
    config = load_config()
    configure_logging(str(config["system"]["log_level"]))
    args = parse_args()
    run_mode(args.mode, args.days, args.interval, args.phase, args.daemon)


if __name__ == "__main__":
    main()
