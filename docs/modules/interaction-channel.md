# Module: 交互通道（Interaction Channel） — L3 模块详细

> 本文档定位：做**跨分辨率直接交互**模块工作时加载，可独立喂给 AI。
> 三段式：[是什么] / [为什么] / [不变量]。模板来源 [`docs-templates/module-doc.md`](../../docs-templates/module-doc.md)。
> **本模块已交付：两个原子（身份侧 `bind`/`unbind` = N2-1/N2-4/N2-5；质量侧 `transfer` = N2-6）
> + 第一条交互规则（跨分辨率婚配 = N2-7，默认关）**。
> 规则**默认不注册**（`RULES` 空）⇒ 生产路径的权威数字不变；`SIM_CHANNEL_MARRIAGE=1` 才开启。
> `transfer` 见 [`adr-005`](../decisions/adr-005-transfer-quality-side.md)，婚配规则见 [`adr-007`](../decisions/adr-007-cross-resolution-marriage.md)。

---

## [是什么] — 模块需求与子组件

`novelty=N2`

**功能**：给「共演单元（coarse）↔ 单位个体（resolved）」提供一条**点对点、双向、可具名**的交互路径，
使 R↔C 的交互不必再经由全局测度中转。

对比现有**间接路径**（两跳、匿名、单向）：`C —overflow_fraction→ 全局测度 —materialize→ 窗口`。

**它不做什么**：不定义任何交互语义。通道只保证"意图 → 守恒且确定的现实"这一转换是**正确、可对账、可复现**的；
"什么意图、绑定后建什么边"由**交互规则**（第 9 缝；默认空注册表，第一条见 N2-7）决定。

**术语**（定义见 [`docs/glossary.md`](../glossary.md)，此处只引用）：
交互通道、意图（Intent）、bind、unbind、extract、link、先扣后加律、谓词式寻址、可重建维度、通道账本、交互规则。

**子组件**：

| 子组件 | 职责 | 本期 |
|---|---|---|
| `Intent`（frozen dataclass） | 通道唯一输入形态：`kind / origin / scope / match / payload` | ✅ |
| `Match`（声明式谓词） | 可匹配性；**声明式**而非任意闭包。编译为**桶索引谓词**，两侧共用（见决策 4） | ✅ |
| `InteractionChannel` | 收集意图 → 确定性排序 → 配额闸 → `bind` / `unbind` → 记账本 | ✅ |
| `bind` | 原子：`extract` + `link`（**有身份**，先扣后加） | ✅ |
| `unbind` | `bind` 的逆：`unlink`（断链）+ 把该角色折算回 **coarse**（按**当前**属性落桶，见 N2-4） | ✅ |
| `extract` | 从 coarse `Measure` 按 `Match` 析出 `amount` 个整人并扣减（`_sample_cell` 的按谓词泛化；`amount=2` = N2-5 的成对析出） | ✅（第 0 步已交付） |
| `link` | **边的唯一入口**：一次调用双向写 `relationships`（对称；非对称用 `reverse`）。**不记档**——`relation_record` 只由 `unlink(..., record=True)` 双向追加 | ✅（第 0 步已交付） |
| `InteractionRule`（Protocol + `RULES` 注册表） | 规则缝：**只声明"发起什么意图"**；**建边由通道统一执行**（`link`），规则不碰边。签名（MVP）：`offers(context: ChannelContext) -> Iterable[Intent]` | ✅（第一条规则 = N2-7 跨分辨率婚配，默认关） |
| 通道账本（有界 `deque`，`maxlen=4096`） | 每条操作一条记录，供观测与对账 | ✅ |
| **`transfer`（原子：无身份质量移动）** | 质量侧：继承 / 馈赠 / 族内再分配（C↔C 本期不做） | ✅（N2-6） |

### 本期已交付（第 0 步基础设施，2026-10-17）

**不含任何交互语义**，已落地并可独立验证：

| # | 交付 | 位置 | 验收 |
|---|---|---|---|
| 1 | `link` / `unlink` 边单入口（对称关系 + 非对称 `reverse`；`record=True` 记档） | `app/core/person/links.py` | `tests/test_infra.py` |
| 2 | 已接管站点：广场配对、物化建网、退场断链（child 边）、生育（sibling 与 child-parent）、死亡通知 | `simulation/events.py`、`measure/window.py`、`person/childbirth.py`、`person/death.py` | 同上 |
| 3 | 随机源注入：`IndividualWindow.rng` / `ClusterStore.rng` / `TickContext.rng` **打通为同一实例**（默认仍为模块级 `random`，保持全局 seed 复现） | `measure/window.py`、`measure/cluster.py` | 同上 |
| 4 | `extract(mini, predicate, amount)`：`_sample_cell` 的按谓词泛化 + **候选按桶索引升序**（确定性）+ 扣减内置 | `measure/cluster.py` | 同上 |
| 5 | `person → cluster` 反向索引：按 `store.revision` 惰性重建，`cluster_of` 由 O(簇×成员) 降为 O(1) | `measure/cluster.py` | differential 测试（vs 暴力扫描，长跑 120 tick） |

### 本期已交付（第 1 步：通道骨架，「通电但不做功」）

| # | 交付 | 位置 | 验收 |
|---|---|---|---|
| 9 | `Match` + `compile_match`（声明式 → 桶索引谓词；引用不可重建维度**抛错**） | `measure/channel.py` | `tests/test_channel.py` |
| 10 | `Intent` / `ChannelRecord` / `InteractionChannel`（排序 → 去重 → 配额闸 → reserve → 析出 → link → commit） | 同上 | 同上 |
| 11 | `unbind`（账本定位对端 → `unlink(record=True)` → 按**当前**属性折算回 coarse / 全局测度） | 同上 | 同上 |
| 12 | 失败**逆序全撤**（析出撤销 + reserve 回滚 + `reserved` 配平） | 同上 | `test_bind_rolls_back_fully_when_link_fails` |
| 13 | 接入 `ResolutionManager.step`：`step_coarse` **之后**、`allocate/apply` **之前**；宽限期 `_grace_ids` **分辨率冻结**（不换档、不回收） | `measure/cluster.py` | 同上 |
| 14 | 观测面 `channel_summary()`（配额 / 宽限期 / 账本最近若干条） | `measure/cluster.py`、`measure/channel.py` | — |
| 15 | `_refill` 的**通道名额预留**（`headroom_reserve`；无规则时为 0） | `measure/window.py`、`measure/channel.py` | 惰性不变（全量 `pytest` 141 条） |
| 16 | **探针规则 + 长跑验收**：把 `bind`/`unbind` 接进真实 `ResolutionManager.step` 循环 | `tests/test_channel.py` | 逐次操作守恒 + 同 seed 账本逐条一致 |

**惰性验证**：`RULES` 为空 ⇒ `_collect_intents` 恒返回 `[]` ⇒ 账本零记录、`reserved` 恒 0、
`bench.audit_ledger --resolution/--clusters` 数字不退化（实测 `dev = 0`、`identity error = 0`、
`rho = 2143` 与接入前一致）。

**已交付（2026-10-17，拍板后实现）**：`marital` **双人析出**（N2-5）——`RECONSTRUCTIBLE` 含 `marital`、
`extract(amount=2)` 成对、闸按 `amount` 计、账本 `spouse_id`/`spouse_cell`、双向 `unbind`。
拍板落档见 [`../decisions/adr-003-interaction-channel.md`](../decisions/adr-003-interaction-channel.md)（状态 accepted）；
规格经 **3 轮 teach-back**（对账见 [`../reviews/2026-10-17-N2-5-marital-teachback.md`](../reviews/2026-10-17-N2-5-marital-teachback.md)）。
**实现期又暴露 3 处文档与代码不符**（`link` 无 `record` 参数 / 折算 `marital` 不能一律取 0 /
`made` 必须按人计），均已就地修正。

**mutation 检验**（证"测试本身有效"）：把 `ClusterStore.extract` 的 `mini.add(chosen, -amount)` 改成 `…, 0.0`，
`tests/test_channel.py` 中守恒 / 可逆 / 回滚三条**变红**——测试确实在守不变量。

### 本期已交付（第 2 步：质量侧 `transfer`，2026-10-17）

| # | 交付 | 位置 |
|---|---|---|
| 17 | `Intent.op`（`"bind"` 缺省 / `"transfer"`）+ `payload["amount"]` | `measure/channel.py` |
| 18 | `Measure.transfer_pool`（**每个粗侧一个**）+ `mass()` / `wealth()` | `measure/measure.py` |
| 19 | R→C：个体精确借记 → 目标池；C→R：池/清算 → 个体精确收款 | `measure/channel.py` |
| 20 | 向下清算（人数最少桶优先、整桶）与年度投递（最穷桶优先、整桶） | `channel.py`、`transitions.py` |
| 21 | 池随生命周期折叠：`coarsen` / `merge` / `dissolve`（**含 `yearly_inherited`**） | `measure/cluster.py`、`measure.py` |
| 22 | 快照往返含 `transfer_pool` 与 `yearly_inherited` | `measure/measure.py` |
| 23 | 财富审计：`bench.audit_transfer` + `tests/test_transfer.py` | `bench/`、`tests/` |
| 24 | `ChannelContext.rng`（规则可做**确定性**抽样；= 唯一随机源 `window.rng`） | `measure/channel.py`、`measure/cluster.py` |
| 25 | **第一条交互规则** `MarriageRule`（跨分辨率婚配，N2-7） | `measure/rules.py` |
| 26 | 生产开关 `SIM_CHANNEL_MARRIAGE`（缺省 0 ⇒ 不注册 ⇒ 惰性不变） | `simulation/runner.py` |

**惰性不变**：`RULES` 仍为空 ⇒ 生产里没有任何 `transfer` 意图 ⇒ 新路径不执行，池恒 0；
`pytest` 与 `bench.audit_ledger --resolution/--clusters` 数字不退化。
**已知边界**：`unbind` / `dematerialize` / `coarsen` 把精确财富折回桶中心仍有 ≤ `w/2` 的量化差
（ADR-005 方案 H 未做）——`transfer` 原子自身严格守恒，全局 W 只在无分辨率折算的区间内严格。

### 消歧与冻结面（2026-10-17，个体引擎简化）

**消歧**（不删任何模型功能；收敛数字实测零漂移）：

