# SimuWorld 工程规范（Model & Contracts）

本文是**规范**：模型语义、速率、守恒律、数据契约的权威定义。逐步演进的历史与实测数字见 `docs/history.md`；工具用法见 `bench/README.md`。

## 1. 分层架构

```
SIM_MODE=individual ──► 个体引擎（SimulationEngine / EventEngine；高保真参照，O(N)）
                              ▲ 收敛验证（bench.convergence --full-compare）
SIM_MODE=measure ──────────┤
                           │  测度引擎（MeanFieldEngine：稀疏计数分布 + 流算子，成本=O(占用桶数)）
                           │        ↕ materialize / dematerialize 守恒交换
                           └  物化窗口（≤capacity 个真 Character，真实关系图）
                                    │
                                    ▼
                        观测（SSE）/ 持久化（snapshot）/ 控制（/api/v1/simulation）
```

- **个体引擎**是语义真值：所有均值场近似必须收敛于它。
- **测度引擎**承载无限人口；**窗口**从测度层引出固定数量的真个体供观测。
- 驱动：`SimulationRunner`（app/core/simulation/runner.py）按 1s/tick 稳定推进（`time_limit(1)`），可经控制路由反复 start/stop（状态原地保留）。

## 2. 个体模型语义（Character，τ = step_threshold = 10）

每 tick `pedometer.step += 1`。判定发生在 `step % τ == 0`；属性变化与判定相位共享（由 `bench.world.make_characters` 的随机相位离散化，DES 引擎与其逐位一致）。

| 属性/事件 | 条件 | 率/公式（每判定周期，τ=10） |
| --- | --- | --- |
| 年龄 +1 | 每 360 tick | 固定 |
| 收入 +1000 | 每 30 tick，18<age<60 | 固定 |
| 结识 acquaintance | age≥6 | `round_up(0.1·τ·12/(n_acq+12))`（自己的副本投入广场格） |
| 熟络 familiarity | acquaintance→familiarity | `round_up(0.01·τ·n_acq/(n_fam+6)·6/12)`；上限 6，超出随机降级 |
| 结友 friend | familiarity→friend | `round_up(0.001·τ·n_fam/(n_fri+3)·3/6)`；上限 3，超出随机降级 |
| 婚配 spouse | 单身、18≤age<60 | `round_up(0.1·τ/360)`；从 friend+familiarity 中（过滤单身且成年）均匀挑 1 人；**性别中立**，每桩婚事消耗 2 个单身 |
| 生育 | 已婚、age≤50 | `round_up(0.1·0.1/2·τ/27)`（≈0.005/27 每 tick） |
| 死亡 | age≥60 | `round_up(0.05·τ/360)`（≈0.05/360 每 tick） |
| 死亡结算 | — | 通知全部关系（有关系者双向移除并记 `relation_record`）；每个子女得遗产 `parent.wealth×0.1/n_child`；死者自身 `status='dead'` 出场 |

**广场配对**（`PeopleEvents`，每 tick）：各格内 `pairs = n//4`，O(pairs) 抽样腾挪配对；非亲缘、非同人 → 双向补 acquaintance。

**关系漏斗**：acquaintance(≤12) → familiarity(≤6) → friend(≤3) → spouse。度分布由此漏斗闭合（与精简参照模型收敛）。

**稀有事件降频**（个体 DES 引擎，`rare_stride=K`）：评估每 K 个判定周期一次、单次概率 ×K（泊松累积不变式）；`K=1` 与原引擎逐位一致。

## 3. 测度层

**状态空间**（`space.py`）：`(age 0..120, gender 0/1, wealth_bucket, marital 0..2)`；
- 财富**线性分桶**宽度 w=1000（桶中心 = (b+0.5)·w）——使"+1000 收入"退化为精确的一桶位移；
- 上限 60000 桶（单人财富 6e7）：Stage 10 起计数为**稀疏容器**（内存 ∝ 占用桶数），bins 不再带来线性内存代价——上限实质解除（t=20000 实测最高 ~551k）。
- 混合基数 `encode/decode`。

**分布**（`measure.py`）：`counts` numpy 稀疏数组 + `occupied` 集合；一切成本准则 = **O(占用桶数)**，与人口 N 无关。

**流算子**（`transitions.py`，`FULL_FLOWS` = 衰老 → 收入 → 死亡 → 婚配 → 生育 → 继承）：

| 算子 | 语义（与 §2 逐项对应） | 成本 |
| --- | --- | --- |
| aging | 每 360 tick 全体 +1 岁（整桶平移） | O(占用) |
| income | 每 30 tick，18<age<60 桶 +1（精确） | O(占用) |
| death | age≥60 每 tick 划掉 `count×0.05/360`；记录 ``(age, wealth, amount)`` 入 `recent_deaths` | O(占用) |
| marriage | 每 tick：单身成年 `singles×0.1/360×availability`，availability=`1-(1-p_elig)^2.5`；婚配消耗 2 单身，按桶占比摊 | O(占用) |
| birth | 已婚 18≤age≤50 的 `×0.005/27`，新生男女各半入 (0岁,财富0) 桶 | O(占用) |
| inheritance | 见下 | O(占用)/年 |

