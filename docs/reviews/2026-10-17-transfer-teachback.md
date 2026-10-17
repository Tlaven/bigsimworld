# Teach-back 对账：质量侧 `transfer`（N2-6）

- **待验证单元**：`docs/modules/interaction-channel.md` 的 **N2-6「质量侧 transfer」**（联动 §第二期 / 不变量 1、9–13 / N2-1 账本形状 / N2-3 配额）
- **判定范围**：**实现级**（N2 单元）+ 决策级（[`adr-005`](../decisions/adr-005-transfer-quality-side.md)）
- **方法**：派**看不到本会话**的独立验证者，只喂文档（允许为裁决"文档是否自相矛盾"而读代码，需披露），
  按 [`docs-templates/teach-back-verifier-prompt.md`](../../docs-templates/teach-back-verifier-prompt.md) 判三档
- **结论**：**有缺口但可补**（主协议"规划 → 应用 → 实付记账"被判定正确；给出的缺口在实现前全部补完）

## 验证者的独立复述（节选）

R→C = 精确借记 + 入池；C→R = 可支付性 → 缺口 → **只算不改**的清算计划（人数最少优先、`k ≤ wealth_bucket`）
→ 按源桶财富**升序**应用 → 硬前提 `pool ≥ A` 才支付；年度投递 = 整人桶、最穷优先、按目标桶财富**降序**应用；
生命周期折叠 = `coarsen`/`merge`/`dissolve`/`split` 折 `transfer_pool` + `yearly_inherited`。
文档里 5 个精确例子（2500 / 500 / `3@10+1@5` / 只 `4@0` / 池 2500 投递）**逐个复算自洽**。

## 缺口与处置（按优先级）

| # | 验证者发现 | 性质 | 处置 |
|---|---|---|---|
| 1 | 文档已写"已交付 #17–23 + `bench.audit_transfer`"，但工作树里没有对应代码 | 规格先行的**时序**问题 | 同轮实现闭合（`Measure.transfer_pool`/`mass()`/`wealth()`、`Intent.op`、`bench/audit_transfer.py`、`tests/test_transfer.py`）；本文件记录这一时序 |
| 2 | **池的生命周期没闭合**：`materialize` 保留 mini ⇒ resolved 簇也持池；`merge` 的 resolved+resolved 快路径与 `split` 会 `del` 掉持 mini 的簇（连**分数计数残留**都丢） | **真缺口**（W 与人头都会漏，且 `audit_transfer` 的脚本覆盖不到） | 不变量 12 扩到 `split`；N2-6 第 7 步写明三处；实现用 `fold_pools` 折 `coarsen`/`merge`/`dissolve`/`split`，并加 `test_merge_resolved_fast_path_keeps_leftover_pools`、`test_split_folds_leftover_pools_into_global` |
| 3 | 超取上界写成"≤ **最小** `count×w`" | **文档算错**（反例 `1@5+3@6`、A=6000 ⇒ 超取 2000） | ADR-005「取舍/选择」、glossary、N2-6 例子三处改为"**被清算桶中最大 `count×w`**"，并加具名夹具 `test_c2r_overdraw_bound_is_largest_liquidated_count` |
| 4 | 三个容差不自洽（`1e-9`/`1e-12`）⇒ `pool -= A` 可能微负，违反池非负 | **真缺口** | N2-6 第 5.5 步改成**硬前提 `pool ≥ A`**、计划"宁可多清算一步、绝不欠付"，并明确**禁止** `max(0, …)` 钳制；实现加浮点补足循环 + 保险丝 |
| 5 | 只写了"相邻桶会级联"，没写真正触发条件；投递反向会让**池变负** | **文档理由不完整** | N2-6 例子补 `3@9+1@10`（池 4500，升序 ⇒ 负池/凭空 +3000）；陷阱 3 写明触发条件；mutation 加"投递改升序"一条 |
| 6 | `k ≤ wealth_bucket` 只写"不越过桶 0"，未标为正确性前提 | 表述不足 | 改为"**正确性前提**：越界会把桶索引串到别的 age/gender 桶"；加 `test_shift_age_wealth_refuses_to_cross_bucket_zero`；实现给 `_shift_age_wealth` 加下界守卫 |
| 7 | 年度投递取分数桶 ⇒ "最穷优先"退化成"最稀优先"（`count=0.001` 吃掉整池） | **真缺口** | N2-6 第 6 步改为**只取 `count ≥ 1.0` 的整人桶**；加 `test_deliver_skips_fractional_buckets` |
| 8 | 去重键不含 `op`，且去重不写账本（与"每条丢弃都有记录"冲突） | **真缺口** | N2-1 第 2/3 步：排序键与去重键都加 `op`，被去重记 `dropped:duplicate`；加 `test_duplicate_intent_is_recorded_not_silently_swallowed`、`test_dedupe_key_includes_op` |
| 9 | "Σ 粗侧"没定义范围（是否含全局测度） | 歧义 | 不变量 9 / N2-6 第 8 步写明"全局测度 + 每个簇 mini（含 resolved 残留）" |
| 10 | "可花费量"名不副实（`bucket 0` 不可清算，仍可能 `illiquid`） | 歧义 | 改名"**可支付总额**"与"**可清算量**"，并写明两者差 ⇒ `illiquid` |
| 11 | 析出者初始 `wealth` 未规定；文档把 `bind` 也算进"≤w/2 量化差" | 歧义 | N2-6 第 4 步写明 = `space.wealth_value(bucket)`（桶中心）⇒ `bind`/`materialize` 精确；量化差只在"精确 → 桶中心"方向 |
| 12 | 快照要求只写到函数名，旧档"缺字段按 0"的后果未登记 | 表述不足 | N2-6 第 7 步写明"每个粗侧（全局 + 各 mini）"、旧档恢复 W 有断点属兼容边界；实现 `measure_to_payload` / `measure_from_payload` 往返两池 |
| 13 | 投递相位理由写反（"让池可用于支付"——可支付总额不因投递改变） | **文档理由错** | 改为"年度结清先于本 tick 意图，避免池跨年累积；代价是更依赖清算"，并写明相对继承年清算的顺序 |
| 14 | `pool < w` 与 `count < 1` 的单步值冲突 | 真缺口（与 #7 同源） | 改成 `pool <= 0 ⇒ 不动` |
| 15 | "上限余量"未定义，`wealth_bins` 与状态空间桶数混用 | 歧义 | 定义为 `wealth_bins − 1 − wealth_bucket` 步 |
| 16 | `headroom_reserve` 按"`RULES` 非空"预留 ⇒ 纯 transfer 规则会白留名额 | 真缺口（退化） | 规则可声明 `emits_bind=False`（缺省 `True`）；`headroom_reserve` 据此判定 |
| 17 | transfer 与 `unbind` 的隔离靠"`new_id=None`"，没写成硬约束 | 表述不足 | N2-6 陷阱 11 写成硬约束 |
| 18 | 账本有界 deque 挤出 `bind` 记录 ⇒ `unbind` 失效；transfer 加速挤出 | 既有边界 | N2-6 陷阱 12 登记为已知边界 |
| 19 | `isinstance(A, (int,float))` 放行 `bool` | 小缺口 | 改 `type(A) in (int, float)`；参数化测试含 `True` |

