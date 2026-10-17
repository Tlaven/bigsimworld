# ADR-006: 分辨率折算的财富残差 = 每个 `Measure` 的**符号账**（全局 W 严格）

## 状态

accepted（2026-10-17；实现 = `Measure.conversion_residual` + `record_conversion`；门禁 = `bench.audit_ledger --wealth`）

## 背景

[`adr-005`](adr-005-transfer-quality-side.md) 把质量侧 `transfer` 的残差收进了**每个粗侧的通道池**，
但明确留了一处已知边界（当时的「方案 H」）：

> `unbind` / `dematerialize` / `coarsen` 把具名个体的**精确浮点 wealth** 折回**桶中心**，
> 天然带 ≤ `w/2` 的量化差（`w` = 财富桶宽）。

这不是零头。每次折算平均差 ~0（随机正负），但**有偏**：
年龄/收入结构让个体财富**不落在桶中心**（收入每 30 tick +1000 是精确桶位移，但死亡/继承后就不是了），
所以差值会随人口、随折算次数累积。现状下它**无人记账**（记 `wealth` = 个人精确财富、`c` = 目标桶中心）：

- `IndividualWindow.dematerialize`：窗口 `−wealth`，测度 `+c` ⇒ 世界少了 `wealth − c`；
- `ClusterStore.coarsen`：aggregate 由成员桶中心重建（`measure_from_characters`），随后 `detach` 掉成员 ⇒ 同样少 `wealth − c`；
- `Channel.unbind`：把角色折算回 mini（或全局）⇒ 同样少 `wealth − c`。

（反向的 `materialize` / `bind` / `ClusterStore.materialize` **是精确的**：它们从桶里取走 `c` 并造出 `c`。
所以损失只发生在"精确 → 桶中心"这一个方向。）

⇒ 需求：让**全局** W 在分辨率折算处也严格，否则"财富守恒可审计"只对 `transfer` 成立，对世界不成立。

## 考虑过的方案

### 方案 A：每个 `Measure` 一个**符号**残差账（采纳）
- 新增 `Measure.conversion_residual: float`（**可正可负**）。折算时记 `wealth − c`：
  正值 = "该测度欠世界这么多"（把高于桶中心的个体折低了），负值反之。
- 恒等式扩为：
  ```
  W = Σ_测度 [ count×桶中心 + transfer_pool + conversion_residual + Σ yearly_inherited ]
      + Σ_窗口 wealth
  ```
- 随生命周期折叠（`fold_pools` 一并折），随快照往返（每个粗侧各自恢复）。
- 优点：折算点各写各的、总额严格；出处（哪个测度）保留；与被折叠的计数走同一条路径，**不会漏折**。
- 缺点：多一个**不可花费**的字段要维护；它永不结算（是一条纪律账，不是钱）；数值上可正可负，
  观测面要解释清楚。

### 方案 B：全局单一残差（被拒）
- 优点：一个数就够。
- **拒绝理由**：`coarsen`/`merge`/`dissolve`/`split` 会把测度搬走——全局残差无法回答"这一笔该不该跟着搬"，
  会被**重复计入或漏计**。出处必须随测度走（与 ADR-005 拒绝全局池是同一条理由）。

### 方案 C：让 `Character` 保留"桶内偏移"、折算时精确还原（被拒）
- 想法：给每个真个体存 `wealth − 桶中心`，折算回测度时按偏移补偿。
- **拒绝理由**：`coarsen → materialize` 是**重采样新代表**（身份不守恒，见 engineering-spec §9）——
  偏移跟着身份，一旦重采样就无处可归；且窗口侧要把偏移塞进桶索引，等于重开"分数桶"。
  这正是 Stage 3 被否的碎片化。

### 方案 D：折算前把 `wealth` 四舍五入到桶中心（被拒）
- **拒绝理由**：改模型语义——个体的精确财富是**语义真值**（个体引擎是参照本位）。
  为了让账好看而改真值，是本末倒置；且会改变继承/收敛数字。

### 方案 E：残差并入 `transfer_pool`（被拒）
- **拒绝理由**：`transfer_pool` 是**可花费的流动性**（C→R 会从它付钱）。
  把可正可负的符号残差混进去 ⇒ C→R 能花掉一条"IOU"甚至负余额 ⇒ **凭空造钱**。
  两者必须分账：池是钱，残差是纪律。

### 方案 F：不记，只把 W 的门禁放宽（被拒）
- **拒绝理由**：等于宣布"全局财富守恒不成立"。ADR-005 已把财富列为可审计项，
  放宽度量而不是补账，会让下一次改动（比如继承/婚配的跨分辨率规则）失去护栏。

