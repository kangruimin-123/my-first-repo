# Codex 工程任务路线图

Codex 负责所有代码、测试、架构实现。

## 阶段 A：工程基础

不依赖任何 BDC 输入。

| Task | 做什么 | 产出 |
|---|---|---|
| 00 工程骨架 | 目录结构 + pyproject.toml + 空模块 + /ask 最小桩 | 项目可启动，pytest 可运行 |
| 01 核心协议 | StandardRequest / ToolResponse / EvaluationContext 的 Pydantic schema | 所有模块的数据契约 |
| 02 EvaluationContext | trace_id 生成、log_step、record_tool_call、finalize | 全链路追踪能力 |
| 03 Entry 层 | EntryHandler 接收请求 → 转 StandardRequest → 检查 KillSwitch | 统一入口 |

完成标志：`uvicorn app:app --reload` 可启动，`POST /ask` 返回 trace_id。

## 阶段 B：语义和路由

依赖 config YAML 的 schema，不依赖真实内容。

| Task | 做什么 | 依赖 |
|---|---|---|
| 04 Semantic 层 | EntityNormalizer 读 YAML，做项目、指标、日期、渠道匹配 | project_alias.yaml、metric_dictionary.yaml |
| 05 Intent Router | 确定性关键词规则 | 无 |
| 06 Resolution Policy | intent + entity → 决定路径 | 无 |
| 07 Session State | 会话上下文管理 | 无 |

完成标志：苍蓝→canglan、收入→revenue、为什么跌→metric_diagnosis 测试通过。

## 阶段 C：工具系统

依赖 API 契约，不依赖真实 API。

| Task | 做什么 | 依赖 |
|---|---|---|
| 08 Tool Registry | 8 个工具的名称、输入 schema、输出 schema | docs/02_tool_contracts.md |
| 09 Tool Executor | 注册检查、参数校验、权限检查、执行、记录 ctx | 无 |
| 10 Mock BDC Tools | query_from_config、detect_anomalies、dashboard_snapshot、prebuilt_report | API 契约 JSON |
| 11 Harness | 参数校验、敏感字段拦截、限流、熔断 | field_mapping.yaml |

完成标志：未注册工具 reject、SQL reject、敏感字段 reject、所有 ToolResponse 有 data_status。

## 阶段 D：AI 双路径

| Task | 做什么 |
|---|---|
| 12 Agent Runtime Mock | metric_diagnosis 走 query + detect_anomalies |
| 13 Messages Runtime Mock | 只接收 data_context 生成总结，不调工具 |
| 14 Prompt Registry | 从 config/prompts/ 加载 Prompt，管理 VERSION |

完成标志：为什么跌→Agent→tool_call 正确；总结表格→Messages→无 tool_call。

## 阶段 E：流程引擎

| Task | 做什么 | 依赖 |
|---|---|---|
| 15 Workflow Engine | 按步骤执行确定性流程，每步通过 ToolExecutor | workflow 定义 |
| 16 Analysis Template | 加载模板、校验 event、转自助分析 JSON Config | analysis_templates、event_dictionary |
| 17 Self-Service Adapter | 模板参数转 BDC 自助分析引擎 JSON | BDC 自助分析接口格式 |

## 阶段 F：/ask 总编排 + 验收

| Task | 做什么 |
|---|---|
| 18 /ask Orchestrator | Entry → Intent → Semantic → Resolution → 分流执行 → 返回 |
| 19 验收测试 | 8 个端到端验收用例 |
| 20 修复到全绿 | 循环修复直到 pytest 全绿 |

完成标志：Mock 全链路 8 个验收用例全绿。

## 阶段 G-J：替换真实能力

| 阶段 | Codex 做什么 | 依赖 BDC 什么 |
|---|---|---|
| G 业务资产导入 | AI 抽取分析师文档→YAML，补 normalizer tests | 分析师校验过的 YAML |
| H 真实 BDC 接入 | Mock Tool → 真实 HTTP 调用，加错误处理 | 后端 3 个真实 API |
| I 真实 Claude 接入 | 接 Messages API → 接 Agent SDK | Claude API Key |
| J 飞书生产化 | 飞书适配、卡片格式、KillSwitch、灰度 | 飞书机器人配置 |