| # | 内容 | 位置 |
|---|---|---|
| 6 | **删除死字段 `relatives`**，关系人唯一真相源 = `relationships`（求度用 `neighbors`） | `person/character.py`、`person/links.py` |
| 7 | `link`/`unlink` 铺满 `person/*`；广场配对改走 `link`，并**删除从未生效的"亲属避让"检查**（详见陷阱 7） | `person/death.py`、`simulation/events.py` |
| 8 | **rng 注入贯穿个体引擎**：`SimulationEngine`/`EventEngine`/`IndividualWindow` 均持 `rng`，`IndividualEvents`、`PeopleEvents`、`round_up_probability` 全部改用注入的 rng（默认模块级 `random`，故逐位一致性保持） | `simulation/engine.py`、`simulation/event_engine.py`、`person/events.py`、`simulation/events.py` |

**例外（刻意不接管）**：`marry.py` 的 `self_event` 仍是手写 append——`MarryEvent.happen` 的协议是
**每方各调一次**（`a.happen(b); b.happen(a)`），用双向的 `link` 会**重复建边**。改造它需要先改调用协议
（会动个体引擎事件语义），故留待后续。

**已冻结的公共面**（本主题期间不再改动；它们与通道无关，只是让引擎"显得复杂"）：

- 4 层关系漏斗（`acquaintance ≤12 → familiarity ≤6 → friend ≤3 → spouse`）与其概率常数
- 广场分区（`n_cells` / `event_plaza`）与 `PeopleEvents` 的配对策略
- `SimulationEngine` / `EventEngine` 两个 driver（通道从不接触它们）
- DB 队列 / 统计问卷 / Web 发布链

### 第二期（已落地）：质量侧 `transfer`

`transfer`（无身份质量移动）**不是**身份操作。它有一个必须先解决的硬问题：

> coarse 侧的财富只能以 **`count × 桶宽度`** 为最小单位整桶挪动（沿用"整数桶位移"纪律），
> 而具名个体的 `wealth` 是精确浮点 ⇒ **两个方向的转移都必须有量化残差，且残差需要一个"通道池"承接**，
> 否则财富会被凭空造出/销毁。这需要一条**独立的财富守恒不变量**（形如 `bench.audit_ledger` 的 `pool_residual`），
> 与 `bind` 的人头守恒是两码事。

**决策（[`adr-005`](../decisions/adr-005-transfer-quality-side.md)）**：每个**粗侧**各持一个 `transfer_pool`；
R→C 精确借记入池，C→R 精确支付（池不够就向下整桶清算），每 360 tick 把池按整桶投递回分布。
步骤级规格 = **N2-6**。**池随共演单元生命周期折叠**（`coarsen`/`merge`/`dissolve`），否则财富会丢——
这也是本次顺手修掉的既有漏洞（`yearly_inherited` 与快照此前同样不折叠）。

---

## [为什么] — 设计决策与实现方向

### 决策 1：身份侧与质量侧分开，本期只做身份侧
- **身份侧**（`bind`/`unbind`）：产生/解除**持久身份边** ⇒ 必须析出恰好 1 个具名个体。
- **质量侧**（`transfer`）：只动质量、不产生身份 ⇒ 可交换、不需析出；但有上述量化问题 ⇒ 下期。

分界依据是**不重复计数律**（不变量 2）：**会产生边的交互必须先扣后加；只调制速率/质量的交互不必**。

### 决策 2：`bind` 方向无关——**析出永远发生在 coarse 侧**
`Intent` 的字段契约（这是本模块的对外主接口）：

```python
@dataclass(frozen=True)
class Intent:
    kind: str          # 规则名（"marry"/"befriend"/…）；通道不解释，仅透传与记账
    origin: tuple      # 发起者：("character", rid) 或 ("cluster", cid)
    scope: tuple       # 对手侧范围：("cluster", cid) 或 ("window",)
    match: Match       # 可匹配性（作用于**对手侧**）
    payload: dict = field(default_factory=dict)   # 规则私有，通道透传
```

`bind` 的推导（唯一一条路径，两个方向共用）：

1. **coarse 侧** = `origin` 若是 `("cluster", …)` 则取 `origin`，否则取 `scope`（此时 `scope` 必须是 `("cluster", …)`）。
2. **resolved 侧发起者** = `origin` 若是 `("character", …)` 则该角色本人；否则（C 侧发起）在 `scope=("window",)` 里
   按 `match` 选出**一个已有窗口角色**作为对手方。
3. **析出**永远在 **coarse 侧**（唯一没有身份的一侧）：析出整人（1 个；`Match(marital=1)` 时**成对 2 个**，见 N2-5）→ 得到新 `Character`。
4. **建边**：`link(发起者角色, 析出的新角色, kind)`——两者此时**都已是 `Character`**。
   - R→C：发起者是 R，析出的是**对手方**；
   - C→R：析出的是**发起者**（代表该簇），对手方是第 2 步选中的窗口角色。

于是 ②③ 是一套实现、一套验收。

### 决策 3：先扣后加由通道强制，规则免责
规则作者拿不到绕过 `reserve → commit → rollback` 的入口，所以"忘记守恒"在结构上不可能发生。

### 决策 4：寻址只能是谓词式，且两侧共用同一个谓词
- 粗侧**没有 id**（C 是分布）⇒ 意图只能携带 `Match`，id 只在 `extract` **之后**才存在。
  **先设计 id 式 API 一定会推倒重来。**
- `Match` 是**声明**，其字段（**闭区间**，两端都含）：
  ```python
  Match(age=(lo, hi), gender=0|1, wealth_bucket=(lo, hi), marital=0|1)   # 全部可选，None = 不限
  ```
  `wealth_bucket` 用**桶索引**（线性宽 1000），不用财富值——避免"值是连续、桶是离散"的二次换算。
  **`age` 的单位是"岁"**（不是龄段号）：年龄桶是 1:1 的（121 桶 = 0..120），故 `age` 值与桶索引相等。
  **`marital` 是标量 0/1**（不是区间；桶空间里它只有 0/1 两档）。**缺省（`None`）的语义见 N2-5 第 1 步**：
  单人路径自动排除 `marital=1`。
- `Match` 编译为**桶索引谓词** `pred(index) -> bool`，两侧共用：
  - R→C：直接作用于 coarse 的 `occupied` 桶索引；
  - C→R：把每个窗口角色折算成桶索引
    （`space.encode(c.age, gender, space.wealth_bucket(c.wealth), 1 if c.relationships.get("spouse") else 0)`）
    后作用——代价 O(窗口人数) = O(`capacity`)，可接受。
  - **C→R 的对手方选取顺序固定为 `Character.id` 升序取第一个匹配**（不得依赖窗口 `dict` 迭代序）。
- **可重建维度 = `{age, gender, wealth, marital}`**（`RECONSTRUCTIBLE`；2026-10-17 拍板，ADR-003 未定点 1 = **双人析出**）。
  `Match(marital=1)` 合法，但**已婚者不得单独析出**——必须成对（见 N2-5）。
  规则：`Match` 引用 ∉ `RECONSTRUCTIBLE` 的维度 ⇒ 在 `compile` **抛错**（不变量 4）。

### 决策 5：先做通道，再做规则；第一条规则 = 跨分辨率婚配（ADR-007）
通道建设期 `RULES` 为空——"规则未知"恰好是对通道设计的**检验**：零规则 + 探针规则即可完整验收通道。
**2026-10-17 落地第一条真实规则**：[`adr-007`](../decisions/adr-007-cross-resolution-marriage.md) 的
`MarriageRule`（R→C 婚配，默认关）。它只声明意图，守恒/建边/配额/宽限期全部由通道保证（N2-7）。

### 同构参考（不是等同）
"两级互相耦合 + 守恒通量交换"在数值方法里有成熟同构：**自适应网格加密（AMR）的粗/细界面**。

| 本模块 | AMR 对应物 |
|---|---|
| `transfer`（下期） | 粗/细界面的通量修正（flux correction） |
| `reserve → commit → rollback` | **flux register / refluxing** |
| 可重建维度约束 | 限制算符（prolongation）必须良定义 |
| 配额 | 稳定性约束（类 CFL） |

可借其纪律与验收思路（守恒测试 / 反射测试）；**没有对应物的是 `bind`**——让一个 coarse 单元
**吐出一个具名个体**并建立持久关系，在数值方法里不存在。这就是本模块标 N2 的原因。

### 决策 6：窗口预算必须在「常规回填」与「通道」之间分配
`WindowEngine._refill` 每 tick 把窗口补满到 `capacity`。接进真实循环后发现：**通道会被永久饿死**
——窗口恒满 ⇒ `bind` 恒命中 `dropped:window`（单测里逐条调 `channel.run` 时看不到）。
解法（MVP）：**有规则注册时**，`_refill` 预留 `channel.headroom_reserve() = cap_per_tick` 个名额给通道；
**无规则时预留为 0 ⇒ 惰性路径行为与从前完全一致**（全部既有测试不变）。
这样不变量 7 的"窗口不超 `capacity`"被**严格**保持（而不是允许瞬时超出再靠 `enforce_capacity` 收敛）。
预留量是 MVP 取值，可换（与配额同属缝 9 的调参面）。

### 被拒方案
- **边际化建边（匿名对手方）**（被拒）：既**重复计数**（测度层已按速率算过一次），又**伪造身份**
  （产生"半个身份"：有边却无对象）。
- **id 式寻址**（被拒）：粗侧无 id，实现不出来。
- **把交互塞进 `Character.step()` / `PeopleEvents`**（被拒）：通道有**副作用**（改 coarse 分布、改窗口容量），
  且必须确定性排序——事件层做不到。
- **继续用间接路径（全局测度中转）**（被拒）：两跳、匿名、单向，无法具名、无法反向发起。
- **为每条规则各写一套专用通道**（被拒）：违反"机制通用、策略可插拔"
  （见 [`adr-001-resolution-layer.md`](../decisions/adr-001-resolution-layer.md) 的立场）。
- **把 `transfer` 挤进本期**（被拒）：它的财富量化残差池需要独立规格与独立不变量；混进来会让
  人头守恒与财富守恒两种账搅在一起，两个都说不清。

---

## [不变量] — 内部约束与工程注意事项

### 不变量（规则无关；`[强制]` = 有测试 / 检查器）

1. **人头守恒** `[强制]`：通道的身份侧操作（`bind` / `unbind`）不改变 `Σmeasure + ΣCoarse + len(window)`；
   `transfer` 不改变人头（它只动财富）。**财富**守恒是另一条账（不变量 9）。
