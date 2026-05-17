from __future__ import annotations

import csv
import base64
import json
import logging
import os
import secrets
import threading
from functools import lru_cache
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import func

from backend.config import load_config
from backend.db import (
    DailyKline,
    EvaluationResult,
    LeaderRadarRecord,
    LianbanRecord,
    LimitUpRecord,
    MainlineHistory,
    MainlineRadarRecord,
    ManualPosition,
    RoleAssignment,
    SectorMapping,
    StageAnalysis,
    StrategySignal,
    get_system_meta,
    get_session,
    init_db,
)
from backend.engine.daily_runner import DailyRunner


logger = logging.getLogger(__name__)


class PositionCreate(BaseModel):
    symbol: str = Field(min_length=6, max_length=20)
    name: str = ""
    entry_price: float = Field(gt=0)
    entry_date: date
    quantity: int = Field(gt=0)
    stop_loss: float | None = Field(default=None, ge=0)
    notes: str | None = None


def _frontend_dist_path() -> Path:
    return Path(__file__).resolve().parents[1] / "主线龙头交易系统" / "dist"


def create_app(config: dict[str, Any] | None = None) -> FastAPI:
    app_config = config or load_config()
    init_db(db_path=str(app_config["system"]["db_path"]))
    app = FastAPI(title="主线龙头交易系统 API", version=str(app_config["system"].get("version", "0.1.0")))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    _install_basic_auth(app)

    @app.on_event("startup")
    def bootstrap_positions() -> None:
        _bootstrap_positions_from_env()
        _start_daily_bootstrap_if_enabled(app_config)

    @app.get("/api/status")
    def status() -> dict[str, Any]:
        latest_date = _latest_trading_date()
        with get_session() as session:
            meta = get_system_meta(session)
        return {
            "status": "ok",
            "latest_trade_date": latest_date.isoformat() if latest_date else "",
            "updated_at": datetime.now(UTC).isoformat(),
            "trade_day": {
                "last_phase": meta.get("trade_day.last_phase", ""),
                "last_message": meta.get("trade_day.last_message", ""),
                "last_detail": meta.get("trade_day.last_detail", ""),
                "last_run_at": meta.get("trade_day.last_run_at", ""),
            },
        }

    @app.get("/api/evaluation")
    def evaluation() -> dict[str, Any]:
        target_date = _latest_trading_date()
        if target_date is None:
            return _empty_evaluation()
        mainlines = _mainlines(target_date)
        observations = _evaluations(target_date, mainlines)
        focus_pool = [item for item in observations if item["buy_grade"] in {"A", "B"} and item["action"] != "deny"][:10]
        return {
            "date": target_date.isoformat(),
            "market_risk": {"regime": "neutral", "breadth": 0.5, "index_above_ma20": True},
            "mainline_top5": mainlines[:5],
            "focus_pool": focus_pool,
            "lianban_pool": _lianban_pool(target_date),
            "strategy_signal_pool": _strategy_signal_pool(target_date, mainlines, {item["symbol"] for item in focus_pool}),
            "sell_signals": _sell_signals(observations),
            "stage_denied": [item for item in observations if item["action"] == "deny" and "阶段" in item["action_text"]],
            "observation_pool": observations,
        }

    @app.get("/api/radar")
    def radar() -> dict[str, Any]:
        target_date = _latest_trading_date()
        if target_date is None:
            return {"date": "", "mainline_radar": [], "risk_warnings": []}
        return {
            "date": target_date.isoformat(),
            "mainline_radar": _mainline_radar(target_date),
            "risk_warnings": [],
        }

    @app.get("/api/positions")
    def positions() -> list[dict[str, Any]]:
        latest_date = _latest_trading_date()
        with get_session() as session:
            rows = session.query(ManualPosition).order_by(ManualPosition.entry_date.desc()).all()
        return [_position_payload(row, latest_date) for row in rows]

    @app.post("/api/positions")
    def create_position(payload: PositionCreate) -> dict[str, Any]:
        symbol = _normalize_symbol(payload.symbol)
        with get_session() as session:
            row = (
                session.query(ManualPosition)
                .filter(ManualPosition.symbol == symbol, ManualPosition.entry_date == payload.entry_date)
                .one_or_none()
            )
            if row is None:
                row = ManualPosition(
                    symbol=symbol,
                    name=payload.name or _stock_name(symbol) or symbol,
                    entry_price=payload.entry_price,
                    entry_date=payload.entry_date,
                    quantity=payload.quantity,
                    stop_loss=payload.stop_loss,
                    notes=payload.notes,
                )
                session.add(row)
            else:
                row.name = payload.name or _stock_name(symbol) or row.name
                row.entry_price = payload.entry_price
                row.quantity = payload.quantity
                row.stop_loss = payload.stop_loss
                row.notes = payload.notes
        latest_date = _latest_trading_date()
        with get_session() as session:
            saved = (
                session.query(ManualPosition)
                .filter(ManualPosition.symbol == symbol, ManualPosition.entry_date == payload.entry_date)
                .one()
            )
            return _position_payload(saved, latest_date)

    @app.get("/api/watchlist")
    def watchlist() -> list[dict[str, Any]]:
        latest_date = _latest_trading_date()
        return _watchlist_payload(latest_date)

    @app.get("/api/backtest")
    def backtest() -> dict[str, Any]:
        return {
            "strategy_stats": _csv_rows(Path("output/signal_eval_report.csv")),
            "stage_stats": _csv_rows(Path("output/signal_eval_by_stage.csv")),
        }

    frontend_dist = _frontend_dist_path()
    if frontend_dist.exists():
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")

    return app


