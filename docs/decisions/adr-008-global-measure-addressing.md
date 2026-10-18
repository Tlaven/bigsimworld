# ADR-008: 全局测度寻址——粗侧的第二种形态（`scope`/`origin` 加 `("measure",)`，只 bind、双向）

## 状态

accepted（2026-10-18 起草并同日拍板；规格见 [`modules/interaction-channel.md`](../modules/interaction-channel.md) N2-8；
teach-back 对账见 [`reviews/2026-10-18-measure-addressing-teachback.md`](../reviews/2026-10-18-measure-addressing-teachback.md)）

## 背景

[`adr-007`](adr-007-cross-resolution-marriage.md) 的校准（2026-10-18）给出一个实测结论：
**真正的瓶颈是"可达性"，不是 rate**——生产样态（无合成族）下 crossings = **0**，
因为规则只能同 `scope=("cluster", cid)` 的 coarse **簇**成婚，而生产世界里大多数单身在**全局测度**里。
文档当时的原话："要让这条通道真正改变宏观，下一步是让 `bind` 能**寻址全局测度**（通道扩展，独立决策）"。

本轮回答的问题：**如何给通道加全局测度寻址**，且不污染既有的簇语义、守恒、确定性纪律？

约束：

- 粗侧的本质是"**没有 id 的分布**"——全局测度与簇在这点上**同构**（只能谓词式寻址），
  但全局测度**不是**共演单元：没有 `level`、没有注意力、不回收、不是宽限期的对象；
- ADR-003 决策 2：**析出永远发生在 coarse 侧**——全局测度只要成为 coarse 侧的**第二种形态**，
  全部提交协议（先扣后加 / 回滚 / 账本 / 配额）即可复用；
- 通道惰性纪律：默认（`RULES` 空）必须**零行为变化**。

## 考虑过的方案

### 方案 A：`scope`/`origin` 加 `("measure",)`；`_resolve_sides` 返回 `coarse=None` 表示全局测度（采纳）

- 优点：复用全部既有纪律（先扣后加 / 配额闸 / 逆序全撤 / 账本 / 确定性 / 性能预算）；
  析出算子 `ClusterStore.extract` 对 mini **无簇依赖** ⇒ 直接传 `window.measure` 即可；
  `unbind` 折回全局测度的路径**已经存在**（"簇已被回收"的回退）⇒ 零新代码；
  改动收口在 `channel.py` 一个文件（`cluster.py` / `window.py` 零改动）。
- 缺点：`coarse=None` 承担两个语义的不同位置（元组内 = 全局测度；整体返回 `None` = 解析失败）——
  易错点，须靠注释与规格钉死；`cap_per_cluster` 对全局测度无意义，须附注。

### 方案 B：把全局测度包装成"伪簇"/哨兵 cid（被拒）

- 优点：`_resolve_sides` 返回类型不用变，全路径类型统一。
- **拒绝理由**：伪簇会**污染簇语义**——`level` / 配额 / 注意力 / 回收 / 宽限期 / `_reconcile` 连通分量
  对它全部无意义，每一处都要加"不是伪簇"的特判；哨兵 cid（如 `-1`）更糟：会渗透进每个
  `store.clusters.get()` 调用点，且账本 `coarse_id` 的"无簇"语义与哨兵值互相污染。
  **为省一个 `Optional` 引入 N 个特判，方向反了。**

### 方案 C：规则绕过通道，直调 `materialize_sample` / `window.materialize`（被拒）

- 优点：零通道改动。
- **拒绝理由**：先扣后加 / 配额 / 账本 / 确定性会散落到规则里（每条规则重新发明一遍）——
  正是 ADR-003 方案 B 拒绝过的路径；且 `materialize_sample` 的抽样**不接受谓词**，无法表达 `Match`
  （id 式/无谓词采样与"声明式可匹配性"不兼容）。

### 方案 D：只单向 R→M（被拒）

- 优点：更保守，只做有规则需求的方向。
- **拒绝理由**：违背 ADR-003 决策 2 的"方向对称、一套实现"——M→R 与 C→R **完全同构**
  （窗口对手选取取 `id` 最小者），边际成本 ≈ 0；只做单向会让"粗侧两种形态 × 两个方向"的寻址空间残缺，
  下一个人补 M→R 时还要重走一遍规格/验收。

### 方案 E：顺带做 `transfer` 的全局测度寻址（被拒，留独立决策）