**继承（段池整数分配，Stage 7 设计）**：
1. 每个 `recent_deaths` 记录注入 `inherited = amount × wealth_value × 0.1`，按 gap 窗口 `u ∈ [a−50, a−18]`（生育对 18–50 岁父母近似均匀 → 差值密度均匀）流入年度段池 `yearly_inherited[u]`；
2. 每 360 tick 清算：对每个非空段，按接收桶**财富质量占比**（count×桶中心）分配理想份额；每桶支付 `floor(理想/ (count·w))` 个**整数桶位移**（整桶平移，不拆分桶计数）；余量**留池**下年再分。
3. 守恒（`bench.audit_ledger`）：`期末报告财富 + 段池余量 == 初始 + Σ收入 + Σ出生桶值 − Σ死者×0.9`；审计误差现为 0.06%（桶中心与整数位移的量化差）。

## 4. 物化窗口

`window.py`：`IndividualWindow` 实现个体模型的 model 接口（characters/event_plaza/publish_list…），因此内部跑完整个体语义。

- `materialize(age,gender,wealth,marital)`：测度 −1 → 生成 Character（`generate_character`）。要求该桶计数 ≥1。**入窗建网（Stage 9）**：成年人入窗时与至多 3 位窗口内成年人互认 acquaintance（避免"空图老人"式凭空物化）。
- `dematerialize(id)`：**退场断链（Stage 9）**——先借用 DeathEvent 的 notify 语义（在**对方**的事件上以离场者为参数）解除 acquaintance/familiarity/friend/spouse/parent/sibling 并双向记档；`child` 边手工断链（**离场不触发死亡结算，子女不继承**）；随后把本人从广场格清除；最后折算 (age,gender,财富,婚配) 回测度（配偶边已断 → 折算为单身）。
- 容量强制：超 `capacity` 时按**最小嵌入优先**退场（嵌入度 = `2×|spouse| + |friend| + |familiarity| + |acquaintance|`，同分按插入序；已婚者最后离场——家庭连续性）。
- **守恒律**：`Σ测度 + len(窗口) == 初始 + 窗口出生 − 窗口死亡`（断链不改变总量；测试覆盖长跑 + 无幽灵断言）。
- `WindowEngine` = `MeanFieldEngine` + `IndividualWindow`；`WindowEngine.restore(snapshot, capacity)` 从快照重建整世界（测度 payload + 窗口 Character 字典，id/关系图按 id 接回；恢复后的 population == 存档时，含池余）。

## 5. 持久化（snapshot）

`app/models/snapshot.py`：表 `snapshots(simulation_time, measure, window)`。
- `measure` payload：`{"size", "cells": [[index, count(6位小数)], …]}`（只存非零桶，往返误差 <1e-6/桶）。
- `window` payload：每个窗口 Character 的全量 `__dict__`（含 relationships 为 id 列表）。
- 写入：`simulation/stop`（measure 模式自动）；`SIM_RESUME=1` 时 `run.py` 启动即 `load_latest()` 恢复；无档/空表/无表 → 新建世界。
- 注意：恢复后窗口负载回到 capacity 上限之内；窗口计数与测度不重复计（存档时两者守恒互斥）。

## 6. 运行契约

**环境变量**（run.py）：

| 变量 | 默认 | 语义 |
| --- | --- | --- |
| `SIM_MODE` | measure | measure \| individual |
| `SIM_CAPACITY` | 1000 | 窗口真个体上限 |
| `SIM_POPULATION` | 5000 | 初始人口（measure） |
| `SIM_RESUME` | 0 | `1` = 启动时从最新快照恢复 |
| `SIM_SEED` | — | 整数；设了即**确定性模式**——固定随机种子并禁用墙钟负载反馈，同种子必然同发展 |

（另：`REDIS_URL`、`SIM_DB_PATH`、`CORS_ORIGINS` 见 `app/__init__.py` / `app/models/table.py`。）

**SSE**（`/stream?channel=<client_id>`）：
- 事件 `data`（每 tick）：`{time(世界时间 y-m-d), population, simulation_load(秒), people: [{id,name,gender,age,wealth,relationships:{friend,spouse,parent,child:[[id,name]…]}}], age: [labels,counts], wealth: [labels,counts]}`
- 事件 `initial_data`（连接建立补发）：`survey_data`（或 `{status:'connected'}` 兜底）。
- 前端契约细节：受管单连接 + 指数退避重连 + 关页 sendBeacon 退订（web/README）。

**控制 API**（`api/v1/simulation.py`，runner 挂在 `app.extensions['sim_runner']`）：

| 路由 | 行为 |
| --- | --- |
| `GET /api/v1/simulation` | running/mode/simulation_time/population |
| `POST /api/v1/simulation/start` | 启动（已运行→ success:false） |
| `POST /api/v1/simulation/stop` | 停止线程（measure 落快照）；未运行→ success:false |

