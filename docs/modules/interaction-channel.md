# Module: 交互通道（Interaction Channel） — L3 模块详细

> 本文档定位：做**跨分辨率直接交互**模块工作时加载，可独立喂给 AI。
> 三段式：[是什么] / [为什么] / [不变量]。模板来源 [`docs-templates/module-doc.md`](../../docs-templates/module-doc.md)。
> **本期范围：只做通道的身份侧（`bind`），不做交互规则，也不做质量侧（`transfer`）**——
> 婚配 / 结友 / 继承的**语义**不在本模块；`transfer` 的**规格**见 §第二期。

---

## [是什么] — 模块需求与子组件

`novelty=N2`

**功能**：给「共演单元（coarse）↔ 单位个体（resolved）」提供一条**点对点、双向、可具名**的交互路径，
使 R↔C 的交互不必再经由全局测度中转。

对比现有**间接路径**（两跳、匿名、单向）：`C —overflow_fraction→ 全局测度 —materialize→ 窗口`。

**它不做什么**：不定义任何交互语义。通道只保证"意图 → 守恒且确定的现实"这一转换是**正确、可对账、可复现**的；
"什么意图、绑定后建什么边"由**交互规则**（第 9 缝，本期为空注册表）决定。

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
| `extract` | 从 coarse `Measure` 按 `Match` 析出 1 个整人并扣减（`_sample_cell` 的按谓词泛化） | ✅（第 0 步已交付） |
| `link` | **边的唯一入口**：一次调用双向写 `relationships`（对称；非对称用 `reverse`），`record=True` 时并写 `relation_record` | ✅（第 0 步已交付） |
| `InteractionRule`（Protocol + `RULES` 注册表） | 规则缝：**只声明"发起什么意图"**；**建边由通道统一执行**（`link`），规则不碰边。签名（MVP）：`offers(context: ChannelContext) -> Iterable[Intent]` | ✅（空注册表） |
| 通道账本（有界 `deque`，`maxlen=4096`） | 每条操作一条记录，供观测与对账 | ✅ |
| **`transfer`（原子：无身份质量移动）** | 质量侧：继承 / 馈赠 / 族间再分配 | **下期**（见 §第二期） |

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

**mutation 检验**（证"测试本身有效"）：把 `ClusterStore.extract` 的 `mini.add(chosen, -amount)` 改成 `…, 0.0`，
`tests/test_channel.py` 中守恒 / 可逆 / 回滚三条**变红**——测试确实在守不变量。

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

### 第二期（本期不做）：质量侧 `transfer`

`transfer`（无身份质量移动）**不是**身份操作，且有一个本期未解决的硬问题：

> coarse 侧的财富只能以 **`count × 桶宽度`** 为最小单位整桶挪动（沿用"整数桶位移"纪律），
> 而具名个体的 `wealth` 是精确浮点 ⇒ **两个方向的转移都必须有量化残差，且残差需要一个"通道池"承接**，
> 否则财富会被凭空造出/销毁。这需要一条**独立的财富守恒不变量**（形如 `bench.audit_ledger` 的 `pool_residual`），
> 与 `bind` 的人头守恒是两码事。

