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
| ρ（rho） | 已遗忘的身份质量（coarsen 增、merge 减、dissolve 记入累计） | `float ≥ 0` | `IdentityMassRho` | | — |
| 显要（notability） | 自身财富 ≥ 全人口高位分位阈值的个体；**不逐出、不粗化** | `WealthNotability`；`SIM_NOTABLE_FRACTION`（默认 `0.01`） | | 不是"注意力高"（两者取 max，但含义不同） | — |
| 桶（bucket） | 状态空间的一格；"占用桶" = 计数 > 0 的桶 | `int` 索引 | `occupied` | | — |
| 段池（yearly_inherited） | 继承的年度分段池（gap 窗口 `u∈[a−50,a−18]`）；**整数桶支付 + 余量留池** | `dict[segment→float]` | | 不是 per-cell 账本（会注水） | — |
| 分数桶位移 | 按小数部分把计数拆到相邻两桶——**禁止**（碎片化） | | | 正解 = 段池 + 整数桶 | — |
| 广场（event_plaza） | 结识的配对场所（按 `n_cells` 分区） | `PeopleEvents` | | | — |
| 关系漏斗 | `acquaintance(≤12) → familiarity(≤6) → friend(≤3) → spouse` | | | | — |
| rare_stride | 稀有事件降频：每 K 个判定周期评估一次、单次概率 ×K | | `rare_stride=1` 逐位一致 | | — |
| 收敛门槛 | 测度 vs 个体的验收阈值 | `gini_diff<0.02`、`wealth_ks<0.06`、`age_l1<0.06`、`married_diff<0.10` | | | — |
| 确定性模式 | 设 `SIM_SEED` 即固定随机 + 跳过墙钟负载反馈 | | | 与"按机器吃满预算"互斥 | — |
| 快照（snapshot） | `simulation_time` + 测度 + 窗口（含关系图 id）的持久化 | `snapshots` 表 | | | — |
| 继承溢出（overflow_fraction） | 族内继承中改注入**全局池**的比例（0 = 完全内化 = "富族恒富"） | `float ∈ [0,1]` | | | — |

## 维护规则

- 出现**新领域概念** → 当场登记，再在别处使用。
- 文档里出现**未登记的名词** = 漂移信号：补齐，或改用已登记词。
- 术语含义变化 → 视为可能的不变量变更，走 ADR。
- 一个词只在一处定义；别处只引用——重述必然产生第二个定义。

## 相关文档

- L1：[`../AGENTS.md`](../AGENTS.md) · L2：[`architecture.md`](architecture.md) · L3：`docs/modules/<name>.md` · L4：`core-code.md`
- 决策：[`decisions/`](decisions/README.md)
