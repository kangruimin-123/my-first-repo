from __future__ import annotations

import json
import logging
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from dataclasses import replace
from types import SimpleNamespace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import func
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from backend.analysis.market_risk_analyzer import MarketRiskResult
from backend.analysis.leader_radar import LeaderRadar, PotentialLeader
from backend.analysis.mainline_radar import MainlineRadar, MainlineRadarResult
from backend.analysis.position_analyzer import analyze_position
from backend.analysis.risk_radar import RiskRadar, RiskWarning
from backend.analysis.stage_analyzer import StageAnalyzer, StageResult
from backend.analysis.trend_analyzer import analyze_trend
from backend.analysis.volume_price_analyzer import analyze_volume_price
from backend.config import load_config
from backend.data.data_sync import DataSync, SyncResult
from backend.db import AuctionSnapshot, DailyBasic, DailyKline, EvaluationResult, LeaderRadarRecord, LianbanRecord, LimitUpRecord, MainlineRadarRecord, SectorDaily, SectorMapping, StageAnalysis, StrategySignal as StrategySignalRow, get_session, init_db
from backend.engine.grading import Evaluation, Grader
from backend.output.csv_reporter import write_evaluation_csv
from backend.output.html_reporter import write_html_report
from backend.output.terminal_view import render_terminal_report
from backend.llm.llm_review import LLMReview
from backend.strategy.base_strategy import StrategyContext, StrategySignal
from backend.strategy.leader_detect_strategy import LeaderDetectStrategy
from backend.strategy.elastic_strategy import ElasticBreakoutStrategy, PanicReversalStrategy
from backend.strategy.leader_trade_strategy import LeaderBreakoutStrategy, LeaderFirstDivergenceStrategy, LeaderPullbackStrategy, LeaderTrendContinueStrategy
from backend.strategy.lianban_strategy import LianbanLeaderStrategy
from backend.strategy.mainline_strategy import MainlineStrategy, MainlineSwitchStrategy
from backend.strategy.mid_trend_strategy import CoreMidPullbackStrategy, TrendHoldStrategy


logger = logging.getLogger(__name__)
SessionContextFactory = Callable[[], AbstractContextManager[Session]]


@dataclass(frozen=True)
class DailyRunResult:
    sync_result: SyncResult
    focus_pool: list[Evaluation]
    observation_pool: list[Evaluation]
    radar_results: list[MainlineRadarResult]
    risk_warnings: list[RiskWarning]
    output_dir: Path
    terminal_report: str