2. **不重复计数律（先扣后加）** `[强制]`：任何 `bind` 产生的边，都存在一条**先于它**、且与之配对的 coarse 侧质量扣减。
3. **无幽灵** `[强制]`：`bind` 后双方视图闭合；`unbind` 后关系**双向解除**。
   判据（"三查"）= ① 双方 `relationships` 互不含对方；② 双方 `relation_record` 对称记档；
   ③ 该角色已从 `event_plaza["acquaintance"][cell]` 清除。
   **注意：`unbind` 不保证"逐桶复原"**——coarse 侧在绑定期间持续演化（`aging`/`income` 会移动桶），
   折算按**当前**属性落桶（见 N2-4）。跨 tick 的 `unbind` 只保证**人头守恒 + 无幽灵**，不保证回到原桶。
4. **寻址封闭** `[强制]`：`Match` 引用 ∉ `RECONSTRUCTIBLE` 的维度 ⇒ **拒绝（抛错）**，不得静默失配。
5. **确定性** `[强制]`：同 `SIM_SEED` ⇒ 同一份意图序列与账本。
   **随机源只有一个**：`window.rng`（`ClusterStore.rng` 与 `TickContext.rng` 都是它的同一实例）；
   通道与 `extract` 一律用它，**禁止模块级 `random`**。
6. **可交换** `[强制]`：`bind` 的处理结果与"同 tick 内其它**无关**意图"的顺序无关；
   与竞争同一份 coarse 质量的意图**相关但确定**（由不变量 5 的排序保证）。
7. **配额有界** `[强制]`：单簇单 tick 析出 ≤ `cap_per_cluster`；单 tick 总析出 ≤ `cap_per_tick`；
   窗口不超 `capacity`。**按人计，且闸必须 `amount` 感知**（N2-1 第 4 步）——否则双人析出会越过上界。
   **取值**：`cap_per_cluster=2`、`cap_per_tick=8`（常数）。
8. **可对账** `[强制]`：每条通道操作（含每次丢弃）在账本有且仅有一条记录；逐条可核平。
9. **财富守恒（transfer 口径）** `[强制]`：
   `W = Σ 全局测度 + Σ 每个簇 mini + Σ transfer_pool（全局与各 mini） + Σ yearly_inherited + Σ 窗口个体 wealth`
   （每项都是 `count×桶中心`；**resolved 簇的 mini 残留也要算**）。
   在 `transfer` / 清算 / 投递 / 池折叠下**严格不变**（浮点容差）。
   **注意**：`bind`/`unbind`/`dematerialize`/`coarsen` 的桶中心折算仍有 ≤ `w/2` 的量化差
   （ADR-005 方案 H，已知边界）——全局 W 的严格性只在"无分辨率折算"的区间内成立。
10. **池非负** `[强制]`：任何时刻 `measure.transfer_pool ≥ 0`；不存在"预支"。
    C→R 必须先保证"池 + 可清算量 ≥ 金额"才动分布；不足 ⇒ 整笔丢弃、**零副作用**。
11. **方向守恒** `[强制]`：R→C 与 C→R 是同一个原子（`op="transfer"`，`payload["amount"]`），
    唯一区别是发起者/对手方；两者都**不创建身份、不建边、不改窗口容量**。
12. **池随生命周期折叠** `[强制]`：`coarsen` / `merge` / `dissolve` / `split` 必须同时折叠
    `transfer_pool` 与 `yearly_inherited`（逐段相加），不得只折 `counts`。
    `materialize` 保留 mini（分数残留 + 池）⇒ **resolved 簇也可能持池**；其池在 resolved 期间冻结
    （不接 transfer，年度投递仍可把它送回该 mini 的残留分布）。`merge` 的 resolved+resolved 快路径
    与 `split` 也必须先把被删簇的 mini 折走（否则人头与财富一起丢）。
13. **配额豁免** `[强制]`：transfer **不**消耗 `cap_per_cluster` / `cap_per_tick` / 窗口 headroom，
    也**不**登记 `recently_active`（它不产生需要保护的身份）。反过来说，配额闸只属于 `bind`。

### N2 步骤级说明

**N2-1 · `bind` 的先扣后加提交协议**

1. **收集**：R 侧意图在 `window.step()` 之后由规则提供；C 侧意图在 `store.step_coarse()` 之后由规则提供。
   两路都经 **`channel.submit(intent)`** 进本 tick 队列。**默认 `RULES` 为空 ⇒ 两条路都不产生意图**（通道惰性）；
   开启 N2-7 后，R 侧意图由规则在 `_collect_intents` 产出（`store.step_coarse()` + `_settle_transfer_pools` **之后**、
   `channel.run()` **之前**）——因此规则看到的 coarse 权重与同 tick 的 `extract` **同源**。
2. **排序**：按 `(origin_side, origin_id, op, kind, scope_type, scope_id)` 升序（`origin_side`：`character`=0、`cluster`=1；
   `scope_type`：`cluster`=0、`window`=1）。字符串比大小即可（Python 元组比较），**唯一确定的处理序**。
3. **去重**：同一 `(op, origin, kind, scope)` 只保留第一条（**含 `op`**——否则 bind 与 transfer 会互撞、
   transfer 的 `amount` 会被静默吞掉）；被去重的意图各记一条 `dropped:duplicate`（不变量 8：
   含丢弃在内**每条意图都有记录**）。同一 `(op, origin, kind, scope)` 同一 tick 只能发一次；
   要发多笔请换 `kind`。
4. **配额闸（`amount` 感知）** `[强制]`：设本次意图需要的析出量 `amount`（单人路径 = 1；婚配成对 = 2，见 N2-5）：
   `per_cluster + amount > cap_per_cluster` ⇒ 丢弃（记 `dropped:quota_cluster`）；
   `made_total + amount > cap_per_tick` ⇒ 丢弃（记 `dropped:quota_tick`）；
   `len(window) + reserved + amount > capacity` ⇒ 丢弃（记 `dropped:window`）。
   **闸必须在 reserve 之前、按 `amount` 判定**——否则婚配意图会在"只剩 1 个名额"时挤进来，
   事后 `+= 2` 直接**破坏不变量 7**。
   **口径统一**：闸、`per_cluster`、`made_total`、报告里的 `made` **一律按人计**（成对 = 2）——
   `run()` 按"本次实际析出人数"累加，而不是"每个成功意图 +1"。
5. **解析两侧**（决策 2 第 1–2 步）：定出 `coarse_cluster` 与 `initiator_character`。
   任一解析不出（簇不存在 / 窗口侧无匹配 / 发起者已离场）⇒ 丢弃（记 `dropped:stale` 或 `dropped:no_match`）。
6. **reserve**：在 `coarse_cluster` 的 mini `Measure` 上，取满足 `Match` **且** `count ≥ amount` 的候选桶
   （单人 1.0；成对 2.0，见 N2-5），**按桶索引升序**后做**计数加权抽样**（用 `ctx.rng`）。候选为空 ⇒ 丢弃（记 `dropped:no_match`）。
   随后 `mini.add(cell, -amount)` 并 `reserved += amount`。
   - **此刻起质量已离开 coarse 侧。**
7. **析出**：由 `(age, gender, wealth_bucket)` 造新 `Character` 并入窗口（`window.attach`）。
   - **不写 `coarse_cluster.member_ids`**：coarse 簇的 `member_ids` 按契约**必须为空**（`cluster-contract.md` §1）；
     析出者是"与该簇相连的具名个体"，不是它的成员。若建的是**亲属**边，下一个 `form_interval` 的
     `_reconcile` 会按既有机制把它抽入（level→1）；非亲属边则保持浮动——这正是想要的语义。
   - **第 7 步抛异常**（`generate_character` / `window.attach`）⇒ 回滚第 6 步：`mini.add(cell, +amount)`、
     `reserved -= amount`、丢弃（`dropped:error`）。
8. **link**：`link(initiator_character, new_character, kind)`——双向写 `relationships`（**`link` 不记档**；`relation_record` 只由 `unlink(..., record=True)` 追加）。
   - **第 8 步抛异常** ⇒ **逆序撤销第 7 步**（`window.detach(new_id)`）**+ 回滚第 6 步**
     （`mini.add(cell, +amount)`、`reserved -= amount`）、丢弃（`dropped:error`）。
     **回滚清单必须是"已完成步骤的逆序全撤"**——只回滚测度会留下"已入窗口的真人 + 测度已退"，
     破坏不变量 1（人头守恒）与不变量 3（无幽灵）。
9. **宽限期登记**：`recently_active[cid] = tick`。**放在建边成功之后**——失败的意图不该给簇一段宽限期。
10. **commit**：账本追加一条 `ok` 记录；`reserved -= amount`。

> 上面第 6–10 步里的 `amount`：单人路径 = 1；`Match(marital=1)` 时 = 2（**成对析出**，
> 多一条 `spouse` 边与一个配偶回滚对象——完整规格见 **N2-5**）。

> **`bind` 只对 `level==0`（coarse）簇有效**：resolved 簇的成员本就是具名角色，规则可直接取用，无需"析出"。
> 命中 resolved/不存在的簇 ⇒ `dropped:stale`。

**账本记录形状（统一，`ok` 与 `dropped:*` 同一结构）**

```python
@dataclass(frozen=True)
class ChannelRecord:
    tick: int
    status: str                 # "ok" | "unbound" | "dropped:duplicate" |
                                # "dropped:quota_cluster" | "dropped:quota_tick" | "dropped:window" |
                                # "dropped:stale" | "dropped:no_match" | "dropped:error" |
                                # transfer 专用：dropped:bad_op | dropped:bad_amount | dropped:unsupported_match |
                                #               dropped:insufficient_funds | dropped:illiquid
    kind: str
    origin: tuple
    scope: tuple
    cell: int | None = None         # reserve 到的桶；未 reserve 时为 None
    delta_mass: float = 0.0         # ok 时 = -1.0；其余为 0.0
    initiator_id: int | None = None # 意图边**非 `new_id` 的一端**（恒为窗口侧：R→C=R，C→R=W）；
                                    # unbind 靠它定位对端（N2-5 第 5 步）
    new_id: int | None = None
    spouse_id: int | None = None    # 仅 N2-5 双人析出：配偶 id（`new_id` 记 `a`）
    coarse_id: int | None = None    # 析出源簇（unbind 靠它决定折算回簇还是全局测度）
    spouse_cell: int | None = None  # 仅 N2-5 的 `unbind`：配偶的折算目标桶
    op: str = "bind"                # "bind" | "transfer"（N2-6）
    wealth_delta: float = 0.0       # transfer ok：以**窗口个体**为口径（付 = 负，收 = 正）；其余 0
    pool_after: float = 0.0         # transfer ok：目标粗侧的 `transfer_pool` 余额；其余 0
    note: str = ""                  # dropped:error 存异常摘要；transfer 可记 `liquidated:<mass>`
```

