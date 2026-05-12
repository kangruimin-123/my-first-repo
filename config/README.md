# config

Runtime 配置契约目录。

这里存放 Codex 和 BDC 团队之间的可执行契约文件。代码可以读取这些配置，测试可以校验这些配置。

## 子目录

```text
contracts/             Tool、API、字段、业务语义等通用契约
prompts/               Prompt 资产，按版本管理
workflows/             高频业务流程定义
analysis_templates/    复杂分析模板
```

## 文件原则

- 使用 YAML 或 JSON
- 字段名稳定
- 有 schema 或测试校验
- 不写密钥
- 变更需要同步测试
