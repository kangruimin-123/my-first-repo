# Task 00 — 项目骨架 + SQLite + 配置

> **Phase**: 1（地基）
> **依赖**: 无
> **验收命令**: `python run.py --mode status && pytest tests/test_db.py`

---

## 全局约束（每个 Task 都必须遵守）

```
1. 所有函数必须有类型注解
2. 所有策略规则必须有注释说明判断依据
3. 所有管线步骤必须写 logger.info 日志
4. 所有外部调用必须有 try-except + 降级处理
5. 阈值从 config.yaml 读取，不硬编码
6. 浮点数比较使用 epsilon 容差
7. 不允许写 pass / TODO / 硬编码返回值
8. 数据源逐级降级：首选→降级→兜底
9. 所有 API 返回数据先写 SQLite，策略层只从 SQLite 读
10. 每个 Task 完成后 pytest 全绿才进下一个
11. mock 模式通过 config.yaml 开关控制
12. 服务重启后从 SQLite 恢复状态
13. 每个策略第一版允许简化核心逻辑，但入口、配置项、输出格式必须完整
14. 未解锁的策略步骤在管线中 enabled=false 自动跳过
15. manual_positions 只允许手工录入，禁止实现任何券商同步
```

---

## Goal

创建完整目录结构、config.yaml、requirements.txt、SQLite 全部建表、最小可运行入口。

## 目录结构（必须完整创建）

```
trading-system/
├── run.py
├── config.yaml
├── requirements.txt
├── README.md
├── backend/
│   ├── __init__.py
│   ├── config.py
│   ├── db.py
│   ├── data/
│   │   ├── __init__.py
│   │   ├── provider_base.py
│   │   ├── tushare_provider.py
│   │   ├── efinance_provider.py
│   │   ├── akshare_provider.py
│   │   ├── mock_provider.py
│   │   ├── cache_manager.py
│   │   ├── data_sync.py
│   │   ├── degradation.py
│   │   └── stock_pool_filter.py
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── mainline_analyzer.py
│   │   ├── role_analyzer.py
│   │   ├── trend_analyzer.py
│   │   ├── position_analyzer.py
│   │   ├── volume_price_analyzer.py
│   │   └── market_risk_analyzer.py
│   ├── strategy/
│   │   ├── __init__.py
│   │   ├── base_strategy.py
│   │   ├── mainline_strategy.py
│   │   ├── leader_detect_strategy.py
│   │   ├── leader_trade_strategy.py
│   │   ├── mid_trend_strategy.py
│   │   ├── elastic_strategy.py
│   │   ├── auction_strategy.py
│   │   ├── lianban_strategy.py
│   │   ├── risk_rules.py
│   │   └── signal_eval_strategy.py
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── llm_client.py
│   │   ├── llm_review.py
│   │   └── prompts.py
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── pipeline.py
│   │   ├── grading.py
│   │   ├── daily_runner.py
│   │   ├── auction_runner.py
│   │   └── intraday_runner.py
│   └── output/
│       ├── __init__.py
│       ├── terminal_view.py
│       ├── csv_reporter.py
│       └── html_reporter.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_db.py
│   ├── test_data_providers.py
│   ├── test_degradation.py
│   ├── test_stock_pool_filter.py
│   ├── test_mainline.py
│   ├── test_role_detect.py
│   ├── test_analysis.py
│   ├── test_strategies.py
│   ├── test_risk_rules.py
│   ├── test_grading.py
│   ├── test_pipeline.py
│   └── test_signal_eval.py
├── sample_data/
│   ├── watchlist.csv
│   └── mock_kline/
├── backups/
└── output/
```

## AI 做

### 1. config.yaml

完整配置如下（必须全量创建，不可截断）：

