# Core Code — L4 核心代码（N2 收录）

> **定位**：只收录**跨模块 / 架构骨架 / 高扇入**的 N2（AI 未见的领域核心）。
> **不收什么**：只被单个模块内部依赖的 N2 → 该模块 L3（`docs/modules/<name>.md`）；事实细节（模型语义 / 速率 / 公式 / API 契约）的唯一定义处 = [`engineering-spec.md`](engineering-spec.md)——此处**只写实现所需的步骤与判据**，不重述数字。
> 三段式：[是什么] / [为什么] / [不变量]。N2 怎么造验收见 [`../docs-templates/verifying-n2.md`](../docs-templates/verifying-n2.md)。

`novelty=N2`

---

## [是什么] — 收录清单

| # | N2 单元 | 代码位置 | 为什么在 L4（而不是某模块 L3） |
|---|---|---|---|
| N2-1 | 稀疏计数状态空间与「成本 = O(占用桶数)」 | `measure/space.py`、`measure/measure.py` | **骨架**：换层成立的前提，全层成本纪律 |
| N2-2 | 流算子的顺序契约与「只移动不产生」 | `measure/transitions.py` | **高扇入**：窗口 / 共演单元 / 通道复用同一批算子 |
| N2-3 | 继承的段池整数分配（守恒可审计优先） | `measure/transitions.py` | **骨架样板**：任何"质量转移"必须照此做，否则守恒立刻破 |
| N2-4 | 分辨率算子的计数中性（整人析出 / 残留并入） | `measure/cluster.py`、`measure/window.py`、`measure/channel.py` | **高扇入**：3 个模块共用同一条纪律 |
| N2-5 | 分辨率折算的财富残差（**符号账**，折算点唯一写法） | `measure/measure.py`、`measure/window.py`、`measure/cluster.py`、`measure/channel.py` | **骨架**：财富恒等式的最后一块；漏记/多记会让全局 W 静默失真 |

**术语**（定义见 [`glossary.md`](glossary.md)，此处只引用）：测度、状态空间、桶 / 占用桶、段池、分数桶位移、计数中性、可用性闭合、materialize、dematerialize、extract。

**相关模块**：物化窗口 / 共演单元层的事实细节见 [`engineering-spec.md`](engineering-spec.md) §4/§9 与 [`cluster-contract.md`](cluster-contract.md)；跨分辨率交互的 N2（`bind`/`unbind`）归 [`modules/interaction-channel.md`](modules/interaction-channel.md)。

---

## [为什么] — 收录判据与实现方向

### 判据（与 L1 的 N2 路由一致）

1. **跨模块**：被 ≥2 个模块依赖；**或**是架构骨架（其余模块的正确性建立在它之上）；**或**高扇入（改错会同时破坏多个不变量）。
2. 收录的这四条都满足「改错会同时破坏多个不变量」：
   - N2-1 破 ⇒ 成本随 N 变（"可承载无限人口"的招牌失效）；
   - N2-2 破 ⇒ 与个体引擎的收敛失守（且守恒测试仍可能全绿——**错得很安静**）；
   - N2-3 破 ⇒ 财富守恒立刻注水或碎片化；
   - N2-4 破 ⇒ 人头守恒破。
3. **反面样本**：交互通道的 `bind` / `unbind` 同样是 N2，但只被通道自身依赖 ⇒ 归 L3，不进本文件。

### 被拒方案（金矿——记"为什么不"）

