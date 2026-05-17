> **Codex 必读**：每个 task 开始前必须先读本文件。所有代码必须遵守以下规则，违反即 reject。

---

## 项目定位

BDC AI Agent Service 是受控数据分析 Agent Runtime（Text-to-Semantic-Tool 架构，非 Text-to-SQL）。 它是 AI 调度层，不替代 BDC 后端。

---

## 12 条铁律

### 数据安全

1. **LLM 不生成 SQL，不直连数据库。** 所有数据访问通过 Tool → BDC 后端。
2. **所有数据访问必须通过 ToolExecutor。** 任何模块不得绕过 ToolExecutor 直接调用后端或 Mock Tool。
3. **query_from_config 只接受 structured config。** 参数是 project_id + metrics + dimensions + filters + date_range，不是 SQL 字符串。
4. **敏感字段必须 reject。** user_id / device_id / ip / openid / phone / email / idfa / imei 出现在用户问题或工具参数中时，立即拒绝。

### 路径隔离

5. **Messages 路径不调用 ToolExecutor。** ClaudeMessagesClient 只接受已有的 data_context 做总结，绝对不查数据。
6. **Agent 路径必须通过 ToolExecutor。** AgentRuntimeClient 的每次工具调用都经过 ToolExecutor。
7. **Workflow 每步通过 ToolExecutor。** WorkflowEngine 的每个 step 都调 ToolExecutor.execute()。

### 可观测性

8. **每个请求创建 EvaluationContext。** 在 EntryHandler 阶段创建，贯穿全链路。
9. **每个 ToolResponse 必须有 data_status + data_version。** 不允许 Optional，不允许缺省。
10. **所有请求返回 trace_id。** AskResponse.trace_id 必填。

### 工程纪律

11. **不允许删除/放宽已有 tests。** 只能新增测试，不能修改已通过的测试使其变宽松。
12. **不允许为通过测试绕过架构规则。** 如果测试失败，修代码不修测试。

---

## Intent 枚举

```text
metric_query          # 具体指标查询
metric_diagnosis      # 为什么跌/涨，异常原因
dashboard_query       # 看板/大盘
prebuilt_report_query # 日报/周报/投放日报
report_generate       # 总结已有数据（Messages 路径）
analysis_template     # 漏斗/留存/路径/分布/归因/分群
workflow_run          # 定时/自动流程
chat                  # 闲聊
unsupported           # 不支持
follow_up             # 追问
```

## Resolution Mode 枚举

```text
resolved                # 实体完整，直接走工具
clarify                 # 缺信息，追问
reject                  # 敏感/无权限
agent_fallback          # 多步诊断，走 Agent
workflow_route          # 走 Workflow
messages_route          # 走 Messages API
dashboard_route         # 走看板工具
prebuilt_report_route   # 走预制报表
analysis_template_route # 走分析模板
```

## Task 执行顺序

```text
00 → 01 → 02 → 03 → 04 → 05 → 06 → 07 → 08 → 09 → 10 → 11 → 12
```

每个 task 完成后必须 `pytest` 全绿才能进入下一个。

---

## MVP 范围

第一版接入（Mock）：

```text
EntryHandler / IntentRouter / EntityNormalizer / ResolutionPolicy
AgentRuntimeClient (Mock) / ClaudeMessagesClient (Mock)
ToolRegistry / ToolExecutor
query_from_config (Mock) / detect_anomalies (Mock)
get_dashboard_snapshot (Mock) / read_custom_dashboard (Mock) / read_prebuilt_report (Mock)
EvaluationContext
```

第一版不接：真实 SQL / 明细查询 / 复杂分群 / 路径归因 / 跨报表合并 / 自动写回。

### Tool 能力演进

`read_custom_dashboard` 属于 MVP 范围，但必须以受控方式实现：

- MVP 阶段只读 Mock 数据或受控后端结果，返回时必须带 warning，标明非官方固定看板。
- 后续 BDC 数据和接口增多时，Tool 能力要按领域沉淀为 Skill，例如指标查询 Skill、看板读取 Skill、日报 Skill、异常诊断 Skill。
- 再后续需要 MCP 化：把稳定 Tool/Skill 封装成 MCP Server 能力，供 Codex、Agent Runtime 和其他客户端复用。
- 即使 Skill 化或 MCP 化，所有数据访问仍必须经过 ToolExecutor / 权限校验 / 敏感字段拦截 / EvaluationContext 记录。

---

## 验收标准（10 条）

```text
1. /ask 返回 trace_id
2. "苍蓝昨天收入" → query_from_config
3. "苍蓝昨天收入为什么跌" → Agent SDK（2+ tool_call）
4. 页面已有 data_context → Messages API（0 tool_call）
5. "昨天投放日报" → read_prebuilt_report
6. "看一下项目大盘" → get_dashboard_snapshot
7. 每个工具调用写入 agent_steps
8. query_from_config 不接受 SQL
9. read_custom_dashboard 必须带 Warning
10. 所有输出包含 data_status
```
