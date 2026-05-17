# 后端 API 契约

## API 1：query_from_config

`POST /api/v1/query_from_config`

功能：接收结构化查询配置，返回指标数据。不接受 SQL 字符串或自由文本。

```json
{
  "project_id": "canglan",
  "metrics": ["revenue"],
  "dimensions": ["date", "channel"],
  "filters": { "channel": "xiaomi" },
  "date_range": { "start": "2026-05-02", "end": "2026-05-02" },
  "limit": 50
}
```

成功响应：

```json
{
  "status": "success",
  "data": [
    { "date": "2026-05-02", "channel": "xiaomi", "revenue": 123456 }
  ],
  "metric_definitions": {
    "revenue": "游戏内充值流水，未扣除渠道分成"
  },
  "data_status": "valid",
  "data_version": "bdc_query_v1",
  "source": "sql_builder"
}
```

## API 2：get_dashboard_snapshot

`POST /api/v1/get_dashboard_snapshot`

功能：返回指定看板的快照数据。

```json
{
  "dashboard_id": "official_project_overview",
  "project_id": "canglan",
  "date_range": { "start": "2026-05-02", "end": "2026-05-02" }
}
```

## API 3：read_prebuilt_report

`POST /api/v1/read_prebuilt_report`

功能：返回指定预制报表的数据和摘要。

```json
{
  "report_code": "daily_ua_report",
  "project_id": "canglan",
  "date": "2026-05-02"
}
```

## data_status 含义

| 值 | 含义 | AI Runtime 行为 |
|---|---|---|
| valid | 数据完整可用 | 正常使用 |
| partial | 部分数据缺失 | 使用但加 warning |
| stale | 数据可能过时 | 使用但加 warning |
| unavailable | 数据不可用 | 走 fallback |
