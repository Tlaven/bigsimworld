# Teach-back 对账：分辨率折算的财富残差（ADR-006 / N2-5）

- **待验证单元**：`docs/decisions/adr-006-conversion-residual.md` + `docs/core-code.md` 的 **N2-5「分辨率折算的财富残差（符号账）」**
- **判定范围**：**实现级**（N2 单元）+ 决策级（ADR-006）
- **方法**：派**看不到本会话**的独立验证者，只喂文档（允许为裁决"文档是否自相矛盾"而读代码，需披露）
- **结论**：**有缺口但可补**（机制自洽：定义 / 符号 / 恒等式三处一致，5 个例子复算全对；缺口全在**文档层**，实现前全部补完）

## 验证者的独立复述（节选）

`conversion_residual` = 每个 `Measure` 一个的**可正可负** float；当具名个体离场、财富改由桶表示时
`residual += wealth − c`（`c` = 目标桶中心）。三处恒等式（L1 / engineering-spec §9 / N2-5）一致。
三个损失点 = `dematerialize` / `coarsen`（每成员）/ `unbind`；四个精确点 =
`materialize` / `materialize_sample` / `ClusterStore.materialize` / `bind`。
随 `fold_pools` 折叠（`coarsen`/`merge`/`dissolve`/`split`），随快照往返；**不可花费**
（`transfer` 的可支付总额 = `mass() + transfer_pool`，不含残差）。

## 缺口与处置

| # | 验证者发现 | 性质 | 处置 |
|---|---|---|---|
| G1 | `history.md` Stage 17 仍写"方案 H 未做"，且 ADR-006 引用"Stage 18"却不存在 | **文档矛盾 + 悬空引用**（铁律 6） | Stage 17 该行标"已由 ADR-006 接管"；本轮补 **Stage 18**（折算点清单 + 实测） |
| G2 | `--wealth` 逐算子清单不统一，N2-5 漏 `merge`/`split`/`bind`/`extract` | 门禁可验收性 | core-code N2-5 与 engineering-spec §9 写死同一份**穷尽清单**（含 `merge`/`split`/`bind`+`extract`） |
| G3 | 符号 `w` 重载（桶宽 vs 个人财富）：`w − c` 按桶宽读会算出 `−500`，与例子矛盾 | **会算错号** | 全文统一：`w` 只表示桶宽、`wealth` 表示个人财富；`w − c` → `wealth − c` |
| G4 | `Measure.wealth()` 是否含残差未定义（N2-6 定义不含，审计口径含） | 歧义 | 统一为"**审计/观测口径，含残差**"；glossary 测度词条同步；并写死"可支付总额不含残差" |
| G5 | `engineering-spec.md` §5 的 measure payload 仍只写 `size/cells` | 陈旧 | §5 补 `transfer_pool` / `inherited` / `conversion_residual`（旧档缺字段按 0） |
| G6 | `materialize_sample` 号称精确，但若采样桶内**随机值**就会变成第四个损失点 | 需核对代码 | 核对：`IndividualWindow.materialize` 用 `space.wealth_value(bucket)`（桶中心）⇒ **确认精确**；补精确例子 + 断言测试 |
| G7 | "只有三个损失点"缺**穷尽性论证** | 表述不足 | ADR-006 点 7 / N2-5 点 7 加"离场路径逐条：记 or 不记"（含容量逐出、`coarsen` 不得复用 `dematerialize`、窗口死亡不记、`split`/`merge`/`dissolve` 只折不记） |
| G8 | 门禁容差口径与 N2-4 不统一（相对 vs 绝对） | 表述不足 | 统一为 `|ΔW| ≤ max(1e-6, 1e-9·W)` |
| G9 | 精确点清单漏 `extract`（成对析出） | 小缺口 | 精确点显式纳入 `extract(amount=2)` |
| G10 | 旧档按 0 的"一次性断点"无验收 | 小缺口 | 加测试 `test_snapshot_roundtrip_and_old_payload_default` |
| 附 | "量化残差"（transfer 清算超取）与"折算残差"近名不同义 | 术语漂移风险 | glossary 两行互相加反例引用 |

## 实现期发现（teach-back 判不出的一类）

| # | 发现 | 处置 |
|---|---|---|
| 1 | `coarsen` 若复用 `dematerialize` 通道会**双记**（成员既进 aggregate 又被折回全局） | 实现里 `coarsen` 直接在自己新建的 `aggregate` 上 `record_conversion`，不经 `dematerialize` |
| 2 | `unbind` 的目标测度可能是 mini 也可能是全局（簇已回收）⇒ 残差必须记到**同一个**目标 | 实现里按 `target` 变量统一（计数与残差同目标） |

## 值得记住的两条

1. **符号重载是安静的**：`w` 同时当桶宽与个人财富时，公式在纸面上"看起来对"，只有代数字才算得出来（G3）。
2. **"精确点 / 损失点"是一张必须穷尽的清单**：漏一个损失点只是少记，多记一个精确点就是凭空造账——
   两者都只在**跨折算的长跑**里现形，所以门禁必须是逐算子 W 探针（`bench.audit_ledger --wealth`）。
