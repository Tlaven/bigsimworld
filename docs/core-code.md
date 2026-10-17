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
| 全尺寸 `np.zeros(space.size)` 计数 | 内存 ∝ 桶数而非占用桶数；一提财富上限就得翻内存 | 默认 2.18e6 桶 ≈ 17MB；Stage 10 改稀疏后**反而更快**（1e6 人口 2.47 → 1.75 ms/step） |
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

1. 状态空间 = 4 维分桶 `(age 0..120, gender 0/1, wealth_bucket, marital 0/1)`，混合基数编码（`space.encode` / `decode`）。第 3 维传的是**桶索引**，不是财富值。
2. 财富**线性分桶**，宽度 `w` = 收入步长：桶中心 = `(b+0.5)·w` ⇒ `+w` 恰为 `b+1`（精确整桶位移，无小数漂移）。**改 `w` 即改模型语义**（收入不再是一次整桶位移）。
3. 计数容器是**稀疏**的：读未写入的桶返回 `0.0` 且**不写入**；写 ≤0 时置 0 并移出 `occupied`（**夹零**——负计数不可表示）。
4. 一切遍历只走 `occupied`；成本 = O(占用桶数)，与人口 N、与 `space.size` **都**无关。
5. 序列化只存非零桶（`measure_to_payload`），往返误差 <1e-6/桶。

**精确例子**

- `wealth_bucket(10500.0)` = 10；`wealth_value(10)` = 10500.0 ⇒ `income` 把 b=10 整桶移到 b=11（+1000 精确，无残差）。
- `space.encode(30, 0, 10, 0)` = `10_800_030`，`decode` 回到 `(30, 0, 10, 0)`（可直接当 fixture）。

**验收**:`python -m pytest tests/test_measure_space.py tests/test_measure_core.py -q` → 全绿（编码双射 / 桶单调 / 稀疏容器语义）；
`python -m bench.convergence --window --sizes 10000 100000 1000000 --capacity 1000 --steps 3000` → `ms/step` 与窗口规模**不随 N 变化**（只放大每桶计数，占用桶数不变）。

**陷阱**：别按 `space.size` 分配（Stage 10 前的形态）；别用对数分桶（小额加法无法整桶位移）；别让"读空桶"有副作用（污染 `occupied` ⇒ 成本失控）。

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

**陷阱**：婚配的可用性闭合是 Stage 2 的发现（两种"直觉"写法都被否，见上表）；`recent_deaths` 跨 tick 复用 ⇒ 重复入账；"边遍历边写" ⇒ 重复计数。

### N2-3 · 继承的段池整数分配（守恒可审计优先）

**步骤级说明**（三段：注入 → 清算 → 触顶）

1. **注入**（每 tick，`inject_inherited`）：每条死亡记录把 `amount × 桶中心值 × 10%` 按 **gap 窗口** `u ∈ [a−50, a−18]`（`a` = 死者年龄）**均匀**摊入 `yearly_inherited[u]`（子女段池）；随后清空 `recent_deaths`（防重复入账）。`overflow_fraction` 可把该份额改注入**全局池**（族内继承的溢出缝）。
2. **清算**（每 360 tick，`distribute_pool`）：对每个非空段池，按接收桶的**财富质量占比**（`count × 桶中心值`）算理想份额；每桶只支付 `floor(理想 / (count × w))` 个**整数桶位移**（整桶平移，**不拆桶内计数**），余量**留池**下年再分；接收段无人 ⇒ 整段留池。
3. **触顶（上限）**：位移若越过 `wealth_bins` 上限 ⇒ 该桶**不支付**，份额**留池**（不越界、不注水）。
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

**陷阱**

- **禁止** per-bucket 欠账（Stage 7：+1.39e8 注水）；**禁止**分数桶位移（Stage 3：碎片化）。
- **支付顺序**：本算子遍历 `measure.occupied`（set），而 `ideal` 随已支付额缩小 ⇒ **谁收到钱依赖遍历序**（已实测：总量同为 1000 时，收款桶随顺序在 X / Y 之间改变）。int 哈希使同一操作序列下可复现，但对代码改动**脆弱**——要严格化就照通道 `extract` 的做法**显式按桶索引升序**。
- 别把 `recent_deaths` 当"可跨 tick 的账本"——它是每 tick 覆盖的临时记录。
- **审计的账法必须与算子同相位**：收入/出生按**流前后财富差分**计量。用"`step` 之前快照 × 1000"的解析式计量会引入相位误差（`income` 跑在同 tick 的 `aging` **之后**）——历史上它被误读成"模型守恒误差 0.06%"（见 [`history.md`](history.md) Stage 7「口径校正」编注）。
- **审计的盲区**：触顶分支在真实世界不可达（占用桶最高 ~551/60000）⇒ `bench.audit_ledger` 的恒等误差照样好看。**"不可达分支"上的守恒只能靠强制构造的测试守**（见验收），别指望长跑审计。

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

**陷阱**：从分数桶取整人 ⇒ `Measure.add` 夹零 ⇒ 只扣分数却生出一整个人（**质量泄漏**，Stage 14 的 bug）；`--clusters`（质量保持子集）**结构上盖不住**分数桶 / 残留泄漏 ⇒ **两个门禁都要跑**；身份不守恒（`coarsen → materialize` 是**重采样新代表**）——别把身份当守恒量。

---

## 相关文档

- L1：[`../AGENTS.md`](../AGENTS.md) · L2：[`architecture.md`](architecture.md) · L3：`docs/modules/<name>.md`
- 事实细节（语义 / 速率 / 公式 / 契约）：[`engineering-spec.md`](engineering-spec.md) · [`cluster-contract.md`](cluster-contract.md)
- 术语：[`glossary.md`](glossary.md)
- 基准工具与权威数字：[`../bench/README.md`](../bench/README.md)
- 演进史 / 负结果（Stage 3 碎片化、Stage 7 账本注水、Stage 10 稀疏计数、Stage 14 泄漏、Stage 15 确定性）：[`history.md`](history.md)
- N2 验收方法论：[`../docs-templates/verifying-n2.md`](../docs-templates/verifying-n2.md)