| 被拒 | 为什么不 | 实测代价 |
|---|---|---|
| 全尺寸 `np.zeros(space.size)` 计数 | 内存 ∝ 桶数而非占用桶数；一提财富上限就得翻内存 | 全尺寸 ≈ 桶数 × 8B——当前默认 43.56M 桶（121×2×60000×3）≈ 348MB；Stage 10 改稀疏后**反而更快**（1e6 人口 2.47 → 1.75 ms/step） |
| per-bucket 欠账账本（复用桶索引） | 桶会换主人 / 被合并，新住户继承旧住户欠账 ⇒ **凭空注水** | 审计抓到 **+1.39e8**（Stage 7） |
| 分数桶位移（按小数部分拆到相邻两桶） | 拆分桶计数 ⇒ `occupied` 碎片化 | `occupied` 500 → 19,512、77 ms/step（Stage 3） |
| 婚配 `r·min(M,F)` / `r·(M+F)` | 严重欠婚 / 过婚——个体模型是**性别中立**的 | 正解 = 可用性闭合（Stage 2） |
| 从分数桶析出整人（`count < 1.0` 也取 1） | `Measure.add` 在 ≤0 时夹零 ⇒ 只扣分数却生出一整个人 | 质量泄漏（Stage 14，`test_materialize_skips_fractional_buckets`） |

---

## [不变量] — 全局纪律 + 逐单元规格

### 全局纪律（四条共用）

1. **成本 = O(占用桶数)**：任何遍历只走 `occupied`；**禁止**按 `space.size` 分配或枚举。
2. **只移动，不产生**：算子要么整桶平移、要么按率移除（`death`）或产生（`birth`）；此外不得凭空增删计数。
3. **确定性**：同 `SIM_SEED` ⇒ 同发展（`tests/test_determinism.py`）；**不得依赖 set / dict 迭代序**（history Stage 15 的确定性 bug 即此类）。
4. **守恒恒等式**：`Σ measure.counts + Σ_coarse size + len(window.characters) == 初始 + 出生 − 死亡`（源：`engineering-spec.md` §9）。

### N2-1 · 稀疏计数状态空间与「成本 = O(占用桶数)」

**步骤级说明**

1. 状态空间 = 4 维分桶 `(age 0..120, gender 0/1, wealth_bucket, marital)`，混合基数编码（`space.encode` / `decode`）。第 3 维传的是**桶索引**，不是财富值；`marital` 桶空间有 **3 档**（只写 0/1，第 3 档预留恒空——见 `engineering-spec.md` §3）。
2. 财富**线性分桶**，宽度 `w` = 收入步长：桶中心 = `(b+0.5)·w` ⇒ `+w` 恰为 `b+1`（精确整桶位移，无小数漂移）。**改 `w` 即改模型语义**（收入不再是一次整桶位移）。
3. 计数容器是**稀疏**的：读未写入的桶返回 `0.0` 且**不写入**；写 ≤0 时**删除条目**并移出 `occupied`（**夹零**——负计数不可表示；**零条目不留** ⇒ 底表键集 ≡ `occupied`。反例实测：40 年长跑残壳 2,000 → 64,931 条）。
4. 一切遍历只走 `occupied`；成本 = O(占用桶数)，与人口 N、与 `space.size` **都**无关。
5. 序列化只存非零桶（`measure_to_payload`），往返误差 <1e-6/桶。

**精确例子**

- `wealth_bucket(10500.0)` = 10；`wealth_value(10)` = 10500.0 ⇒ `income` 把 b=10 整桶移到 b=11（+1000 精确，无残差）。
- `space.encode(30, 0, 10, 0)` = `10_800_030`，`decode` 回到 `(30, 0, 10, 0)`（可直接当 fixture）。

**验收**:`python -m pytest tests/test_measure_space.py tests/test_measure_core.py tests/test_measure_transitions.py -q` → 全绿（编码双射 / 桶单调 / 稀疏容器语义 / **零条目不留**：`test_zero_buckets_are_deleted_not_left_as_residue`、`test_counts_backing_store_matches_occupied_in_long_run`）；
`python -m bench.convergence --window --sizes 10000 100000 1000000 --capacity 1000 --steps 3000` → `ms/step` 与窗口规模**不随 N 变化**（只放大每桶计数，占用桶数不变）。

**危险实现清单**

