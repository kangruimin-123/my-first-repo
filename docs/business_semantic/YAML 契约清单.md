# YAML 契约清单

## 第一批 YAML

### project_alias.yaml

```yaml
projects:
  canglan:
    name: "苍蓝誓约"
    aliases: ["苍蓝", "苍兰", "蓝服", "canglan"]
    status: active

  wmcq:
    name: "文明曙光：重启"
    aliases: ["文明", "文明重启", "wmcq"]
    status: active
```

### metric_dictionary.yaml

```yaml
metrics:
  revenue:
    name: "充值流水"
    aliases: ["收入", "流水", "充值", "营收", "充值收入"]
    definition: "游戏内充值流水，未扣除渠道分成"
    unit: "元"
    aggregation: "sum"
    dimensions_allowed: ["date", "channel", "platform"]
```

### dimension_mapping.yaml

```yaml
dimensions:
  date:
    aliases: ["日期", "时间", "天"]
    type: "date"

  channel:
    aliases: ["渠道", "来源", "投放渠道"]
    type: "categorical"

  platform:
    aliases: ["平台", "系统", "操作系统"]
    type: "categorical"
    values: ["ios", "android"]
```

### value_alias_mapping.yaml

```yaml
channel:
  xiaomi: ["小米", "MI", "xiaomi"]
  huawei: ["华为", "HUAWEI", "huawei"]
  oppo: ["OPPO", "oppo"]
  vivo: ["vivo", "VIVO"]
  tencent: ["应用宝", "腾讯", "myapp"]
  taptap: ["TapTap", "tap"]
  bilibili: ["B站", "bilibili", "哔哩哔哩"]
  apple: ["苹果", "AppStore", "iOS官方"]

platform:
  ios: ["iOS", "苹果", "iphone"]
  android: ["安卓", "Android"]
```

## 第二批 YAML

### event_dictionary.yaml

```yaml
events:
  register:
    name: "注册"
    description: "完成账号注册"
    projects: ["canglan", "wmcq"]
```

### field_mapping.yaml

```yaml
sensitive_fields:
  - user_id
  - device_id
  - ip
  - openid
  - phone
  - email
  - idfa
  - imei

allowed_filter_fields:
  - channel
  - platform
  - date
  - server_id
  - level_range
```

### business_conventions.yaml

```yaml
defaults:
  date_range: "last_7_days"
  dimension: "date"
  project: null
  timezone: "Asia/Shanghai"
  currency: "CNY"

rules:
  - "如果用户没说时间，默认最近 7 天"
  - "如果用户没说维度，默认按日期"
  - "如果用户没说项目，必须追问，不能猜"
  - "如果用户说'昨天'，指自然日昨天，不是 T-1"
  - "ROI 计算口径统一使用 7 日回收"
```