def _install_basic_auth(app: FastAPI) -> None:
    username = os.getenv("APP_USERNAME", "").strip()
    password = os.getenv("APP_PASSWORD", "")
    print(
        "BASIC_AUTH_CONFIG "
        f"username_present={bool(username)} "
        f"password_present={bool(password)}",
        flush=True,
    )
    if not username or not password:
        logger.warning("Basic auth disabled: APP_USERNAME or APP_PASSWORD is not configured")
        return
    logger.info("Basic auth enabled")
    print("BASIC_AUTH_ENABLED true", flush=True)

    @app.middleware("http")
    async def basic_auth(request: Request, call_next: Any) -> Response:
        if request.method == "OPTIONS":
            return await call_next(request)
        auth_header = request.headers.get("authorization", "")
        if _valid_basic_auth(auth_header, username, password):
            return await call_next(request)
        return Response(
            content="Authentication required",
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers={"WWW-Authenticate": 'Basic realm="Stock Trading System"'},
        )


def _valid_basic_auth(auth_header: str, username: str, password: str) -> bool:
    scheme, _, encoded = auth_header.partition(" ")
    if scheme.lower() != "basic" or not encoded:
        return False
    try:
        decoded = base64.b64decode(encoded).decode("utf-8")
    except Exception:
        return False
    provided_username, separator, provided_password = decoded.partition(":")
    if not separator:
        return False
    return secrets.compare_digest(provided_username, username) and secrets.compare_digest(provided_password, password)


def _bootstrap_positions_from_env() -> None:
    raw_positions = os.getenv("INITIAL_POSITIONS_JSON", "").strip()
    if not raw_positions:
        return
    try:
        positions = json.loads(raw_positions)
    except json.JSONDecodeError as exc:
        logger.warning("INITIAL_POSITIONS_JSON is invalid JSON: %s", exc)
        return
    if not isinstance(positions, list):
        logger.warning("INITIAL_POSITIONS_JSON must be a JSON array")
        return

    imported = 0
    with get_session() as session:
        for item in positions:
            if not isinstance(item, dict):
                continue
            try:
                symbol = _normalize_symbol(str(item["symbol"]))
                entry_date = date.fromisoformat(str(item["entry_date"]))
                entry_price = float(item["entry_price"])
                quantity = int(item["quantity"])
            except (KeyError, TypeError, ValueError) as exc:
                logger.warning("Skip invalid initial position: %s", exc)
                continue
            row = (
                session.query(ManualPosition)
                .filter(ManualPosition.symbol == symbol, ManualPosition.entry_date == entry_date)
                .one_or_none()
            )
            stop_loss = item.get("stop_loss")
            stop_loss_value = float(stop_loss) if stop_loss not in (None, "") else None
            name = str(item.get("name") or _stock_name(symbol) or symbol)
            notes = item.get("notes")
            if row is None:
                session.add(
                    ManualPosition(
                        symbol=symbol,
                        name=name,
                        entry_price=entry_price,
                        entry_date=entry_date,
                        quantity=quantity,
                        stop_loss=stop_loss_value,
                        notes=str(notes) if notes is not None else None,
                    )
                )
            else:
                row.name = name
                row.entry_price = entry_price
                row.quantity = quantity
                row.stop_loss = stop_loss_value
                row.notes = str(notes) if notes is not None else None
            imported += 1
    if imported:
        logger.info("Bootstrapped %s positions from INITIAL_POSITIONS_JSON", imported)
        print(f"BOOTSTRAP_POSITIONS imported={imported}", flush=True)


def _start_daily_bootstrap_if_enabled(config: dict[str, Any]) -> None:
    if os.getenv("RUN_DAILY_ON_STARTUP", "").strip().lower() not in {"1", "true", "yes", "on"}:
        return

    def run_daily() -> None:
        print("DAILY_BOOTSTRAP started", flush=True)
        try:
            result = DailyRunner(config).run()
            print(
                "DAILY_BOOTSTRAP finished "
                f"focus={len(result.focus_pool)} "
                f"observation={len(result.observation_pool)} "
                f"radar={len(result.radar_results)} "
                f"risk={len(result.risk_warnings)} "
                f"skipped={result.sync_result.skipped}",
                flush=True,
            )
        except Exception as exc:
            logger.exception("Daily bootstrap failed")
            print(f"DAILY_BOOTSTRAP failed: {exc}", flush=True)

    thread = threading.Thread(target=run_daily, name="daily-bootstrap", daemon=True)
    thread.start()


app = create_app()