**N2-4 · `unbind` 契约**

1. **定位**：由 `new_id` 在该 `kind` 的 `ok` 记录里查得 `initiator_id` 与 `cell`（一个 `new_id` 只可能由一次
   `bind` 创建 ⇒ 唯一）。
2. **两端的边**：`unlink(record.initiator_id, new_id, record.kind)`（`record=True`）——**不猜"哪条边"**，就是这条。
   （`initiator_id` 的定义见 N2-1 的账本形状与 N2-5 第 5 步：**恒为意图边非 `new_id` 的一端**。）
3. **折算回 coarse**：把该角色按**当前** `(age, gender, space.wealth_bucket(wealth), marital=0)` 折算回
   `coarse_cluster` 的 mini 引擎（`mini.add(encode(...), +1.0)`），随后 `window.detach(new_id)`、
   `coarse_cluster.member_ids.discard(new_id)`。
   - **`marital` 按该角色"当时"的 `relationships["spouse"]` 判定**（在 `unlink` 之后取）：
     **不保证是单身**——绑定期间窗口内可能新结了婚，一律取 0 会把已婚者折回单身桶。
     （`detach` 会解除关系 ⇒ 口径必须在 `detach` **之前**取。）
   - **不**用账本里的 `cell` 强写回：coarse 侧在此期间持续演化，强写回会把一个已变老/变富的人塞回旧桶，
     破坏 mini 的年龄结构。代价是**不保证回到原桶**（见不变量 3 的注意）。
   - 若 `coarse_cluster` 已被回收/`dissolve` ⇒ 折算回**全局测度**（该角色退场，人头不变）。
4. **失败语义**：`new_id` 不在窗口 ⇒ 返回 `False`，不抛错；应在窗口但查不到账本记录 ⇒ 返回 `False` 并记一条
   `dropped:error`（供对账发现）。
5. **`unbind` 可跨 tick 调用**（宽限期正是为此存在）；同一 tick 内调用时 `unbind` 应与 `bind` 记录**独立**，
   不合并、不抵消。
6. **账本**：`unbind` 追加一条 `status="unbound"` 的记录（`delta_mass=+1.0`，`cell` = 折算的**目标桶**；
   并带 `new_id` 与 `initiator_id`，便于把该记录**挂回**原 `bind` 记录——对账需要）。

**N2-5 · `marital` 双人析出（已婚者不得单独析出）**（2026-10-17 拍板并实现）

**为什么**：个体引擎里"已婚"**不是属性**，而是 `relationships["spouse"]`（一条双向边）。
从 `marital=1` 的桶析出**1 个人**，必然造出一个**假单身**（今天的物化路径正是如此：丢 `_marital`、
`generate_character` 默认单身）。所以"寻址已婚"在语义上**只能**成对。

**步骤级说明**

1. **寻址**：`Match(marital=1)` 合法（`RECONSTRUCTIBLE` 已含 `marital`）。`Match(marital=0)` 走原有单人路径。
   **`Match(marital=None)`（缺省 = 不限）在单人路径下自动排除 `marital=1` 桶**——否则会造出 N2-5 明令禁止的
   假单身（"已婚者不得单独析出"是**硬规则**，不因谓词缺省而失效）。⇒ 本期的"不限"实为"未婚或未指定婚配"；
   要寻址已婚**必须显式** `marital=1`（成对）。
   **`amount` 只由 `match.marital` 决定**（`= 1` ⇒ 2；否则 ⇒ 1）⇒ 闸在 reserve **之前**即可判定（N2-1 第 4 步）。
   **该排除只作用于 coarse 侧的析出**：C→R 的**窗口侧对手选取**不受它影响——窗口角色本就是真个体，
   其 `marital` 由 `relationships["spouse"]` 折算（决策 4），不存在"假单身"问题。
2. **成对析出**：命中 `marital=1` 时，`extract(mini, predicate, amount=2.0)` —— **同一桶取 2.0**，得到一个桶索引。
   候选桶由 `extract` 内部按 `count ≥ amount` 过滤 ⇒ 此时天然是 `count ≥ 2.0`（N2-1 第 6 步的 `count ≥ 1.0` 在 `amount=2` 下的特例）。
3. **前置条件**：该桶 `count ≥ 2.0`（两个人都在桶里）。不足 ⇒ `dropped:no_match`。**禁止跨桶凑对**——
   不同桶的两人年龄/财富都不同（**代价见下「性别与"重建哪段婚姻"」**）。
4. **两个析出者 `a` / `b` 的确定（方向无关）**：`a` = 那一对里**承接意图边**的一个；`b` = `a` 的配偶。
   **`a`/`b` 由 `window.attach` 的调用序决定**（先 attach 的是 `a`）——不得依赖 `dict` / `set` 迭代序（不变量 5）。
5. **重建婚姻 + 建意图边**（方向语义**完全复用决策 2**，两者都必须是 `Character` 之后才建边）：
   - 先 `link(a, b, "spouse")`——这是"重建既有婚姻"，不是"新办婚事"（`link` **不记档**，见 N2-1 第 8 步）；
   - **R→C**（发起者是窗口角色 `R`，析出的是**对手方**）：`link(R, a, intent.kind)`；
   - **C→R**（析出的是**簇的代表**）：`link(a, W, intent.kind)`，`W` = 决策 2 第 2 步选出的窗口角色。
   - **账本 `initiator_id` 的唯一规则**：**恒为意图边"非 `new_id` 的一端"**——R→C ⇒ `R`；C→R ⇒ `W`
     （**不是** `a`！）。这条规则让 N2-4 第 2 步的 `unlink(record.initiator_id, new_id, record.kind)`
     对两个方向**都**成立；若 C→R 存成 `a`，`unbind` 会退化成 `unlink(a, a)`（空操作），
     `a—W` 边**永不解除** ⇒ 违反不变量 3（无幽灵）。
   - ⚠️ **两个"发起者"不是一回事**：**语义发起者**在 C→R 下是**簇**（由析出的 `a` 代表），
     而**账本 `initiator_id`** 恒指**窗口侧**那一端（R→C 的 `R` / C→R 的 `W`）。别混用这两个词。
6. **配额按人计**（闸见 N2-1 第 4 步，按 `amount=2` 判定）：reserve 时 `reserved += 2`；成功时
   `per_cluster[cluster.id] += 2`、`made_total += 2`。
   ⚠️ **一次婚配绑定即用满单簇配额**（`cap_per_cluster=2`）⇒ 单簇单 tick 至多一次婚配绑定；
   若该簇本 tick 已析出 1（单人路径），后续婚配意图会被**闸**丢弃（`1 + 2 > 2`）。
7. **账本**：**一条** `bind` 记录，`delta_mass = -2.0`；`ChannelRecord` 新增两字段——`spouse_id`
   （配偶 id；`new_id` 记 `a`）与 `spouse_cell`（bind 时为 `None`，`unbind` 时填配偶的折算目标桶）。
   `initiator_id` 按第 5 步的唯一规则（窗口侧那一端）。**commit 时 `reserved -= 2`**（N2-1 第 10 步的 `-= 1` 在此为 `-= 2`）。
8. **回滚（逆序全撤）**：任一步失败 ⇒ `unlink` 已建的边（先 `intent.kind`、再 `"spouse"`）→ `detach` 两人 →
   `mini.add(cell, +2.0)` → `reserved -= 2`。**只回滚测度会留下幽灵**（同 N2-1 第 8 步）。
9. **`unbind`**：断**两条**边——`unlink(record.initiator_id, new_id, record.kind)` 与 `unlink(a, b, "spouse")`
   （均 `record=True`）——然后两人各按**当前**属性折算回 coarse（或全局测度）。
   **折算的 `marital` 按"当时"的 `relationships["spouse"]` 判定**（两条配偶边都已断 ⇒ 通常为 0，
   但**不强制**——绑定期间窗口内可能新结了婚；同 N2-4 第 3 步口径）。
   **账本一条** `status="unbound"`：`delta_mass = +2.0`、`cell` = `a` 的折算目标桶、
   `spouse_cell` = `b` 的折算目标桶（两人可能落**不同**桶——绑定期间 `income`/`aging` 会移动它们；
   见不变量 3 的注意）。簇已回收 ⇒ 两人都折算回全局测度。
   **配偶 `b` 已不在窗口**（被逐出 / 离场）：只解除**仍存在**的边、只折算**仍在窗口**的那一个；
   仍记一条 `unbound`（`spouse_cell = None`，`note` 记 `spouse_gone`），**不抛错**（与 N2-4 第 4 步同精神）。
   **反向（`a` = `new_id` 已离场、`b` 仍在窗口）**：按 N2-4 第 4 步**返回 `False`**，不抛错；
   `b` 的状态由它自己的离场 / `unbind` 路径处理——**不**在这里顺手折算（避免双重记账）。
   `unbound` 记录同样带 `new_id` / `initiator_id`（挂回原 `bind`）。

**精确例子**

- **R→C**：桶 `count=2.0 @ encode(30, 0, b, 1)`、`Intent(origin=("character", R.id), scope=("cluster", cid), match=Match(marital=1), kind="probe")`
  ⇒ 该桶 `2.0 → 0.0`；`len(window) +2`；`a`/`b` 之间有 `spouse` 边；**`R ↔ a`** 有 `probe` 边（不是 `R ↔ b`）；
  账本 1 条 `delta_mass=-2.0`、`new_id=a`、`spouse_id=b`；`per_cluster` 记 2 ⇒ 该簇本 tick 再收不到第二个意图。
- **C→R**：`origin=("cluster", cid)`、`scope=("window",)`、`match=Match(marital=1)`，窗口内有匹配的 `W`
  ⇒ 析出的一对是**簇的代表**：`a` = 承接意图边的那一个（语义发起者 = 簇），`b` = `a` 的配偶；
  `link(a, b, "spouse")` + `link(a, W, "probe")`；账本 `new_id=a`、`spouse_id=b`、
  **`initiator_id=W`**（窗口侧那一端，见第 5 步）。