因此 `transfer` 的规格（池的结构、方向语义、"金额 vs 桶步"的表达方式、财富账本不变量）留待第二期，
**本期不实现、不声明**。已登记进 [`adr-003`](../decisions/adr-003-interaction-channel.md) 的「需要跟进的」。

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
3. **析出**永远在 **coarse 侧**（唯一没有身份的一侧）：析出 1 个整人 → 得到新 `Character`。
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
  Match(age=(lo, hi), gender=0|1, wealth_bucket=(lo, hi))   # 全部可选，None = 不限
  ```
  `wealth_bucket` 用**桶索引**（线性宽 1000），不用财富值——避免"值是连续、桶是离散"的二次换算。
  **`age` 的单位是"岁"**（不是龄段号）：年龄桶是 1:1 的（121 桶 = 0..120），故 `age` 值与桶索引相等。
- `Match` 编译为**桶索引谓词** `pred(index) -> bool`，两侧共用：
  - R→C：直接作用于 coarse 的 `occupied` 桶索引；
  - C→R：把每个窗口角色折算成桶索引（`space.encode(c.age, gender, space.wealth_bucket(c.wealth), …)`）后作用——
    代价 O(窗口人数) = O(`capacity`)，可接受。
  - **C→R 的对手方选取顺序固定为 `Character.id` 升序取第一个匹配**（不得依赖窗口 `dict` 迭代序）。
- **本期可重建维度 = `{age, gender, wealth}`**（`RECONSTRUCTIBLE`）。`marital` **本期不可寻址**：
  `Match(marital=…)` ⇒ **抛错**。（ADR-003 未定点 1 若将来选"双人析出"，只需扩 `RECONSTRUCTIBLE` 并让
  `extract` 支持 `amount=2`——扩展缝已留好。）

### 决策 5：本期只做通道，不做规则
"规则未知"恰好是对通道设计的**检验**：零规则 + 探针规则即可完整验收通道（见 [不变量] 的验收）。

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

1. **人头守恒** `[强制]`：通道的身份侧操作（`bind` / `unbind`）不改变 `Σmeasure + ΣCoarse + len(window)`。
   （**财富**守恒是另一条账，属 `transfer`，见 §第二期——本条**不**声称管财富。）
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
   窗口不超 `capacity`。**MVP 取值**：`cap_per_cluster=2`、`cap_per_tick=8`（常数，可换）。
8. **可对账** `[强制]`：每条通道操作（含每次丢弃）在账本有且仅有一条记录；逐条可核平。

### N2 步骤级说明

**N2-1 · `bind` 的先扣后加提交协议**

1. **收集**：R 侧意图在 `window.step()` 之后由规则提供；C 侧意图在 `store.step_coarse()` 之后由规则提供。
   两路都经 **`channel.submit(intent)`** 进本 tick 队列。**本期 `RULES` 为空 ⇒ 两条路都不产生意图**（通道惰性）。
2. **排序**：按 `(origin_side, origin_id, kind, scope_type, scope_id)` 升序（`origin_side`：`character`=0、`cluster`=1；
   `scope_type`：`cluster`=0、`window`=1）。字符串比大小即可（Python 元组比较），**唯一确定的处理序**。
3. **去重**：同一 `(origin, kind, scope)` 只保留第一条。
4. **配额闸**：`coarse` 簇本 tick 已析出数 ≥ `cap_per_cluster` ⇒ 丢弃（记 `dropped:quota_cluster`）；
   本 tick 总析出 ≥ `cap_per_tick` ⇒ 丢弃（记 `dropped:quota_tick`）；
   `len(window) + reserved ≥ capacity` ⇒ 丢弃（记 `dropped:window`）。
5. **解析两侧**（决策 2 第 1–2 步）：定出 `coarse_cluster` 与 `initiator_character`。
   任一解析不出（簇不存在 / 窗口侧无匹配 / 发起者已离场）⇒ 丢弃（记 `dropped:stale` 或 `dropped:no_match`）。
6. **reserve**：在 `coarse_cluster` 的 mini `Measure` 上，取满足 `Match` **且** `count ≥ 1.0` 的候选桶，
   **按桶索引升序**后做**计数加权抽样**（用 `ctx.rng`）。候选为空 ⇒ 丢弃（记 `dropped:no_match`）。
   随后 `mini.add(cell, -1.0)` 并 `reserved += 1`。
   - **此刻起质量已离开 coarse 侧。**
7. **析出**：由 `(age, gender, wealth_bucket)` 造新 `Character` 并入窗口（`window.attach`）。
   - **不写 `coarse_cluster.member_ids`**：coarse 簇的 `member_ids` 按契约**必须为空**（`cluster-contract.md` §1）；
     析出者是"与该簇相连的具名个体"，不是它的成员。若建的是**亲属**边，下一个 `form_interval` 的
     `_reconcile` 会按既有机制把它抽入（level→1）；非亲属边则保持浮动——这正是想要的语义。
   - **第 7 步抛异常**（`generate_character` / `window.attach`）⇒ 回滚第 6 步：`mini.add(cell, +1.0)`、
     `reserved -= 1`、丢弃（`dropped:error`）。
8. **link**：`link(initiator_character, new_character, kind)`——双向写 `relationships`（`record=True` 时并写 `relation_record`）。
   - **第 8 步抛异常** ⇒ **逆序撤销第 7 步**（`window.detach(new_id)`）**+ 回滚第 6 步**
     （`mini.add(cell, +1.0)`、`reserved -= 1`）、丢弃（`dropped:error`）。
     **回滚清单必须是"已完成步骤的逆序全撤"**——只回滚测度会留下"已入窗口的真人 + 测度已退"，
     破坏不变量 1（人头守恒）与不变量 3（无幽灵）。
9. **宽限期登记**：`recently_active[cid] = tick`。**放在建边成功之后**——失败的意图不该给簇一段宽限期。
10. **commit**：账本追加一条 `ok` 记录；`reserved -= 1`。

> **`bind` 只对 `level==0`（coarse）簇有效**：resolved 簇的成员本就是具名角色，规则可直接取用，无需"析出"。
> 命中 resolved/不存在的簇 ⇒ `dropped:stale`。

**账本记录形状（统一，`ok` 与 `dropped:*` 同一结构）**

```python
@dataclass(frozen=True)
class ChannelRecord:
    tick: int
    status: str                 # "ok" | "dropped:quota_cluster" | "dropped:quota_tick" |
                                # "dropped:window" | "dropped:stale" | "dropped:no_match" | "dropped:error"
    kind: str
    origin: tuple
    scope: tuple
    cell: int | None = None         # reserve 到的桶；未 reserve 时为 None
    delta_mass: float = 0.0         # ok 时 = -1.0；其余为 0.0
    initiator_id: int | None = None # 建边两端（unbind 靠它定位对端）
    new_id: int | None = None
    coarse_id: int | None = None    # 析出源簇（unbind 靠它决定折算回簇还是全局测度）
    note: str = ""                  # dropped:error 存异常摘要