## 7. 验收与回归

- `pytest`（92 条）：个体 DES 逐位一致、测度收敛门槛（gini<0.02、KS<0.06、age_l1<0.06）、窗口守恒/断链、财富守恒门禁（`bench.audit_ledger.run_audit`）、快照往返、控制路由、bench 构建冒烟。
- 任何算子改动：`bench.convergence --full-compare` + `bench.audit_ledger`（门：identity 误差 <0.1%）+ `bench.diagnose_tail`（区分系统性偏差与 p100 噪声）。
- `docs/history.md` 记录结论；`bench/results/` 存证据。

## 8. 已知边界

1. 婚配性别中立是个体模型的**既定语义**（修改它 = 修改两引擎契约，需同步）；
2. 均值场婚配早期瞬态偏快（联系即时可用假设），稳态一致；
3. p100（最富个体）存在跨种子 ±0.6% 的采样摆动——有界噪声，勿当优化目标；
4. individual 模式成本 O(N)（高保真参照的本位），与测度层的 N 无关性并存；
5. SSE/缓存依赖本机 Redis；测度快照表共享 `db.sqlite3`。

## 9. 分辨率与团层（Cluster / Resolution）

契约细节见 `docs/cluster-contract.md`；实现 `app/core/measure/cluster.py`。

**概念**：测度（匿名）与窗口（个体）是同一个"分辨率连续谱"的两端。**团 = 身份敏感交互（parent/child/spouse）的连通闭包**；分辨率 `level`：`0`=聚合（coarse），`1`=个体（resolved）。被观测/被认识者保持高分辨率，否则随注意力衰减溶回统计。

**数据模型**：`Cluster{id, kind, level, member_ids, state, interface, rho, parent_id}`；`ResolutionManager` 拥有 `ClusterStore` + 注意力场 + `WaterlinePolicy`。

**算子**（`ClusterStore`）与守恒：`create/materialize/coarsen/merge/split/dissolve` 全部**质量中性**（计数只在 measure / coarse / window 间移动）。守恒律扩为：

```
Σ measure.counts + Σ_coarse size + len(window.characters) == 初始 + 出生 − 死亡
```

**coarse 团** = mini `MeanFieldEngine`（`FamilyKind.flows` = FULL_FLOWS 去掉 `inheritance`）；继承由 `step_coarse` 手动调 `family_inheritance`（含 `overflow_fraction`：族内继承中改注入全局池的比例，0 = 完全内化 ="富族恒富"）。

**注意力**：外生 `set_attention(cid, v)`（观察者 pin，`a ← γa` 衰减）；内生 `_endogenous_attention`（被窗口内非成员的**强关系**认识程度 / `endogenous_scale`）；取 `max`。`WaterlinePolicy`：`a ≥ theta_base` 且 leaf 预算足够 → resolved；`feedback` 按负载调预算。

**成团与边界**（`_reconcile`，每 `form_interval`）：剪离场成员→抽入一跳浮层亲属→跨团边记 `interface`→未入团浮层按连通分量建团；`_merge_coupled`（分量内合并后 ≤ `max_members` 的团并一）；`_split_fragmented`（团内断连则切分）；`_recycle`（无注意 coarse 团 `dissolve` 回全局，防饱和）。

**接口**：`GET /api/v1/resolution`；`GET/POST /api/v1/attention`（`cluster_id` 或 `person_id`）；`GET /api/v1/life/<person_id>`（个体生命轨迹）。SSE `data` 增 `resolution`（θ/预算/ρ/团条目）与 `notables`（resolved 个体）。

**参数**：`min_size=2, max_members=12, max_clusters=64, form_interval=30, gamma=0.99, initial_attention=0.8, dissolve_floor=0.1, endogenous_scale`（runner=`max(6, capacity/25)`）, `budget_leaves=capacity, theta_base=0.5`。

**确定性 vs 自适应（`SIM_SEED`）**：默认每 tick 按**实测墙钟负载** `feedback` 调 `budget_leaves`，在本机预算内尽量多留显名者——代价是"规则"依赖机器速度，**同种子不可复现**。设 `SIM_SEED` 即进入**确定性模式**：固定随机种子并跳过负载反馈（`budget_leaves` 恒定 = capacity），换取"同种子 + 同口径（mode/capacity/population）⟹ 同发展"。二者互斥，取舍由运行者定：要复现/回放就设种子，要按机器吃满预算就不设。注意 `SIM_RESUME=1` 以快照为准，不参与种子重演。

**已验**：`bench.audit_ledger --clusters` 恒等误差 **0.0000%**；`bench.cluster_inheritance` 族内 vs 全局人均留存 ~181×（peers=120）。

**已知边界（本层）**：resolved 团的婚配/出生仍族内闭合（跨团婚配只**记录** `interface`，未在 coarse 模型消费，除 `overflow_fraction`）；`life_log` 只保留窗口内当前个体。