def _latest_trading_date() -> date | None:
    with get_session() as session:
        trading_date = session.query(func.max(DailyKline.date)).scalar()
        if trading_date is not None:
            return trading_date
        for model in (EvaluationResult, MainlineHistory, MainlineRadarRecord):
            value = session.query(func.max(model.date)).scalar()
            if value is not None:
                return value
    return None


def _empty_evaluation() -> dict[str, Any]:
    return {
        "date": "",
        "market_risk": {"regime": "neutral", "breadth": 0, "index_above_ma20": False},
        "mainline_top5": [],
        "focus_pool": [],
        "lianban_pool": [],
        "strategy_signal_pool": [],
        "sell_signals": [],
        "stage_denied": [],
        "observation_pool": [],
    }


def _mainlines(target_date: date) -> list[dict[str, Any]]:
    with get_session() as session:
        rows = session.query(MainlineHistory).filter(MainlineHistory.date == target_date).order_by(MainlineHistory.rank).all()
        roles = session.query(RoleAssignment).filter(RoleAssignment.date == target_date).all()
    leaders_by_sector: dict[str, str] = {}
    for role in sorted(roles, key=lambda item: item.score, reverse=True):
        if role.role == "leader" and role.sector_name and role.sector_name not in leaders_by_sector:
            leaders_by_sector[role.sector_name] = role.symbol
    payload = []
    for row in rows:
        factors = _loads(row.factors_json, {})
        payload.append(
            {
                "sector_name": row.sector_name,
                "mainline_score": row.mainline_score,
                "mainline_status": row.mainline_status,
                "rank": row.rank,
                "limit_up_count": int(factors.get("limit_up_count", 0) or 0),
                "lianban_count": int(factors.get("lianban_count", 0) or 0),
                "leader": leaders_by_sector.get(row.sector_name, ""),
            }
        )
    return payload


