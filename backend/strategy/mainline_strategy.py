from __future__ import annotations

import json
import logging
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import date, datetime
from typing import Any

import pandas as pd
from sqlalchemy import func
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from backend.analysis.mainline_analyzer import MainlineAnalyzer, MainlineResult
from backend.db import DailyKline, LianbanRecord, LimitUpRecord, MainlineHistory, SectorDaily, get_session
from backend.strategy.base_strategy import BaseStrategy, StrategyContext, StrategySignal


logger = logging.getLogger(__name__)
SessionContextFactory = Callable[[], AbstractContextManager[Session]]


class MainlineStrategy(BaseStrategy):
    @property
    def name(self) -> str:
        return "mainline_detect"

    def __init__(self, config: dict[str, Any], session_factory: SessionContextFactory | None = None) -> None:
        super().__init__(config)
        self.session_factory = session_factory or get_session
        self.analyzer = MainlineAnalyzer(config)

    def execute(self, context: StrategyContext) -> list[StrategySignal]:
        """Read SQLite inputs, detect mainlines, persist results, and emit watch signals."""
        logger.info("mainline_strategy.execute started")
        target_date = self._latest_sector_date()
        if target_date is None:
            logger.info("mainline_strategy.execute no sector_daily rows")
            return []

        sector_daily = self._sector_daily_frame(target_date)
        limit_up = self._limit_up_frame(target_date)
        lianban = self._lianban_frame(target_date)
        history = self._history_before(target_date)
        results = self.analyzer.detect(sector_daily, limit_up, lianban, history)
        self._write_results(target_date, results)
        context.mainline_results = results

        signals = [
            StrategySignal(
                strategy_name=self.name,
                symbol=result.sector_name,
                action="watch",
                confidence=min(1.0, result.mainline_score / 100.0),
                reason=f"主线排名第{result.rank}，状态{result.mainline_status}",
                action_text=f"关注主线：{result.sector_name}，分数 {result.mainline_score}",
                data_quality=context.data_quality,
                grade="NONE",
            )
            for result in results
        ]
        context.add_signals(signals)
        logger.info("mainline_strategy.execute finished results=%s", len(results))
        return signals

    def _latest_sector_date(self) -> date | None:
        with self.session_factory() as session:
            latest_trading_date = session.query(func.max(DailyKline.date)).scalar()
            if latest_trading_date is not None:
                sector_date = (
                    session.query(SectorDaily.date)
                    .filter(SectorDaily.date <= latest_trading_date)
                    .order_by(SectorDaily.date.desc())
                    .limit(1)
                    .scalar()
                )
                if sector_date is not None:
                    return sector_date
            return session.query(SectorDaily.date).order_by(SectorDaily.date.desc()).limit(1).scalar()

    def _sector_daily_frame(self, target_date: date) -> pd.DataFrame:
        with self.session_factory() as session:
            rows = session.query(SectorDaily).filter(SectorDaily.date == target_date).all()
        return pd.DataFrame(
            [
                {
                    "sector_name": row.sector_name,
                    "date": row.date,
                    "pct_chg": row.pct_chg or 0.0,
                    "amount": row.amount or 0.0,
                    "limit_up_count": row.limit_up_count or 0,
                    "lianban_count": row.lianban_count or 0,
                    "leader_strength": row.pct_chg or 0.0,
                }
                for row in rows
            ]
        )

    def _limit_up_frame(self, target_date: date) -> pd.DataFrame:
        with self.session_factory() as session:
            rows = session.query(LimitUpRecord).filter(LimitUpRecord.date == target_date).all()
        return pd.DataFrame([{"symbol": row.symbol, "date": row.date} for row in rows])

    def _lianban_frame(self, target_date: date) -> pd.DataFrame:
        with self.session_factory() as session:
            rows = session.query(LianbanRecord).filter(LianbanRecord.date == target_date).all()
        return pd.DataFrame([{"symbol": row.symbol, "date": row.date, "lianban_count": row.lianban_count} for row in rows])

    def _history_before(self, target_date: date) -> list[MainlineResult]:
        with self.session_factory() as session:
            rows = (
                session.query(MainlineHistory)
                .filter(MainlineHistory.date < target_date)
                .order_by(MainlineHistory.date.desc(), MainlineHistory.rank.asc())
                .limit(10)
                .all()
            )
        return [
            MainlineResult(
                sector_name=row.sector_name,
                mainline_score=row.mainline_score,
                mainline_status=row.mainline_status,
                rank=row.rank,
                factors=json.loads(row.factors_json or "{}"),
            )
            for row in rows
        ]

    def _write_results(self, target_date: date, results: list[MainlineResult]) -> None:
        if not results:
            return
        rows = [
            {
                "date": target_date,
                "sector_name": result.sector_name,
                "mainline_score": result.mainline_score,
                "mainline_status": result.mainline_status,
                "rank": result.rank,
                "factors_json": json.dumps(result.factors, ensure_ascii=False),
                "updated_at": datetime.now(),
            }
            for result in results
        ]
        with self.session_factory() as session:
            statement = insert(MainlineHistory).values(rows)
            session.execute(
                statement.on_conflict_do_update(
                    index_elements=["date", "sector_name"],
                    set_={
                        "mainline_score": statement.excluded.mainline_score,
                        "mainline_status": statement.excluded.mainline_status,
                        "rank": statement.excluded.rank,
                        "factors_json": statement.excluded.factors_json,
                        "updated_at": statement.excluded.updated_at,
                    },
                )
            )


class MainlineSwitchStrategy(BaseStrategy):
    @property
    def name(self) -> str:
        return "mainline_switch"

    def execute(self, context: StrategyContext) -> list[StrategySignal]:
        """Compare today's Top5 with previous Top5 and classify continuation or rotation."""
        today = [item.sector_name for item in context.mainline_results[:5]]
        yesterday = list(context.stock_analysis.get("previous_mainlines", []))
        if not today:
            return []
        if not yesterday:
            status = "无明确主线"
            confidence = 0.3
        else:
            changed = len(set(today) - set(yesterday))
            if changed == 0:
                status = "延续"
                confidence = 0.8
            elif changed >= 3:
                status = "轮动"
                confidence = 0.7
            else:
                status = "切换"
                confidence = 0.6
        signal = StrategySignal(
            strategy_name=self.name,
            symbol="MARKET",
            action="watch",
            confidence=confidence,
            reason=f"主线{status}",
            action_text=f"主线状态：{status}",
            data_quality=context.data_quality,
        )
        context.add_signals([signal])
        return [signal]