```yaml
system:
  name: "主线龙头交易系统"
  version: "4.2.0"
  timezone: "Asia/Shanghai"
  log_level: "INFO"
  db_path: "trading_system.db"
  backup_dir: "backups"
  data_retention_days: 180

data_source:
  daily:
    chain: ["tushare", "akshare", "cache"]
  auction:
    chain: ["efinance", "tushare", "mock"]
  intraday:
    chain: ["efinance", "tushare", "mock"]
  level2:
    chain: ["mock"]
  tushare:
    token: ""
    request_interval: 0.3
    retry_times: 3
    history_days: 120
  cache:
    expire_hours: 12
    sector_expire_days: 7

stock_pool:
  exclude_st: true
  exclude_bse: true
  min_list_days: 60
  min_avg_amount_5d: 50000000
  exclude_suspended: true
  watchlist_path: "sample_data/watchlist.csv"
  max_observation_pool: 50
  max_focus_pool: 10

mainline:
  top_n: 5
  score_weights:
    sector_pct_chg: 0.20
    sector_amount: 0.15
    limit_up_count: 0.20
    lianban_count: 0.15
    leader_strength: 0.15
    duration: 0.10
    money_flow: 0.05
  status_thresholds:
    rising_min_score: 60
    fading_max_score: 30
    rotation_volatility: 0.5
  switch_threshold: 0.3

role_detect:
  leader:
    min_amount_rank_pct: 0.2
    min_pct_chg_rank_pct: 0.2
  core_mid:
    min_market_cap: 100
    require_ma20_up: true
    require_ma60_up: true
  elastic:
    max_market_cap: 100
    min_turnover: 5.0

strategies:
  leader_pullback:
    enabled: true
    ma_support: 20
    pullback_max_pct: 5.0
    require_volume_shrink: true
    min_sector_score: 50
    position_pct: [0.10, 0.20]
  leader_breakout:
    enabled: true
    breakout_window: 20
    volume_ratio_min: 1.5
    pct_change_min: 1.5
    close_position_min: 0.7
    require_sector_sync: true
    position_pct: [0.10, 0.15]
  leader_first_divergence:
    enabled: false
    max_drop_from_high: 10.0
    require_mainline_active: true
    position_pct: [0.10, 0.15]
  leader_trend_continue:
    enabled: false
    require_ma20_hold: true
  leader_reseal:
    enabled: false
    require_realtime: true
  core_mid_trend_pullback:
    enabled: true
    ma_support: 20
    require_ma60_up: true
    position_pct: [0.20, 0.30]
  elastic_breakout:
    enabled: false
    require_mainline: true
    max_position_pct: 0.10
  panic_reversal:
    enabled: false
    max_position_pct: 0.10
    require_leader_intact: true
  auction_relative_strength:
    enabled: false
    require_realtime_data: true
    skip_if_data_unavailable: true
    compare_with_sector: true
    compare_with_lianban_group: true
  lianban_leader_template:
    enabled: false
    require_mainline: true
    min_lianban_count: 2
    require_auction_strength: true
    skip_if_data_unavailable: true
    deny_back_row: true
    deny_overheated_high_open: true
    max_position_pct: 0.10
  mainline_switch:
    enabled: false
    score_diff_threshold: 0.3
  trend_hold:
    enabled: false

risk:
  deny_check:
    non_mainline_deny: true
    back_row_deny: true
    overheated_deny: true
    no_stop_loss_deny: true
    min_risk_reward_ratio: 2.0
  position_control:
    leader_pullback: [0.10, 0.20]
    lianban_leader: [0.05, 0.15]
    core_mid_trend: [0.20, 0.30]
    elastic: [0.05, 0.10]
    panic_reversal: [0.00, 0.10]
    max_total_position: 0.80
    weak_market_max: 0.20
  stop_loss:
    default_pct: 5.0
    use_ma20: true
    use_prev_low: true
  sell_rules:
    strong_stock_protection: true
    clear_signal_no_downgrade: true

grading:
  a_grade:
    require_top5_mainline: true
    require_deny_pass: true
    require_full_data: true
    min_confidence: 0.6
    require_stop_loss: true
  b_grade:
    allow_top10_mainline: true
    allow_degraded_data: true
    min_confidence: 0.4

llm:
  enabled: false
  provider: "openrouter"
  model: "anthropic/claude-3-haiku"
  api_key: ""
  timeout: 10
  fallback_on_error: true

output:
  terminal: true
  csv: true
  html: true

signal_eval:
  eval_windows: [1, 3, 5]
  max_drawdown_window: 5
```