def _evaluations(target_date: date, mainlines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    with get_session() as session:
        rows = session.query(EvaluationResult).filter(EvaluationResult.date == target_date).all()
    return [_stock_focus_payload(row, mainlines) for row in rows]


def _stock_focus_payload(row: EvaluationResult, mainlines: list[dict[str, Any]]) -> dict[str, Any]:
    data = _loads(row.signals_json, {})
    symbol = str(data.get("symbol") or row.symbol)
    display_name = str(data.get("name") or "")
    if not display_name or display_name == symbol:
        display_name = _stock_name(symbol) or symbol
    latest = _latest_kline(symbol)
    signal = _latest_signal(row.date, symbol, str(data.get("strategy_name", "")))
    signal_json = _loads(signal.signal_json if signal else "", {})
    stage = _stage(row.date, symbol)
    sector = str(data.get("sector", ""))
    sector_detail = next((item for item in mainlines if item["sector_name"] == sector), {})
    return {
        "symbol": symbol,
        "name": display_name,
        "sector": sector,
        "role": _frontend_role(str(data.get("role", ""))),
        "stage": str(data.get("stage") or getattr(stage, "stage", "")),
        "current_price": float(latest.close if latest else 0.0),
        "pct_chg": _pct_chg(latest),
        "buy_grade": _frontend_grade(str(data.get("buy_grade") or row.buy_grade)),
        "buy_score": float(data.get("buy_score", 0.0) or 0.0),
        "strategy_name": str(data.get("strategy_name", "")),
        "action": _frontend_action(str(data.get("action", ""))),
        "action_text": str(data.get("action_text", "")),
        "confidence": float(data.get("confidence", 0.0) or 0.0),
        "data_quality": str(data.get("data_quality", "full")),
        "entry_price_low": float(data.get("entry_low", data.get("entry_price_low", 0.0)) or 0.0),
        "entry_price_high": float(data.get("entry_high", data.get("entry_price_high", 0.0)) or 0.0),
        "stop_loss_price": float(data.get("stop_loss", data.get("stop_loss_price", 0.0)) or 0.0),
        "position_pct": float(data.get("position_pct", 0.0) or 0.0),
        "sell_urgency": str(data.get("sell_urgency", row.sell_urgency)),
        "risk_warnings": list(data.get("risk_warnings", []) or []),
        "trend": {"state": "unknown", "ma_alignment": "unknown", "slope_20": 0},
        "volume_price": {"volume_ratio": 0, "status": ""},
        "sector_detail": {
            "sector_score": float(sector_detail.get("mainline_score", 0.0) or 0.0),
            "mainline_status": str(sector_detail.get("mainline_status", "")),
        },
        "deny_result": str(signal_json.get("reason") or data.get("action_text") or ""),
        "llm_review": _llm_review(row.date, symbol),
    }


def _strategy_signal_pool(target_date: date, mainlines: list[dict[str, Any]], focus_symbols: set[str]) -> list[dict[str, Any]]:
    excluded = {"mainline_detect", "leader_detect"}
    with get_session() as session:
        rows = (
            session.query(StrategySignal)
            .filter(StrategySignal.date == target_date, StrategySignal.strategy_name.notin_(excluded), StrategySignal.action.in_(["buy", "watch", "add"]))
            .order_by(StrategySignal.confidence.desc())
            .all()
        )
        roles = session.query(RoleAssignment).filter(RoleAssignment.date == target_date).all()
    role_by_symbol = {role.symbol: role for role in sorted(roles, key=lambda item: item.score, reverse=True)}
    payload: list[dict[str, Any]] = []
    for row in rows:
        data = _loads(row.signal_json, {})
        symbol = row.symbol
        display_name = str(data.get("name") or "")
        if not display_name or display_name == symbol:
            display_name = _stock_name(symbol) or symbol
        role = role_by_symbol.get(symbol)
        sector = str(getattr(role, "sector_name", "") or data.get("sector", ""))
        mainline = next((item for item in mainlines if item["sector_name"] == sector), {})
        latest = _latest_kline(symbol)
        payload.append(
            {
                "symbol": symbol,
                "name": display_name,
                "sector": sector,
                "role": _frontend_role(str(getattr(role, "role", "") or data.get("role", ""))),
                "strategy_name": row.strategy_name,
                "action": _frontend_action(row.action),
                "action_text": str(data.get("action_text") or data.get("reason") or ""),
                "confidence": float(row.confidence or 0.0),
                "grade": _frontend_grade(str(data.get("grade", "C"))),
                "is_focus": symbol in focus_symbols,
                "current_price": float(latest.close if latest else 0.0),
                "pct_chg": _pct_chg(latest),
                "entry_price_low": float(data.get("entry_price_low", 0.0) or 0.0),
                "entry_price_high": float(data.get("entry_price_high", 0.0) or 0.0),
                "stop_loss_price": float(data.get("stop_loss_price", 0.0) or 0.0),
                "position_pct": float(data.get("position_pct", 0.0) or 0.0),
                "sector_score": float(mainline.get("mainline_score", 0.0) or 0.0),
                "sector_status": str(mainline.get("mainline_status", "")),
                "data_quality": row.data_quality,
            }
        )
    return payload[:30]


def _lianban_pool(target_date: date) -> list[dict[str, Any]]:
    with get_session() as session:
        rows = session.query(LianbanRecord).filter(LianbanRecord.date == target_date, LianbanRecord.lianban_count >= 1).all()
        limits = session.query(LimitUpRecord).filter(LimitUpRecord.date == target_date).all()
        signals = (
            session.query(StrategySignal)
            .filter(StrategySignal.date == target_date, StrategySignal.strategy_name == "lianban_leader_template")
            .all()
        )
        stages = session.query(StageAnalysis).filter(StageAnalysis.date == target_date).all()
        mappings = session.query(SectorMapping).all()
        mainlines = session.query(MainlineHistory).filter(MainlineHistory.date == target_date).all()
    limit_by_symbol = {_normalize_symbol(row.symbol): row for row in limits}
    signal_by_symbol = {_normalize_symbol(row.symbol): row for row in signals}
    stage_by_symbol = {_normalize_symbol(row.symbol): row for row in stages}
    sector_by_symbol: dict[str, str] = {}
    for mapping in mappings:
        sector_by_symbol.setdefault(_normalize_symbol(mapping.symbol), mapping.sector_name)
    mainline_by_sector = {row.sector_name: row for row in mainlines}
    latest_by_symbol: dict[str, dict[str, Any]] = {}
    for row in rows:
        symbol = _normalize_symbol(row.symbol)
        current = latest_by_symbol.get(symbol)
        if current is None or row.lianban_count > current["lianban_count"]:
            latest_by_symbol[symbol] = {"symbol": symbol, "lianban_count": row.lianban_count}
    payload = []
    for item in sorted(latest_by_symbol.values(), key=lambda value: int(value["lianban_count"]), reverse=True):
        symbol = str(item["symbol"])
        lianban_count = int(item["lianban_count"])
        if lianban_count > 2:
            continue
        signal = signal_by_symbol.get(symbol)
        data = _loads(signal.signal_json if signal else "", {})
        action_text = str(data.get("action_text") or "")
        limit = limit_by_symbol.get(symbol)
        stage = stage_by_symbol.get(symbol)
        sector = sector_by_symbol.get(symbol, "")
        mainline = mainline_by_sector.get(sector)
        latest = _latest_kline(symbol)
        score, reasons, action, grade = _lianban_potential_score(
            lianban_count=lianban_count,
            first_time=str(getattr(limit, "first_time", "") or ""),
            stage_name=str(getattr(stage, "stage", "") or ""),
            sector_rank=int(getattr(mainline, "rank", 999) or 999) if mainline else 999,
            pct_chg=_pct_chg(latest),
        )
        payload.append(
            {
                "symbol": symbol,
                "name": _stock_name(symbol) or symbol,
                "lianban_count": lianban_count,
                "limit_type": str(getattr(limit, "limit_type", "") or ""),
                "first_time": _format_limit_time(str(getattr(limit, "first_time", "") or "")),
                "open_count": int(getattr(limit, "open_count", 0) or 0),
                "strategy_name": "lianban_leader_template",
                "action": _frontend_action(action),
                "grade": _frontend_grade(grade),
                "confidence": round(score / 100.0, 2),
                "score": round(score, 1),
                "sector": sector,
                "stage": str(getattr(stage, "stage", "") or ""),
                "action_text": action_text if signal and signal.action == "deny" else "；".join(reasons),
            }
        )
    return sorted(payload, key=lambda value: float(value["score"]), reverse=True)[:20]


def _lianban_potential_score(lianban_count: int, first_time: str, stage_name: str, sector_rank: int, pct_chg: float) -> tuple[float, list[str], str, str]:
    score = 0.0
    reasons: list[str] = []
    if lianban_count == 2:
        score += 42
        reasons.append("二板确认，开始具备连板辨识度")
    else:
        score += 26
        reasons.append("首板启动，进入二板观察池")

    first_minutes = _limit_time_minutes(first_time)
    if first_minutes and first_minutes <= 9 * 60 + 35:
        score += 24
        reasons.append("早盘快速封板，资金抢筹明显")
    elif first_minutes and first_minutes <= 10 * 60:
        score += 18
        reasons.append("上午封板，强度较好")
    elif first_minutes and first_minutes <= 11 * 60:
        score += 10
        reasons.append("封板时间尚可，需要看次日承接")
    else:
        score += 4
        reasons.append("封板偏晚，优先级降低")

    if stage_name == "stage_1_start":
        score += 16
        reasons.append("处于启动初期，适合识别连板潜力")
    elif stage_name == "stage_2_rising":
        score += 10
        reasons.append("处于主升阶段，趋势仍有承接")
    elif stage_name == "stage_0_accumulation":
        score += 6
        reasons.append("底部蓄势转强，需要二板验证")
    elif stage_name in {"stage_3_distribution", "stage_4_decline"}:
        score -= 18
        reasons.append("阶段偏高或退潮，连板持续性打折")

    if sector_rank <= 5:
        score += 12
        reasons.append("处于当前主线/强势板块")
    elif sector_rank <= 10:
        score += 6
        reasons.append("板块有一定热度")
    else:
        reasons.append("板块共振不足")

    if pct_chg >= 9.5:
        score += 6
        reasons.append("涨停强度确认")

    score = max(0.0, min(100.0, score))
    if score >= 72:
        return score, reasons, "watch", "B"
    if score >= 58:
        return score, reasons, "watch", "C"
    return score, reasons, "watch", "NONE"


def _limit_time_minutes(value: str) -> int | None:
    text = value.strip()
    if not text:
        return None
    if ":" in text:
        parts = text.split(":")
        return int(parts[0]) * 60 + int(parts[1])
    if len(text) >= 4 and text[:4].isdigit():
        return int(text[:2]) * 60 + int(text[2:4])
    return None


def _format_limit_time(value: str) -> str:
    text = value.strip()
    if len(text) >= 4 and text[:4].isdigit():
        return f"{text[:2]}:{text[2:4]}"
    return text


@lru_cache(maxsize=1)
def _stock_name_map() -> dict[str, str]:
    config = load_config()
    candidates = [
        Path(str(config.get("stock_pool", {}).get("watchlist_path", ""))),
        Path("sample_data/tushare_watchlist.csv"),
    ]
    names: dict[str, str] = {}
    for path in candidates:
        if not path or not path.exists():
            continue
        with path.open(newline="", encoding="utf-8") as file:
            for row in csv.DictReader(file):
                symbol = str(row.get("symbol") or "").strip()
                name = str(row.get("name") or "").strip()
                if symbol and name:
                    names[symbol] = name
        if names:
            break
    return names


def _stock_name(symbol: str) -> str:
    return _stock_name_map().get(_normalize_symbol(symbol), "")


def _sell_signals(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for item in observations:
        if item["sell_urgency"] != "无" or item["action"] in {"sell", "reduce"}:
            result.append(
                {
                    "symbol": item["symbol"],
                    "name": item["name"],
                    "reason": item["action_text"],
                    "suggested_action": item["sell_urgency"] if item["sell_urgency"] != "无" else item["action"],
                }
            )
    return result


def _mainline_radar(target_date: date) -> list[dict[str, Any]]:
    with get_session() as session:
        rows = session.query(MainlineRadarRecord).filter(MainlineRadarRecord.date == target_date).order_by(MainlineRadarRecord.radar_score.desc()).all()
        leaders = session.query(LeaderRadarRecord).filter(LeaderRadarRecord.date == target_date).all()
    leaders_by_sector: dict[str, list[LeaderRadarRecord]] = {}
    for leader in leaders:
        leaders_by_sector.setdefault(leader.sector_name, []).append(leader)
    payload = []
    for row in rows:
        suggested = [
            {"symbol": item.symbol, "name": item.name, "probability": item.leader_probability}
            for item in sorted(leaders_by_sector.get(row.sector_name, []), key=lambda item: item.leader_probability, reverse=True)[:5]
        ]
        if not suggested:
            suggested = [
                {"symbol": symbol, "name": _stock_name(symbol) or symbol, "probability": 0}
                for symbol in _loads(row.suggested_watch, [])
            ]
        else:
            suggested = [
                {
                    "symbol": item["symbol"],
                    "name": _stock_name(item["symbol"]) or item["name"],
                    "probability": item["probability"],
                }
                for item in suggested
            ]
        payload.append(
            {
                "sector_name": row.sector_name,
                "radar_score": row.radar_score,
                "signal_type": row.signal_type,
                "stage_filter": row.stage_filter,
                "reason": _loads(row.reason, []),
                "suggested_watch": suggested,
            }
        )
    return payload


def _position_payload(row: ManualPosition, latest_date: date | None) -> dict[str, Any]:
    latest = _latest_kline(row.symbol)
    current_price = float(latest.close if latest else row.entry_price)
    pnl_amount = (current_price - row.entry_price) * row.quantity
    pnl_pct = (current_price - row.entry_price) / max(row.entry_price, 1e-9) * 100
    stage = _stage(latest_date, row.symbol) if latest_date else None
    position_context = _position_context(row.symbol)
    hold_days = (date.today() - row.entry_date).days
    position_context["hold_days"] = hold_days
    action_suggestion, action_reason = _position_action(row, latest, stage, pnl_pct, position_context)
    return {
        "symbol": row.symbol,
        "name": row.name,
        "buy_price": row.entry_price,
        "entry_date": row.entry_date.isoformat(),
        "quantity": row.quantity,
        "current_price": current_price,
        "pct_chg": _pct_chg(latest),
        "stop_loss": row.stop_loss or 0.0,
        "hold_days": hold_days,
        "stage": getattr(stage, "stage", ""),
        "trend_state": "unknown",
        "action_suggestion": action_suggestion,
        "action_reason": action_reason,
        "market_value": round(current_price * row.quantity, 2),
        "pnl_amount": round(pnl_amount, 2),
        "pnl_pct": round(pnl_pct, 2),
        "notes": row.notes or "",
    }


def _position_action(
    row: ManualPosition,
    latest: DailyKline | None,
    stage: StageAnalysis | None,
    pnl_pct: float,
    context: dict[str, Any] | None = None,
) -> tuple[str, str]:
    context = context or {}
    current_price = float(latest.close if latest else row.entry_price)
    stage_name = str(getattr(stage, "stage", "") or "")
    risk_level = str(getattr(stage, "risk_level", "") or "")
    daily_pct = _pct_chg(latest)
    stop_loss = float(row.stop_loss or 0.0)
    support_5d = float(context.get("support_5d", 0.0) or 0.0)
    ma20 = float(context.get("ma20", 0.0) or 0.0)
    sector_name = str(context.get("sector_name", "") or "")
    sector_rank = int(context.get("sector_rank", 999) or 999)
    sector_status = str(context.get("sector_status", "") or "")
    hold_days = int(context.get("hold_days", 0) or 0)
    is_long_term = bool(context.get("is_long_term", False) or hold_days >= 180)
    breakeven_gap = (row.entry_price - current_price) / max(current_price, 1e-9) * 100
    broken_5d = support_5d > 0 and current_price < support_5d
    broken_ma20 = ma20 > 0 and current_price < ma20
    sector_text = f"{sector_name}板块" if sector_name else "所属板块"
    if stop_loss > 0 and current_price <= stop_loss:
        return "sell", f"现价 {current_price:.2f} 已触及止损 {stop_loss:.2f}，优先卖出或严格执行风控"
    if is_long_term:
        return _long_term_position_action(
            row=row,
            pnl_pct=pnl_pct,
            current_price=current_price,
            stage_name=stage_name,
            sector_text=sector_text,
            sector_rank=sector_rank,
            sector_status=sector_status,
            support_5d=support_5d,
            ma20=ma20,
            broken_5d=broken_5d,
            broken_ma20=broken_ma20,
            breakeven_gap=breakeven_gap,
        )
    if stage_name == "stage_4_decline" or (pnl_pct <= -10 and broken_5d and broken_ma20):
        return "sell", (
            f"浮亏 {pnl_pct:.2f}%，同时跌破5日低点"
            f"{support_5d:.2f}和20日均线{ma20:.2f}，持仓逻辑失效，建议卖出"
        )
    if stage_name == "stage_3_distribution" and pnl_pct > 0:
        return "reduce", f"高位分歧且仍有浮盈 {pnl_pct:.2f}%，不是清仓信号，建议先分批落袋，剩余仓位看能否重新转强"
    if stage_name == "stage_3_distribution" and pnl_pct <= 0:
        return "reduce", "高位分歧但未盈利，建议降低仓位，等待重新转强再说"
    if risk_level in {"high", "critical"}:
        return "reduce", f"阶段风险为 {risk_level}，建议降低仓位；若放量跌破前低再升级为卖出"
    if pnl_pct >= 12 and daily_pct < 0:
        return "reduce", f"浮盈 {pnl_pct:.2f}% 且当日走弱，建议先锁定部分利润"
    if pnl_pct <= -10:
        if stage_name in {"stage_1_start", "stage_2_rising"} and not broken_5d:
            return "reduce", (
                f"浮亏 {pnl_pct:.2f}%但仍处于{_stage_text(stage_name)}，且未跌破5日低点{support_5d:.2f}；"
                "建议先降仓控风险，等放量反包或站回成本线再恢复"
            )
        return "reduce", (
            f"浮亏 {pnl_pct:.2f}%，尚未同时确认破位；建议减仓，若继续跌破5日低点"
            f"{support_5d:.2f}或20日均线{ma20:.2f}再卖出"
        )
    if pnl_pct <= -5:
        return "reduce", f"浮亏 {pnl_pct:.2f}%，未到强制止损；先降低仓位，观察是否站回20日均线{ma20:.2f}"
    if stage_name in {"stage_1_start", "stage_2_rising"}:
        sector_hint = f"，{sector_text}排名{sector_rank}" if sector_rank < 999 else f"，{sector_text}未进入主线Top"
        return "hold", f"{_stage_text(stage_name)}{sector_hint}；持有观察，跌破5日低点{support_5d:.2f}或转入高位分歧再处理"
    if latest is None:
        return "hold", "暂无最新行情，只保留成本持仓，等待行情更新后重新判断"
    if sector_status:
        return "hold", f"暂无明确破位信号，{sector_text}状态为{sector_status}，继续持有观察"
    return "hold", "暂无明确破位或减仓信号，继续持有观察"


def _long_term_position_action(
    *,
    row: ManualPosition,
    pnl_pct: float,
    current_price: float,
    stage_name: str,
    sector_text: str,
    sector_rank: int,
    sector_status: str,
    support_5d: float,
    ma20: float,
    broken_5d: bool,
    broken_ma20: bool,
    breakeven_gap: float,
) -> tuple[str, str]:
    sector_hint = f"{sector_text}主线排名{sector_rank}，状态{sector_status}" if sector_rank < 999 else f"{sector_text}暂未进入主线Top"
    breakeven_text = f"距离成本价 {row.entry_price:.2f} 还需上涨约 {breakeven_gap:.2f}%"
    if pnl_pct >= -3:
        return "hold", (
            f"长线持仓已接近回本，{breakeven_text}。先定位为成本修复仓："
            f"若放量站稳成本线可继续持有，若回落跌破5日低点{support_5d:.2f}再减仓。{sector_hint}"
        )
    if stage_name in {"stage_1_start", "stage_2_rising"} and not broken_5d:
        return "hold", (
            f"长线持仓不宜按短线亏损直接卖出，当前为{_stage_text(stage_name)}且未跌破5日低点{support_5d:.2f}。"
            f"{breakeven_text}；策略是等站回20日均线{ma20:.2f}和成本线确认修复，未确认前不加仓。{sector_hint}"
        )
    if pnl_pct <= -15 and broken_5d and broken_ma20:
        return "reduce", (
            f"长线仓浮亏 {pnl_pct:.2f}% 且跌破5日低点{support_5d:.2f}/20日均线{ma20:.2f}，"
            "说明修复失败。不是因为亏损机械卖出，而是趋势结构未修复，建议先降低仓位，保留小仓等产业/板块重新走强。"
        )
    if broken_ma20 or broken_5d:
        return "reduce", (
            f"长线仓仍未完成回本修复，{breakeven_text}。短线结构偏弱，建议先减仓控波动；"
            f"重新站回20日均线{ma20:.2f}后再评估是否恢复仓位。{sector_hint}"
        )
    return "hold", (
        f"长线仓目前没有明确破位，{breakeven_text}。先定位为修复观察："
        f"看能否站回20日均线{ma20:.2f}并接近成本线，不建议在未确认前盲目补仓。{sector_hint}"
    )


def _position_context(symbol: str) -> dict[str, Any]:
    with get_session() as session:
        rows = session.query(DailyKline).filter(DailyKline.symbol == symbol).order_by(DailyKline.date.desc()).limit(20).all()
        position = session.query(ManualPosition).filter(ManualPosition.symbol == symbol).order_by(ManualPosition.entry_date.desc()).first()
        mapping = session.query(SectorMapping).filter(SectorMapping.symbol == symbol).first()
        latest_date = rows[0].date if rows else None
        mainline = None
        if mapping is not None and latest_date is not None:
            mainline = (
                session.query(MainlineHistory)
                .filter(MainlineHistory.date == latest_date, MainlineHistory.sector_name == mapping.sector_name)
                .one_or_none()
            )
    lows = [float(row.low or 0.0) for row in rows[:5]]
    closes = [float(row.close or 0.0) for row in rows]
    return {
        "support_5d": min(lows) if lows else 0.0,
        "ma20": sum(closes) / len(closes) if closes else 0.0,
        "sector_name": getattr(mapping, "sector_name", ""),
        "sector_rank": getattr(mainline, "rank", 999),
        "sector_status": getattr(mainline, "mainline_status", ""),
        "is_long_term": _is_long_term_note(getattr(position, "notes", "") or ""),
    }


def _is_long_term_note(notes: str) -> bool:
    return any(keyword in notes for keyword in ("长线", "中长线", "一年", "1年", "长期"))


def _stage_text(stage_name: str) -> str:
    labels = {
        "stage_0_accumulation": "底部蓄势",
        "stage_1_start": "启动初期",
        "stage_2_rising": "主升阶段",
        "stage_3_distribution": "高位分歧",
        "stage_4_decline": "下跌退潮",
    }
    return labels.get(stage_name, stage_name or "阶段未知")


def _watchlist_payload(latest_date: date | None) -> list[dict[str, Any]]:
    rows = _manual_watchlist_rows()
    latest_by_symbol: dict[str, DailyKline | None] = {}
    evaluations: dict[str, EvaluationResult] = {}
    stages: dict[str, StageAnalysis] = {}
    if latest_date is not None:
        symbols = [row["symbol"] for row in rows]
        with get_session() as session:
            eval_rows = session.query(EvaluationResult).filter(EvaluationResult.date == latest_date, EvaluationResult.symbol.in_(symbols)).all()
            stage_rows = session.query(StageAnalysis).filter(StageAnalysis.date == latest_date, StageAnalysis.symbol.in_(symbols)).all()
        evaluations = {row.symbol: row for row in eval_rows}
        stages = {row.symbol: row for row in stage_rows}
    payload = []
    for row in rows:
        symbol = row["symbol"]
        latest = latest_by_symbol.setdefault(symbol, _latest_kline(symbol))
        eval_row = evaluations.get(symbol)
        eval_data = _loads(eval_row.signals_json, {}) if eval_row else {}
        stage = stages.get(symbol)
        payload.append(
            {
                "symbol": symbol,
                "name": row["name"] or _stock_name(symbol) or symbol,
                "group": row["group"],
                "source": row["source"],
                "current_price": float(latest.close if latest else 0.0),
                "pct_chg": _pct_chg(latest),
                "stage": str(eval_data.get("stage") or getattr(stage, "stage", "")),
                "buy_grade": _frontend_grade(str(eval_data.get("buy_grade") or (eval_row.buy_grade if eval_row else "NONE"))),
                "strategy_name": str(eval_data.get("strategy_name", "")),
                "action": _frontend_action(str(eval_data.get("action", ""))),
                "action_text": str(eval_data.get("action_text", "")),
                "risk_warnings": list(eval_data.get("risk_warnings", []) or []),
            }
        )
    return payload


def _manual_watchlist_rows() -> list[dict[str, str]]:
    path = Path("sample_data/manual_watchlist.csv")
    if not path.exists():
        return []
    rows: list[dict[str, str]] = []
    with path.open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            symbol = str(row.get("symbol") or "").strip()
            if not symbol:
                continue
            rows.append(
                {
                    "symbol": symbol,
                    "name": str(row.get("name") or "").strip(),
                    "source": str(row.get("source") or "").strip(),
                    "group": str(row.get("group") or "自选股").strip(),
                }
            )
    return rows


def _latest_kline(symbol: str) -> DailyKline | None:
    with get_session() as session:
        return session.query(DailyKline).filter(DailyKline.symbol == symbol).order_by(DailyKline.date.desc()).first()


def _latest_signal(target_date: date, symbol: str, strategy_name: str) -> StrategySignal | None:
    with get_session() as session:
        query = session.query(StrategySignal).filter(StrategySignal.date == target_date, StrategySignal.symbol == symbol)
        if strategy_name:
            query = query.filter(StrategySignal.strategy_name == strategy_name)
        return query.order_by(StrategySignal.updated_at.desc()).first()


def _stage(target_date: date | None, symbol: str) -> StageAnalysis | None:
    if target_date is None:
        return None
    with get_session() as session:
        return session.query(StageAnalysis).filter(StageAnalysis.date == target_date, StageAnalysis.symbol == symbol).one_or_none()


def _llm_review(target_date: date, symbol: str) -> str:
    with get_session() as session:
        row = (
            session.query(StrategySignal)
            .filter(StrategySignal.date == target_date, StrategySignal.symbol == symbol, StrategySignal.strategy_name == "llm_review")
            .one_or_none()
        )
    if row is None:
        return ""
    payload = _loads(row.signal_json, {})
    return str(payload.get("action_text") or payload.get("reason") or "")


def _pct_chg(row: DailyKline | None) -> float:
    if row is None:
        return 0.0
    return round((row.close - row.open) / max(row.open, 1e-9) * 100, 2)


def _frontend_grade(value: str) -> str:
    return value if value in {"A", "B", "C", "NONE", "SELL"} else "NONE"


def _frontend_action(value: str) -> str:
    return value if value in {"buy", "sell", "hold", "reduce", "deny", "watch", "add"} else "hold"


def _frontend_role(value: str) -> str:
    return "leader" if value == "leader" else "follower"


def _loads(text: str, default: Any) -> Any:
    if not text:
        return default
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default


def _normalize_symbol(value: str) -> str:
    text = value.strip().upper()
    if "." in text:
        return text
    if text.startswith(("6", "9")):
        return f"{text}.SH"
    return f"{text}.SZ"


def _csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))