- 桶 `count=1.0 @ marital=1` ⇒ `dropped:no_match`（**凑不出一对**，宁可丢弃也不造假单身）。
- `Match(marital=0)` ⇒ 单人路径，行为与从前逐位一致。

**性别与"重建哪段婚姻"（两条已知性质，不是缺陷）**

- **聚合态不记录"谁与谁"** ⇒ 成对析出重建的是**一段合法婚姻**，不是**原来那段婚姻**（身份在本层本就不守恒：
  `coarsen → materialize` 是重采样新代表，见 `engineering-spec.md` §9）。
- **`gender` 是桶维度** ⇒ 同桶取 2 必然**同性**。这在本模型里**合法**：个体引擎的婚配**无性别约束**
  （`spouse_event` 只筛 `18 ≤ age < 60` 且未婚，见 `app/core/person/events.py`），测度层的婚配维度同样是"性别中立"的。
  若将来要**异性配对**，需改成跨 `gender` 桶取对（新原语 + 新不变量，属**独立决策**）。

**验收**:`python -m pytest tests/test_channel.py -q` → 全绿，覆盖：`test_paired_extraction_conserves_headcount_and_builds_spouse_edge`（同桶取 2.0 + `spouse` 边 + 人头守恒）、
`test_paired_extraction_needs_two_in_the_bucket`（只有 1 人 ⇒ `dropped:no_match`）、
`test_unspecified_marital_never_extracts_a_married_bucket`（缺省谓词不得单人析出已婚桶）、
`test_quota_gate_is_amount_aware`（已析出 1 后成对意图被丢弃 ⇒ 守住不变量 7）、
`test_paired_unbind_severs_both_edges_and_folds_back_both`、`test_paired_bind_rolls_back_both_when_link_fails`；
**长跑**（接进真实 `ResolutionManager.step` 循环）：`test_channel_ops_are_mass_neutral_in_long_run` 里含一条 `Match(marital=1)` 探针规则
⇒ 成对析出与其 `unbind` **在真实循环里逐次操作守恒**，且测试**断言该路径确实被执行到**（否则断言是空的）；
`python -m bench.audit_ledger --resolution --n 3000 --steps 2000 --capacity 300` → 逐算子 `identity error = 0`（**惰性不变**：无规则时该路径不执行）。
**mutation 检验**（证测试有效）：把闸改回"按 1 判定" ⇒ `test_quota_gate_is_amount_aware` 变红（实测析出 **3** > cap 2）；
去掉缺省排除 ⇒ `test_unspecified_marital_never_extracts_a_married_bucket` 变红。

**范围声明（本次不动）**：物化丢婚配的**其余两条路径**——`ClusterStore.materialize`（分辨率层析出代表）
与窗口 `_refill`（`materialize_sample`，从全局测度抽样代表）——**本次不改**：它们是"抽样代表"，
成对析出会改**窗口人口构成**与回填口径（属独立决策）。二者记为**已知近似**（状态：planned，集中在此处）。

**陷阱**

- **配额 / headroom 闸必须按 `amount` 判定**（N2-1 第 4 步）：按"1 个"判会让婚配意图在只剩 1 个名额时挤进来，
  事后 `+= 2` ⇒ 破坏不变量 7。这是本单元最容易被写错的一处。
- **C→R 时账本 `initiator_id` 存 `W`（窗口侧），不是 `a`**：存错 ⇒ `unbind` 退化成 `unlink(a, a)`，
  `a—W` 边永不解除（幽灵）。别把"语义发起者（簇，由 `a` 代表）"与"账本 `initiator_id`（窗口侧那一端）"混用。
- 不得"析出 1 人 + 伪造配偶边"（幽灵边）；不得跨桶凑对。
- **`a` / `b` 的确定必须来自 `window.attach` 的调用序**，不得依赖 `dict` / `set` 迭代序（不变量 5）。
- 析出者**从不进** `coarse_cluster.member_ids`（N2-1 第 7 步）；N2-4 第 3 步的 `discard` 是**幂等防御**，不是"曾经写进去过"。
- 别把本规则推广成"所有 `marital=1` 的析出都成对"——`ClusterStore.materialize` / `_refill` 当前**有意**不遵守（范围声明）。

**N2-6 · `transfer` 质量侧（每粗侧池 + 整桶清算/投递）**（2026-10-17 拍板并实现）

**为什么**：见 §第二期与 [`adr-005`](../decisions/adr-005-transfer-quality-side.md)。一句话——
粗侧财富的最小可动单位是 `count × w`，个体的 `wealth` 是精确浮点；差额必须由**每个粗侧各自的池**承接，
否则要么凭空造/毁财富，要么跨族泄漏。`transfer` 是**无身份**原子：不 `extract`、不 `link`、不占窗口名额。

规格经 **1 轮 teach-back**（独立验证者，判"有缺口但可补"；14 条缺口在实现前全部补完）——
对账与"实现期回改"见 [`../reviews/2026-10-17-transfer-teachback.md`](../reviews/2026-10-17-transfer-teachback.md)。

**对象**

- `Intent.op = "transfer"`（缺省 `"bind"`）；`payload = {"amount": A}`；`kind` 只作标签（不是边名）。
- `origin` / `scope` 与 `bind` 同构：
  - **R→C**：`origin=("character", rid)`、`scope=("cluster", cid)`；
  - **C→R**：`origin=("cluster", cid)`、`scope=("window",)` + `Match` 选**接收者**。
- 粗侧池 = 该簇 `state["engine"].measure.transfer_pool`（**每个 Measure 一个**；全局测度也有，供 `dissolve` 汇入）。
- `Measure.mass()` = `Σ count × 桶中心`；
  `Measure.wealth()` = `mass() + transfer_pool + conversion_residual + Σ yearly_inherited`（**观测/审计口径**，
  见 [`adr-006`](../decisions/adr-006-conversion-residual.md)）。
  **可支付总额** = `mass() + transfer_pool`（`yearly_inherited` 是继承专用、`conversion_residual` 是**不可花费**的
  符号账，两者都不得挪用）；
  **可清算量** = 其中 `wealth_bucket > 0` 的桶能向下整桶挪出的质量（bucket 0 不可清算）。
  `可支付总额 ≥ A` 只保证"总额够"；若可清算量 + 池 < A，仍是 `illiquid`。

**步骤级说明**

1. **分派**：`op="bind"` 走 N2-1；`op="transfer"` 走本单元。未知 `op` ⇒ `dropped:bad_op`。
2. **解析两侧**（复用 `_resolve_sides`）：目标簇必须 `level==0`；R→C 的发起者必须在窗口；
   C→R 的接收者按 `Match` 过滤后取 `id` 最小者。任一解析不出 ⇒ `dropped:stale` / `dropped:no_match`。
   - **R→C 不接受 `Match`**：`Match` 非空（`used_dimensions()` 非空）⇒ `dropped:unsupported_match`。
   - **只支持 R↔C**：C↔C 与 resolved 簇 ⇒ `dropped:stale`（见「边界条件」）。
3. **校验金额**：`A = payload["amount"]`，必须 `type(A) in (int, float)`（**排除 `bool`**）、
   `math.isfinite(A)`、`A > 0`；否则 `dropped:bad_amount`。**不得抛错**（规则给的坏金额是运行期数据，不是契约违例）。
4. **R→C**：`A > character.wealth + 1e-12` ⇒ `dropped:insufficient_funds`；
   否则 `character.wealth -= A`、`mini.transfer_pool += A`。**不立即改分布**。
   账本 `ok`：`op="transfer"`、`wealth_delta=-A`、`pool_after=mini.transfer_pool`。
   不占配额、不占 headroom、不登记 `recently_active`。
   `bind`/`materialize` 的析出者 `wealth = space.wealth_value(bucket)`（**桶中心**）⇒ 它们是精确的，
   **不带**量化差；量化差只出现在 `unbind`/`dematerialize`/`coarsen` 的"精确财富 → 桶中心"方向。
5. **C→R**：
   1. **可支付性**：`total = mini.mass() + mini.transfer_pool`；`A > total + 1e-9` ⇒ `dropped:insufficient_funds`（零副作用）。
   2. **缺口**：`shortfall = A - mini.transfer_pool`；`shortfall <= 1e-9` ⇒ 无需清算。
   3. **清算计划**（**只算不改**）：候选 = `occupied` 中 `wealth_bucket > 0` 的桶，按
      `(count, −wealth_bucket, index)` **升序**（**人数最少优先**；并列取更富的桶；再并列取索引小者）。
      对每个桶：`unit = count × w`；`k = min(wealth_bucket, ceil(shortfall / unit − 1e-12))`；
      `k > 0` 记入计划，`shortfall -= unit × k`；`shortfall <= 1e-9` 即停。
      扫完仍 `shortfall > 1e-9` ⇒ `dropped:illiquid`（**零副作用**：计划尚未应用）。
      **`k ≤ wealth_bucket` 是正确性前提，不是口味**：`_shift_age_wealth` 不检查下界，
      `steps < 0` 越过桶 0 会把索引串到别的 age/gender 桶（测试必须守）。
   4. **应用清算**：计划按**源桶财富升序**应用 `_shift_age_wealth(mini, space, [index], -k)`；
      返回值 `paid < 0` 是**实际移出**的质量，`mini.transfer_pool += -paid`。
      **不得**用 `count×k×w` 重算（触底/触顶分支可能不支付）。
      **为什么升序**：源桶只可能被更高桶注入；先处理低桶可保证每个源桶在应用时仍是原始计数，不会级联重复扣减。
   5. **支付**：**硬前提 `mini.transfer_pool ≥ A`**（计划必须保守：宁可多清算一步，也绝不欠付）。
      满足后 `mini.transfer_pool -= A`、`character.wealth += A`；
      账本 `ok`：`wealth_delta=+A`、`pool_after` 为支付后的池；`note` 记 `liquidated:<实际清算质量>`
      （实际清算为 0 时省略 `note`）。**不得**用 `max(0, …)` 钳制——钳制会凭空造财富。
