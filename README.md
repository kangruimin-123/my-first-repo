# my-first-repo

BDC AI Runtime 工程仓库。

本仓库是工程事实源，是 Codex 的唯一工作目录。所有可执行代码、配置、测试、任务书都应在这里维护。

## 目录结构

```text
app/                         Runtime 后端代码
config/                      可执行配置契约
config/contracts/            Tool、API、字段、业务语义契约
config/prompts/              Prompt 资产，版本化管理
config/workflows/            高频业务流程定义
config/analysis_templates/   复杂分析模板
docs/                        工程文档和契约说明
tasks/                       Codex 开发任务书
tests/                       单元测试、API 测试、验收测试
scripts/                     初始化、校验、导入脚本
```

## 工作原则

1. Obsidian 用于讨论和沉淀，Git Repo 用于执行和验证。
2. 业务侧输入确认后，必须转成契约文件进入 `config/` 或 `docs/`。
3. Codex 只以本仓库文件作为工程事实源。
4. 所有行为变化都要有测试或验收用例。
5. 先跑通 Mock 链路，再替换真实 BDC API。