| # | 最可能被写成的样子 | 为什么错（语义差在哪） | 由谁挡住（不变量 / 验收） |
|---|---|---|---|
| 1 | 按 `space.size` 分配 / 枚举全空间（全尺寸数组的形态） | 内存与遍历 ∝ 桶数（当前默认 43.56M），不是占用桶数 ⇒ 成本不再与 N 解耦 | 全局纪律 1（禁止按 `space.size` 分配或枚举）+ 验收 ②（`ms/step` 不随 N 变——挡"遍历"形态） |
| 2 | 对数 / 非线性分桶 | `+w` 不再等于整桶位移，收入 / 继承无法精确落桶 | 第 2 步的桶中心公式（`(b+0.5)·w` ⇒ `+w` 恰为 `b+1`——对数分桶不满足）+ 精确例子（b=10 → b=11 精确） |
| 3 | "读空桶"有副作用（写入 0 / 建桶） | 污染 `occupied` ⇒ 遍历成本失控；稀疏语义被破坏 | 验收 ①（稀疏容器语义）+ 全局纪律 1 |
| 4 | 归零写成 `counts[i] = 0.0`（留零残壳，不删除条目） | 底表随桶漂移**无界增长**（实测 40 年 2,000 → 64,931 条）⇒ "成本 = O(占用桶数)" 在**时间轴**上失真、字典操作变慢 | 第 3 步（零条目不留）+ 验收 ①（`test_counts_backing_store_matches_occupied_in_long_run`） |

### N2-2 · 流算子的顺序契约与「只移动不产生」

**步骤级说明**

1. `FULL_FLOWS` 顺序**固定**：衰老 → 收入 → 死亡 → 婚配 → 生育 → 继承（`transitions.py`）。顺序是契约，不是实现细节：换序会改变语义（例：把 `birth` 提到 `death` 前，新生者会被本 tick 的死亡流扫到）。
2. 每个算子的**周期性**（每 30 / 360 tick）与**年龄 / 性别条件**是模型语义；速率与公式的权威定义处 = `engineering-spec.md` §2/§3，此处不重述数字。
3. 计数中性：`aging` / `income` 是**整桶平移**（移动，不增删）；`marriage` 只改 `marital` 维度（人数不变）；`death` 按率移除并**记录** `(age, wealth_bucket, amount)` 进 `recent_deaths`（每 tick **覆盖**，供继承算子消费）；只有 `birth` 产生人。
4. 婚配必须是**性别中立 + 可用性闭合**：从单身者出发，成功率由"可接触对象中至少有一个单身"的可用性决定；**每桩婚事消耗 2 个单身者**。
5. 平移类算子必须**先算 `moves`、再统一落桶**（先清零源桶）——"边遍历边写"在源 / 目标重合时会重复计数。

**精确例子**

- 周期：`aging` 仅在 `tick % 360 == 0` 生效（`test_aging_off_boundary_noop` 守"非周期 tick 不动"）。
- 婚配：100 单身 + 100 已婚成年（`p_elig = 0.5`，`deg = 2.5`）⇒ `availability = 1 − 0.5^2.5 ≈ 0.823`；`to_marry ≈ min(0.1/360 × 100 × 0.823 × 2, 100) ≈ 0.046` 人 ⇒ 这 0.046 人从 `marital=0` 移到 `marital=1`，**总人数不变**。

**验收**:`python -m pytest tests/test_measure_transitions.py tests/test_measure_engine.py -q` → 全绿（周期边界 / 死亡率 / 收入位移 / 人数守恒）；
`python -m bench.convergence --full-compare --sizes 2000 5000 10000 --steps 4000` → 门槛 `gini_diff < 0.02`、`wealth_ks < 0.06`、`age_l1 < 0.06`、`married_diff < 0.10`。

**危险实现清单**