6. **投递（settle）**：每 360 tick，对**全局测度 + 每个簇的 mini**（含 resolved 簇的残留）调
   `deliver_transfer_pool(measure)`：
   - **`pool <= 0` ⇒ 不动**（不要用 `pool < w`：`count < 1` 的桶一步只值 `count×w < w`）。
   - **目标只取 `count ≥ 1.0` 的整人桶**（分数桶是残留质量，不在年度投递里被抬升；
     它们的池等 `coarsen`/`dissolve` 或计数长到 ≥1 再处理）。
   - 目标按**财富桶升序**（最穷优先）；对每桶
     `k = min(wealth_bins − 1 − wealth_bucket, floor(plan_pool / (count × w)))`；`k > 0` 记入计划，
     并从计划池扣 `count×k×w`。
   - 计划按**目标桶财富降序**应用 `_shift_age_wealth(..., +k)`，按**实付量**扣池；
     余量留池。**为什么降序**：与清算相反——目标是"向上"，先处理高桶才不会把低桶刚收到的质量再搬一次。
   - 投递是再分配：最穷桶优先是 MVP 口味（ADR-005），不是守恒要求。
   - **相位**：`ResolutionManager.step` 里 `store.step_coarse()`（含继承年清算）**之后**、通道 `run()` **之前**。
     先年度结清、再做本 tick 意图；`mass + pool` 不因投递改变，所以这不是"提高支付能力"，
     而是"避免池跨年累积、让分布先吃到钱"——代价是 C→R 更常走清算。
7. **生命周期折叠**：`coarsen` 在建好 aggregate、折完计数残留后，把旧 mini 的 `transfer_pool` 与
   `yearly_inherited` **逐段相加**到 aggregate；`merge` 把 b 折进 a（**resolved+resolved 快路径**也要折，
   否则 b 的 mini 残留与池一起蒸发）；`dissolve` 折进全局测度；`split`（MVP 只切 resolved）把被删簇的
   mini 残留与池**折进全局测度**（没有"分给哪个孩子"的策略，不做猜测）。
   **只折 `counts` 会丢财富**——这是本次修掉的既有漏洞；快照 `measure_to_payload` / `measure_from_payload`
   必须同时往返两个池；**旧档缺字段按 0 读**（这意味着 `SIM_RESUME=1` 从旧档恢复时 W 有断点，
   登记为兼容边界，不是守恒失败）。
8. **对账**：`W = 全局 measure + Σ 每个簇 mini + Σ 池 + Σ yearly_inherited + Σ 窗口 wealth`
   （每项 `count×桶中心`）；
   `transfer` / 清算 / 投递 / 折叠都是 W-中性。账本新增 `op` / `wealth_delta` / `pool_after`；
   `run()` 报告新增 `transferred`（成功转移的金额绝对值之和）。丢弃 = 零副作用（分布、池、个体财富都不动）。

**精确例子**

- **R→C**：`R.wealth=3000`、`mini.transfer_pool=0`、`A=2500`
  ⇒ `R.wealth=500`、池 `2500`；mini 的 `counts` 与 `mass()` **不变**；W 不变。
- **C→R（池够）**：池 `2500`、`A=500` ⇒ 池 `2000`、`W.wealth += 500`；无桶位移。
- **C→R（需清算）**：mini 有 `count=3 @ wealth=10`（mass `31500`）与 `count=1 @ wealth=5`（mass `5500`），池 `0`，`A=500`
  ⇒ 候选先命中 `count=1 @ 5`：`unit=1000`、`k=1`；桶 `5→4`，池 `1000`，付 `500` 后池 `500`；
  `count=1` 的居民整体从 5500 降到 4500（**超取 500** 留在池里）；W 不变。
- **C→R（只剩 bucket 0）**：mini 只有 `count=4 @ wealth=0`（mass `2000`）、池 `0`、`A=500`
  ⇒ 总额够，但没有可下移的桶 ⇒ `dropped:illiquid`；**零副作用**（这不是 `insufficient_funds`）。
- **超取上界（反例，别记成"最小 count"）**：`count=1 @ 5` + `count=3 @ 6`、池 `0`、`A=6000`
  ⇒ 计划 `{5: 5 步（5000）, 6: 1 步（3000）}`（先按 count 升序命中 5，缺口剩 1000，再命中 6）
  ⇒ 实付 8000，**超取 2000**，池余 2000。**超取上界 = 被清算桶中 `count` 最大的那个 × `w`**
  （此处 3×1000 > 1×1000），不是"最小 count × w"。
- **清算的级联陷阱（升序才安全）**：沿用上例，若**降序**应用（先 `6→5`，桶 5 变 4 人，再移 5 步）
  ⇒ 实付 `4×5×1000 + … = 20000`，是计划的 2.5 倍。**触发条件是"计划序 ≠ 财富序且低桶 count 更大"**，
  不是"任何相邻桶"。
- **投递**：池 `2500`；桶 `count=1 @ wealth=1` 与 `count=1 @ wealth=10`
  ⇒ 计划：桶 1 取 `k=2`（`2000`）、池余 `500`；桶 10 的 `floor(500/1000)=0`；
  按降序应用 ⇒ 桶 1 → 3；池 `500`；W 不变。
- **投递的级联陷阱（降序才安全）**：池 `4500`；`count=3 @ 9` + `count=1 @ 10`
  ⇒ 计划 `{9: 1 步（3000）, 10: 1 步（1000）}`。降序应用（先 `10→11`，再 `9→10`）⇒ 实付 4000、池 500；
  若**升序**应用 ⇒ 桶 10 先变 4 人，再移 1 步实付 4000，池变 **负**（或按计划扣池则 W 凭空 +3000）。
- **生命周期**：簇池 `700`、`yearly_inherited={5:300}`；`coarsen` 后 aggregate 同值；`dissolve` 后全局测度同值。
- **resolved 簇的池**：`materialize` 后 mini 仍持池与分数残留 ⇒ 该簇 `level=1` 时池**冻结**
  （不接 transfer）；`merge`/`split`/`coarsen` 必须把它折走。

**边界条件**

- `A == character.wealth` 合法（付到 0）；`A <= 0` / `NaN` / `inf` ⇒ `dropped:bad_amount`。
- 总额够但无桶可下移（只有 bucket 0 / 全部触底）⇒ `dropped:illiquid`；总额不够 ⇒ `dropped:insufficient_funds`。
- **分数桶可以参与清算**（它代表质量，不是人）；位移不改变计数，因而不违反人头守恒。
  **年度投递只取 `count ≥ 1.0` 的整人桶**——分数残留不在投递里被抬升（否则"最穷优先"会退化成"最稀优先"，一个 `count=0.001` 的桶能吃掉整池并顶到上限）。
- 投递触顶（`wealth_bucket + k > wealth_bins − 1`）⇒ 该桶少付/不付，**余量留池**（同 N2-3 的触顶纪律）；
  上限余量 = `wealth_bins − 1 − wealth_bucket` 步。
- `unbind` 与 `transfer` 无关：transfer 不产生 `new_id`，`unbind` 查不到它的记录 ⇒ 返回 `False`；
  **别**为 transfer 造逆操作——它是"质量移动"，不是"绑定"。
- C↔C（族间再分配）**本期不做**：`_resolve_sides` 对 `origin=cluster`/`scope=cluster` 返回 `None` ⇒ `dropped:stale`。
- resolved 簇上的 transfer ⇒ `dropped:stale`（没有聚合态可动；成员的财富由成员自己持有）。

**验收**

- `python -m pytest tests/test_transfer.py -q` → 全绿，覆盖：
  R→C/C→R 的**逐笔 W 恒等**、清算的**人数最少桶优先**、`illiquid` / `insufficient_funds` 的**零副作用**、
  **超取上界夹具**（`1@5 + 3@6`，A=6000）、**清算升序夹具**（同上，降序会级联）、
  **投递降序夹具**（`3@9 + 1@10`，池 4500，升序会使池变负）、**`k ≤ wealth_bucket` 越界守卫**、
  分数桶不进年度投递、配额/headroom 豁免、`coarsen`/`merge`/`dissolve`/`split` 的池折叠（含 resolved 簇残留）、
  快照往返（含旧档缺字段）、同序确定性、真实 `ResolutionManager.step` 循环里的逐次守恒。
- `python -m bench.audit_transfer` → `identity error = 0`（脚本化：R→C → C→R → 清算 → 投递 → dissolve）。
- **惰性**：`RULES == {}` 时 `pytest -q` 与 `bench.audit_ledger --resolution/--clusters` 数字不退化。
- **mutation**（证测试有效）：① 去掉 R→C 的 `mini.transfer_pool += A` ⇒ W 断言变红；
  ② 把**清算**的应用顺序改成降序 ⇒ `1@5 + 3@6` 用例变红；③ 把**投递**的应用顺序改成升序 ⇒
  `3@9 + 1@10` 用例变红（池负）；④ `dissolve`/`split` 不折池 ⇒ 生命周期用例变红；
  ⑤ 去掉清算的 `k ≤ wealth_bucket` 下界 ⇒ 越界串桶用例变红。

**陷阱**

1. **池不能做成全局单例**（ADR-005 方案 B）：会跨族泄漏，破坏"富族恒富"，也无法对账归属。
2. **C→R 必须先规划、后改动**：计划不足时直接丢弃，**不能**先把分布改了再回滚（回滚顺序写错就会留下半截清算）。
3. **清算/投递的应用方向相反**：清算按源桶**升序**、投递按目标桶**降序**；写反会级联重复扣/加（相邻桶用例专抓这个）。
4. **按 `paid` 记账，不按公式重算**：`_shift_age_wealth` 在触底/触顶时不支付，重算会凭空造/毁质量（N2-3 的教训）。
5. **别把 `yearly_inherited` 当可花费资金**：它是继承专用池；动用它会改变代际语义。
6. **别让 transfer 走配额/headroom/宽限期**：它不析出、不建边；闸只属于 `bind`。
7. **别用 `delta_mass` 记财富**：`delta_mass` 是人头口径；transfer 的字段是 `wealth_delta` / `pool_after`。
8. **别在 `coarsen`/`merge`/`dissolve`/`split` 只折计数**：池会蒸发；`yearly_inherited` 与 `transfer_pool` 都要折。
   `merge` 的 resolved+resolved 快路径与 `split` 是最容易漏的两处（它们会**删掉**持有 mini 的簇）。
9. **池必须非负**：C→R 的支付前提是"池 + 可清算量 ≥ A"；不要允许"先欠着"，
   也**不要**用 `max(0, pool - A)` 钳制（凭空造财富）。
10. **排序不得依赖 `set`/`dict` 迭代序**：候选桶/目标桶都要显式排序（不变量 5）。
11. **transfer 记录 `new_id` 必须为 `None`**：`unbind` 靠 `status=="ok" and new_id==…` 定位；
    若 transfer 填了 `new_id`，会把质量移动误当成可逆绑定。
