# Git Repo 的角色

Git Repo 是工程事实源，是 Codex 唯一的工作目录。所有可执行代码、配置、测试、任务书都在这里。

## 2.1 Git Repo 的角色

Obsidian 是知识库和协作空间，用来沉淀架构思路、业务口径、会议记录和决策记录。

Git Repo 是可执行事实源，用来保存代码、配置、测试、任务书和可回归的工程资产。

Codex 后续只以 Git Repo 中的文件作为工程事实源。

## Git Repo 目录结构

```text
app/                         Runtime 后端代码
frontend/                    前端代码，如有
netlify/                     部署和 Functions 适配，如有
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

## 什么必须进入 Git Repo

- 会被代码读取的配置
- 会被测试验证的契约
- 会指导 Codex 实现的任务书
- 会影响 Runtime 行为的 Prompt / Workflow / Template
- API、Tool、字段、错误码等工程契约

## 什么不应该进入 Git Repo

- 未确认的业务口径草稿
- 散乱会议记录
- API Key、token、cookie、私密配置
- 本地依赖目录，如 `node_modules/`
- 构建产物和缓存，如 `dist/`、`.pytest_cache/`

## 工作规则

1. 业务侧输入先在 Obsidian 讨论，确认后变成契约文件进入 Git Repo。
2. Codex 根据 Git Repo 文件实现代码。
3. 所有行为变化都要有测试或验收用例。
4. 先跑通 Mock 链路，再替换真实 BDC API。
5. Prompt、Workflow、Analysis Template 必须版本化。
