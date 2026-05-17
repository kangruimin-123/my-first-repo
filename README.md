# 主线龙头交易系统

个人 A 股主线龙头交易辅助系统，当前实现 Phase 1 / Task 00：项目骨架、配置、SQLite 建表和最小运行入口。

## 快速验收

```bash
python run.py --mode status
pytest tests/test_db.py -v
```

## 当前边界

- 数据和策略状态统一落 SQLite。
- 持仓只支持 `manual_positions` 手工录入，禁止自动同步券商。
- 未解锁策略保留配置入口，后续任务逐步实现。