| # | 最可能被写成的样子 | 为什么错（语义差在哪） | 由谁挡住（不变量 / 验收） |
|---|---|---|---|
| 1 | 婚配写成"直觉式"速率（`r·min(M,F)` / `r·(M+F)`） | 严重欠婚 / 过婚——个体模型是**性别中立**的 | 被拒方案表（实测欠婚 / 过婚）+ 验收 ②（`bench.convergence --full-compare` 门槛） |
| 2 | `recent_deaths` 跨 tick 复用（不清空） | 同一批死亡被继承算子重复入账 | N2-3 第 1 步（每 tick 覆盖）+ 验收 ①（`test_measure_transitions` 全绿） |
| 3 | "边遍历边写"（不清零源桶就落目标桶） | 源 / 目标重合时重复计数 | N2-2 第 5 步（先算 `moves` 再统一落桶）+ 验收 ①（人数守恒断言） |

### N2-3 · 继承的段池整数分配（守恒可审计优先）

**步骤级说明**（三段：注入 → 清算 → 触顶）

1. **注入**（每 tick，`inject_inherited`）：每条死亡记录把 `amount × 桶中心值 × 10%` 按 **gap 窗口** `u ∈ [a−50, a−18]`（`a` = 死者年龄）**均匀**摊入 `yearly_inherited[u]`（子女段池）；随后清空 `recent_deaths`（防重复入账）。`overflow_fraction` 可把该份额改注入**全局池**（族内继承的溢出缝）。
   **实现**：差分数组展平窗口（每记录 2 次写 + 一趟前缀和；原逐槽版 = 每记录 × ~33 槽 × 2 次字典操作）——贡献非负 ⇒ **池键集不变**，仅浮点累加序不同（末位）⇒ 2026-10-18 重基线（[`reviews/2026-10-18-core-operator-polish.md`](reviews/2026-10-18-core-operator-polish.md)）。复杂度 O(死亡记录 + 年龄跨度)。
2. **清算**（每 360 tick，`distribute_pool`）：对每个非空段池，按接收桶的**财富质量占比**（`count × 桶中心值`）算理想份额；每桶只支付 `floor(理想 / (count × w))` 个**整数桶位移**（整桶平移，**不拆桶内计数**），余量**留池**下年再分；接收段无人 ⇒ 整段留池。
3. **触顶 / 触底**：位移若越过 `wealth_bins` 上限、或下移越过桶 0 ⇒ 该桶**不支付**，份额**留池**
   （不越界、不注水）。`_shift_age_wealth` 的 `steps` **可正可负**（下移用于通道 `transfer` 的清算，
   见 [`modules/interaction-channel.md`](modules/interaction-channel.md) N2-6）；下界守卫是**正确性前提**——
   负索引会把桶串到别的 age/gender 桶。**触顶/触底分支在真实世界不可达（占用桶最高 ~551/60000）⇒
   长跑审计看不见，只能靠强制构造的测试守**。
   **正确性条件（不是实现细节）**：支付方必须**返回实付量**，调用方按实付扣池。
   曾有一版（2026-10-17 修）触顶时 `_shift_age_wealth` 提前返回，而调用方**仍按 `count×k×w` 扣池**
   ⇒ **凭空销毁质量**（实测：桶 `59999`、`count=1`、池 `2500` ⇒ 池变 `500`、桶未动，损失 2000）。
   当前占用桶最高 ~551/60000 ⇒ 该分支在真实世界**不可达**，`bench.audit_ledger` **看不见它**
   ——只能靠**强制触顶**的测试守（见验收）。
4. **守恒**：池只进（遗产注入）出（支付 ≤ 理想份额）⇒ `期末财富 + 池余 == 初始 + Σ收入 + Σ出生桶值 − Σ死者×0.9`。

**三条禁令**（源：`bench/README.md`「守恒纪律」）：① 账本**禁止挂桶索引**；② **禁止分数桶位移**；③ 转移只走"段池 + 整数桶支付 + 余量留池"。

**精确例子**

