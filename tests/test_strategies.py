from __future__ import annotations

from types import SimpleNamespace

from backend.analysis.position_analyzer import PositionResult
from backend.analysis.trend_analyzer import TrendResult
from backend.analysis.volume_price_analyzer import VolumePriceResult
from backend.strategy.base_strategy import StrategyContext
from backend.strategy.elastic_strategy import PanicReversalStrategy
from backend.strategy.leader_trade_strategy import (
    LeaderBreakoutStrategy,
    LeaderFirstDivergenceStrategy,
    LeaderPullbackStrategy,
    LeaderTrendContinueStrategy,
)
from backend.strategy.lianban_strategy import LianbanLeaderStrategy
from backend.strategy.mainline_strategy import MainlineSwitchStrategy
from backend.strategy.mid_trend_strategy import CoreMidPullbackStrategy, TrendHoldStrategy


def strategy_config() -> dict[str, object]:
    return {
        "strategies": {
            "leader_pullback": {"pullback_max_pct": 5.0, "min_sector_score": 50, "position_pct": [0.10, 0.20]},
            "leader_breakout": {"volume_ratio_min": 1.5, "pct_change_min": 1.5, "close_position_min": 0.7, "require_sector_sync": True, "position_pct": [0.10, 0.15]},
            "leader_first_divergence": {"max_drop_from_high": 10.0, "require_mainline_active": True, "position_pct": [0.10, 0.15]},
            "leader_trend_continue": {"require_ma20_hold": True},
            "core_mid_trend_pullback": {"position_pct": [0.20, 0.30]},
            "lianban_leader_template": {"min_lianban_count": 2, "max_position_pct": 0.10},
            "panic_reversal": {"max_position_pct": 0.10, "require_leader_intact": True},
            "mainline_switch": {"score_diff_threshold": 0.3},
            "trend_hold": {"enabled": True},
        }
    }


def trend(state: str = "up", slope: float = 0.01) -> TrendResult:
    return TrendResult(state, ma5=10.5, ma10=10.3, ma20=10.0, ma60=9.0, ma_alignment="多头排列", slope_20=slope)


def volume(ratio: float = 0.7, upper_shadow: float = 0.1) -> VolumePriceResult:
    return VolumePriceResult(ratio, turnover_rate=5.0, price_volume_divergence=False, upper_shadow_ratio=upper_shadow, lower_shadow_ratio=0.1, body_ratio=0.6)


def position(close_bar: float = 0.8) -> PositionResult:
    return PositionResult(-0.01, 0.2, 0.8, False, False, close_bar)


def context_for(role: str = "leader", status: str = "rising", score: float = 70.0, analysis_override: dict | None = None) -> StrategyContext:
    symbol = "000001.SZ"
    analysis = {
        "trend": trend(),
        "volume_price": volume(),
        "position": position(),
        "current_price": 10.2,
        "pct_chg": 1.0,
        "high_20": 10.0,
        "sector_pct_chg": 1.0,
        "ma60_slope": 0.01,
    }
    if analysis_override:
        analysis.update(analysis_override)
    return StrategyContext(
        config=strategy_config(),
        mainline_results=[SimpleNamespace(sector_name="AI应用", mainline_score=score, mainline_status=status, rank=1)],
        role_results={symbol: SimpleNamespace(symbol=symbol, role=role, score=100.0, sector_name="AI应用")},
        stock_analysis={symbol: analysis},
    )


def test_leader_pullback_triggers() -> None:
    signals = LeaderPullbackStrategy(strategy_config()).execute(context_for())
    assert signals and signals[0].action == "buy"


def test_leader_pullback_not_trigger_downtrend() -> None:
    ctx = context_for(analysis_override={"trend": trend("down", -0.01)})
    assert LeaderPullbackStrategy(strategy_config()).execute(ctx) == []


def test_leader_pullback_boundary_five_percent() -> None:
    ctx = context_for(analysis_override={"current_price": 10.5})
    signals = LeaderPullbackStrategy(strategy_config()).execute(ctx)
    assert signals and signals[0].entry_price_low == 10.0


def test_leader_pullback_deny_volume_drop() -> None:
    ctx = context_for(analysis_override={"volume_price": volume(1.6), "pct_chg": -2.5})
    signals = LeaderPullbackStrategy(strategy_config()).execute(ctx)
    assert signals[0].action == "deny"


def test_leader_breakout_triggers() -> None:
    ctx = context_for(analysis_override={"volume_price": volume(1.6), "current_price": 10.5, "pct_chg": 2.0, "high_20": 10.0})
    signals = LeaderBreakoutStrategy(strategy_config()).execute(ctx)
    assert signals and signals[0].action == "buy"


def test_leader_breakout_deny_shrink() -> None:
    ctx = context_for(analysis_override={"volume_price": volume(0.8), "current_price": 10.5, "pct_chg": 2.0})
    assert LeaderBreakoutStrategy(strategy_config()).execute(ctx)[0].action == "deny"


def test_leader_breakout_deny_sector_not_following() -> None:
    ctx = context_for(analysis_override={"volume_price": volume(1.6), "current_price": 10.5, "pct_chg": 2.0, "sector_pct_chg": -0.1})
    assert LeaderBreakoutStrategy(strategy_config()).execute(ctx)[0].reason == "板块无跟随"


def test_leader_breakout_boundary() -> None:
    ctx = context_for(analysis_override={"volume_price": volume(1.5), "current_price": 10.01, "pct_chg": 1.5, "high_20": 10.0, "position": position(0.7)})
    assert LeaderBreakoutStrategy(strategy_config()).execute(ctx)[0].action == "buy"


