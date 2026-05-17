# Task 02 — 股票池过滤 + 增量同步

> **Phase**: 1（地基）
> **依赖**: Task 00, 01
> **验收命令**: `python run.py --mode sync && python run.py --mode status`

---

## Goal

全市场过滤器 + SQLite 缓存读写 + 增量数据同步。Phase 1 交付完成。

## AI 做

### 1. backend/data/stock_pool_filter.py

```python
class StockPoolFilter:
    def filter_universe(self, daily_basic: pd.DataFrame) -> list[str]:
        """
        排除规则（从 config.stock_pool 读取）：
        - ST / *ST（name 包含 ST）
        - 北交所（symbol 以 .BJ 结尾或代码 8/9 开头）
        - 上市不足 60 个交易日
        - 近 5 日平均成交额 < 5000 万
        - 停牌
        返回约 3000~3500 只合格 symbol
        """
    
    def load_watchlist(self, path: str) -> list[str]:
        """加载手动自选池"""
```

### 2. backend/data/cache_manager.py

```python
class CacheManager:
    def read_daily(self, symbol: str, start: str, end: str) -> pd.DataFrame | None: ...
    def write_daily(self, symbol: str, df: pd.DataFrame) -> None: ...
    def get_missing_dates(self, symbol: str, start: str, end: str) -> list[str]: ...
    def is_fresh(self, table: str, max_age_hours: int) -> bool: ...
    # 去重写入（symbol + date unique）
    # 增量查询缺失日期
```

### 3. backend/data/data_sync.py

```python
@dataclass
class SyncResult:
    success_count: int
    fail_count: int
    degradation_count: int
    skipped: bool          # 今天已同步则 True

class DataSync:
    def sync_daily(self, symbols: list[str]) -> SyncResult:
        """增量同步日线数据"""
    def sync_limit_up(self, date: str) -> SyncResult: ...
    def sync_lianban(self, date: str) -> SyncResult:
        """从 limit_up_records 计算连板天数"""
    def sync_sector_mapping(self) -> SyncResult:
        """7 天过期刷新"""
    def sync_sector_daily(self, date: str) -> SyncResult:
        """汇总板块日度数据"""
    def sync_all(self) -> SyncResult:
        """
        1. 读 system_meta.last_daily_update
        2. 今天 → 跳过
        3. 否则增量拉取
        4. 写 SQLite + 更新 meta
        """
```

### 4. 更新 run.py

- `--mode sync`：调用 data_sync.sync_all()，打印 SyncResult
- `--mode status`：增加显示 last_daily_update 和各表行数

### 5. 测试

- `tests/test_stock_pool_filter.py`：ST 排除 / 北交所排除 / 次新排除 / 低额排除
- 更新 `tests/test_db.py`：缓存读写 + 去重验证

---

## 人工验收（10 分钟）

```
□ python run.py --mode sync 不报错，输出同步结果
□ sqlite3 trading_system.db "SELECT COUNT(*) FROM daily_kline" 有数据
□ 再跑一次 --mode sync，输出"数据已是最新，跳过"
□ python run.py --mode status 显示各表行数和最后更新时间
□ 断网后重启，python run.py --mode status 数据仍在
□ pytest 全绿
```

**至此 Phase 1 交付完成。数据层 + 持久化 + 降级链全部就绪。**
