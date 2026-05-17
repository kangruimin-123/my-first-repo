from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class MainlineRadarResult:
    sector_name: str
    radar_score: float
    confidence: float
    signal_type: str
    stage_filter: str
    reason: list[str] = field(default_factory=list)
    suggested_watch: list[str] = field(default_factory=list)


class MainlineRadar:
    """Scan non-Top5 sectors for emerging sector opportunities."""

    def scan(
        self,
        sector_daily: pd.DataFrame,
        limit_up: pd.DataFrame,
        mainline_history: list[Any],
        stage_results: dict[str, Any],
        config: dict[str, Any],
    ) -> list[MainlineRadarResult]:
        if sector_daily.empty:
            return []
        radar_config = config.get("radar", {}).get("mainline_radar", {})
        scan_start, scan_end = radar_config.get("scan_range", [6, 20])
        min_score = float(radar_config.get("min_radar_score", 50))
        weights = radar_config.get(
            "signal_weights",
            {"limit_up_cluster": 0.35, "volume_surge": 0.25, "leader_move": 0.25, "sustained": 0.15},
        )
        ranked = self._rank_sectors(sector_daily)
        candidates = ranked[(ranked["radar_rank"] >= int(scan_start)) & (ranked["radar_rank"] <= int(scan_end))]
        results: list[MainlineRadarResult] = []
        for _, row in candidates.iterrows():
            sector_name = str(row["sector_name"])
            active_signals, reason, suggested = self._signals_for_sector(row, limit_up, mainline_history)
            if not active_signals:
                continue
            weighted_signal_score = sum(float(weights.get(signal, 0.0)) for signal in active_signals)
            score = 40.0 + weighted_signal_score * 60.0
            stage = self._sector_stage(sector_name, stage_results)
            stage_filter = self._stage_filter(stage)
            multiplier = self._stage_multiplier(stage, radar_config)
            score *= multiplier
            if score < min_score:
                continue
            signal_type = "sustained" if "sustained" in active_signals else active_signals[0]
            results.append(
                MainlineRadarResult(
                    sector_name=sector_name,
                    radar_score=round(min(100.0, score), 2),
                    confidence=round(min(1.0, score / 100.0), 4),
                    signal_type=signal_type,
                    stage_filter=stage_filter,
                    reason=reason + [f"周期过滤：{stage_filter}，倍率 {multiplier:.1f}"],
                    suggested_watch=suggested[:5],
                )
            )
        return sorted(results, key=lambda item: item.radar_score, reverse=True)[:5]

    def _rank_sectors(self, sector_daily: pd.DataFrame) -> pd.DataFrame:
        frame = sector_daily.copy()
        if "rank" in frame.columns:
            frame["radar_rank"] = pd.to_numeric(frame["rank"], errors="coerce")
            return frame
        if "mainline_score" in frame.columns:
            frame = frame.sort_values("mainline_score", ascending=False)
        else:
            limit_up = pd.to_numeric(frame.get("limit_up_count", 0), errors="coerce").fillna(0)
            pct = pd.to_numeric(frame.get("pct_chg", frame.get("sector_pct_chg", 0)), errors="coerce").fillna(0)
            amount = pd.to_numeric(frame.get("amount", frame.get("sector_amount", 0)), errors="coerce").fillna(0)
            frame["_radar_sort_score"] = limit_up * 20 + pct * 5 + amount.rank(pct=True) * 20
            frame = frame.sort_values("_radar_sort_score", ascending=False)
        frame["radar_rank"] = range(1, len(frame) + 1)
        return frame

    def _signals_for_sector(self, row: pd.Series, limit_up: pd.DataFrame, mainline_history: list[Any]) -> tuple[list[str], list[str], list[str]]:
        sector_name = str(row["sector_name"])
        pct_chg = float(row.get("pct_chg", row.get("sector_pct_chg", 0.0)) or 0.0)
        amount = float(row.get("amount", row.get("sector_amount", 0.0)) or 0.0)
        avg_amount = float(row.get("avg_amount_5d", row.get("amount_5d_avg", 0.0)) or 0.0)
        limit_up_count = int(row.get("limit_up_count", 0) or 0)
        sector_limit_ups = self._limit_ups_for_sector(sector_name, limit_up)
        if sector_limit_ups:
            limit_up_count = max(limit_up_count, len(sector_limit_ups))
        signals: list[str] = []
        reason: list[str] = []
        suggested_watch: list[str] = list(sector_limit_ups)
        if limit_up_count >= 2:
            signals.append("limit_up_cluster")
            reason.append(f"涨停扩散：{limit_up_count}只涨停，板块涨幅{pct_chg:.2f}%")
        elif limit_up_count == 1 and pct_chg >= 2.0:
            signals.append("limit_up_cluster")
            reason.append(f"首板试探：1只涨停且板块涨幅{pct_chg:.2f}%")
        if avg_amount > 0 and amount > avg_amount * 1.5 and pct_chg < 3.0:
            signals.append("volume_surge")
            reason.append(f"成交额异动：今日成交额为5日均额{amount / avg_amount:.2f}倍")
        if not signals and pct_chg >= 3.0 and amount > 0:
            signals.append("leader_move")
            reason.append(f"板块强势：涨幅{pct_chg:.2f}%且成交额进入扫描区间，关注明日承接")
        leader_symbol = str(row.get("leader_symbol", "") or "")
        leader_pct = float(row.get("leader_pct_chg", 0.0) or 0.0)
        leader_volume_ratio = float(row.get("leader_volume_ratio", 0.0) or 0.0)
        if leader_symbol and 3.0 < leader_pct < 9.5 and leader_volume_ratio > 1.5:
            signals.append("leader_move")
            reason.append(f"龙头异动：{leader_symbol}涨幅{leader_pct:.2f}%且放量")
            suggested_watch.append(leader_symbol)
        if self._has_sustained_signal(sector_name, mainline_history):
            signals.append("sustained")
            reason.append("连续2天出现异动信号")
        return signals, reason, _dedupe(suggested_watch)

    def _limit_ups_for_sector(self, sector_name: str, limit_up: pd.DataFrame) -> list[str]:
        if limit_up.empty or "sector_name" not in limit_up.columns:
            return []
        frame = limit_up[limit_up["sector_name"] == sector_name]
        if "symbol" not in frame.columns:
            return []
        return [str(symbol) for symbol in frame["symbol"].dropna().tolist()]

    def _has_sustained_signal(self, sector_name: str, history: list[Any]) -> bool:
        hits = 0
        for item in history:
            item_sector = getattr(item, "sector_name", None) if not isinstance(item, dict) else item.get("sector_name")
            if item_sector != sector_name:
                continue
            signal_type = getattr(item, "signal_type", None) if not isinstance(item, dict) else item.get("signal_type")
            radar_score = float(getattr(item, "radar_score", 0.0) if not isinstance(item, dict) else item.get("radar_score", 0.0) or 0.0)
            if signal_type or radar_score >= 50:
                hits += 1
        return hits >= 1

    def _sector_stage(self, sector_name: str, stage_results: dict[str, Any]) -> str:
        stages = []
        for result in stage_results.values():
            result_sector = getattr(result, "sector_name", "")
            if result_sector and result_sector != sector_name:
                continue
            stage = str(getattr(result, "stage", ""))
            if stage:
                stages.append(stage)
        if not stages:
            return "unknown"
        return Counter(stages).most_common(1)[0][0]

    def _stage_filter(self, stage: str) -> str:
        if stage in {"stage_0_accumulation", "stage_1_start"}:
            return "early"
        if stage == "stage_2_rising":
            return "rising"
        if stage == "stage_3_distribution":
            return "fading"
        if stage == "stage_4_decline":
            return "decline"
        return "unknown"

    def _stage_multiplier(self, stage: str, radar_config: dict[str, Any]) -> float:
        multipliers = radar_config.get(
            "stage_multiplier",
            {"stage_0": 1.0, "stage_1": 1.0, "stage_2": 0.8, "stage_3": 0.3, "stage_4": 0.3},
        )
        short_stage = stage.replace("_accumulation", "").replace("_start", "").replace("_rising", "").replace("_distribution", "").replace("_decline", "")
        return float(multipliers.get(short_stage, 1.0))


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            result.append(item)
            seen.add(item)
    return result