- 死者 `age=45`、财富桶 `b=10`（中心 10500）、`amount=1.0` ⇒ 遗产 = `1.0 × 10500 × 0.1 = 1050`；gap 窗口 `u ∈ [0, 27]` ⇒ 28 段，每段 37.5。
- 清算：接收桶 `count=1`、段池 `available=2500` ⇒ `k = floor(2500 / (1×1000)) = 2` ⇒ 该桶**整体上移 2 桶**（支付 2000），余 500 留池。
- 同一段池、接收桶 `count=3` ⇒ `k = floor(2500 / 3000) = 0` ⇒ **全部留池**（宁可迟一年，也不超付）。
- 触顶：接收桶在 `wealth_bins−1`（上限）、`count=1`、池 `2500` ⇒ **不支付、池不变**（`k` 照算，但位移不可能 ⇒ 份额留池）。

**验收**:`python -m bench.audit_ledger --n 5000 --steps 8000` → `identity error < 0.1%`（量化噪声级；2026-10-17 本机实测**绝对 ≈1e-05、相对 ≈1e-14**）；
`python -m pytest tests/test_measure_transitions.py tests/test_audit_ledger.py tests/test_measure_convergence.py -q` → 全绿（含**强制触顶**的质量守恒守卫 + 恒等式 + 尾部门槛 `wealth_ks < 0.06`）。

**危险实现清单**

| # | 最可能被写成的样子 | 为什么错（语义差在哪） | 由谁挡住（不变量 / 验收） |
|---|---|---|---|
| 1 | per-bucket 欠账账本（复用桶索引） | 桶会换主人 / 被合并，新住户继承旧欠账 ⇒ **凭空注水** | 三条禁令 ① + 被拒方案表（实测 +1.39e8） |
| 2 | 分数桶位移（按小数部分拆到相邻两桶） | 计数碎片化（`occupied` 爆炸） | 三条禁令 ② + 被拒方案表（实测 `occupied` 500 → 19.5k） |
| 3 | 支付顺序依赖 `occupied` 遍历序 | 谁收到钱随遍历序改变（已实测：总量同为 1000 时收款桶会变）；对代码改动脆弱 | 全局纪律 3；严整改方向 = 照通道 `extract` 显式按桶索引升序 |
| 4 | 把 `recent_deaths` 当"可跨 tick 的账本" | 它是每 tick 覆盖的临时记录 ⇒ 重复入账 | N2-3 第 1 步（覆盖清空）+ 验收 ②（`test_measure_transitions`） |
| 5 | 审计账法与算子**不同相位**（如用 `step` 前快照 × 1000 的解析式计量） | 引入相位误差，会被误读成"模型守恒误差 0.06%" | 验收 ①（`bench.audit_ledger` 与算子同相位计量） |
| 6 | 以为长跑审计能守住触顶 / 触底分支 | 该分支在真实世界不可达（占用桶最高 ~551/60000）⇒ 恒等误差照样好看 | 验收 ②（**强制触顶**的质量守恒守卫；别指望长跑审计） |

### N2-4 · 分辨率算子的计数中性（整人析出 / 残留并入）

**步骤级说明**

1. 分辨率算子（`create` / `materialize` / `coarsen` / `merge` / `split` / `dissolve`，以及窗口侧 `materialize` / `dematerialize`）**计数中性**：只移动，不产生 / 销毁。
2. **整人析出守卫**：只能从 `count ≥ amount` 的桶取整人（单人 `amount=1.0`；通道的双人析出 `amount=2.0`），每取 1 人恰好扣 1.0；分数桶（<1 人份额，来自 coarse 的 `death` / `birth`）**留在共演单元内**。
3. **残留并入**：`coarsen` 以窗口成员重建聚合态时，必须并入共演单元内的分数残留；否则再次粗化会丢质量。
4. 恒等式扩为：`Σ measure.counts + Σ_coarse size + len(window.characters) == 初始 + 出生 − 死亡`。

**精确例子**

