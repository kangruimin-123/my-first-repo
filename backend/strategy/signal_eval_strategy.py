from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from backend.config import load_config
from backend.db import DailyKline, StageAnalysis, StrategySignal, get_session, init_db


SessionContextFactory = Callable[[], AbstractContextManager[Session]]


@dataclass(frozen=True)
class EvalResult:
    strategy_name: str
    total_signals: int
    win_rate_1d: float
    win_rate_3d: float
    win_rate_5d: float
    avg_return_1d: float
    avg_return_3d: float
    avg_return_5d: float
    max_drawdown_5d: float
    hit_stop_loss_rate: float


@dataclass(frozen=True)
class SignalOutcome:
    strategy_name: str
    symbol: str
    stage: str
    action: str
    blocked_by_stage: bool
    return_1d: float | None
    return_3d: float | None
    return_5d: float | None
    max_drawdown_5d: float | None
    hit_stop_loss: bool


class SignalEval:
    """Evaluate historical buy signals against subsequent daily kline data."""

    def __init__(self, config: dict[str, Any] | None = None, session_factory: SessionContextFactory | None = None) -> None:
        self.config = config or load_config()
        if session_factory is None:
            engine = init_db(db_path=str(self.config["system"]["db_path"]))
            self.session_factory = lambda: get_session(engine)
        else:
            self.session_factory = session_factory

    def evaluate(self, days: int = 60) -> list[EvalResult]:
        """Evaluate recent buy signals and write output/signal_eval_report.csv."""
        buy_signals = self._load_signals(days, actions=["buy"])
        buy_outcomes = [outcome for signal in buy_signals if (outcome := self._evaluate_signal(signal)) is not None]
        blocked_signals = self._load_stage_blocked_signals(days)
        blocked_outcomes = [outcome for signal in blocked_signals if (outcome := self._evaluate_signal(signal)) is not None]
        all_stage_outcomes = buy_outcomes + blocked_outcomes
        self._write_stage_report(self._aggregate_by_stage(all_stage_outcomes))
        if len(buy_outcomes) < 5:
            self._write_report([])
            return []
        grouped: dict[str, list[SignalOutcome]] = defaultdict(list)
        for outcome in buy_outcomes:
            grouped[outcome.strategy_name].append(outcome)
        results = [self._aggregate(strategy_name, items) for strategy_name, items in sorted(grouped.items())]
        self._write_report(results)
        return results

    def _load_signals(self, days: int, actions: list[str]) -> list[StrategySignal]:
        start_date = datetime.now(UTC).date() - timedelta(days=days)
        with self.session_factory() as session:
            return (
                session.query(StrategySignal)
                .filter(StrategySignal.date >= start_date, StrategySignal.action.in_(actions))
                .order_by(StrategySignal.date, StrategySignal.strategy_name)
                .all()
            )

    def _load_stage_blocked_signals(self, days: int) -> list[StrategySignal]:
        return [signal for signal in self._load_signals(days, actions=["deny"]) if self._blocked_by_stage(signal)]

    def _evaluate_signal(self, signal: StrategySignal) -> SignalOutcome | None:
        with self.session_factory() as session:
            current = session.query(DailyKline).filter(DailyKline.symbol == signal.symbol, DailyKline.date == signal.date).one_or_none()
            future_rows = (
                session.query(DailyKline)
                .filter(DailyKline.symbol == signal.symbol, DailyKline.date > signal.date)
                .order_by(DailyKline.date)
                .limit(5)
                .all()
            )
        if current is None or not future_rows:
            return None
        close = float(current.close)
        stop_loss = self._stop_loss_from_json(signal.signal_json)
        stage = self._stage_for_signal(signal)

        def ret(day_index: int) -> float | None:
            if len(future_rows) < day_index:
                return None
            return (float(future_rows[day_index - 1].close) - close) / close

        lows = [float(row.low) for row in future_rows[:5]]
        max_drawdown = (min(lows) - close) / close if lows else None
        hit_stop = bool(stop_loss > 0 and any(float(row.low) <= stop_loss for row in future_rows[:5]))
        return SignalOutcome(
            strategy_name=signal.strategy_name,
            symbol=signal.symbol,
            stage=stage,
            action=signal.action,
            blocked_by_stage=signal.action == "deny" and self._blocked_by_stage(signal),
            return_1d=ret(1),
            return_3d=ret(3),
            return_5d=ret(5),
            max_drawdown_5d=max_drawdown,
            hit_stop_loss=hit_stop,
        )

    def _aggregate(self, strategy_name: str, outcomes: list[SignalOutcome]) -> EvalResult:
        return EvalResult(
            strategy_name=strategy_name,
            total_signals=len(outcomes),
            win_rate_1d=self._win_rate([item.return_1d for item in outcomes]),
            win_rate_3d=self._win_rate([item.return_3d for item in outcomes]),
            win_rate_5d=self._win_rate([item.return_5d for item in outcomes]),
            avg_return_1d=self._average([item.return_1d for item in outcomes]),
            avg_return_3d=self._average([item.return_3d for item in outcomes]),
            avg_return_5d=self._average([item.return_5d for item in outcomes]),
            max_drawdown_5d=self._average([item.max_drawdown_5d for item in outcomes]),
            hit_stop_loss_rate=sum(1 for item in outcomes if item.hit_stop_loss) / len(outcomes),
        )

    def _aggregate_by_stage(self, outcomes: list[SignalOutcome]) -> list[dict[str, Any]]:
        grouped: dict[str, list[SignalOutcome]] = defaultdict(list)
        for outcome in outcomes:
            stage_key = f"{outcome.stage or 'unknown'}(拦截)" if outcome.blocked_by_stage else outcome.stage or "unknown"
            grouped[stage_key].append(outcome)
        rows: list[dict[str, Any]] = []
        for stage, items in sorted(grouped.items()):
            rows.append(
                {
                    "stage": stage,
                    "total_signals": len(items),
                    "blocked_signals": sum(1 for item in items if item.blocked_by_stage),
                    "win_rate_1d": self._win_rate([item.return_1d for item in items]),
                    "win_rate_3d": self._win_rate([item.return_3d for item in items]),
                    "win_rate_5d": self._win_rate([item.return_5d for item in items]),
                    "avg_return_1d": self._average([item.return_1d for item in items]),
                    "avg_return_3d": self._average([item.return_3d for item in items]),
                    "avg_return_5d": self._average([item.return_5d for item in items]),
                    "max_drawdown_5d": self._average([item.max_drawdown_5d for item in items]),
                }
            )
        return rows

    def _win_rate(self, returns: list[float | None]) -> float:
        valid = [item for item in returns if item is not None]
        if not valid:
            return 0.0
        return sum(1 for item in valid if item > 0) / len(valid)

    def _average(self, values: list[float | None]) -> float:
        valid = [item for item in values if item is not None]
        if not valid:
            return 0.0
        return sum(valid) / len(valid)

    def _stop_loss_from_json(self, signal_json: str) -> float:
        if not signal_json:
            return 0.0
        try:
            payload = json.loads(signal_json)
        except json.JSONDecodeError:
            return 0.0
        return float(payload.get("stop_loss_price") or payload.get("stop_loss") or 0.0)

    def _stage_for_signal(self, signal: StrategySignal) -> str:
        stage_from_json = self._stage_from_json(signal.signal_json)
        if stage_from_json:
            return stage_from_json
        with self.session_factory() as session:
            row = session.query(StageAnalysis).filter(StageAnalysis.symbol == signal.symbol, StageAnalysis.date == signal.date).one_or_none()
        return str(row.stage) if row is not None else "unknown"

    def _stage_from_json(self, signal_json: str) -> str:
        if not signal_json:
            return ""
        try:
            payload = json.loads(signal_json)
        except json.JSONDecodeError:
            return ""
        return str(payload.get("stage") or "")

    def _blocked_by_stage(self, signal: StrategySignal) -> bool:
        payload_text = signal.signal_json or ""
        if "阶段" in payload_text:
            return True
        try:
            payload = json.loads(payload_text) if payload_text else {}
        except json.JSONDecodeError:
            payload = {}
        reason = str(payload.get("reason", "")) + str(payload.get("action_text", "")) + " ".join(payload.get("risk_warnings", []))
        return "阶段" in reason

    def _write_report(self, results: list[EvalResult]) -> Path:
        output_dir = Path("output")
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "signal_eval_report.csv"
        frame = pd.DataFrame([result.__dict__ for result in results])
        if frame.empty:
            frame = pd.DataFrame(
                columns=[
                    "strategy_name",
                    "total_signals",
                    "win_rate_1d",
                    "win_rate_3d",
                    "win_rate_5d",
                    "avg_return_1d",
                    "avg_return_3d",
                    "avg_return_5d",
                    "max_drawdown_5d",
                    "hit_stop_loss_rate",
                ]
            )
        frame.to_csv(path, index=False, encoding="utf-8")
        return path

    def _write_stage_report(self, rows: list[dict[str, Any]]) -> Path:
        output_dir = Path("output")
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "signal_eval_by_stage.csv"
        columns = [
            "stage",
            "total_signals",
            "blocked_signals",
            "win_rate_1d",
            "win_rate_3d",
            "win_rate_5d",
            "avg_return_1d",
            "avg_return_3d",
            "avg_return_5d",
            "max_drawdown_5d",
        ]
        frame = pd.DataFrame(rows, columns=columns)
        frame.to_csv(path, index=False, encoding="utf-8")
        return path