class DailyRunner:
    def __init__(self, config: dict[str, Any] | None = None, session_factory: SessionContextFactory | None = None) -> None:
        self.config = config or load_config()
        if session_factory is None:
            engine = init_db(db_path=str(self.config["system"]["db_path"]))
            self.session_factory = lambda: get_session(engine)
        else:
            self.session_factory = session_factory
        self.grader = Grader(self.config)

    def run(self) -> DailyRunResult:
        """Run daily Phase 2-3 pipeline and write terminal/CSV/HTML outputs."""
        logger.info("daily_runner.run started")
        sync_result = DataSync(self.config, session_factory=self.session_factory).sync_all()
        context = StrategyContext(config=self.config)
        MainlineStrategy(self.config, session_factory=self.session_factory).execute(context)
        MainlineSwitchStrategy(self.config).execute(context)
        LeaderDetectStrategy(self.config, session_factory=self.session_factory).execute(context)
        self._inject_manual_watchlist_roles(context)
        self._populate_stock_analysis(context)
        self._populate_strategy_inputs(context)

        for strategy in (
            LeaderPullbackStrategy(self.config),
            LeaderBreakoutStrategy(self.config),
            LeaderFirstDivergenceStrategy(self.config),
            LeaderTrendContinueStrategy(self.config),
            CoreMidPullbackStrategy(self.config),
            ElasticBreakoutStrategy(self.config),
            PanicReversalStrategy(self.config),
            LianbanLeaderStrategy(self.config),
            TrendHoldStrategy(self.config),
        ):
            if strategy.enabled:
                strategy.execute(context)

        evaluations = self._build_evaluations(context)
        focus_pool = self.grader.select_focus_pool(evaluations, int(self.config["stock_pool"]["max_focus_pool"]))
        context.focus_pool = focus_pool
        LLMReview(self.config).execute(context)
        self._write_evaluations(evaluations)
        self._write_stage_results(context)
        self._write_signals(context.signals)
        radar_results = self._run_mainline_radar(context)
        leader_results = self._run_leader_radar(radar_results, context)
        radar_results = self._attach_leader_watch(radar_results, leader_results)
        self._write_leader_radar_results(leader_results)
        self._write_radar_results(radar_results)
        risk_warnings = self._run_risk_radar(context)
        output_dir = self._output_dir()
        write_evaluation_csv(evaluations, output_dir)
        write_html_report(focus_pool, evaluations, context.mainline_results, self._market_summary(), output_dir, radar_results, risk_warnings)
        terminal_report = render_terminal_report(focus_pool, evaluations, context.mainline_results, self._market_summary(), radar_results, risk_warnings)
        logger.info("daily_runner.run finished focus=%s observation=%s", len(focus_pool), len(evaluations))
        return DailyRunResult(sync_result, focus_pool, evaluations, radar_results, risk_warnings, output_dir, terminal_report)

    def _inject_manual_watchlist_roles(self, context: StrategyContext) -> None:
        path = Path("sample_data/manual_watchlist.csv")
        if not path.exists():
            return
        manual = pd.read_csv(path)
        if "symbol" not in manual.columns:
            return
        symbols = manual["symbol"].dropna().astype(str).drop_duplicates().tolist()
        if not symbols:
            return
        target_date = self._today()
        with self.session_factory() as session:
            mappings = session.query(SectorMapping).filter(SectorMapping.symbol.in_(symbols)).all()
            klines = session.query(DailyKline).filter(DailyKline.symbol.in_(symbols), DailyKline.date == target_date).all()
        sector_by_symbol = {row.symbol: row.sector_name for row in mappings}
        kline_by_symbol = {row.symbol: row for row in klines}
        manual_sectors: set[str] = set()
        for symbol in symbols:
            if any(getattr(role, "symbol", "") == symbol for role in context.role_results.values()):
                continue
            sector = sector_by_symbol.get(symbol)
            if not sector and "group" in manual.columns:
                sector = str(manual.loc[manual["symbol"].astype(str) == symbol, "group"].iloc[0])
            sector = sector or "自选股"
            manual_sectors.add(sector)
            kline = kline_by_symbol.get(symbol)
            pct_chg = 0.0 if kline is None or not kline.open else (kline.close - kline.open) / max(kline.open, 1e-9) * 100
            score = max(45.0, min(75.0, 55.0 + pct_chg))
            context.role_results[f"manual:{symbol}"] = SimpleNamespace(symbol=symbol, role="core_mid", score=score, sector_name=sector, reason="手工自选股强制体检")
        context.stock_analysis["manual_watchlist_sectors"] = manual_sectors

    def _populate_stock_analysis(self, context: StrategyContext) -> None:
        for role in context.role_results.values():
            if role.symbol in context.stock_analysis:
                continue
            frame = self._daily_frame(role.symbol)
            if frame.empty:
                continue
            trend = analyze_trend(frame, self.config)
            position = analyze_position(frame)
            volume_price = analyze_volume_price(frame)
            stage = StageAnalyzer().analyze(role.symbol, frame, self.config) if bool(self.config.get("stage", {}).get("enabled", True)) else None
            if stage is not None:
                context.stage_results[role.symbol] = stage
            latest = frame.iloc[-1]
            previous_close = float(frame.iloc[-2]["close"]) if len(frame) >= 2 else float(latest["open"])
            pct_chg = (float(latest["close"]) - previous_close) / max(previous_close, 1e-9) * 100
            high_20 = float(pd.to_numeric(frame["high"], errors="coerce").tail(20).max())
            previous = frame.iloc[-2] if len(frame) >= 2 else latest
            previous_low = float(previous["low"])
            previous_close = float(previous["close"])
            drop_from_high = (high_20 - float(latest["close"])) / max(high_20, 1e-9) * 100
            recent = frame.tail(6)
            consecutive_up_days = 0
            for _, recent_row in recent.iloc[::-1].iterrows():
                if float(recent_row["close"]) > float(recent_row["open"]):
                    consecutive_up_days += 1
                else:
                    break
            total_pct_chg = (float(latest["close"]) - float(recent.iloc[0]["open"])) / max(float(recent.iloc[0]["open"]), 1e-9) * 100 if not recent.empty else 0.0
            higher_high_low = len(frame) >= 3 and float(latest["high"]) >= float(frame.iloc[-2]["high"]) and float(latest["low"]) >= float(frame.iloc[-2]["low"])
            context.stock_analysis[role.symbol] = {
                "trend": trend,
                "position": position,
                "volume_price": volume_price,
                "stage": stage,
                "last_5d_summary": self._window_summary(frame.tail(5)),
                "last_10d_summary": self._trend_summary(frame.tail(10)),
                "amount_trend": self._series_trend(frame["amount"].tail(5)),
                "turnover_trend": self._series_trend(frame["turnover_rate"].tail(5)),
                "current_price": float(latest["close"]),
                "pct_chg": pct_chg,
                "high_20": high_20,
                "drop_from_high": drop_from_high,
                "close_above_prev_low": float(latest["close"]) > previous_low,
                "previous_pct_chg": (float(previous["close"]) - float(previous["open"])) / max(float(previous["open"]), 1e-9) * 100,
                "turnover_rate": float(latest.get("turnover_rate", 0.0) or 0.0),
                "turnover_acceptance": min(100.0, float(latest.get("turnover_rate", 0.0) or 0.0) * 10.0),
                "consecutive_up_days": consecutive_up_days,
                "total_pct_chg": total_pct_chg,
                "higher_high_low": higher_high_low,
                "auction_pct_chg": 0.0,
                "broken_board_yesterday": False,
                "sector_pct_chg": self._sector_pct(role.sector_name, context),
                "ma60_slope": trend.slope_20,
                "data_quality": context.data_quality,
            }


    def _populate_strategy_inputs(self, context: StrategyContext) -> None:
        target_date = self._today()
        with self.session_factory() as session:
            lianban_rows = session.query(LianbanRecord).filter(LianbanRecord.date == target_date).all()
            auction_rows = session.query(AuctionSnapshot).filter(AuctionSnapshot.date == target_date).all()
        context.stock_analysis["lianban_records"] = {row.symbol: row.lianban_count for row in lianban_rows}
        auction_scores = {row.symbol: min(100.0, max(0.0, float(row.pct_chg or 0.0) * 10.0 + 50.0)) for row in auction_rows}
        if not auction_scores and lianban_rows:
            auction_scores = {row.symbol: 50.0 for row in lianban_rows}
        context.stock_analysis["auction_scores"] = auction_scores
        context.stock_analysis["market_regime"] = "neutral"

    def _daily_frame(self, symbol: str) -> pd.DataFrame:
        with self.session_factory() as session:
            rows = session.query(DailyKline).filter(DailyKline.symbol == symbol).order_by(DailyKline.date).all()
        return pd.DataFrame(
            [
                {
                    "date": row.date,
                    "open": row.open,
                    "high": row.high,
                    "low": row.low,
                    "close": row.close,
                    "volume": row.volume,
                    "amount": row.amount,
                    "turnover_rate": row.turnover_rate or 0.0,
                }
                for row in rows
            ]
        )

    def _window_summary(self, frame: pd.DataFrame) -> str:
        if frame.empty:
            return "缺失"
        parts: list[str] = []
        previous_close: float | None = None
        for _, row in frame.iterrows():
            close = float(row["close"])
            base = previous_close if previous_close is not None else float(row["open"])
            pct = (close - base) / max(base, 1e-9) * 100
            parts.append(f"{row['date']}:涨跌幅{pct:.2f}%,成交额{float(row['amount']):.0f}")
            previous_close = close
        return "；".join(parts)

    def _trend_summary(self, frame: pd.DataFrame) -> str:
        if frame.empty:
            return "缺失"
        closes = pd.to_numeric(frame["close"], errors="coerce")
        highs = pd.to_numeric(frame["high"], errors="coerce")
        lows = pd.to_numeric(frame["low"], errors="coerce")
        direction = "上行" if float(closes.iloc[-1]) >= float(closes.iloc[0]) else "下行"
        return f"趋势方向:{direction};关键价位:高点{float(highs.max()):.2f}/低点{float(lows.min()):.2f}"

    def _series_trend(self, series: pd.Series) -> str:
        values = pd.to_numeric(series, errors="coerce").dropna()
        if len(values) < 2:
            return "缺失"
        start = float(values.iloc[0])
        end = float(values.iloc[-1])
        ratio = (end - start) / max(abs(start), 1e-9)
        if ratio > 0.1:
            return "放量/上升"
        if ratio < -0.1:
            return "缩量/下降"
        return "平量/平稳"

    def _sector_pct(self, sector_name: str, context: StrategyContext) -> float:
        for item in context.mainline_results:
            if item.sector_name == sector_name:
                return max(0.1, float(item.mainline_score) / 100.0)
        return 0.0

    def _build_evaluations(self, context: StrategyContext) -> list[Evaluation]:
        evaluable_strategies = {
            "leader_pullback",
            "leader_breakout",
            "leader_first_divergence",
            "leader_trend_continue",
            "core_mid_trend_pullback",
            "elastic_breakout",
            "panic_reversal",
            "lianban_leader_template",
        }
        buy_signals = [
            signal
            for signal in context.signals
            if signal.strategy_name in evaluable_strategies and signal.action in {"buy", "watch", "add", "deny"}
        ]
        evaluations: list[Evaluation] = []
        seen: set[tuple[str, str, str]] = set()
        for signal in buy_signals:
            dedupe_key = (signal.symbol, signal.strategy_name, signal.action_text)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            role = self._role_for_signal(signal, context)
            mainline = self._mainline_for_role(role, context) if role else None
            grade = self.grader.grade_buy(signal, mainline, None, signal.data_quality)
            if grade == "NONE" and signal.action != "deny":
                continue
            evaluations.append(
                Evaluation(
                    symbol=signal.symbol,
                    name=signal.symbol,
                    sector=getattr(role, "sector_name", ""),
                    role=getattr(role, "role", ""),
                    buy_grade=grade,
                    buy_score=round(signal.confidence * 100, 2),
                    sell_urgency="无",
                    strategy_name=signal.strategy_name,
                    action=signal.action,
                    confidence=signal.confidence,
                    data_quality=signal.data_quality,
                    entry_low=signal.entry_price_low,
                    entry_high=signal.entry_price_high,
                    stop_loss=signal.stop_loss_price,
                    position_pct=signal.position_pct,
                    action_text=signal.action_text,
                    risk_warnings=signal.risk_warnings,
                    stage=getattr(context.stock_analysis.get(signal.symbol, {}).get("stage"), "stage", ""),
                )
            )
        return evaluations[: int(self.config["stock_pool"]["max_observation_pool"])]

    def _role_for_signal(self, signal: StrategySignal, context: StrategyContext) -> Any | None:
        for role in context.role_results.values():
            if role.symbol == signal.symbol:
                return role
        return None

    def _mainline_for_role(self, role: Any, context: StrategyContext) -> Any | None:
        for item in context.mainline_results:
            if item.sector_name == role.sector_name:
                return item
        manual_sectors = context.stock_analysis.get("manual_watchlist_sectors", set())
        if getattr(role, "sector_name", "") in manual_sectors:
            return SimpleNamespace(sector_name=role.sector_name, mainline_score=50.0, mainline_status="manual_watchlist", rank=10)
        return None

    def _write_evaluations(self, evaluations: list[Evaluation]) -> None:
        target_date = self._today()
        with self.session_factory() as session:
            session.query(EvaluationResult).filter(EvaluationResult.date == target_date).delete(synchronize_session=False)
        if not evaluations:
            return
        rows = [
            {
                "date": target_date,
                "symbol": item.symbol,
                "buy_grade": item.buy_grade,
                "sell_urgency": item.sell_urgency,
                "signals_json": json.dumps(item.__dict__, ensure_ascii=False, default=str),
                "updated_at": datetime.now(UTC).replace(tzinfo=None),
            }
            for item in evaluations
        ]
        with self.session_factory() as session:
            statement = insert(EvaluationResult).values(rows)
            session.execute(
                statement.on_conflict_do_update(
                    index_elements=["date", "symbol"],
                    set_={
                        "buy_grade": statement.excluded.buy_grade,
                        "sell_urgency": statement.excluded.sell_urgency,
                        "signals_json": statement.excluded.signals_json,
                        "updated_at": statement.excluded.updated_at,
                    },
                )
            )

    def _write_signals(self, signals: list[StrategySignal]) -> None:
        target_date = self._today()
        with self.session_factory() as session:
            session.query(StrategySignalRow).filter(StrategySignalRow.date == target_date).delete(synchronize_session=False)
        rows = []
        for signal in signals:
            if not signal.symbol or not signal.strategy_name:
                continue
            rows.append(
                {
                    "date": target_date,
                    "symbol": signal.symbol,
                    "strategy_name": signal.strategy_name,
                    "action": signal.action,
                    "confidence": signal.confidence,
                    "data_quality": signal.data_quality,
                    "signal_json": json.dumps(signal.__dict__, ensure_ascii=False, default=str),
                    "updated_at": datetime.now(UTC).replace(tzinfo=None),
                }
            )
        if not rows:
            return
        with self.session_factory() as session:
            statement = insert(StrategySignalRow).values(rows)
            session.execute(
                statement.on_conflict_do_update(
                    index_elements=["date", "symbol", "strategy_name"],
                    set_={
                        "action": statement.excluded.action,
                        "confidence": statement.excluded.confidence,
                        "data_quality": statement.excluded.data_quality,
                        "signal_json": statement.excluded.signal_json,
                        "updated_at": statement.excluded.updated_at,
                    },
                )
            )

    def _write_stage_results(self, context: StrategyContext) -> None:
        target_date = self._today()
        with self.session_factory() as session:
            session.query(StageAnalysis).filter(StageAnalysis.date == target_date).delete(synchronize_session=False)
        rows = []
        for symbol, analysis in context.stock_analysis.items():
            if not isinstance(analysis, dict):
                continue
            stage = analysis.get("stage")
            if not isinstance(stage, StageResult):
                continue
            rows.append(
                {
                    "date": target_date,
                    "symbol": symbol,
                    "stage": stage.stage,
                    "confidence": stage.confidence,
                    "stage_score": stage.stage_score,
                    "dow_trend": stage.dow_trend,
                    "wave_position": stage.wave_position,
                    "chip_status": stage.chip_status,
                    "volume_price_status": stage.volume_price_status,
                    "chart_pattern": stage.chart_pattern,
                    "risk_level": stage.risk_level,
                    "reason": json.dumps(stage.reason, ensure_ascii=False),
                    "updated_at": datetime.now(UTC).replace(tzinfo=None),
                }
            )
        if not rows:
            return
        with self.session_factory() as session:
            statement = insert(StageAnalysis).values(rows)
            session.execute(
                statement.on_conflict_do_update(
                    index_elements=["date", "symbol"],
                    set_={
                        "stage": statement.excluded.stage,
                        "confidence": statement.excluded.confidence,
                        "stage_score": statement.excluded.stage_score,
                        "dow_trend": statement.excluded.dow_trend,
                        "wave_position": statement.excluded.wave_position,
                        "chip_status": statement.excluded.chip_status,
                        "volume_price_status": statement.excluded.volume_price_status,
                        "chart_pattern": statement.excluded.chart_pattern,
                        "risk_level": statement.excluded.risk_level,
                        "reason": statement.excluded.reason,
                        "updated_at": statement.excluded.updated_at,
                    },
                )
            )

    def _run_mainline_radar(self, context: StrategyContext) -> list[MainlineRadarResult]:
        if not bool(self.config.get("radar", {}).get("mainline_radar", {}).get("enabled", False)):
            return []
        target_date = self._today()
        with self.session_factory() as session:
            sector_rows = session.query(SectorDaily).filter(SectorDaily.date == target_date).all()
            limit_rows = session.query(LimitUpRecord).filter(LimitUpRecord.date == target_date).all()
            mapping_rows = session.query(SectorMapping).all()
            history_rows = session.query(MainlineRadarRecord).filter(MainlineRadarRecord.date < target_date).order_by(MainlineRadarRecord.date.desc()).limit(20).all()
        sector_by_symbol: dict[str, str] = {}
        for mapping in mapping_rows:
            sector_by_symbol.setdefault(self._normalize_symbol(mapping.symbol), mapping.sector_name)
        sector_daily = pd.DataFrame(
            [
                {
                    "sector_name": row.sector_name,
                    "pct_chg": row.pct_chg or 0.0,
                    "amount": row.amount or 0.0,
                    "limit_up_count": row.limit_up_count or 0,
                    "lianban_count": row.lianban_count or 0,
                }
                for row in sector_rows
            ]
        )
        limit_up = pd.DataFrame(
            [
                {
                    "symbol": self._normalize_symbol(row.symbol),
                    "date": row.date,
                    "sector_name": sector_by_symbol.get(self._normalize_symbol(row.symbol), ""),
                }
                for row in limit_rows
            ]
        )
        stage_results = self._radar_stage_results(context)
        return MainlineRadar().scan(sector_daily, limit_up, history_rows, stage_results, self.config)

    def _radar_stage_results(self, context: StrategyContext) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for role in context.role_results.values():
            stage = context.stage_results.get(role.symbol)
            if stage is None:
                continue
            result[role.symbol] = type(
                "RadarStage",
                (),
                {
                    "symbol": role.symbol,
                    "sector_name": role.sector_name,
                    "stage": stage.stage,
                },
            )()
        return result

    def _write_radar_results(self, results: list[MainlineRadarResult]) -> None:
        if not results:
            return
        target_date = self._today()
        rows = [
            {
                "date": target_date,
                "sector_name": item.sector_name,
                "radar_score": item.radar_score,
                "confidence": item.confidence,
                "signal_type": item.signal_type,
                "stage_filter": item.stage_filter,
                "reason": json.dumps(item.reason, ensure_ascii=False),
                "suggested_watch": json.dumps(item.suggested_watch, ensure_ascii=False),
                "updated_at": datetime.now(UTC).replace(tzinfo=None),
            }
            for item in results
        ]
        with self.session_factory() as session:
            statement = insert(MainlineRadarRecord).values(rows)
            session.execute(
                statement.on_conflict_do_update(
                    index_elements=["date", "sector_name"],
                    set_={
                        "radar_score": statement.excluded.radar_score,
                        "confidence": statement.excluded.confidence,
                        "signal_type": statement.excluded.signal_type,
                        "stage_filter": statement.excluded.stage_filter,
                        "reason": statement.excluded.reason,
                        "suggested_watch": statement.excluded.suggested_watch,
                        "updated_at": statement.excluded.updated_at,
                    },
                )
            )

    def _run_leader_radar(self, radar_results: list[MainlineRadarResult], context: StrategyContext) -> dict[str, list[PotentialLeader]]:
        if not radar_results or not bool(self.config.get("radar", {}).get("leader_radar", {}).get("enabled", True)):
            return {}
        limit_history = self._limit_up_history_frame()
        results: dict[str, list[PotentialLeader]] = {}
        for radar in radar_results:
            stocks = self._sector_stocks_frame(radar.sector_name)
            leaders = LeaderRadar().scan(radar.sector_name, stocks, limit_history, context.stage_results, self.config)
            if leaders:
                results[radar.sector_name] = leaders
        return results

    def _attach_leader_watch(
        self,
        radar_results: list[MainlineRadarResult],
        leader_results: dict[str, list[PotentialLeader]],
    ) -> list[MainlineRadarResult]:
        updated: list[MainlineRadarResult] = []
        for radar in radar_results:
            leaders = leader_results.get(radar.sector_name, [])
            if leaders:
                updated.append(replace(radar, suggested_watch=[item.symbol for item in leaders[:5]]))
            else:
                updated.append(radar)
        return updated

    def _sector_stocks_frame(self, sector_name: str) -> pd.DataFrame:
        target_date = self._today()
        with self.session_factory() as session:
            mappings = session.query(SectorMapping).filter(SectorMapping.sector_name == sector_name).all()
            symbols = [row.symbol for row in mappings]
            basics = {
                row.symbol: row
                for row in session.query(DailyBasic).filter(DailyBasic.symbol.in_(symbols), DailyBasic.date == target_date).all()
            } if symbols else {}
            klines = {
                row.symbol: row
                for row in session.query(DailyKline).filter(DailyKline.symbol.in_(symbols), DailyKline.date == target_date).all()
            } if symbols else {}
            turnover_rows = (
                session.query(DailyKline)
                .filter(DailyKline.symbol.in_(symbols), DailyKline.date <= target_date)
                .order_by(DailyKline.symbol, DailyKline.date.desc())
                .all()
                if symbols
                else []
            )
        turnover_by_symbol: dict[str, float] = {}
        for symbol in symbols:
            values = [float(row.turnover_rate or 0.0) for row in turnover_rows if row.symbol == symbol][:20]
            turnover_by_symbol[symbol] = sum(values)
        rows = []
        concept_counts = self._concept_counts(symbols)
        for symbol in symbols:
            basic = basics.get(symbol)
            kline = klines.get(symbol)
            rows.append(
                {
                    "symbol": symbol,
                    "name": symbol,
                    "sector_name": sector_name,
                    "market_cap": float(getattr(basic, "market_cap", 0.0) or 0.0),
                    "float_market_cap": float(getattr(basic, "market_cap", 0.0) or 0.0),
                    "concept_count": concept_counts.get(symbol, 1),
                    "turnover_20d": turnover_by_symbol.get(symbol, 0.0),
                    "pct_chg": 0.0 if kline is None else float(kline.close - kline.open) / max(float(kline.open), 1e-9) * 100,
                }
            )
        return pd.DataFrame(rows)

    def _concept_counts(self, symbols: list[str]) -> dict[str, int]:
        if not symbols:
            return {}
        with self.session_factory() as session:
            mappings = session.query(SectorMapping).filter(SectorMapping.symbol.in_(symbols)).all()
        counts: dict[str, int] = {}
        for row in mappings:
            counts[row.symbol] = counts.get(row.symbol, 0) + 1
        return counts

    def _limit_up_history_frame(self) -> pd.DataFrame:
        target_date = self._today()
        with self.session_factory() as session:
            rows = session.query(LimitUpRecord).filter(LimitUpRecord.date <= target_date).order_by(LimitUpRecord.date.desc()).limit(200).all()
        return pd.DataFrame(
            [
                {
                    "symbol": row.symbol,
                    "date": row.date,
                    "lianban_count": 1,
                    "was_sector_leader": False,
                }
                for row in rows
            ]
        )

    def _write_leader_radar_results(self, results_by_sector: dict[str, list[PotentialLeader]]) -> None:
        rows = []
        target_date = self._today()
        for leaders in results_by_sector.values():
            for item in leaders:
                rows.append(
                    {
                        "date": target_date,
                        "symbol": item.symbol,
                        "name": item.name,
                        "sector_name": item.sector_name,
                        "leader_probability": item.leader_probability,
                        "role_type": item.role_type,
                        "confidence": item.confidence,
                        "factors_json": json.dumps(item.factors, ensure_ascii=False),
                        "reason": json.dumps(item.reason, ensure_ascii=False),
                        "updated_at": datetime.now(UTC).replace(tzinfo=None),
                    }
                )
        if not rows:
            return
        with self.session_factory() as session:
            statement = insert(LeaderRadarRecord).values(rows)
            session.execute(
                statement.on_conflict_do_update(
                    index_elements=["date", "symbol", "sector_name"],
                    set_={
                        "name": statement.excluded.name,
                        "leader_probability": statement.excluded.leader_probability,
                        "role_type": statement.excluded.role_type,
                        "confidence": statement.excluded.confidence,
                        "factors_json": statement.excluded.factors_json,
                        "reason": statement.excluded.reason,
                        "updated_at": statement.excluded.updated_at,
                    },
                )
            )

    def _run_risk_radar(self, context: StrategyContext) -> list[RiskWarning]:
        if not bool(self.config.get("radar", {}).get("risk_radar", {}).get("enabled", False)):
            return []
        radar = RiskRadar(self.config)
        warnings: list[RiskWarning] = []
        limit_history = self._limit_up_history_frame()
        seen: set[tuple[str, str]] = set()
        for role in context.role_results.values():
            if getattr(role, "role", "") != "leader":
                continue
            warning = radar.scan_leader_decay(role.symbol, self._daily_frame(role.symbol), limit_history)
            if warning and (warning.target, warning.signal_type) not in seen:
                warnings.append(warning)
                seen.add((warning.target, warning.signal_type))
        sector_daily = self._sector_daily_history_frame()
        limit_up = self._today_limit_up_frame()
        for mainline in context.mainline_results[:5]:
            warning = radar.scan_sector_decay(mainline.sector_name, sector_daily, limit_up)
            if warning and (warning.target, warning.signal_type) not in seen:
                warnings.append(warning)
                seen.add((warning.target, warning.signal_type))
        cycle_warnings = radar.scan_cycle_end(self._radar_stage_results(context), context.mainline_results)
        for warning in cycle_warnings:
            if (warning.target, warning.signal_type) not in seen:
                warnings.append(warning)
                seen.add((warning.target, warning.signal_type))
        return warnings

    def _sector_daily_history_frame(self) -> pd.DataFrame:
        with self.session_factory() as session:
            rows = session.query(SectorDaily).order_by(SectorDaily.date).all()
        return pd.DataFrame(
            [
                {
                    "date": row.date,
                    "sector_name": row.sector_name,
                    "pct_chg": row.pct_chg or 0.0,
                    "amount": row.amount or 0.0,
                    "limit_up_count": row.limit_up_count or 0,
                    "leader_pct_chg": row.pct_chg or 0.0,
                }
                for row in rows
            ]
        )

    def _today_limit_up_frame(self) -> pd.DataFrame:
        target_date = self._today()
        with self.session_factory() as session:
            rows = session.query(LimitUpRecord).filter(LimitUpRecord.date == target_date).all()
        return pd.DataFrame([{"symbol": row.symbol, "date": row.date} for row in rows])

    def _today(self) -> date:
        with self.session_factory() as session:
            latest_trading_date = session.query(func.max(DailyKline.date)).scalar()
        if latest_trading_date is not None:
            return latest_trading_date
        timezone_name = str(self.config["system"]["timezone"])
        return datetime.now(ZoneInfo(timezone_name)).date()

    def _normalize_symbol(self, value: str) -> str:
        text = value.strip().upper()
        if "." in text:
            return text
        if text.startswith(("6", "9")):
            return f"{text}.SH"
        return f"{text}.SZ"

    def _output_dir(self) -> Path:
        return Path("output") / self._today().strftime("%Y%m%d")

    def _market_summary(self) -> str:
        return MarketRiskResult("neutral", True, 0.5).regime + " | breadth: 0.50"
