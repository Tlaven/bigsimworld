# Glossary — 术语表（SimuWorld）

> **一个词只在这里定义一次**（单一事实来源），文档别处只引用、不重述。
> 判据：读者（AI 或新人）看到这个词，能否**不看代码**就知道它指什么、结构是什么、边界在哪。
> 出处：词条从既有作者文档 / 代码提取的**标来源**；靠推断补的标 `推断,待确认`。

## 术语表

| 术语 | 定义（一句话） | 类型 / 结构 | 例子 | 反例 / 易混 | 禁用别名 |
|---|---|---|---|---|---|
| 个体引擎 | 逐个体演化的高保真引擎，是语义真值（生产不跑它） | `SimulationEngine` / `EventEngine`；O(N) | `SIM_MODE=individual` | 不是测度层；不是"折衷" | — |
| 测度层 / 测度引擎 | 状态空间上的稀疏计数分布 + 流算子，成本 = O(占用桶数)，承载无限人口 | `MeanFieldEngine` | `SIM_MODE=measure` | 不是"抽样近似"——是完整分布 | — |
| 测度（Measure） | 年龄×性别×财富桶×婚配 的稀疏计数容器 | `counts`（稀疏）+ `occupied`（set） | `measure.total()` | 不含窗口内真个体 | — |
| 状态空间（StateSpace） | 维度分桶 + 混合基数编码 | 财富**线性分桶**宽 1000、60000 桶、121 龄段 | `encode(age,gender,wealth,marital)` | 财富不是连续值，是桶索引 | — |
| 物化窗口 | ≤ `capacity` 个带真实关系图的真个体，供观测 | `IndividualWindow` / `WindowEngine` | `SIM_CAPACITY=1000` | 不是旧"轻量个体"层（已删） | — |
| materialize | 测度 −1 → 生成真 `Character`（要求该桶计数 ≥ 1.0） | | | | — |
| dematerialize | 真个体退场：**断链**（不触发死亡/继承）+ 折算回测度 | | | 不是 death | — |
| 共演单元（Cluster） | 身份敏感交互（parent/child/spouse）的**连通闭包**；同档分辨率共同演算的最小单元 | `Cluster{id,kind,level,member_ids,state,interface,rho,parent_id}` | `FamilyKind` | 不是"团队 / 公会"（后者是未来 kind） | **团**（旧称，已改） |
| 分辨率（level） | 共演单元的演化档位：`0`=聚合，`1`=逐个体 | `int` | `level=1` | | — |
| coarse / resolved | `level=0`（聚合态）/ `level=1`（逐个体） | | | | — |
| 注意力（attention） | 决定共演单元是否保持 resolved 的"凝视"量 | `dict[cid→float]`，`a ← γ·a` 衰减 | | 不是"重要度"绝对值 | — |
| 水位线（WaterlinePolicy） | `attention ≥ theta_base` 且 leaf 预算够 → resolved | `theta_base=0.5`、`budget_leaves=capacity` | | | — |
| ρ（rho） | 已遗忘的身份质量 = 收编时 `Σ(1 + 关系度)`（关系度 = `neighbors` 大小）；coarsen 增、dissolve 记入累计 | `float ≥ 0` | `IdentityMassRho` | | 不是"簇成员数"（取死字段 `relatives` 的旧后果，已修） | — |
| 显要（notability） | 自身财富 ≥ 全人口高位分位阈值的个体；**不逐出、不粗化** | `WealthNotability`；`SIM_NOTABLE_FRACTION`（默认 `0.01`） | | 不是"注意力高"（两者取 max，但含义不同） | — |
| 桶（bucket） | 状态空间的一格；"占用桶" = 计数 > 0 的桶 | `int` 索引 | `occupied` | | — |
| 计数中性 | 分辨率算子（`create`/`materialize`/`coarsen`/`merge`/`split`/`dissolve` 与窗口侧 `materialize`/`dematerialize`）只**移动**计数，不产生 / 销毁 | | 门禁 `bench.audit_ledger --resolution` | 不是"守恒"——恒等式里 `出生`/`死亡` 才是真正的源与汇 | — |
| 段池（yearly_inherited） | 继承的年度分段池（gap 窗口 `u∈[a−50,a−18]`）；**整数桶支付 + 余量留池** | `dict[segment→float]` | | 不是 per-cell 账本（会注水） | — |
| 分数桶位移 | 按小数部分把计数拆到相邻两桶——**禁止**（碎片化） | | | 正解 = 段池 + 整数桶 | — |
| 广场（event_plaza） | 结识的配对场所（按 `n_cells` 分区） | `PeopleEvents` | | | — |
| 关系漏斗 | `acquaintance(≤12) → familiarity(≤6) → friend(≤3) → spouse` | | | | — |
| 可用性闭合 | 均值场婚配的成功率：单身者的可接触对象中"至少有一个单身"的概率（性别中立） | `q ≈ 1-(1-p_elig)^deg`（`deg=2.5`） | `transitions.marriage` | 不是 `r·min(M,F)`（欠婚）/ `r·(M+F)`（过婚） | — |
| rare_stride | 稀有事件降频：每 K 个判定周期评估一次、单次概率 ×K | | `rare_stride=1` 逐位一致 | | — |
| 收敛门槛 | 测度 vs 个体的验收阈值 | `gini_diff<0.02`、`wealth_ks<0.06`、`age_l1<0.06`、`married_diff<0.10` | | | — |
| 确定性模式 | 设 `SIM_SEED` 即固定随机 + 跳过墙钟负载反馈 | | | 与"按机器吃满预算"互斥 | — |
| 快照（snapshot） | `simulation_time` + 测度 + 窗口（含关系图 id）的持久化 | `snapshots` 表 | | | — |
| 继承溢出（overflow_fraction） | 族内继承中改注入**全局池**的比例（0 = 完全内化 = "富族恒富"） | `float ∈ [0,1]` | | | — |
| 交互通道（InteractionChannel） | 共演单元 ↔ 单位个体的**点对点、双向、可具名**交互路径 | `Intent` 队列 + `bind`/`unbind` + 账本 | `channel.run(ctx)` | 不是"经全局测度中转"的间接路径（`overflow_fraction`→测度→`materialize`） | — |
| 意图（Intent） | 通道的唯一输入形态：`kind / origin / scope / match / payload`；`origin` = 发起者（角色或簇） | frozen dataclass | `Intent(kind="probe", origin=("character",3), scope=("cluster",7), match=…)` | 粗侧**不能**用 id 寻址（只能带 `Match`） | — |
| Match | 声明式可匹配性（`age`/`gender`/`wealth_bucket`/`marital`，**闭区间**；`marital` 是标量 0/1），编译为**桶索引谓词**，R↔C 两侧共用 | frozen dataclass + `compile(match, space, extraction=…)` | `Match(age=(28,35), gender=0)` | 不是任意闭包；引用不可重建维度必须抛错；`marital=1` ⇒ **成对析出** | — |
| bind | **有身份**的绑定 = `extract` + `link`，先扣后加；**析出永远发生在 coarse 侧**；`Match(marital=1)` 时**成对**（取 2 人 + `link` 成配偶） | 通道原子 | 婚配 / 结友 | 不是 transfer（不产生身份） | — |
| unbind | `bind` 的逆：`unlink`（断链）+ 把该角色折算回 coarse；成对绑定时**连配偶一起**（断两条边、两人各自折算） | 通道逆算子 | `unbind(new_id)` | 不是 `dematerialize`（后者折算回**全局测度**） | — |
| extract | 从 coarse `Measure` 按 `Match` 析出 `amount` 个整人（要求桶 `count ≥ amount`：单人 1.0 / 成对 2.0） | 通道原子 | `extract(mini, pred, amount=2.0)` | 不是 `materialize`（后者从全局测度取） | — |
| `link` | **边的唯一入口**：一次调用双向写 `relationships`（对称；非对称用 `reverse`）。**不记档**——`relation_record` 只由 `unlink(..., record=True)` 追加 | `link(a, b, "friend")` / `link(parent, child, "child", "parent")` | 不是直接改 `relationships`（会漏写另一侧、造幽灵边） | — |
| 关系人（`neighbors`） | 个体的**关系人集合**（`relationships` 全部关系桶的并集，去重）；"关系度" = `len(neighbors)` | `links.neighbors` | `len(neighbors(c))` | 不是已删除的 `relatives`（构造后从不更新 ⇒ 度恒为 0） | — |
| 先扣后加律 | 会产生边的跨分辨率交互**必须先把质量从 coarse 侧移出**，否则重复计数 | 通道强制的提交协议 | `bind` 的 reserve→commit→rollback | 不是"守恒"（守恒只管人头，不管重复计数） | — |
| 谓词式寻址 | 粗侧无 id ⇒ 意图只用 `Match` 声明可匹配性；id 只在 `extract` 之后存在 | `Match` 声明 | `Match(gender=0)` | 不是 id 式寻址（粗侧无 id，表达不出来） | — |
| 可重建维度 | `extract` 之后能重建的桶维度；`{age, gender, wealth, marital}` | `RECONSTRUCTIBLE` | | `marital` **可寻址但只能成对析出**（N2-5）——单独析出会造假单身 | — |
| transfer | **无身份**的质量移动（可交换、不产生边）——**本期不做**：其财富量化残差池需独立规格与独立不变量 | 质量侧原子（下期） | 继承 / 馈赠 / 族间再分配 | 不是 bind；也**不**受"人头守恒"约束 | — |
| 通道账本 | 每条通道操作的逐条记录（有界 deque），供观测与对账 | `deque(maxlen=…)` | 逐条核平 | 不是 `yearly_inherited`（那是继承段池） | — |
| 交互规则（InteractionRule） | 第 9 缝：声明"发起什么意图 + 绑定后建什么边"；**本期为空注册表** | `Protocol` + `RULES` | `RULES = {}` | 不是通道（通道保证守恒/确定性，规则只管语义） | — |

## 维护规则

- 出现**新领域概念** → 当场登记，再在别处使用。
- 文档里出现**未登记的名词** = 漂移信号：补齐，或改用已登记词。
- 术语含义变化 → 视为可能的不变量变更，走 ADR。
- 一个词只在一处定义；别处只引用——重述必然产生第二个定义。

## 相关文档

- L1：[`../AGENTS.md`](../AGENTS.md) · L2：[`architecture.md`](architecture.md) · L3：`docs/modules/<name>.md` · L4：`core-code.md`
- 决策：[`decisions/`](decisions/README.md)
