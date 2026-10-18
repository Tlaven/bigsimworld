# Architecture Decision Records (ADR)

本目录记录项目所有重要架构决策。每条 ADR 一个文件,按编号递增。

> **规则归属:** ADR 的**触发粒度与推翻时的联动义务**是跨领域规则,唯一归属是 `docs-templates/evolution-rules.md`(随项目落地;L1 记忆文件里只留一行指针)——**何时记见 E4,推翻决策的联动义务见 E3**。本文件只讲 ADR 自身(为什么记 / 格式 / 命名 / 索引),不重述那些规则。

## 为什么记 ADR

- **决策的"为什么"比"是什么"更重要**——代码能读出做了什么,读不出为什么
- **被拒方案要记"为什么不"**——记下"考虑过 X 但拒绝了，因为 Y"，防止后续重复踩坑
- **AI 协作的约束记录**——AI 不知道历史，会反复提出已否决的方案；ADR 是唯一能挡住它的记录

## ADR 格式

每条 ADR 包含五段:

```
# ADR-XXX: [决策标题]

## 状态
proposed / accepted / deprecated / superseded by ADR-YYY

## 背景
为什么需要这个决策?遇到了什么问题?

## 考虑过的方案
列出所有考虑过的方案(包括被拒绝的),每个方案的优缺点,被拒的要写"拒绝理由"

## 选择
选了哪个?为什么?(不是"它最好",而是"在我们的约束下它最合适")

## 后果
正面 / 负面后果;需要跟进的
```

模板见 `docs-templates/adr-template.md`(按需复制为 `adr-XXX-[短描述].md`;模板本身不是真实决策,不要列进下方索引)。

## 命名规则

```
adr-XXX-[短描述].md
```

- `XXX` 是零填充的递增编号(001, 002, ...)
- 短描述用英文 kebab-case(例:`adr-003-use-event-sourcing.md`)

## ADR 索引

<!-- 列出所有 ADR,按编号倒序(最新在上) -->
<!-- 示例(刻意不写成 markdown 链接——否则空索引会触发 check-doc-refs 的「死链」告警):
- ADR-003: 用事件溯源替代直接 CRUD — accepted
- ADR-002: 模块间用消息队列通信 — superseded by ADR-003
- ADR-001: 选 PostgreSQL 作为主数据库 — accepted
-->