## 选择

**方案 A。** 规则：

1. **折算点唯一写法**：`record_conversion(measure, space, wealth)` ——
   `bucket = space.wealth_bucket(wealth)`；`measure.conversion_residual += wealth − space.wealth_value(bucket)`。
   仅在"具名个体离场、其财富改由桶表示"时调用：`IndividualWindow.dematerialize`、
   `ClusterStore.coarsen`（每个成员）、`Channel.unbind`（每个折算者）。
2. **精确点不得调用**：`materialize` / `materialize_sample`（角色 `wealth` **取桶中心** `c`，
   不是桶内随机值）/ `ClusterStore.materialize` / `bind`（含成对析出的 `extract(amount=2)`）
   ——它们"移走 `c`、造出 `c`"，天然精确；多记一次就破坏恒等式。
3. **随测度折叠**：`fold_pools(src, dst)` 连同 `transfer_pool` / `yearly_inherited` 一起折 `conversion_residual`
   （`coarsen` / `merge` / `dissolve` / `split` 四处，与 ADR-005 的池生命周期同一套路径）。
4. **随快照往返**：`measure_to_payload` / `measure_from_payload` 带上该字段（旧档缺字段按 0）。
5. **不可花费**：`transfer` 的"可支付总额" = `mass() + transfer_pool`，**不含** `conversion_residual`、也不含
   `yearly_inherited`；残差不进任何池。`Measure.wealth()`（"这个测度的财富总额"）= `mass() + transfer_pool
   + conversion_residual + Σ yearly_inherited`——**观测/审计口径**，不是可花费量。
6. **符号语义**：正 = 该测度把高于桶中心的个体折低（欠世界）；负 = 折高。观测面只报**总额**与**每测度值**，
   不要把它当余额解读。
7. **穷尽性**（"记 or 不记"必须逐路径确认）：具名个体的**离场路径**只有四类——
   （a）窗口容量逐出 / 回填收缩 ⇒ 走 `dematerialize` ⇒ **记**；
   （b）通道 `unbind` 折算 ⇒ **记**；
   （c）共演单元 `coarsen` 收编成员 ⇒ **记**（每个成员；**不得**复用 `dematerialize` 通道，否则同一成员双记）；
   （d）窗口内死亡 ⇒ 走死亡/继承结算（90% 蒸发、10% 给子女），**不是**桶折算 ⇒ **不记**。
   `split` / `merge` / `dissolve` 只搬运已有的计数与残差（`fold_pools`）⇒ **只折、不记**。

### 取舍

- 为了**总额严格**，接受一个永不结算、可正可负的字段；它会让 `Measure` 多一个状态。
- 折算点的调用**必须逐处人工确认**（"精确点 vs 损失点"）：多记/漏记都会破坏恒等式，
  且只有在**跨折算**的长跑里才现形——单点测试守不住，必须配"逐算子 W 探针"。

## 后果

### 正面后果
- **全局 W 严格**：从"transfer 原子严格、别处 ≤ `w/2`"升级为"所有分辨率折算都严格"，
  财富账第一次覆盖整条分辨率链（materialize / coarsen / dissolve / refill / unbind）。
- 与 ADR-005 的池共用同一套折叠路径 ⇒ 生命周期只有一处需要维护（`fold_pools`）。
- 新增一条**逐算子**门禁（`bench.audit_ledger --wealth`），把"折算点写错"变成一个会变红的测试。

### 负面后果
- `Measure` 多一个字段；快照与序列化多一个键（旧档按 0 兼容 ⇒ 旧档恢复后 W 有一次性断点，登记为兼容边界）。
- 残差**永不结算**：它不会变成任何人的钱，也不应被用来做决策（只做审计）。
- 折叠路径变长：`fold_pools` 现在要折三样（池 ×2 + 残差）；漏折任一都会静默丢账。

### 需要跟进的
- 若将来残差量级被证明不可忽略（例如"富族恒富"被判受其影响），再决定是否给它一个**结算**规则
  （那将是新 ADR：残差如何回到分布）。当前证据（`bench.audit_ledger --wealth` 的 worst dev）是**浮点级**。
- `docs/history.md` Stage 18 记录实测数字与"折算点清单"。
- teach-back 对账（独立验证者，判"有缺口但可补"，10 条在实现前补完）：
  [`reviews/2026-10-17-conversion-residual-teachback.md`](../reviews/2026-10-17-conversion-residual-teachback.md)。
