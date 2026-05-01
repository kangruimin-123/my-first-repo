# AI 工具申请审批流程 V1 - 校验规则

## 1. 订阅工具单选校验
- 输入：`resourceType`、`selectedTools`
- 规则：
  - 如果 `resourceType = 订阅账号 / 席位`，`selectedTools` 数量必须为 1。
  - 如果数量大于 1，返回错误：`订阅类工具只能单选。`

## 2. 同类型订阅工具限制校验
- 输入：`applicant`、`selectedTool`、`toolCategory`、`existingSubscriptions`
- 规则：
  - 如果申请人已有同 `toolCategory` 的订阅工具，生成冲突提示。
  - 冲突不自动拒绝，但必须展示给前置审核人与审批人。

## 3. API Key 多选校验
- 输入：`resourceType`、`selectedTools`
- 规则：
  - 如果 `resourceType = API Key / 接口额度`，`selectedTools` 允许多选。
  - 至少选择 1 个工具。

## 4. 共享账号冲突校验
- 输入：`sharedUsers`、`toolCategory`、`existingSharedAccounts`
- 规则：
  - 检查 `sharedUsers` 是否有人已在同类型共享账号中。
  - 若存在，生成冲突提示并交由前置审核人判断。

## 5. 费用默认值校验
- 规则：
  - 不允许出现成本归属输入字段。
  - 成本归属部门必须默认取申请人所属部门。
  - 费用类型必须默认为 AI 费用。
  - 币种必须默认为人民币 / CNY。

## 6. API Key 字段清理校验
- 规则：
  - API Key 表单中不得出现「后台调用量查看」。
  - API Key 表单中不得出现「负责人」输入字段。
  - API Key 表单中不得出现「成本负责人」输入字段。
  - API Key 默认负责人 = 申请人。
  - API Key 默认成本负责人 = 申请人。

## 7. 规则实现建议（飞书原生优先）
1. 使用飞书原生审批实现字段条件显隐、必填约束、审批节点与退回修改。
2. 使用多维表格台账进行历史记录比对与冲突人工核对提示。
3. 如原生能力不足，使用自建应用 / VIBE coding 小程序补充自动冲突检查、摘要生成、台账/费控同步。