- 桶 `count=0.3` ⇒ **不析出**（`test_materialize_skips_fractional_buckets`）；`count=1.4` ⇒ 析出 1 人、留 0.4；随后 `coarsen` ⇒ 0.4 必须折回（`test_coarsen_keeps_materialize_residue`）。

**验收**:`python -m pytest tests/test_resolution_conservation.py -q` → 全绿；
`python -m bench.audit_ledger --resolution --n 3000 --steps 2000 --capacity 300` → **逐算子** `identity error = 0`（生产口径，coarse 流含 `death` / `birth`）。

**危险实现清单**

| # | 最可能被写成的样子 | 为什么错（语义差在哪） | 由谁挡住（不变量 / 验收） |
|---|---|---|---|
| 1 | 从分数桶（`count < amount`）取整人 | `Measure.add` 夹零 ⇒ 只扣分数却生出一整个人（质量泄漏） | 整人析出守卫（第 2 步）+ 验收 ①（`test_materialize_skips_fractional_buckets` 等） |
| 2 | 只跑 `--clusters` 门禁就收工 | 质量保持子集**结构上盖不住**分数桶 / 残留泄漏 | 验收 ②（**两个门禁都要跑**：`--resolution` 是生产口径） |
| 3 | 把身份当守恒量（要求 `coarsen → materialize` 是同一批人） | 它是**重采样新代表**——人数守恒、身份不保 | 恒等式的口径（第 4 步）+ `engineering-spec.md` §9 的界定 |

### N2-5 · 分辨率折算的财富残差（符号账）

**为什么**：`w` = 财富桶宽。具名个体的 `wealth` 是精确浮点，折回测度时只能落在**桶中心** `c`。
"精确 → 桶"这一方向差 `wealth − c`（可正可负，≤ `w/2`）；不记账，全局财富恒等式就不成立。

**步骤级说明**

1. **恒等式**（在每个 `Measure` 上扩一项）：
   ```
   W = Σ_测度 [ count×桶中心 + transfer_pool + conversion_residual + Σ yearly_inherited ]
       + Σ_窗口 wealth
   ```
2. **唯一写法**（折算点）：`record_conversion(measure, space, wealth)`：
   `bucket = space.wealth_bucket(wealth)`；`measure.conversion_residual += wealth − space.wealth_value(bucket)`。
   **正号** = 该测度把高于桶中心的个体折低了（欠世界）；负号反之。
3. **只有三个损失点可以调用**：`IndividualWindow.dematerialize`、`ClusterStore.coarsen`（**每个**成员）、
   `Channel.unbind`（每个折算者）。
4. **精确点不得调用**：`materialize` / `materialize_sample`（角色 `wealth` 取**桶中心**，不是桶内随机值）/
   `ClusterStore.materialize` / `bind`（含成对析出的 `extract(amount=2)`）——它们"移走 `c`、造出 `c`"，
   天然精确；多记一次就破坏恒等式。
5. **随测度走**：`fold_pools(src, dst)` 除两个池外**也要折 `conversion_residual`**
   （`coarsen` / `merge` / `dissolve` / `split` 四处，**只折不记**）；快照往返该字段（旧档按 0 读）。
6. **不可花费**：`transfer` 的"可支付总额" = `mass() + transfer_pool`，**不含**残差；
   它不进池、不结算、不做决策，只做审计。`Measure.wealth()` = `mass() + transfer_pool + conversion_residual
   + Σ yearly_inherited`（**观测/审计口径**，不是可花费量）。
7. **穷尽性**（哪条离场路径该记）：容量逐出 / 回填收缩 ⇒ `dematerialize` ⇒ 记；`unbind` ⇒ 记；
   `coarsen` 收编 ⇒ 记（**不得**复用 `dematerialize`，否则同一成员双记）；窗口内**死亡** ⇒ 死亡/继承结算，**不记**；
   `split` / `merge` / `dissolve` ⇒ 只折已有的残差，**不记**。

**精确例子**（`w=1000`，桶中心 `c=(b+0.5)·w`）