### 2. requirements.txt

```
tushare>=1.4.0
efinance>=0.5.0
akshare>=1.14.0
sqlalchemy>=2.0
pandas>=2.2
numpy>=1.26
rich>=13.0
httpx>=0.27
pyyaml>=6.0
apscheduler>=3.10
pytest>=8.0
```

### 3. backend/config.py

```python
def load_config(path: str = "config.yaml") -> dict:
    """加载配置，环境变量覆盖敏感字段"""
    # TS_TOKEN → data_source.tushare.token
    # LLM_API_KEY → llm.api_key
```

### 4. backend/db.py

SQLAlchemy ORM，定义所有表：

```
market_data:
  daily_kline          (id, symbol, date, open, high, low, close, volume, amount, turnover_rate, updated_at)
  index_kline          (id, code, date, open, high, low, close, volume, amount, updated_at)
  daily_basic          (id, symbol, date, market_cap, pe, turnover_rate, updated_at)
  limit_up_records     (id, symbol, date, limit_type, first_time, last_time, open_count, updated_at)
  lianban_records      (id, symbol, date, lianban_count, updated_at)
  sector_mapping       (id, symbol, sector_name, sector_code, updated_at)
  sector_daily         (id, sector_name, date, pct_chg, amount, limit_up_count, lianban_count, updated_at)
  moneyflow            (id, symbol, date, net_amount, updated_at)
  auction_snapshot     (id, symbol, date, open_price, auction_amount, auction_volume, pct_chg, updated_at)
  intraday_snapshot    (id, symbol, date, time, price, volume, amount, updated_at)

strategy_data:
  mainline_history     (id, date, sector_name, mainline_score, mainline_status, rank, factors_json, updated_at)
  role_assignment      (id, date, symbol, role, score, sector_name, updated_at)
  evaluation_results   (id, date, symbol, buy_grade, sell_urgency, signals_json, updated_at)
  strategy_signals     (id, date, symbol, strategy_name, action, confidence, data_quality, signal_json, updated_at)

portfolio_data:
  manual_positions     (id, symbol, name, entry_price, entry_date, quantity, stop_loss, notes, updated_at)
  trade_history        (id, symbol, action, price, quantity, date, reason, updated_at)
  stop_loss_levels     (id, symbol, stop_price, reason, created_at, updated_at)

system:
  system_meta          (id, key, value, updated_at)
```

提供：
- `init_db()` 建表
- `get_session()` 获取会话
- 所有表的 unique constraint 确保去重

### 5. run.py

```python
# argparse 支持: --mode [sync|daily|auction|intraday|detail|eval|status]
# --mode status: 打印各表行数 + system_meta 中 last_daily_update 等
# 启动时调 init_db()
```

### 6. sample_data/watchlist.csv

```csv
symbol,name,reason
002415.SZ,海康威视,AI安防龙头
600886.SH,国投电力,电力核心
601989.SH,中国重工,军工中军
002466.SZ,天齐锂业,有色弹性
300124.SZ,汇川技术,机器人核心
```

### 7. tests/conftest.py

```python
# 内存 SQLite fixture: 每个测试用例独立数据库
# mock config fixture
```

### 8. tests/test_db.py

```python
# 建表成功
# 插入 daily_kline 去重
# 插入 manual_positions
# system_meta 读写
# 所有表可查询
```

---

## 人工验收（5 分钟）

```
□ python run.py --mode status 不报错，显示所有表名和行数（均为 0）
□ trading_system.db 文件生成
□ pytest tests/test_db.py -v 全绿
□ 删除 db 文件后重跑 run.py，自动重建
```
