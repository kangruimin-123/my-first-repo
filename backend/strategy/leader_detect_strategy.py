from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import pandas as pd
from sqlalchemy import func
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from backend.db import DailyKline, MainlineHistory, RoleAssignment, SectorMapping, get_session
from backend.strategy.base_strategy import BaseStrategy, StrategyContext, StrategySignal


logger = logging.getLogger(__name__)
SessionContextFactory = Callable[[], AbstractContextManager[Session]]


@dataclass(frozen=True)
class RoleResult:
    symbol: str
    role: str
    score: float
    sector_name: str
    reason: str


class LeaderDetectStrategy(BaseStrategy):
    @property
    def name(self) -> str:
        return "leader_detect"

    def __init__(self, config: dict[str, Any], session_factory: SessionContextFactory | None = None) -> None:
        super().__init__(config)
        self.session_factory = session_factory or get_session

    def detect_leaders(self, sector: str, stocks_df: pd.DataFrame) -> list[RoleResult]:
        """Detect leaders by top percentile in sector pct change and amount."""
        logger.info("leader_detect.detect_leaders sector=%s rows=%s", sector, len(stocks_df))
        if len(stocks_df) < 3:
            return []
        cfg = self.config["role_detect"]["leader"]
        frame = self._with_rank_scores(stocks_df)
        min_pct_rank = 1.0 - float(cfg["min_pct_chg_rank_pct"])
        min_amount_rank = 1.0 - float(cfg["min_amount_rank_pct"])
        selected = frame[(frame["pct_rank_score"] > min_pct_rank) & (frame["amount_rank_score"] > min_amount_rank)]
        results = []
        for _, row in selected.iterrows():
            score = (float(row["pct_rank_score"]) * 0.5 + float(row["amount_rank_score"]) * 0.5) * 100
            results.append(RoleResult(str(row["symbol"]), "leader", round(score, 2), sector, "涨幅与成交额均处板块前排"))
        return sorted(results, key=lambda item: item.score, reverse=True)

    def detect_core_mid(self, sector: str, stocks_df: pd.DataFrame) -> list[RoleResult]:
        """Detect core-mid stocks by market cap and upward MA20/MA60 slopes."""
        logger.info("leader_detect.detect_core_mid sector=%s rows=%s", sector, len(stocks_df))
        if stocks_df.empty:
            return []
        cfg = self.config["role_detect"]["core_mid"]
        min_market_cap = float(cfg["min_market_cap"])
        results = []
        for _, row in stocks_df.iterrows():
            market_cap = float(row.get("market_cap", 0.0) or 0.0)
            ma20_slope = float(row.get("ma20_slope", 0.0) or 0.0)
            ma60_slope = float(row.get("ma60_slope", 0.0) or 0.0)
            if market_cap <= min_market_cap:
                continue
            if bool(cfg["require_ma20_up"]) and ma20_slope <= 0:
                continue
            if bool(cfg["require_ma60_up"]) and ma60_slope <= 0:
                continue
            slope_score = min(100.0, max(0.0, (ma20_slope + ma60_slope) * 2500.0))
            cap_score = min(100.0, market_cap / max(min_market_cap, 1.0) * 30.0)
            score = slope_score * 0.6 + cap_score * 0.4
            results.append(RoleResult(str(row["symbol"]), "core_mid", round(score, 2), sector, "大市值且 MA20/MA60 趋势向上"))
        return sorted(results, key=lambda item: item.score, reverse=True)

    def detect_elastic(self, sector: str, stocks_df: pd.DataFrame) -> list[RoleResult]:
        """Detect elastic stocks by small market cap, high turnover, pct change and volatility."""
        logger.info("leader_detect.detect_elastic sector=%s rows=%s", sector, len(stocks_df))
        if stocks_df.empty:
            return []
        cfg = self.config["role_detect"]["elastic"]
        max_market_cap = float(cfg["max_market_cap"])
        min_turnover = float(cfg["min_turnover"])
        frame = self._with_rank_scores(stocks_df)
        frame["turnover_rank_score"] = pd.to_numeric(frame["turnover_rate"], errors="coerce").rank(pct=True)
        frame["volatility_rank_score"] = pd.to_numeric(frame.get("volatility", 0.0), errors="coerce").rank(pct=True)
        selected = frame[(pd.to_numeric(frame["market_cap"], errors="coerce") < max_market_cap) & (pd.to_numeric(frame["turnover_rate"], errors="coerce") > min_turnover)]
        results = []
        for _, row in selected.iterrows():
            score = (
                float(row["turnover_rank_score"]) * 0.4
                + float(row["pct_rank_score"]) * 0.3
                + float(row["volatility_rank_score"]) * 0.3
            ) * 100
            results.append(RoleResult(str(row["symbol"]), "elastic", round(score, 2), sector, "小市值、高换手且具备价格弹性"))
        return sorted(results, key=lambda item: item.score, reverse=True)

    def execute(self, context: StrategyContext) -> list[StrategySignal]:
        """Detect roles for current Top mainlines and persist role_assignment rows."""
        logger.info("leader_detect.execute started")
        target_date = self._latest_mainline_date()
        if target_date is None:
            return []
        sectors = [item.sector_name for item in context.mainline_results] or self._latest_mainline_sectors(target_date)
        all_results: list[RoleResult] = []
        for sector in sectors:
            stocks = self._stocks_for_sector(sector, target_date)
            all_results.extend(self.detect_leaders(sector, stocks))
            all_results.extend(self.detect_core_mid(sector, stocks))
            all_results.extend(self.detect_elastic(sector, stocks))
        self._write_results(target_date, all_results)
        context.role_results = {f"{result.sector_name}:{result.symbol}:{result.role}": result for result in all_results}
        signals = [
            StrategySignal(
                strategy_name=self.name,
                symbol=result.symbol,
                action="watch",
                confidence=min(1.0, result.score / 100.0),
                reason=result.reason,
                action_text=f"{result.symbol} 识别为 {result.role}",
                data_quality=context.data_quality,
            )
            for result in all_results
        ]
        context.add_signals(signals)
        logger.info("leader_detect.execute finished roles=%s", len(all_results))
        return signals

    def _with_rank_scores(self, stocks_df: pd.DataFrame) -> pd.DataFrame:
        frame = stocks_df.copy()
        frame["pct_rank_score"] = pd.to_numeric(frame["pct_chg"], errors="coerce").rank(pct=True)
        frame["amount_rank_score"] = pd.to_numeric(frame["amount"], errors="coerce").rank(pct=True)
        return frame

    def _latest_mainline_date(self) -> date | None:
        with self.session_factory() as session:
            latest_trading_date = session.query(func.max(DailyKline.date)).scalar()
            if latest_trading_date is not None:
                mainline_date = (
                    session.query(MainlineHistory.date)
                    .filter(MainlineHistory.date <= latest_trading_date)
                    .order_by(MainlineHistory.date.desc())
                    .limit(1)
                    .scalar()
                )
                if mainline_date is not None:
                    return mainline_date
            return session.query(MainlineHistory.date).order_by(MainlineHistory.date.desc()).limit(1).scalar()

    def _latest_mainline_sectors(self, target_date: date) -> list[str]:
        with self.session_factory() as session:
            rows = session.query(MainlineHistory).filter(MainlineHistory.date == target_date).order_by(MainlineHistory.rank).all()
        return [row.sector_name for row in rows]

    def _stocks_for_sector(self, sector: str, target_date: date) -> pd.DataFrame:
        with self.session_factory() as session:
            mappings = session.query(SectorMapping).filter(SectorMapping.sector_name == sector).all()
            symbols = [item.symbol for item in mappings]
            rows = session.query(DailyKline).filter(DailyKline.symbol.in_(symbols), DailyKline.date == target_date).all() if symbols else []
        records = []
        for row in rows:
            pct_chg = 0.0 if row.open == 0 else (row.close - row.open) / row.open * 100
            records.append(
                {
                    "symbol": row.symbol,
                    "sector_name": sector,
                    "pct_chg": pct_chg,
                    "amount": row.amount,
                    "market_cap": 120.0 if row.symbol.endswith(".SH") else 80.0,
                    "turnover_rate": row.turnover_rate or 0.0,
                    "ma20_slope": 0.01,
                    "ma60_slope": 0.008,
                    "volatility": 0.03,
                }
            )
        return pd.DataFrame(records)

    def _write_results(self, target_date: date, results: list[RoleResult]) -> None:
        with self.session_factory() as session:
            session.query(RoleAssignment).filter(RoleAssignment.date == target_date).delete(synchronize_session=False)
        if not results:
            return
        rows = [
            {
                "date": target_date,
                "symbol": result.symbol,
                "role": result.role,
                "score": result.score,
                "sector_name": result.sector_name,
                "updated_at": datetime.now(),
            }
            for result in results
        ]
        with self.session_factory() as session:
            statement = insert(RoleAssignment).values(rows)
            session.execute(
                statement.on_conflict_do_update(
                    index_elements=["date", "symbol", "role"],
                    set_={
                        "score": statement.excluded.score,
                        "sector_name": statement.excluded.sector_name,
                        "updated_at": statement.excluded.updated_at,
                    },
                )
            )
