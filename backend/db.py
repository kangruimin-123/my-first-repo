from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any

from sqlalchemy import Date, DateTime, Float, Integer, String, Text, Time, UniqueConstraint, create_engine, func
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from backend.config import load_config


class Base(DeclarativeBase):
    """Base class for all ORM tables."""


def utc_now() -> datetime:
    """Return a timestamp for update columns."""
    return datetime.now(UTC).replace(tzinfo=None)


class DailyKline(Base):
    __tablename__ = "daily_kline"
    __table_args__ = (UniqueConstraint("symbol", "date", name="uq_daily_kline_symbol_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float] = mapped_column(Float, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    turnover_rate: Mapped[float | None] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class IndexKline(Base):
    __tablename__ = "index_kline"
    __table_args__ = (UniqueConstraint("code", "date", name="uq_index_kline_code_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float] = mapped_column(Float, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class DailyBasic(Base):
    __tablename__ = "daily_basic"
    __table_args__ = (UniqueConstraint("symbol", "date", name="uq_daily_basic_symbol_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    market_cap: Mapped[float | None] = mapped_column(Float)
    pe: Mapped[float | None] = mapped_column(Float)
    turnover_rate: Mapped[float | None] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class LimitUpRecord(Base):
    __tablename__ = "limit_up_records"
    __table_args__ = (UniqueConstraint("symbol", "date", name="uq_limit_up_symbol_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    limit_type: Mapped[str | None] = mapped_column(String(50))
    first_time: Mapped[str | None] = mapped_column(String(20))
    last_time: Mapped[str | None] = mapped_column(String(20))
    open_count: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class LianbanRecord(Base):
    __tablename__ = "lianban_records"
    __table_args__ = (UniqueConstraint("symbol", "date", name="uq_lianban_symbol_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    lianban_count: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class SectorMapping(Base):
    __tablename__ = "sector_mapping"
    __table_args__ = (UniqueConstraint("symbol", "sector_code", name="uq_sector_mapping_symbol_sector"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    sector_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    sector_code: Mapped[str] = mapped_column(String(40), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class SectorDaily(Base):
    __tablename__ = "sector_daily"
    __table_args__ = (UniqueConstraint("sector_name", "date", name="uq_sector_daily_name_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sector_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    pct_chg: Mapped[float | None] = mapped_column(Float)
    amount: Mapped[float | None] = mapped_column(Float)
    limit_up_count: Mapped[int | None] = mapped_column(Integer)
    lianban_count: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class Moneyflow(Base):
    __tablename__ = "moneyflow"
    __table_args__ = (UniqueConstraint("symbol", "date", name="uq_moneyflow_symbol_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    net_amount: Mapped[float | None] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class AuctionSnapshot(Base):
    __tablename__ = "auction_snapshot"
    __table_args__ = (UniqueConstraint("symbol", "date", name="uq_auction_symbol_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    open_price: Mapped[float | None] = mapped_column(Float)
    auction_amount: Mapped[float | None] = mapped_column(Float)
    auction_volume: Mapped[float | None] = mapped_column(Float)
    pct_chg: Mapped[float | None] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class IntradaySnapshot(Base):
    __tablename__ = "intraday_snapshot"
    __table_args__ = (UniqueConstraint("symbol", "date", "time", name="uq_intraday_symbol_date_time"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    time: Mapped[time] = mapped_column(Time, nullable=False)
    price: Mapped[float | None] = mapped_column(Float)
    volume: Mapped[float | None] = mapped_column(Float)
    amount: Mapped[float | None] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class MainlineHistory(Base):
    __tablename__ = "mainline_history"
    __table_args__ = (UniqueConstraint("date", "sector_name", name="uq_mainline_date_sector"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    sector_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    mainline_score: Mapped[float] = mapped_column(Float, nullable=False)
    mainline_status: Mapped[str] = mapped_column(String(40), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    factors_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class RoleAssignment(Base):
    __tablename__ = "role_assignment"
    __table_args__ = (UniqueConstraint("date", "symbol", "role", name="uq_role_date_symbol_role"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(40), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    sector_name: Mapped[str | None] = mapped_column(String(120))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"
    __table_args__ = (UniqueConstraint("date", "symbol", name="uq_eval_date_symbol"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    buy_grade: Mapped[str] = mapped_column(String(20), nullable=False)
    sell_urgency: Mapped[str] = mapped_column(String(20), nullable=False)
    signals_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class StrategySignal(Base):
    __tablename__ = "strategy_signals"
    __table_args__ = (UniqueConstraint("date", "symbol", "strategy_name", name="uq_signal_date_symbol_strategy"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    strategy_name: Mapped[str] = mapped_column(String(80), nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    data_quality: Mapped[str] = mapped_column(String(20), nullable=False)
    signal_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class StageAnalysis(Base):
    __tablename__ = "stage_analysis"
    __table_args__ = (UniqueConstraint("date", "symbol", name="uq_stage_date_symbol"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(40), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    stage_score: Mapped[float | None] = mapped_column(Float)
    dow_trend: Mapped[str | None] = mapped_column(String(40))
    wave_position: Mapped[str | None] = mapped_column(String(40))
    chip_status: Mapped[str | None] = mapped_column(String(40))
    volume_price_status: Mapped[str | None] = mapped_column(String(40))
    chart_pattern: Mapped[str | None] = mapped_column(String(60))
    risk_level: Mapped[str | None] = mapped_column(String(20))
    reason: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class MainlineRadarRecord(Base):
    __tablename__ = "mainline_radar"
    __table_args__ = (UniqueConstraint("date", "sector_name", name="uq_radar_date_sector"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    sector_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    radar_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    signal_type: Mapped[str] = mapped_column(String(60), nullable=False)
    stage_filter: Mapped[str] = mapped_column(String(40), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    suggested_watch: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class LeaderRadarRecord(Base):
    __tablename__ = "leader_radar"
    __table_args__ = (UniqueConstraint("date", "symbol", "sector_name", name="uq_leader_radar_date_symbol_sector"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    sector_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    leader_probability: Mapped[float] = mapped_column(Float, nullable=False)
    role_type: Mapped[str] = mapped_column(String(40), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    factors_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class ManualPosition(Base):
    __tablename__ = "manual_positions"
    __table_args__ = (UniqueConstraint("symbol", "entry_date", name="uq_manual_position_symbol_entry_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    stop_loss: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class TradeHistory(Base):
    __tablename__ = "trade_history"
    __table_args__ = (UniqueConstraint("symbol", "action", "price", "quantity", "date", name="uq_trade_identity"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    reason: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class StopLossLevel(Base):
    __tablename__ = "stop_loss_levels"
    __table_args__ = (UniqueConstraint("symbol", "created_at", name="uq_stop_loss_symbol_created"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    stop_price: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class SystemMeta(Base):
    __tablename__ = "system_meta"
    __table_args__ = (UniqueConstraint("key", name="uq_system_meta_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


ALL_MODELS: tuple[type[Base], ...] = (
    DailyKline,
    IndexKline,
    DailyBasic,
    LimitUpRecord,
    LianbanRecord,
    SectorMapping,
    SectorDaily,
    Moneyflow,
    AuctionSnapshot,
    IntradaySnapshot,
    MainlineHistory,
    RoleAssignment,
    EvaluationResult,
    StrategySignal,
    StageAnalysis,
    MainlineRadarRecord,
    LeaderRadarRecord,
    ManualPosition,
    TradeHistory,
    StopLossLevel,
    SystemMeta,
)

SessionFactory = sessionmaker(expire_on_commit=False)


def build_database_url(db_path: str) -> str:
    """Build a SQLite URL from a config path."""
    if db_path == ":memory:":
        return "sqlite+pysqlite:///:memory:"
    return f"sqlite+pysqlite:///{Path(db_path)}"


def create_db_engine(db_path: str | None = None) -> Engine:
    """Create a SQLAlchemy engine for the configured SQLite database."""
    if db_path is None:
        config = load_config()
        db_path = str(config["system"]["db_path"])
    return create_engine(build_database_url(db_path), future=True)


def init_db(engine: Engine | None = None, db_path: str | None = None) -> Engine:
    """Create all database tables and return the active engine."""
    active_engine = engine or create_db_engine(db_path)
    Base.metadata.create_all(active_engine)
    SessionFactory.configure(bind=active_engine)
    return active_engine


@contextmanager
def get_session(engine: Engine | None = None) -> Iterator[Session]:
    """Yield a database session with commit/rollback handling."""
    if engine is not None:
        factory = sessionmaker(bind=engine, expire_on_commit=False)
    else:
        if SessionFactory.kw.get("bind") is None:
            init_db()
        factory = SessionFactory

    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def table_counts(session: Session) -> dict[str, int]:
    """Return row counts for every ORM table."""
    counts: dict[str, int] = {}
    for model in ALL_MODELS:
        count_value = session.query(func.count(model.id)).scalar()
        counts[model.__tablename__] = int(count_value or 0)
    return counts


def get_system_meta(session: Session) -> dict[str, str]:
    """Return all system metadata as a key/value mapping."""
    rows = session.query(SystemMeta).order_by(SystemMeta.key).all()
    return {row.key: row.value for row in rows}
