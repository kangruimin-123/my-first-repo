from __future__ import annotations

from backend.engine.grading import Evaluation


def render_terminal_report(
    focus_pool: list[Evaluation],
    observation_pool: list[Evaluation],
    mainlines: list[object],
    market_summary: str,
    radar_results: list[object] | None = None,
    risk_warnings: list[object] | None = None,
) -> str:
    """Render a compact terminal report without requiring terminal capabilities."""
    lines = [
        "=" * 58,
        "交易重点池（≤10 只）",
        "=" * 58,
        "",
        "A档 确认买点",
        _table([item for item in focus_pool if item.buy_grade == "A"]),
        "",
        "B档 观察",
        _table([item for item in focus_pool if item.buy_grade == "B"]),
        "",
        "卖出信号",
        _sell_table([item for item in focus_pool if item.sell_urgency != "无"]),
        "",
        "明日关注（雷达预警）",
        _radar_table(radar_results or []),
        "",
        "退潮预警",
        _risk_table(risk_warnings or []),
        "",
        "阶段拦截",
        _table([item for item in observation_pool if item.action == "deny" and "阶段" in item.action_text]),
        "",
        f"大盘: {market_summary}",
        "Top5 主线: " + ", ".join(f"{item.sector_name}({item.mainline_score:.0f})" for item in mainlines[:5]),
        "",
        "=" * 58,
        "完整观察池（≤50 只）",
        "=" * 58,
        _table(observation_pool[:50]),
    ]
    return "\n".join(lines)


def _table(items: list[Evaluation]) -> str:
    if not items:
        return "无"
    rows = ["股票 | 板块 | 角色 | 阶段 | 评分 | 策略 | 操作建议"]
    for item in items:
        rows.append(f"{item.symbol} | {item.sector} | {item.role} | {item.stage} | {item.buy_score:.0f} | {item.strategy_name} | {item.action_text}")
    return "\n".join(rows)


def _sell_table(items: list[Evaluation]) -> str:
    if not items:
        return "无"
    rows = ["股票 | 级别 | 原因"]
    for item in items:
        rows.append(f"{item.symbol} | {item.sell_urgency} | {item.action_text}")
    return "\n".join(rows)


def _radar_table(items: list[object]) -> str:
    if not items:
        return "无"
    rows = ["板块 | radar | 信号 | 周期 | 建议关注"]
    for item in items:
        rows.append(
            f"{item.sector_name} | {item.radar_score:.0f} | {item.signal_type} | "
            f"{item.stage_filter} | {', '.join(item.suggested_watch) or '待观察'}"
        )
    return "\n".join(rows)


def _risk_table(items: list[object]) -> str:
    if not items:
        return "无"
    rows = ["级别 | 对象 | 信号 | 原因 | 建议"]
    for item in items:
        rows.append(
            f"{item.level} | {item.target} | {item.signal_type} | "
            f"{'；'.join(item.reason)} | {item.suggested_action}"
        )
    return "\n".join(rows)
