from __future__ import annotations

import logging
import time as time_module
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Any, Literal
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from backend.config import load_config
from backend.db import SystemMeta, get_session, init_db
from backend.engine.auction_runner import AuctionRunner, AuctionRunResult
from backend.engine.daily_runner import DailyRunner, DailyRunResult
from backend.engine.intraday_runner import IntradayRunner, IntradayRunResult


logger = logging.getLogger(__name__)
SessionContextFactory = Callable[[], AbstractContextManager[Session]]
TradePhase = Literal["opening", "intraday", "review", "auto"]


@dataclass(frozen=True)
class TradeDayRunResult:
    phase: str
    skipped: bool
    message: str
    detail: str = ""


class TradeDayRunner:
    """Coordinate opening guidance, intraday monitor and post-market review."""

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        session_factory: SessionContextFactory | None = None,
        now_func: Callable[[], datetime] | None = None,
        auction_factory: Callable[[], AuctionRunner] | None = None,
        intraday_factory: Callable[[], IntradayRunner] | None = None,
        daily_factory: Callable[[], DailyRunner] | None = None,
    ) -> None:
        self.config = config or load_config()
        self.now_func = now_func or self._local_now
        if session_factory is None:
            engine = init_db(db_path=str(self.config["system"]["db_path"]))
            self.session_factory = lambda: get_session(engine)
        else:
            self.session_factory = session_factory
        self.auction_factory = auction_factory or (lambda: AuctionRunner(self.config, session_factory=self.session_factory))
        self.intraday_factory = intraday_factory or (
            lambda: IntradayRunner(self.config, session_factory=self.session_factory, now_func=self.now_func)
        )
        self.daily_factory = daily_factory or (lambda: DailyRunner(self.config, session_factory=self.session_factory))

    def run_phase(self, phase: TradePhase = "auto") -> TradeDayRunResult:
        selected_phase = self._phase_for_now() if phase == "auto" else phase
        if selected_phase == "opening":
            return self._run_opening()
        if selected_phase == "intraday":
            return self._run_intraday()
        if selected_phase == "review":
            return self._run_review()
        result = TradeDayRunResult("idle", True, "当前不在开盘指导、盘中监控或盘后复盘时段")
        self._write_phase_meta(result)
        return result

    def run_daemon(self, interval_seconds: int = 60) -> None:
        """Keep the coordinator alive and run eligible phases when their window arrives."""
        interval = max(10, interval_seconds)
        while True:
            result = self.run_pending_once()
            logger.info("trade_day daemon phase=%s skipped=%s message=%s", result.phase, result.skipped, result.message)
            time_module.sleep(interval)

    def run_pending_once(self) -> TradeDayRunResult:
        phase = self._phase_for_now()
        if phase == "idle":
            return self.run_phase("auto")
        if phase != "intraday" and self._already_ran_today(phase):
            result = TradeDayRunResult(phase, True, f"{phase} 今日已执行，跳过重复运行")
            self._write_phase_meta(result)
            return result
        return self.run_phase(phase)

    def _run_opening(self) -> TradeDayRunResult:
        result: AuctionRunResult = self.auction_factory().run()
        message = f"开盘指导完成：{result.message}"
        detail = f"snapshot_count={result.snapshot_count}; signals={len(result.signals)}"
        run_result = TradeDayRunResult("opening", result.skipped, message, detail)
        self._write_phase_meta(run_result)
        return run_result

    def _run_intraday(self) -> TradeDayRunResult:
        result: IntradayRunResult = self.intraday_factory().run_once()
        message = f"盘中监控完成：{result.message}"
        detail = f"snapshot_count={result.snapshot_count}; alerts={len(result.alerts)}"
        if result.alerts:
            detail += "; " + " | ".join(result.alerts[:5])
        run_result = TradeDayRunResult("intraday", result.skipped, message, detail)
        self._write_phase_meta(run_result)
        return run_result

    def _run_review(self) -> TradeDayRunResult:
        result: DailyRunResult = self.daily_factory().run()
        message = "盘后复盘完成：已更新日线、策略、机会雷达和明日关注池"
        detail = (
            f"focus={len(result.focus_pool)}; observation={len(result.observation_pool)}; "
            f"radar={len(result.radar_results)}; risk={len(result.risk_warnings)}; output={result.output_dir}"
        )
        run_result = TradeDayRunResult("review", result.sync_result.skipped, message, detail)
        self._write_phase_meta(run_result)
        return run_result

    def _phase_for_now(self) -> str:
        now = self.now_func().time()
        if time(9, 15) <= now < time(10, 0):
            return "opening"
        if time(10, 0) <= now <= time(11, 30) or time(13, 0) <= now < time(14, 50):
            return "intraday"
        if time(15, 10) <= now <= time(23, 0):
            return "review"
        return "idle"

    def _already_ran_today(self, phase: str) -> bool:
        key = f"trade_day.{phase}.last_date"
        with self.session_factory() as session:
            row = session.query(SystemMeta).filter_by(key=key).one_or_none()
            return row is not None and row.value == self.now_func().date().isoformat()

    def _write_phase_meta(self, result: TradeDayRunResult) -> None:
        now = self.now_func()
        values = {
            "trade_day.last_phase": result.phase,
            "trade_day.last_message": result.message,
            "trade_day.last_detail": result.detail,
            "trade_day.last_run_at": now.isoformat(timespec="seconds"),
        }
        if not result.skipped and result.phase in {"opening", "review"}:
            values[f"trade_day.{result.phase}.last_date"] = now.date().isoformat()
        if result.phase == "intraday" and not result.skipped:
            values["trade_day.intraday.last_run_at"] = now.isoformat(timespec="seconds")
        with self.session_factory() as session:
            for key, value in values.items():
                row = session.query(SystemMeta).filter_by(key=key).one_or_none()
                if row is None:
                    session.add(SystemMeta(key=key, value=value, updated_at=datetime.now(UTC).replace(tzinfo=None)))
                else:
                    row.value = value
                    row.updated_at = datetime.now(UTC).replace(tzinfo=None)

    def _local_now(self) -> datetime:
        return datetime.now(ZoneInfo(str(self.config["system"]["timezone"])))
