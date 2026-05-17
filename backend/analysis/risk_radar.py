from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


EPSILON = 1e-9


@dataclass(frozen=True)
class RiskWarning:
    target: str
    target_type: str
    level: str
    signal_type: str
    reason: list[str] = field(default_factory=list)
    suggested_action: str = "提高警惕"


class RiskRadar:
    """Detect weakening before hard stop-loss rules trigger."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}
        self.radar_config = self.config.get("radar", {}).get("risk_radar", {})

    def scan_leader_decay(
        self,
        symbol: str,
        daily_df: pd.DataFrame,
        limit_up_history: pd.DataFrame,
    ) -> RiskWarning | None:
        if daily_df.empty:
            return None
        ordered = daily_df.sort_values("date") if "date" in daily_df.columns else daily_df.copy()
        latest = ordered.iloc[-1]
        previous = ordered.iloc[-2] if len(ordered) >= 2 else latest
        cfg = self.radar_config.get("leader_decay", {})
        volume_decay_ratio = float(cfg.get("volume_decay_ratio", 0.8))
        stagnation_volume_ratio = float(cfg.get("stagnation_volume_ratio", 1.5))
        stagnation_max_pct = float(cfg.get("stagnation_max_pct", 1.0))
        upper_shadow_threshold = float(cfg.get("upper_shadow_threshold", 0.3))

        close = float(latest["close"])
        open_price = float(latest["open"])
        high = float(latest["high"])
        low = float(latest["low"])
        previous_close = float(previous["close"])
        pct_chg = (close - previous_close) / max(previous_close, EPSILON) * 100
        volumes = pd.to_numeric(ordered["volume"], errors="coerce")
        avg_volume_5 = float(volumes.tail(5).mean())
        current_volume = float(latest["volume"])
        previous_volume = float(previous["volume"])
        volume_ratio = 0.0 if avg_volume_5 <= EPSILON else current_volume / avg_volume_5
        close_position = (close - float(pd.to_numeric(ordered["low"], errors="coerce").tail(60).min())) / max(
            float(pd.to_numeric(ordered["high"], errors="coerce").tail(60).max()) - float(pd.to_numeric(ordered["low"], errors="coerce").tail(60).min()),
            EPSILON,
        )
        upper_shadow_ratio = (high - max(open_price, close)) / max(high - low, EPSILON)

        if close_position > 0.7 and volume_ratio > 2.0 and pct_chg < 0:
            return RiskWarning(symbol, "stock", "danger", "leader_decay", ["高位放量阴线，可能出货"], "准备止损")
        if volume_ratio > stagnation_volume_ratio and pct_chg < stagnation_max_pct:
            return RiskWarning(symbol, "stock", "caution", "leader_decay", ["放量滞涨，资金分歧加剧"], "关注明日竞价")
        if close_position > 0.8 and upper_shadow_ratio > upper_shadow_threshold:
            return RiskWarning(symbol, "stock", "caution", "leader_decay", ["高位长上影，上方抛压显现"], "提高警惕")
        if self._is_consecutive_limit_volume_decay(symbol, limit_up_history, current_volume, previous_volume, volume_decay_ratio):
            return RiskWarning(symbol, "stock", "caution", "leader_decay", ["连续涨停但量能递减，封单力量衰减"], "提高警惕")
        compression = self._height_compression(limit_up_history)
        if compression:
            return RiskWarning("market", "sector", "watch", "leader_decay", [compression], "控制仓位")
        return None

    def scan_sector_decay(
        self,
        sector_name: str,
        sector_daily: pd.DataFrame,
        limit_up: pd.DataFrame,
    ) -> RiskWarning | None:
        if sector_daily.empty:
            return None
        frame = sector_daily[sector_daily["sector_name"] == sector_name].copy() if "sector_name" in sector_daily.columns else sector_daily.copy()
        if frame.empty:
            return None
        frame = frame.sort_values("date") if "date" in frame.columns else frame
        cfg = self.radar_config.get("sector_decay", {})
        amount_shrink_ratio = float(cfg.get("amount_shrink_ratio", 0.7))
        breadth_warning = float(cfg.get("breadth_warning", 0.4))
        latest = frame.iloc[-1]

        if len(frame) >= 3:
            limit_counts = pd.to_numeric(frame["limit_up_count"], errors="coerce").tail(3).fillna(0).tolist()
            if limit_counts[2] < limit_counts[1] < limit_counts[0]:
                return RiskWarning(sector_name, "sector", "caution", "sector_decay", ["板块涨停数连续下降"], "提高警惕")
        if "up_ratio" in frame.columns and len(frame) >= 2:
            previous_ratio = float(frame.iloc[-2].get("up_ratio", 0.0) or 0.0)
            current_ratio = float(latest.get("up_ratio", 0.0) or 0.0)
            if previous_ratio > 0.6 and current_ratio < breadth_warning:
                return RiskWarning(sector_name, "sector", "caution", "sector_decay", ["跟风减少，上涨家数占比快速回落"], "提高警惕")
        sector_pct = float(latest.get("pct_chg", latest.get("sector_pct_chg", 0.0)) or 0.0)
        leader_pct = float(latest.get("leader_pct_chg", 0.0) or 0.0)
        if (sector_pct > 0 and leader_pct < 0) or (leader_pct > 0 and sector_pct < 0):
            return RiskWarning(sector_name, "sector", "danger", "sector_decay", ["龙头与板块背离"], "减仓")
        if len(frame) >= 3:
            amount = float(latest.get("amount", latest.get("sector_amount", 0.0)) or 0.0)
            avg_amount_3 = float(pd.to_numeric(frame.get("amount", frame.get("sector_amount")), errors="coerce").tail(3).mean())
            if avg_amount_3 > 0 and amount < avg_amount_3 * amount_shrink_ratio:
                return RiskWarning(sector_name, "sector", "caution", "sector_decay", ["板块成交额萎缩，资金撤离"], "提高警惕")
        return None

    def scan_cycle_end(self, stage_results: dict[str, Any], mainline_history: list[Any]) -> list[RiskWarning]:
        warnings: list[RiskWarning] = []
        sector_stages = {}
        for result in stage_results.values():
            sector_name = getattr(result, "sector_name", getattr(result, "symbol", ""))
            stage = getattr(result, "stage", "")
            if sector_name and stage in {"stage_3_distribution", "stage_4_decline"}:
                sector_stages[sector_name] = stage
        for sector_name, stage in sorted(sector_stages.items()):
            warnings.append(RiskWarning(sector_name, "sector", "danger", "cycle_end", [f"主线进入{stage}"], "减仓"))

        top5 = [item for item in mainline_history if int(getattr(item, "rank", 999)) <= 5]
        fading_count = sum(1 for item in top5 if getattr(item, "mainline_status", "") == "fading")
        if fading_count >= 3:
            warnings.append(RiskWarning("market", "sector", "danger", "cycle_end", ["多主线同时退潮，系统性风险"], "控制仓位"))
        if self._market_limit_up_declining(mainline_history):
            warnings.append(RiskWarning("market", "sector", "caution", "cycle_end", ["市场赚钱效应持续下降"], "控制仓位"))
        return warnings

    def _is_consecutive_limit_volume_decay(
        self,
        symbol: str,
        limit_up_history: pd.DataFrame,
        current_volume: float,
        previous_volume: float,
        threshold: float,
    ) -> bool:
        if current_volume >= previous_volume * threshold:
            return False
        if limit_up_history.empty or "symbol" not in limit_up_history.columns:
            return False
        rows = limit_up_history[limit_up_history["symbol"] == symbol]
        return len(rows.tail(2)) >= 2

    def _height_compression(self, limit_up_history: pd.DataFrame) -> str:
        if limit_up_history.empty or "date" not in limit_up_history.columns:
            return ""
        frame = limit_up_history.copy().sort_values("date")
        if "market_highest_lianban" in frame.columns:
            series = pd.to_numeric(frame.drop_duplicates("date", keep="last")["market_highest_lianban"], errors="coerce").dropna().tail(2)
        elif "lianban_count" in frame.columns:
            series = pd.to_numeric(frame.groupby("date")["lianban_count"].max(), errors="coerce").dropna().tail(2)
        else:
            return ""
        if len(series) < 2:
            return ""
        previous_height = int(series.iloc[0])
        current_height = int(series.iloc[1])
        if previous_height >= 5 and current_height <= previous_height - 2:
            return f"市场连板高度从{previous_height}降至{current_height}，赚钱效应下降"
        return ""

    def _market_limit_up_declining(self, mainline_history: list[Any]) -> bool:
        counts = []
        for item in mainline_history:
            value = getattr(item, "market_limit_up_count", None)
            if value is None:
                value = getattr(item, "limit_up_count", None)
            if value is not None:
                counts.append(float(value))
        if len(counts) < 3:
            return False
        last3 = counts[-3:]
        return last3[2] < last3[1] < last3[0]
