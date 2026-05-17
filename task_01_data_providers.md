# Task 01 — 数据源 Provider + 降级链

> **Phase**: 1（地基）
> **依赖**: Task 00
> **验收命令**: `pytest tests/test_data_providers.py tests/test_degradation.py`

---

## Goal

实现 Tushare / akshare / mock 三个数据 Provider 和自动降级装饰器。

## AI 做

### 1. backend/data/provider_base.py

```python
class DataProvider(ABC):
    @abstractmethod
    def get_daily(self, symbol: str, start: str, end: str) -> pd.DataFrame: ...
    @abstractmethod
    def get_index_daily(self, code: str, start: str, end: str) -> pd.DataFrame: ...
    @abstractmethod
    def get_limit_up(self, date: str) -> pd.DataFrame: ...
    @abstractmethod
    def get_daily_basic(self, date: str) -> pd.DataFrame: ...
    @abstractmethod
    def get_sector_mapping(self) -> pd.DataFrame: ...

def with_degradation(chain: list[str]):
    """
    降级装饰器：按 chain 顺序尝试 Provider
    Level 1 失败 → Level 2 → Level 3
    每次降级记 logger.warning + 写 system_meta
    三级全败抛 DataUnavailableError
    返回值附带 data_quality 标记
    """
```

### 2. backend/data/tushare_provider.py

- 封装 tushare pro_api
- 请求节流：每次间隔 config.data_source.tushare.request_interval（0.3s）
- 失败重试 config.data_source.tushare.retry_times（3 次），间隔递增
- token 从 config → 环境变量 TS_TOKEN
- 返回标准 DataFrame 格式

### 3. backend/data/akshare_provider.py

- 封装 akshare 对应接口（stock_zh_a_hist / stock_board_concept 等）
- 作为 Tushare 的 Level 2 降级

### 4. backend/data/mock_provider.py

- 生成 120 天随机 OHLCV（价格 10-50，日波动 ±3%）
- 涨停数据 mock（每天 5-15 只随机涨停）
- 板块映射 mock（5 个板块各 20 只）
- 资金流 mock

### 5. backend/data/degradation.py

```python
class DegradationManager:
    def record_degradation(self, source: str, target: str, reason: str): ...
    def get_current_status(self) -> dict: ...
    # 降级事件写入 system_meta 表
```

### 6. tests/test_data_providers.py

- mock_provider 返回正确 DataFrame 列名和类型
- tushare_provider 在无 token 时抛 ConfigError
- akshare_provider 接口签名正确

### 7. tests/test_degradation.py

- 降级链：Level 1 失败 → 自动切换 Level 2
- 降级链：Level 1+2 失败 → 切换 Level 3
- 三级全败 → 抛 DataUnavailableError
- 降级事件写入 system_meta
- 返回值的 data_quality 正确标记

---

## 人工验收（5 分钟）

```
□ pytest tests/test_data_providers.py tests/test_degradation.py -v 全绿
□ 如果有 Tushare token：设 TS_TOKEN 环境变量后手动测试真实数据
```