- `wealth=1537.2` ⇒ bucket `1`、`c=1500` ⇒ 记 `+37.2`。
- `wealth=999.0` ⇒ bucket `0`、`c=500` ⇒ 记 `+499.0`（"穷但高于桶中心"也是欠账）。
- `wealth=100.0` ⇒ bucket `0`、`c=500` ⇒ 记 `−400.0`（被折高了，世界欠该测度）。
- `coarsen` 两个成员 `1537.2` 与 `100.0`：aggregate 质量 `+2000`、残差 `+37.2−400.0=−362.8`；
  窗口 `−1637.2` ⇒ `2000 − 362.8 = 1637.2` ⇒ W 不变。
- `materialize` / `materialize_sample`：从 bucket `1` 取走 `c=1500`、造出 `wealth=1500` 的角色 ⇒ 残差**不动**，W 不变。
- `extract(amount=2)`：从 bucket 取走 `2×c`、造出两个 `wealth=c` ⇒ 残差**不动**，W 不变。

**验收**:`python -m pytest tests/test_conversion_residual.py -q` → 全绿（三个损失点逐点 + 精确点不记 + 折叠 + 快照 + 旧档）；
`python -m bench.audit_ledger --wealth --n 1500 --steps 2500 --capacity 250` → **逐算子**
`|ΔW| ≤ 1e-6` **且** `|ΔW| / W ≤ 1e-9`（浮点级）。
算子清单**必须穷尽**：`materialize` / `materialize_sample` / `coarsen` / `merge` / `split` / `dissolve` /
`dematerialize` / `refill` / `bind`（含 `extract`）/ `unbind` / channel `run`（transfer + 清算 + 投递）。
每个算子一行期望值（记 / 不记、ΔW=0）。

**危险实现清单**

| # | 最可能被写成的样子 | 为什么错（语义差在哪） | 由谁挡住（不变量 / 验收） |
|---|---|---|---|
| 1 | 漏记一个损失点 / 在精确点多记一次 | 只在**跨折算**的长跑里现形——单点测试守不住 | 验收（逐算子 W 探针 + 穷尽算子清单；`test_conversion_residual.py` 三个损失点逐点 + 精确点不记） |
| 2 | 把残差并进 `transfer_pool` | 混账 ⇒ C→R 能花掉 IOU（造钱） | 不变量（可支付总额 = `mass() + transfer_pool`，不含残差）+ 验收 |
| 3 | `fold_pools` 只折两个池、不折残差 | 静默丢账（`coarsen` / `merge` / `dissolve` / `split` 四处） | 验收（`test_fold_pools_folds_residual_too` + 生命周期折叠用例） |
| 4 | 符号写反（应为 `+` = 欠世界） | 两个方向的误差互相"抵消"成假绿灯 | 验收（`test_record_conversion_sign_and_magnitude`：`+` = 欠世界） |
| 5 | 在 `materialize` / `bind` 记残差 | 它们数值上精确，多记 = 凭空造账 | 验收（`test_materialize_is_exact_and_records_nothing` / `test_bind_is_exact_and_records_nothing`） |

---

## 相关文档

- L1：[`../AGENTS.md`](../AGENTS.md) · L2：[`architecture.md`](architecture.md) · L3：`docs/modules/<name>.md`
- 事实细节（语义 / 速率 / 公式 / 契约）：[`engineering-spec.md`](engineering-spec.md) · [`cluster-contract.md`](cluster-contract.md)
- 术语：[`glossary.md`](glossary.md)
- 基准工具与权威数字：[`../bench/README.md`](../bench/README.md)
- 演进史 / 负结果（Stage 3 碎片化、Stage 7 账本注水、Stage 10 稀疏计数、Stage 14 泄漏、Stage 15 确定性）：[`history.md`](history.md)
- N2 验收方法论：[`../docs-templates/verifying-n2.md`](../docs-templates/verifying-n2.md)