def test_core_mid_pullback_triggers() -> None:
    signals = CoreMidPullbackStrategy(strategy_config()).execute(context_for(role="core_mid", analysis_override={"volume_price": volume(0.7)}))
    assert signals and signals[0].action == "buy"


def test_core_mid_pullback_ma60_down() -> None:
    ctx = context_for(role="core_mid", analysis_override={"volume_price": volume(0.7), "ma60_slope": -0.01})
    assert CoreMidPullbackStrategy(strategy_config()).execute(ctx) == []


def test_core_mid_pullback_sector_fading() -> None:
    ctx = context_for(role="core_mid", status="fading", analysis_override={"volume_price": volume(0.7)})
    assert CoreMidPullbackStrategy(strategy_config()).execute(ctx) == []


def test_core_mid_pullback_boundary_volume() -> None:
    ctx = context_for(role="core_mid", analysis_override={"volume_price": volume(0.79)})
    assert CoreMidPullbackStrategy(strategy_config()).execute(ctx)[0].action == "buy"


def test_lianban_leader_template_triggers() -> None:
    ctx = context_for(score=90, analysis_override={"turnover_acceptance": 90, "consecutive_up_days": 2, "total_pct_chg": 20})
    ctx.stock_analysis["lianban_records"] = {"000001.SZ": 4}
    ctx.stock_analysis["auction_scores"] = {"000001.SZ": 90}
    signals = LianbanLeaderStrategy(strategy_config()).execute(ctx)
    assert signals and signals[0].action == "buy"


def test_lianban_leader_template_not_trigger_low_lianban() -> None:
    ctx = context_for()
    ctx.stock_analysis["lianban_records"] = {"000001.SZ": 1}
    ctx.stock_analysis["auction_scores"] = {"000001.SZ": 80}
    assert LianbanLeaderStrategy(strategy_config()).execute(ctx) == []


def test_lianban_leader_template_high_open_risk() -> None:
    ctx = context_for(score=90, analysis_override={"turnover_acceptance": 90, "auction_pct_chg": 8.0})
    ctx.stock_analysis["lianban_records"] = {"000001.SZ": 4}
    ctx.stock_analysis["auction_scores"] = {"000001.SZ": 90}
    signal = LianbanLeaderStrategy(strategy_config()).execute(ctx)[0]
    assert signal.action == "watch"
    assert "high_open_risk" in signal.reason


def test_lianban_leader_template_back_row_follow() -> None:
    ctx = context_for()
    ctx.role_results["000001.SZ"].score = 40
    ctx.stock_analysis["lianban_records"] = {"000001.SZ": 4}
    ctx.stock_analysis["auction_scores"] = {"000001.SZ": 90}
    signal = LianbanLeaderStrategy(strategy_config()).execute(ctx)[0]
    assert signal.action == "watch"
    assert "back_row_follow" in signal.reason


def test_mainline_switch_continuing() -> None:
    ctx = context_for()
    ctx.stock_analysis["previous_mainlines"] = ["AI应用"]
    signals = MainlineSwitchStrategy(strategy_config()).execute(ctx)
    assert "延续" in signals[0].action_text


def test_mainline_switch_rotation() -> None:
    ctx = context_for()
    ctx.stock_analysis["previous_mainlines"] = ["旧1", "旧2", "旧3", "旧4", "旧5"]
    ctx.mainline_results = [SimpleNamespace(sector_name=f"新{i}", mainline_score=50, mainline_status="risk", rank=i) for i in range(1, 6)]
    signals = MainlineSwitchStrategy(strategy_config()).execute(ctx)
    assert "轮动" in signals[0].action_text


def test_leader_first_divergence_triggers() -> None:
    ctx = context_for(analysis_override={"drop_from_high": 6.0, "close_above_prev_low": True})
    assert LeaderFirstDivergenceStrategy(strategy_config()).execute(ctx)[0].action == "buy"


def test_leader_first_divergence_not_trigger_fading() -> None:
    ctx = context_for(status="fading", analysis_override={"drop_from_high": 6.0, "close_above_prev_low": True})
    assert LeaderFirstDivergenceStrategy(strategy_config()).execute(ctx) == []


def test_leader_trend_continue_adds() -> None:
    ctx = context_for(analysis_override={"trend": trend("strong_up", 0.03), "current_price": 11, "higher_high_low": True})
    assert LeaderTrendContinueStrategy(strategy_config()).execute(ctx)[0].action == "add"


def test_leader_trend_continue_reduces() -> None:
    ctx = context_for(analysis_override={"current_price": 9, "higher_high_low": False})
    assert LeaderTrendContinueStrategy(strategy_config()).execute(ctx)[0].action == "reduce"


def test_trend_hold_holds() -> None:
    assert TrendHoldStrategy(strategy_config()).execute(context_for())[0].action == "hold"


def test_trend_hold_reduces() -> None:
    ctx = context_for(status="fading", analysis_override={"current_price": 9})
    assert TrendHoldStrategy(strategy_config()).execute(ctx)[0].action == "reduce"


def test_panic_reversal_triggers() -> None:
    ctx = context_for(analysis_override={"current_price": 10, "panic_days": 3, "has_intraday_support": True})
    ctx.stock_analysis["market_regime"] = "weak"
    assert PanicReversalStrategy(strategy_config()).execute(ctx)[0].action == "buy"


def test_panic_reversal_not_trigger_neutral_market() -> None:
    ctx = context_for(analysis_override={"current_price": 10, "panic_days": 3, "has_intraday_support": True})
    ctx.stock_analysis["market_regime"] = "neutral"
    assert PanicReversalStrategy(strategy_config()).execute(ctx) == []
