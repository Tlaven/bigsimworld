# 2026-10-18 · 攒批 teach-back（#2：锚点 `158b862` → `f640e20`）

> 复核范围 = 锚点以来的契约文档增量（4 个文件）：`cluster-contract` §1、`engineering-spec` §2/§9、`glossary` 6 行、`interaction-channel` N2-1/N2-7/失败语义/危险清单。
> 复核者 = 独立 agent（teach-back verifier 协议；带允许清单防越界；判"文档写没写清"，不判"断言为真"）。

## 复核结论：**需修（7 条）→ 全部当场收敛**

已确认互洽的部分（无需动作）：`both` 在四处（env 表 / §9 交互规则 / glossary / 通道 N2-7+N2-1 第 4 步）注册名、独立派生流、处理序、配额语义一致；`interface` 预留三处（cluster-contract §1 / engineering-spec 已知边界 / ADR-013）措辞一致、无"它在工作"残留；遍历序段与 `bench/README` 守恒纪律第 6 条互洽且点名测试真实存在并真的在测（先断言两构造序迭代序不同，再断言逐位一致）。

## 问题与收敛

| # | 位置 | 类型 | 问题 | 收敛 |
|---|---|---|---|---|
| 1 | `AGENTS.md`（L1） | 矛盾/未同步 | L1 仍写"单值互斥：`1`/`mass`"——与增量四处 + ADR-012 冲突，且 L1 是自动加载层，把实现者挡在 `both` 外 | L1 改为 `1`/`mass`/`both` + 守卫 + ADR-012 指针 |
| 2 | `interaction-channel` :7 / :32 | 未同步 | 首屏开关口径缺 `both`；子组件表流水线缺"发起者复检" | 两处同步（`1\|mass\|both`；"收集 → 排序 → 发起者复检 + 配额闸 → …"） |
| 3 | `interaction-channel` 账本形状 + 失败语义表 | 缺失/未同步 | `dropped:initiator_married` 未登记进统一 status 枚举；失败表被声明穷尽却缺该行 | 枚举补入；失败表加行（零副作用 + `test_bind_rejects_married_initiator`） |
| 4 | `interaction-channel` 危险清单第 11 行 | 悬空 | 点名的 `test_both_targets_register_side_by_side` 在允许清单内查无落点 | 核实真实存在（`tests/test_rule_marriage.py:294`）→ 补文件路径；N2-7 验收段补 `both` 条目 |
| 5 | `bench/README` / ADR-011 / `decisions/README` | 术语漂移 | 同一机制三名字（社会凝视 / 内生凝视 / 内生注意力），glossary 别名列为空 | 统一为 **社会凝视**；glossary 别名列登记旧称 |
| 6 | `glossary` 社会凝视词条 | 歧义（轻） | 未写机制边界"只对 resolved 簇刷新 ⇒ 无回升源" | 边界列补入 |
| 7 | `interaction-channel` 第 4 步指针 | 悬空（轻） | "见第 2 步"但第 2 步未枚举 `scope_type` 的 `measure`=2 | 第 2 步补 `measure`=2；第 4 步指向 N2-8 |

**复核者越界申请**（未越界读取，仅申请）：`tests/test_rule_marriage.py`（核实第 11 行测试名）、`app/core/measure/channel.py`（核实 `InteractionChannel._process` 符号）——两者均经主会话核实存在（`channel.py:253/288`）。

## 判据设计备注

- 本轮 0 阻断项；7 条均为"同步/悬空/登记"类，已全部收敛。第 4 条的教训：**文档点名的测试应带文件路径**（只说测试名时，复核者的允许清单可能覆盖不到，遮挡链"不可证实"）。
- 收敛含一处**核实而非修改**（第 4 条：测试真实存在，补路径即可）。