12. **账本是有界 `deque`（4096）**：记录被挤出后 `unbind` 会返回 `False`（边成幽灵）——这是既有边界；
    transfer 会加速挤出，规则侧要节制意图数量（或未来给 `bind` 记录单独索引）。
13. **`dropped:*` 记录的 `pool_after` 无定义**：只有 `ok` 的 `pool_after`/`wealth_delta` 有意义；
    观测面不要用丢弃记录读池。
14. **headroom 预留只对能发 `bind` 的规则成立**：当前 `headroom_reserve` 按"`RULES` 非空"预留
    `cap_per_tick`；若某规则只发 transfer，会白留名额。规则可声明 `emits_bind=False`（缺省 `True`）来避免。

**范围声明**：质量侧只做 R↔C 的原子与结算；**C↔C、resolved 簇支付**不在内（交互规则见 N2-7）。
规则若要发起 transfer，必须显式 `Intent(op="transfer", kind=..., payload={"amount": A})`。

**N2-7 · 第一条规则：跨分辨率婚配（`MarriageRule`，R→C）**（2026-10-17 拍板并实现）

**为什么**：见 [`adr-007`](../decisions/adr-007-cross-resolution-marriage.md)。一句话——
`FamilyKind` 的身份敏感边是 `parent/child/spouse`，而"窗口单身与族内单身成婚"是这条边**缺失的通量**；
只有真个体能当发起方（coarse 没有"意愿"）。规则**只声明意图**，守恒/建边/配额/宽限期全部由通道保证。
规格经 **1 轮 teach-back**（独立验证者；11 条缺口实现前补完），对账见
[`../reviews/2026-10-17-marriage-teachback.md`](../reviews/2026-10-17-marriage-teachback.md)。

**步骤级说明**

1. **收集（每 tick 一次）**：规则 `offers(context)` 由 `_collect_intents` 调用，位置在
   `store.step_coarse()` + `_settle_transfer_pools()` **之后**、`channel.run()` **之前** ⇒ 规则算出的 coarse 权重
   与同 tick 的 `extract` **同源**（本 tick 内 coarse 不再演化）。
   `ChannelContext` 携带 `tick / window / store / rng`。
   **随机流（2026-10-18 修订）**：规则应持有**自有**的确定性流（`MarriageRule(rng=…)`；runner 由
   `SIM_SEED` 派生）；`context.rng`（= `window.rng`）只是无自有流时的回退。**不得用模块级 `random`**。
   理由：与窗口共流会让"开关规则"改变个体事件的随机流，A/B 与校准不可控
   （见 [`../reviews/2026-10-18-marriage-calibration.md`](../reviews/2026-10-18-marriage-calibration.md)）。
2. **目标簇候选**（只算一次，避免"每个单身扫一遍簇"）：
   - 取 `level==0` 且 `state["engine"]` 存在的簇；
   - 编译一次 `pred = compile_match(Match(marital=0, age=(18, 59)), window.space)`；
   - 权重 = `Σ mini.counts[i]`（`i ∈ occupied`、`counts[i] ≥ 1.0`、`pred(i)`）；权重 `> 0` 才是候选；
   - 候选按 `cid` **升序**（确定性）；总权重 `> 0` 才继续。
3. **对每个窗口角色**（按 `id` 升序）：
   - 合格 = `18 ≤ age < 60` 且 `relationships["spouse"]` 为空（**性别中立**，不加 `gender` 约束）；
   - 掷 `rng.random() < rate`（`rate` 缺省 = `transitions.MARRIAGE_RATE`）才发起；
   - 在候选中用 `rng.random()` 做**计数加权抽样**（前缀和），定出 `cid`；
   - 产出 `Intent(op="bind", kind="spouse", origin=("character", rid), scope=("cluster", cid),
     match=Match(marital=0, age=(18, 59)))`。
   - **不做"自家簇 / 亲属避让"**：coarse 簇的 `member_ids` 按契约**必为空**，不存在"发起者所属的 coarse 簇"；
     个体引擎也没有亲属避让（`relatives` 检查已删）。这是刻意识别差异，不是遗漏。
4. **执行**：完全交给通道（N2-1）——`extract(amount=1)` 先扣后加、`link(rid, new, "spouse")`、
   配额 `cap_per_tick=8` / `cap_per_cluster=2`、窗口 headroom、宽限期 `recently_active[cid]`。
   规则**不碰**边、不碰分布、不碰配额。
5. **不重复婚配**（两条防线只针对**窗口发起方**）：
   - 规则在 `window.step()` **之后**运行 ⇒ 本 tick 刚在窗口结婚的人已 `marital≠0`，`offers` 跳过；
   - 规则结的婚下一 tick 也被窗口 `spouse_event`（要求 `not relationships['spouse']`）跳过。
   - **粗侧对手方**由另两条机制保护：`step_coarse()` 的均值场婚配**先跑**，且 `bind` **先扣后加**把人移出分布
     ⇒ 同一 tick 不会"一个人被嫁两次"。这两条防线不覆盖粗侧，别混用。
6. **开关**：`SIM_CHANNEL_MARRIAGE`（缺省 `0`）；`=1` 时 runner `register(MarriageRule())`
   （注册幂等）。**默认不注册 ⇒ `RULES` 空 ⇒ 通道惰性、全部权威数字不变。**
7. **语义声明**：开启 = 新增一条婚配通量（窗口自己的婚配事件照常跑）⇒ **不**要求与纯个体引擎收敛；
   `bench.convergence` / `bench.cluster_fidelity` 一律在默认（`RULES` 空）下跑。

**精确例子**

- 窗口有单身 `R`（30 岁）、coarse 族 `c` 有桶 `count=10 @ (age 30, marital 0)`、
  `rate=1.0`、`rng` 命中 `c` ⇒ `bind` 析出 1 人 `N`（`count 10 → 9`），`R—N` 双向 `spouse` 边；
  人头守恒；账本 1 条 `ok`（`kind="spouse"`）；`c` 进入宽限期（分辨率冻结）。
- **计数加权抽样**：`c1`（cid 小）权重 3、`c2` 权重 7 ⇒ 前缀和 `u<0.3 → c1`，否则 `c2`；
  同一 seed 落点固定。
- **已婚跳过**：`R` 已有 `spouse` ⇒ `offers` 不给它产意图。
- **无合格房源**：候选权重全 0（族内无 18–59 未婚桶）⇒ `offers` 返回 `[]`，账本零新记录（**不**产生 `dropped:no_match` 噪声）。
- **默认关**：`RULES == {}` ⇒ 跑一整局账本零记录（同 `test_zero_rules_channel_is_inert`）。

**验收**:`python -m pytest tests/test_rule_marriage.py -q` → 全绿，覆盖：建边 + 人头守恒、已婚后不再发起、
**计数加权抽样确定性**（两簇不同权重、同 seed 落点一致）、**规则只发意图**（跑一局后边/分布与"只跑通道"逐位一致）、
**分数桶不计权重**、无房源不产意图、默认关零记录。
`python -m bench.channel_marriage --ticks 3000` → 打印 A/B（关 / 开）的跨婚配次数、窗口已婚比例、人口，
  并断言开启状态下 `bench.audit_ledger`（人头）与 `--wealth`（逐算子 W）都不退化。
**mutation**（证测试有效）：把"已婚跳过"删掉 ⇒ 重复婚配用例变红；把权重改成"含分数桶" ⇒ 分数桶用例变红；
  让规则直接 `link`（绕过通道）⇒ "只发意图"用例变红。

**陷阱**

1. **规则不得建边、不得改分布**：只有通道能 `link` / `extract`；规则写这两样 = 绕过守恒。
2. **必须用 `context.rng`**：模块级 `random` 会破坏"同 seed 同发展"（不变量 5）。
3. **候选序与抽样都要显式排序**：`store.clusters` 是 dict、`window.characters` 是 dict——不得依赖迭代序。
4. **别把"开启"当成"收敛验证通过"**：开启是新语义（多一条婚配通量）；门槛只在 `RULES` 空下有效。
5. **别在规则里读 `mini.counts` 之外的可变状态做写操作**：规则是**只读**的（`ChannelContext` 只给引用，
   职责上不得写）。
6. **房源权重用 `count ≥ 1.0`**：`extract` 只从整人桶取；把分数残留算进权重会让意图频繁 `dropped:no_match`。
7. **`kind` 在不同 `op` 下身份不同**：`bind` 下 `kind` = **边名**（这里 `"spouse"`）；`transfer` 下 `kind` 只是标签；
   `RULES` 的键（`"cross_marriage"`）是**规则名**——三者别混。
8. **规则婚姻的生命周期**：终止 = 死亡 / `dematerialize`（容量逐出），**不是** `unbind`（`unbind` 的语义是"折算回粗侧"）。
   **可达性边界（2026-10-18 校准）**：`scope` 只支持 coarse **簇** ⇒ 规则只能同"族内单身"成婚；
   生产样态下 coarse 族几乎不含 18–59 未婚桶 ⇒ crossings ≈ 0。大多数单身在**全局测度**里，
   而通道目前**不能寻址全局测度**——要让这条通道改变宏观，得先做那个扩展（独立 ADR）。
   析出的配偶**不进 `member_ids`**、也不建 `acquaintance` 网 ⇒ 只有 1 条 `spouse` 边（嵌入度 2，高于浮层单身但低于有网络者），
   容量吃紧时可能较早退场——MVP 接受，记为边界。

**N2-2 · 谓词式寻址与可重建维度守卫**

1. `Match` 是**声明**（见决策 4 的字段表），**不是任意闭包**——闭包无法静态校验"是否引用不可重建维度"，
   也无法预估配额与确定排序。
2. `compile(match, space)` 返回 `pred(index) -> bool`。R→C 时只作用于 `measure.occupied`（~1.4e3 桶）；
   C→R 时作用于窗口角色的折算桶索引集（O(`capacity`)）。
   **绝不枚举整个状态空间**（默认 2.18e6 桶）。
3. 若 `match` 引用了 ∉ `RECONSTRUCTIBLE` 的维度 ⇒ **在 `compile` 抛错**（不变量 4），
   不得留到运行期静默失配。

**N2-3 · 确定性与配额**

1. 排序键固定为 N2-1 第 2 步；候选桶**按桶索引升序**后加权抽样；**不得依赖 dict / set 迭代序**
   （history Stage 15 的确定性 bug 即此类）。
