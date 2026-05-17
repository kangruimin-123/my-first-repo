from __future__ import annotations

from html import escape
from pathlib import Path

from backend.engine.grading import Evaluation


def write_html_report(
    focus_pool: list[Evaluation],
    observation_pool: list[Evaluation],
    mainlines: list[object],
    market_summary: str,
    output_dir: Path,
    radar_results: list[object] | None = None,
    risk_warnings: list[object] | None = None,
) -> Path:
    """Write a self-contained HTML report."""
    output_dir.mkdir(parents=True, exist_ok=True)
    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>交易系统日报</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 24px; color: #172033; }}
    h1, h2 {{ margin: 0 0 12px; }}
    section {{ margin: 24px 0; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ border-bottom: 1px solid #d8dee8; padding: 8px; text-align: left; }}
    th {{ background: #f2f5f9; }}
    .grade-A {{ color: #087f5b; font-weight: 700; }}
    .grade-B {{ color: #b7791f; font-weight: 700; }}
    .sell {{ color: #c92a2a; font-weight: 700; }}
    .meta {{ color: #5c667a; }}
  </style>
</head>
<body>
  <h1>交易系统日报</h1>
  <p class="meta">大盘环境：{escape(market_summary)}</p>
  <section>
    <h2>交易重点池</h2>
    {_table(focus_pool)}
  </section>
  <section>
    <h2>Top5 主线</h2>
    <p>{escape(", ".join(f"{item.sector_name}({item.mainline_score:.0f}, {item.mainline_status})" for item in mainlines[:5]))}</p>
  </section>
  <section>
    <h2>明日关注（雷达预警）</h2>
    {_radar_table(radar_results or [])}
  </section>
  <section>
    <h2>退潮预警</h2>
    {_risk_table(risk_warnings or [])}
  </section>
  <section>
    <h2>阶段拦截</h2>
    {_table([item for item in observation_pool if item.action == "deny" and "阶段" in item.action_text])}
  </section>
  <section>
    <h2>完整观察池</h2>
    {_table(observation_pool[:50])}
  </section>
</body>
</html>
"""
    path = output_dir / "report.html"
    path.write_text(html, encoding="utf-8")
    return path


def _table(items: list[Evaluation]) -> str:
    if not items:
        return "<p>无</p>"
    rows = [
        "<table><thead><tr><th>股票</th><th>板块</th><th>角色</th><th>阶段</th><th>买入档</th><th>卖出</th><th>策略</th><th>建议</th></tr></thead><tbody>"
    ]
    for item in items:
        grade_class = f"grade-{escape(item.buy_grade)}"
        sell_class = "sell" if item.sell_urgency != "无" else ""
        rows.append(
            "<tr>"
            f"<td>{escape(item.symbol)}</td>"
            f"<td>{escape(item.sector)}</td>"
            f"<td>{escape(item.role)}</td>"
            f"<td>{escape(item.stage)}</td>"
            f"<td class='{grade_class}'>{escape(item.buy_grade)}</td>"
            f"<td class='{sell_class}'>{escape(item.sell_urgency)}</td>"
            f"<td>{escape(item.strategy_name)}</td>"
            f"<td>{escape(item.action_text)}</td>"
            "</tr>"
        )
    rows.append("</tbody></table>")
    return "\n".join(rows)


def _radar_table(items: list[object]) -> str:
    if not items:
        return "<p>无</p>"
    rows = [
        "<table><thead><tr><th>板块</th><th>radar</th><th>信号</th><th>周期</th><th>建议关注</th><th>原因</th></tr></thead><tbody>"
    ]
    for item in items:
        rows.append(
            "<tr>"
            f"<td>{escape(item.sector_name)}</td>"
            f"<td>{item.radar_score:.0f}</td>"
            f"<td>{escape(item.signal_type)}</td>"
            f"<td>{escape(item.stage_filter)}</td>"
            f"<td>{escape(', '.join(item.suggested_watch) or '待观察')}</td>"
            f"<td>{escape('；'.join(item.reason))}</td>"
            "</tr>"
        )
    rows.append("</tbody></table>")
    return "\n".join(rows)


def _risk_table(items: list[object]) -> str:
    if not items:
        return "<p>无</p>"
    rows = [
        "<table><thead><tr><th>级别</th><th>对象</th><th>类型</th><th>原因</th><th>建议</th></tr></thead><tbody>"
    ]
    for item in items:
        rows.append(
            "<tr>"
            f"<td>{escape(item.level)}</td>"
            f"<td>{escape(item.target)}</td>"
            f"<td>{escape(item.signal_type)}</td>"
            f"<td>{escape('；'.join(item.reason))}</td>"
            f"<td>{escape(item.suggested_action)}</td>"
            "</tr>"
        )
    rows.append("</tbody></table>")
    return "\n".join(rows)