- 优点：寻址机制完整（R→M 入池 / M→R 从池支付）。
- **拒绝理由**：无当前用例驱动；且 M→R 支付需要**清算全局分布**（向下整桶位移动的是全世界的财富分布），
  打开新的审计面——按 ADR-003 跟进项把 `transfer` 移出第一期的同样纪律，留独立决策。

### 方案 F：给全局测度设独立配额 `cap_per_measure`（被拒/不做）

- **拒绝理由**：无簇可防（全局测度人口海量，不存在"被抽干"），`cap_per_tick` 已是硬上界；
  不扩参数面——每个新配额参数都要一套取值纪律与校准。

## 选择

**方案 A。** 关键规则（完整步骤级规格见 N2-8）：

1. `Intent.scope` 加 `("measure",)`（**R→M**：窗口角色 × 大众）、`Intent.origin` 加 `("measure",)`
   （**M→R**：大众代表 × 窗口角色）；`Match` 语义与校验照旧（谓词式寻址不变；`marital=1` 照旧成对析出）。
2. `_resolve_sides` 返回 `(coarse | None, counterpart)`：元组内 `None` ⇒ 全局测度
   （`mini = window.measure`，**不查** `level` / `engine`）；整体返回 `None` ⇒ 解析失败（`dropped:stale`）。
3. **配额**：全局测度**不受** `cap_per_cluster`（无簇语义）；`cap_per_tick` / 窗口 headroom **照旧**是硬上界。
4. **宽限期**：全局测度寻址**不登记** `recently_active`（它不换档、不回收——没有需要冻结的分辨率）。
5. **账本**：`coarse_id=None` = "折算目标为全局测度"（与"簇已被回收"殊途同归，`unbind` 既有回退路径直接覆盖）。
6. **排序**：`_ORIGIN_SIDE` / `_SCOPE_TYPE` 的 `"measure"` 取 2（处理序最后；无 id 视 0）——确定性纪律照旧。
7. **只对 `bind` 生效**；`transfer` 遇 `("measure",)` ⇒ `dropped:stale`（范围声明，零副作用）。

### 取舍

- 为了**改动最小**，接受 `coarse=None` 的双重语义成本（靠注释与 N2-8 陷阱 1 钉死，mutation 检验守卫）。
- 为了**不污染簇语义**，放弃"全路径类型统一"的优雅（伪簇/哨兵）。
- 为了**不扩散审计面**，transfer 的全局寻址显式留在范围外——即使它的机制成本看起来很低。

## 后果

### 正面后果

- **可达性瓶颈解锁**：`bind` 第一次能触及全局测度——"窗口 × 大众"的身份边成为可表达；
  规则侧使用（大众婚配等）留独立决策，但通道侧能力已就位。
- 复用全部纪律：先扣后加、配额、逆序全撤、账本、确定性（不变量 5）、性能预算
  （每意图 O(`occupied` log `occupied`)，全局 `occupied` ≈ 1.4e3，`cap_per_tick=8` 封顶 ⇒ 与人口 N 无关）。
- **惰性不变**：`RULES` 空 ⇒ 新分支不执行 ⇒ 全部权威数字与门槛不动（验收含 `bench.audit_ledger --resolution`）。

### 负面后果

- `coarse=None` 的双重语义（元组成员 vs 整体返回）是一个**易错点**——写进 N2-8 陷阱 1，
  由 mutation 检验守卫（"写反 ⇒ R→M 全变 stale 或 stale 意图乱扣 `window.measure`"）。
- 全局测度寻址的析出者（如"大众配偶"）不在任何簇、不建 `acquaintance` 网 ⇒ 容量吃紧时较早退场
  （与 ADR-007 已知边界同类，MVP 接受）。
- M→R 的"大众发起"语义只有**通道表达**意义（粗侧没有意愿）——规则是否使用它需另证
  （ADR-007 方案 B 对"规则语义"的立场保留不变）。

### 需要跟进的

- **规则侧使用**（大众婚配 / 结友）独立决策：本轮只加通道能力，探针验收；宏观读数默认不变。
- **`transfer` 的 measure 寻址**独立决策（方案 E 的拒绝理由即其前置问题：清算全局分布的审计）。
- teach-back 对账：[`reviews/2026-10-18-measure-addressing-teachback.md`](../reviews/2026-10-18-measure-addressing-teachback.md)。