非阻断项（`dropped` 记录的 `pool_after` 无定义、R→C `Match` 语义、`note` 空串 vs `liquidated:0`）也一并写进 N2-6/陷阱。

## 实现期回改（teach-back 判不出的一类）

| # | 发现 | 性质 | 处置 |
|---|---|---|---|
| 1 | `_shift_age_wealth` **没有下界守卫**：`steps < 0` 越过桶 0 会串到别的 age/gender 桶 | **真 bug 隐患**（原实现只走正 steps，从未触发） | 加 `wealth + steps < 0 ⇒ skip`；文档标为"正确性前提" |
| 2 | `coarsen` / `merge` / `dissolve` **不折 `yearly_inherited`**；快照不带池 | **既有财富漏洞**（`--clusters` 只守人头，结构上看不见） | 引入 `fold_pools` 并在四处调用；快照往返两个池；`history.md` Stage 17 记录 |
| 3 | `_ordered_intents` 静默去重、且键不含 `op` | 违反不变量 8 | 键加 `op`；被去重记 `dropped:duplicate` |

## 值得记住的三条

1. **"人数最少优先"不保证超取最小**：它只减少**被触及的桶数**；最后命中的桶可能 `count` 很大。
   界要按"最大被触及 `count`"写，不能想当然按"最小"写。（#3）
2. **`materialize` 不销毁 mini**：所以"resolved 簇不持池"是错的直觉；生命周期算子里的
   `merge` 快路径 / `split` 是**删簇**的两处，最容易漏折。（#2，`audit_transfer` 的脚本也抓不到）
3. **teach-back 的边界仍在**：它抓到了文档内部矛盾与错界，但"既有代码不折池""`_shift_age_wealth` 无下界"
   这类只有**动代码**才现形（同 N2-5 的结论）。先文档后代码之后，仍需"实现后回改文档"（E6）。
