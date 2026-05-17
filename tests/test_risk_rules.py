from __future__ import annotations

from types import SimpleNamespace

from backend.analysis.market_risk_analyzer import MarketRiskResult
from backend.analysis.trend_analyzer import TrendResult
from backend.analysis.volume_price_analyzer import VolumePriceResult
from backend.strategy.base_strategy import StrategySignal
from backend.strategy.risk_rules import DenyCheck, PositionControl, StopLoss


def risk_config() -> dict[str, object]:
    return {
        "risk": {
            "deny_check": {"min_risk_reward_ratio": 2.0},
            "position_control": {
                "leader_pullback": [0.10, 0.20],
                "lianban_leader": [0.05, 0.15],
                "core_mid_trend": [0.20, 0.30],
                "elastic": [0.05, 0.10],
                "panic_reversal": [0.00, 0.10],
                "max_total_position": 0.80,
                "weak_market_max": 0.20,
            },
        }
    }


def role(sector: str = "AI应用", score: float = 80.0) -> SimpleNamespace:
    return SimpleNamespace(symbol="000001.SZ", sector_name=sector, score=score, role="leader")


def mainlines(count: int = 5) -> list[SimpleNamespace]:
    return [SimpleNamespace(sector_name=f"主线{index}", rank=index, mainline_score=70) for index in range(1, count + 1)] + [SimpleNamespace(sector_name="AI应用", rank=count + 1, mainline_score=50)]


def stock(**override) -> dict[str, object]:
    data = {
        "current_price": 10.0,
        "target_price": 12.5,
        "stop_loss_price": 9.0,
        "consecutive_up_days": 0,
        "total_pct_chg": 0.0,
        "volume_price": VolumePriceResult(1.0, 5.0, False, 0.1, 0.1, 0.6),
        "data_quality": "full",
        "confidence": 0.8,
    }
    data.update(override)
    return data


def test_deny_non_mainline() -> None:
    assert DenyCheck().check(stock(), mainlines(5), role("非主线"), risk_config()).action == "deny"


def test_deny_back_row() -> None:
    result = DenyCheck().check(stock(), [SimpleNamespace(sector_name="AI应用", rank=1)], role(score=40), risk_config())
    assert "后排跟风" in result.reasons


def test_deny_overheated() -> None:
    assert DenyCheck().check(stock(consecutive_up_days=5, total_pct_chg=35), [SimpleNamespace(sector_name="AI应用", rank=1)], role(), risk_config()).action == "deny"


def test_deny_no_stop_loss() -> None:
    assert "无止损位" in DenyCheck().check(stock(stop_loss_price=0), [SimpleNamespace(sector_name="AI应用", rank=1)], role(), risk_config()).reasons


def test_deny_data_missing() -> None:
    assert DenyCheck().check(stock(data_quality="mock"), [SimpleNamespace(sector_name="AI应用", rank=1)], role(), risk_config()).action == "deny"


def test_deny_watch_low_confidence() -> None:
    result = DenyCheck().check(stock(confidence=0.5), mainlines(7), role(), risk_config())
    assert result.action == "watch"


def test_position_total_limit() -> None:
    signal = StrategySignal(strategy_name="leader_pullback", position_pct=0.2, stop_loss_price=9, grade="A")
    result = PositionControl().calculate(signal, [{"position_pct": 0.75}], MarketRiskResult("risk_on", True, 0.7), risk_config())
    assert result == 0.05


def test_position_weak_market_limit() -> None:
    signal = StrategySignal(strategy_name="leader_pullback", position_pct=0.2, stop_loss_price=9, grade="A")
    result = PositionControl().calculate(signal, [{"position_pct": 0.1}], MarketRiskResult("weak", False, 0.2), risk_config())
    assert result == 0.1


def test_position_by_strategy_type() -> None:
    signal = StrategySignal(strategy_name="core_mid_trend_pullback", position_pct=0.5, stop_loss_price=9, grade="A")
    result = PositionControl().calculate(signal, [], MarketRiskResult("risk_on", True, 0.7), risk_config())
    assert result == 0.3


def down_trend() -> TrendResult:
    return TrendResult("down", ma5=9, ma10=9.5, ma20=10, ma60=11, ma_alignment="空头排列", slope_20=-0.03)


def up_trend() -> TrendResult:
    return TrendResult("up", ma5=11, ma10=10.5, ma20=10, ma60=9, ma_alignment="多头排列", slope_20=0.02)


def test_stop_loss_clear_not_downgraded() -> None:
    result = StopLoss().check({"is_top5_mainline": True, "role": "leader"}, 8.5, down_trend(), MarketRiskResult("risk_on", True, 0.7), risk_config())
    assert result.urgency == "清仓"


def test_stop_loss_weak_upgrade() -> None:
    result = StopLoss().check({"volume_ratio": 2.0}, 9.5, up_trend(), MarketRiskResult("weak", False, 0.2), risk_config())
    assert result.urgency == "清仓"


def test_stop_loss_strong_protect_reduce() -> None:
    result = StopLoss().check({"volume_ratio": 2.0, "is_top5_mainline": True, "role": "leader"}, 9.5, up_trend(), MarketRiskResult("risk_on", True, 0.7), risk_config())
    assert result.urgency == "防守"


def test_stop_loss_strong_does_not_protect_clear() -> None:
    result = StopLoss().check({"is_top5_mainline": True, "role": "leader"}, 8.5, down_trend(), MarketRiskResult("weak", False, 0.2), risk_config())
    assert result.urgency == "清仓"