```

**N2-4 · `unbind` 契约**

1. **定位**：由 `new_id` 在该 `kind` 的 `ok` 记录里查得 `initiator_id` 与 `cell`（一个 `new_id` 只可能由一次
   `bind` 创建 ⇒ 唯一）。
2. **两端的边**：`unlink(initiator, new, kind)`（`record=True`）——**不猜"哪条边"**，就是这条。
3. **折算回 coarse**：把该角色按**当前** `(age, gender, space.wealth_bucket(wealth))` 折算回
   `coarse_cluster` 的 mini 引擎（`mini.add(encode(...), +1.0)`），随后 `window.detach(new_id)`、
   `coarse_cluster.member_ids.discard(new_id)`。
   - **不**用账本里的 `cell` 强写回：coarse 侧在此期间持续演化，强写回会把一个已变老/变富的人塞回旧桶，
     破坏 mini 的年龄结构。代价是**不保证回到原桶**（见不变量 3 的注意）。
   - 若 `coarse_cluster` 已被回收/`dissolve` ⇒ 折算回**全局测度**（该角色退场，人头不变）。
4. **失败语义**：`new_id` 不在窗口 ⇒ 返回 `False`，不抛错；应在窗口但查不到账本记录 ⇒ 返回 `False` 并记一条
   `dropped:error`（供对账发现）。
5. **`unbind` 可跨 tick 调用**（宽限期正是为此存在）；同一 tick 内调用时 `unbind` 应与 `bind` 记录**独立**，
   不合并、不抵消。
6. **账本**：`unbind` 追加一条 `status="unbound"` 的记录（`delta_mass=+1.0`，`cell` = 折算的**目标桶**）。

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

### 性能预算
- 不破坏"成本与 N 无关"：单簇单 tick 析出 ≤ `cap_per_cluster`（常数）⇒ 每 tick =
  O(簇数 × `cap_per_cluster` + 意图数 × `occupied`/`capacity` 扫描)。
- **禁止**按状态空间规模枚举（N2-2 第 2 步）。

### 错误处理
- 谓词非法（引用不可重建维度）⇒ **拒绝（抛错）**，不是静默失配。
- 其余失败（无匹配 / 无配额 / 过期 / 析出期异常）⇒ 丢弃 + 记账本原因，**不抛错**。

### 陷阱
1. **`bind` 不是纯函数**——它有副作用（改 coarse 分布 + 窗口容量），因此**不能**放进 `Character.step()` / `PeopleEvents`。
2. **随机源必须注入且只有一个**：`window.rng`（`ClusterStore.rng` / `TickContext.rng` 是它的同一实例）。
   **新增代码不得再用模块级 `random`**。
3. **顺序依赖**：多个 R 竞争同一份 coarse 质量时结果依赖处理序 ⇒ 必须排序（N2-3 第 1 步）。
4. **不要枚举状态空间**（2.18e6 桶），只扫 `occupied` / `capacity`。
5. **不要把 `marital` 当普通可寻址维度**——本期它不可重建（物化丢婚配）⇒ `Match` 引用它必须抛错。
6. **边语义的单一真相源是 `relationships`**（经 `links.neighbors` 求关系度）。曾经有个 `relatives` 字段
   只在构造时填充、构造后**从不更新**，导致三处依赖失真（广场配对去重失效、收敛指纹度指标恒为 0、
   ρ 退化为簇成员数）。**该字段已删除**，三处改为真实语义。实测交叉印证：同一次审计里 `rho` 由
   `118`（= 人数）变为 `2143`（≈ 人数 × (1+平均度)，平均度 ≈ 17，与独立测出的度分布峰值 17–18 一致）。
7. **广场的"亲属避让"未实现**：原检查读 `relatives`（恒空）⇒ 从未生效；删除后只保留同 id 保护。
   若要真正避让亲属，属**独立决策**（会改变个体引擎行为与已拟合常数）。
8. **别把 `transfer` 顺手实现进来**——它的财富量化残差池需要独立规格与独立不变量（见 §第二期）。

### 与其他模块的协作
- `IndividualWindow`：`attach` / `detach` / `dematerialize`；析出的新成员**不写** `member_ids`（见 N2-1 第 7 步）。
  `WindowEngine._refill` 会按 `channel.headroom_reserve()` 预留窗口名额（见决策 6）。
- `ResolutionManager`：交互阶段插在 `store.step_coarse()` **之后**、`allocate()/apply` **之前**；
  宽限期冻结集在 `allocate` 前算好（`_grace_ids`）。
- `ClusterStore`：复用 `extract`（"只从 count ≥ 1.0 的桶析出整人"的按谓词泛化）。
- `Character` / `links`：`link` 必须是边的**唯一入口**。

### 验收

**验收**:`pytest tests/test_channel.py -q` → 全部通过，覆盖不变量 1–8（手段 = **不变量 → property test**：每条不变量写成"任意合法输入下恒成立"的断言）。
**验收**:`python -m bench.audit_ledger --resolution --n 1500 --steps 2500 --capacity 250` → `identity error = 0`（通道接入后不改变该恒等式；手段 = **approved scenario / golden**：账本逐条核平）。
**验收**:零规则运行 `python -m pytest -q` + `python -m bench.audit_ledger --resolution --n 3000 --steps 2000` → 全绿且数字不退化（证明通道**惰性**）；**mutation**：把 reserve 的 `-1.0` 改成 `-0.0`，`tests/test_channel.py` 必须变红（手段 = **mutation testing**，证"测试本身有效"）。

---

## 相关文档

- L1：[`../../AGENTS.md`](../../AGENTS.md)
- L2 架构层：[`../architecture.md`](../architecture.md)
- 分辨率 / 共演单元层契约：[`../cluster-contract.md`](../cluster-contract.md)
- 规范（守恒律 / §9）：[`../engineering-spec.md`](../engineering-spec.md)
- 术语：[`../glossary.md`](../glossary.md)
- 相关 ADR：[`../decisions/adr-003-interaction-channel.md`](../decisions/adr-003-interaction-channel.md)
- 被拒方案 / 负结果：[`../history.md`](../history.md)（Stage 3 碎片化 / Stage 7 账本注水 / Stage 15 确定性）
- N2 验收方法论：[`../../docs-templates/verifying-n2.md`](../../docs-templates/verifying-n2.md)
