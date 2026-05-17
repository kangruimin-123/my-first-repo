# MVP Tool 扩展与 MCP 化策略

## 定位

`read_custom_dashboard` 是 MVP 范围内的扩展型工具入口，不是后续才考虑的能力。

它和 `get_dashboard_snapshot` 的关系：

| Tool | 定位 | MVP 行为 |
|---|---|---|
| get_dashboard_snapshot | 官方固定看板快照 | 返回标准大盘数据 |
| read_custom_dashboard | 自定义看板读取入口 | 返回受控 Mock 或受控后端结果，必须带 warning |

## MVP 约束

`read_custom_dashboard` 在 MVP 阶段必须遵守：

1. 不接受 SQL。
2. 不查询敏感字段。
3. 不绕过 ToolExecutor。
4. 所有响应必须有 `data_status` 和 `data_version`。
5. 返回结果必须带 warning，说明这是自定义看板能力，不等同于官方固定看板。

## 后续演进

随着 BDC 数据、接口和分析能力增加，Tool 能力要逐步演进：

```text
Tool Contract
↓
Domain Skill
↓
MCP Server Capability
```

## Skill 化方向

优先沉淀这些 Skill：

- 指标查询 Skill：指标、维度、过滤、时间范围。
- 看板读取 Skill：官方看板、自定义看板、权限和 warning。
- 日报/周报 Skill：预制报表读取、摘要、异常点。
- 异常诊断 Skill：query + detect_anomalies + 归因解释。
- 分析模板 Skill：漏斗、留存、ROI、渠道对比。

## MCP 化方向

当某类 Skill 稳定后，可以封装为 MCP Server：

- 提供标准工具描述。
- 暴露结构化输入 schema。
- 统一返回 `ToolResponse` 兼容结构。
- 接入权限、限流、审计和 trace。

MCP 化后仍然要保持架构铁律：Agent Runtime 不直连数据库，不生成 SQL，所有数据访问必须经过受控工具层。