2. 配额三个量：`cap_per_cluster=2`、`cap_per_tick=8`（常数）、窗口 headroom = `capacity − len(window) − reserved`。
   三个量**只约束 `bind`**（N2-6 第 4 步）；`headroom_reserve` 只在"存在声明 `emits_bind`（缺省 `True`）的规则"时预留。
   **注意（2026-10-18 校准）**：预留是**常驻**的——只要注册了会 `bind` 的规则，窗口就永久少留
   `cap_per_tick` 个名额，**即使规则从不发意图**（实测单独贡献 `married_frac(adults)` +0.003~+0.010）。
   A/B/校准必须用"同为 `emits_bind` 但不发意图"的 **null 臂**对齐；生产默认 `RULES` 空 ⇒ 无影响。
3. **宽限期 = 分辨率冻结**（MVP 归**通道机制**）：被 `bind` 触及的簇记入 `recently_active[cid] = tick`，
   在 `grace_ticks = 180` 内**不换档（不 `coarsen` 也不 `materialize`）、也不被 `_recycle` 回收**。
   - **不得用"把注意力抬到 `theta_base`"来实现**——那会让 `allocate` 反过来**物化**该簇
     （注意力 ≥ 门槛 ⇒ `target=1`），与"别扰动刚建好的关系"的意图相反。`ResolutionManager`
     在 `allocate()` **之前**算好冻结集 `_grace_ids(tick)`，并在「换档」与「回收」两处都跳过它。
   - 过期即释放（`tick - when >= grace_ticks`），簇在此期间消失也一并清掉表项。

### 精确例子

**例 1 · `bind` 守恒 + `unbind` 可逆（R→C）**

输入：某簇 mini 有 `1.0 @ encode(30, 0, 10, 0)`；R = 窗口内 30 岁男性；`kind="probe"`。

- `bind`：`Intent(kind="probe", origin=("character", R.id), scope=("cluster", cid), match=Match(age=(28,35), gender=0))`
  ⇒ mini 该桶 `1.0 → 0.0`；`len(window) +1`；R 与新人双向 `probe` 边；账本 1 条；`reserved` 归 0
- `unbind(new_id)` ⇒ `unlink(R, new, "probe")`；`window.detach(new_id)` 并把**当前** `(age,gender,wealth)` 折算回 mini
  ⇒ **同一 tick 内（mini 无演化）该桶回到 `1.0`**；`len(window) -1`；三查无幽灵
- **跨 tick 的 `unbind` 只保证人头守恒 + 无幽灵**：mini 在此期间会 `aging`/`income`，折算按当前属性落**别的桶**，
  这是物理上正确的（见不变量 3 的注意），**不要**为此写"必须回原桶"的断言

**例 2 · C→R 与 R→C 同一条路径**

输入：`origin=("cluster", cid)`、`scope=("window",)`、`match=Match(gender=1)`，窗口内有 3 个女性。
⇒ 决策 2 第 2 步按 `Character.id` **升序**选出第一个匹配角色 `W`；从 mini 析出 1 人 `N`（发起者的代表）；
`link(N, W, kind)`。**析出对象从 R 变成了 N**——这就是"方向无关"的含义。

### 边界条件
- `scope` 簇已不存在 / `origin` 角色已不在窗口 / 窗口侧无匹配 ⇒ 丢弃（`dropped:stale` / `dropped:no_match`）。
- 窗口无 headroom ⇒ 丢弃（`dropped:window`）；**不得**为容纳绑定而逐出被保护的簇成员。
- 空匹配 ⇒ 丢弃（`dropped:no_match`），**不抛错**（C 侧意图天然可能无匹配）。
- 第 7 / 8 步抛异常 ⇒ **逆序全撤**（见 N2-1 第 7–8 步），不留幽灵、不破坏人头守恒。
- `unbind`：目标角色已不在窗口 ⇒ 返回 `False`，不抛错；`coarse_cluster` 已被回收 ⇒ 折算回全局测度；
  **跨 tick 调用合法**，但不保证逐桶复原（见 N2-4 与不变量 3）。
- `transfer`：金额非法 ⇒ `dropped:bad_amount`；R→C 带 `Match` ⇒ `dropped:unsupported_match`；
  总额不足 ⇒ `dropped:insufficient_funds`；总额够但只有不可下移的桶 ⇒ `dropped:illiquid`；
  C↔C / resolved 簇 ⇒ `dropped:stale`。**所有丢弃都零副作用**（N2-6）。

### 性能预算
- 不破坏"成本与 N 无关"：单簇单 tick 析出 ≤ `cap_per_cluster`（常数）⇒ 每 tick =
  O(簇数 × `cap_per_cluster` + 意图数 × `occupied`/`capacity` 扫描)。
- `transfer`：R→C 为 O(1)；C→R 的清算计划 = O(`occupied` log `occupied`)；年度投递 = 对每个
  Measure O(`occupied` log `occupied`)。均与人口 N、状态空间规模无关。
- **禁止**按状态空间规模枚举（N2-2 第 2 步）。

### 错误处理
- 谓词非法（引用不可重建维度）⇒ **拒绝（抛错）**，不是静默失配。
- transfer 的坏输入（未知 `op` / 金额非正或非有限 / R→C 带 `Match`）⇒ **丢弃 + 记账**，**不抛错**
  （规则给的是运行期数据；崩溃会打断整个 tick）。
- 其余失败（无匹配 / 无配额 / 过期 / 析出期异常 / 金额不足 / 无流动性）⇒ 丢弃 + 记账本原因，**不抛错**；
  **丢弃必须零副作用**（transfer 尤其：不能留下半截清算）。

### 陷阱
1. **`bind` 不是纯函数**——它有副作用（改 coarse 分布 + 窗口容量），因此**不能**放进 `Character.step()` / `PeopleEvents`。
2. **随机源必须注入且只有一个**：`window.rng`（`ClusterStore.rng` / `TickContext.rng` 是它的同一实例）。
   **新增代码不得再用模块级 `random`**。
3. **顺序依赖**：多个 R 竞争同一份 coarse 质量时结果依赖处理序 ⇒ 必须排序（N2-3 第 1 步）。
4. **不要枚举状态空间**（2.18e6 桶），只扫 `occupied` / `capacity`。
5. **`marital` 可寻址，但**不是**普通维度**：个体引擎里"已婚"是 `relationships["spouse"]`（不是属性）⇒
   必须**成对析出**（N2-5）；单独析出一个"已婚桶"的人 = 造出假单身。引用 ∉ `RECONSTRUCTIBLE` 的维度仍须抛错。
6. **边语义的单一真相源是 `relationships`**（经 `links.neighbors` 求关系度）。曾经有个 `relatives` 字段
   只在构造时填充、构造后**从不更新**，导致三处依赖失真（广场配对去重失效、收敛指纹度指标恒为 0、
   ρ 退化为簇成员数）。**该字段已删除**，三处改为真实语义。实测交叉印证：同一次审计里 `rho` 由
   `118`（= 人数）变为 `2143`（≈ 人数 × (1+平均度)，平均度 ≈ 17，与独立测出的度分布峰值 17–18 一致）。
7. **广场的"亲属避让"未实现**：原检查读 `relatives`（恒空）⇒ 从未生效；删除后只保留同 id 保护。
   若要真正避让亲属，属**独立决策**（会改变个体引擎行为与已拟合常数）。
8. **`transfer` 已按 N2-6 实现，但别把它写成 `bind` 的变体**——它不析出、不建边、不占配额；
   财富残差只能进**每个粗侧自己的** `transfer_pool`，不能进全局单例（ADR-005 方案 B）。

### 与其他模块的协作
- `IndividualWindow`：`attach` / `detach` / `dematerialize`；析出的新成员**不写** `member_ids`（见 N2-1 第 7 步）。
  `WindowEngine._refill` 会按 `channel.headroom_reserve()` 预留窗口名额（见决策 6）。
- `ResolutionManager`：交互阶段插在 `store.step_coarse()` **之后**、`allocate()/apply` **之前**；
  宽限期冻结集在 `allocate` 前算好（`_grace_ids`）。
- `ClusterStore`：复用 `extract`（"只从 `count ≥ amount` 的桶析出整人"的按谓词泛化）。
- `Character` / `links`：`link` 必须是边的**唯一入口**。
- `Measure` / `transitions`：`transfer_pool` 挂在每个 `Measure` 上；清算/投递复用
  `_shift_age_wealth`（整桶位移 + 实付量返回），不得另写一套分数桶逻辑。
- `ResolutionManager.step`：年度投递在 `step_coarse()` **之后**、通道 `run()` **之前**
  （先让本 tick 的池可用于支付，再做意图）。

### 验收

**验收**:`pytest tests/test_channel.py tests/test_transfer.py -q` → 全部通过，覆盖不变量 1–13（手段 = **不变量 → property test**：每条不变量写成"任意合法输入下恒成立"的断言）。
**验收**:`python -m bench.audit_transfer` → `identity error = 0`（transfer 原子 / 清算 / 投递 / 生命周期折叠的逐次 W 恒等）。
**验收**:`python -m bench.audit_ledger --resolution --n 1500 --steps 2500 --capacity 250` → `identity error = 0`（通道接入后不改变该恒等式；手段 = **approved scenario / golden**：账本逐条核平）。
**验收**:零规则运行 `python -m pytest -q` + `python -m bench.audit_ledger --resolution --n 3000 --steps 2000` → 全绿且数字不退化（证明通道**惰性**）；**mutation**：把 reserve 的 `-1.0` 改成 `-0.0`，`tests/test_channel.py` 必须变红（手段 = **mutation testing**，证"测试本身有效"）。

---

## 相关文档

- L1：[`../../AGENTS.md`](../../AGENTS.md)
- L2 架构层：[`../architecture.md`](../architecture.md)
- 分辨率 / 共演单元层契约：[`../cluster-contract.md`](../cluster-contract.md)
- 规范（守恒律 / §9）：[`../engineering-spec.md`](../engineering-spec.md)
- 术语：[`../glossary.md`](../glossary.md)
- 相关 ADR：[`adr-003`](../decisions/adr-003-interaction-channel.md)（通道）、[`adr-005`](../decisions/adr-005-transfer-quality-side.md)（质量侧池与清算/投递）
- 被拒方案 / 负结果：[`../history.md`](../history.md)（Stage 3 碎片化 / Stage 7 账本注水 / Stage 15 确定性）
- N2 验收方法论：[`../../docs-templates/verifying-n2.md`](../../docs-templates/verifying-n2.md)
