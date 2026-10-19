# 2026-10-18 · 核心算子打磨轮：零条目内存增长（A）+ 继承注入热点（B）

> 定位：**测度层（核心创新）的算子级打磨**——语义不变，修两处已定位的工程缺陷。A 逐位安全；B 浮点累加序变化 ⇒ 重基线（display 精度下无可见变化，机器精度下已记录差异）。
> 发现 → 修复 → before/after 证据 → 长跑验收，全链在本文。

## 0. 发现的来源（ad-hoc 探查）

100 年长跑（base 20000/tick 36000）+ 逐流单价 + cProfile + 对照实验：

| 现象 | 数据 | 结论 |
|---|---|---|
| 均摊耗时上漂 | 2.84 → 4.83 ms/tick（同期 occupied 反降 1653→1513） | 工作负载自身在变重 |
| 排除 GC | `gc.disable()` 后同漂移；RSS 仅 +3MB | 不是 GC |
| 排除降频 | 同进程恒定 CPU 基准 before 147ms → after 149ms | 不是温控/节流 |
| 热点定位 | 40 年态 `death+inject` = 3.39ms（其中 inject ~2.6），marriage 0.6 / birth 0.4 | **inject 是唯一增长项** |
| 增长机制 | 死亡记录数 = 老年占用桶数：**253 → 1,148**（40 年）；每条记录展开 ~33 槽 × 2 次字典操作 | 记录数×33 的隐式放大 |
| 底表残壳 | `counts` 底层 dict 条目 **2,000 → 64,931**（40 年，≈1.6k/年，与 N 无关） | **A：零条目不删除** |

## 1. A · 零条目删除（逐位安全）

- **改动**：`Measure.add` 零分支 / `aging` / `income` 的归零从"写 `0.0`"改为**删除条目**（`del counts[index]`；`SparseCounts.__delitem__` 既有）。
- **逐位安全的理由**：数值消费者全走 `occupied`；`SparseCounts.sum()` 按 sorted 键累加，去掉零项不改变非零项顺序（正计数求和不可能触 `-0.0` 边界）。
- **证据（实测）**：改动前后——
  - `bench.convergence --full-compare --sizes 2000 5000 10000 --steps 4000`：**逐行 diff 为空**；
  - `bench.audit_ledger --n 5000 --steps 8000`：**逐行 diff 为空**（含 `identity error = -1.579e-05` 末位）。
- **新测试**：`test_zero_buckets_are_deleted_not_left_as_residue`、`test_counts_backing_store_matches_occupied_in_long_run`（1000 tick 后 `set(_data) == occupied`）。

## 2. B · `inject_inherited` 差分数组（重基线）

- **改动**：gap 窗口的逐槽累加（每记录 ~33 槽 × 2 次字典操作）→ **差分数组**（每记录 2 次写 + 一趟前缀和，O(记录 + 年龄跨度)）。clamp 公式（`low = max(0, a−50)`、`high = max(0, a−18)`）与逐记录数学**逐字保留**。
- **安全性质**：贡献非负 ⇒ 前缀和不抵消 ⇒ **池键集与原实现一致**；记录序 = `death` 从 `sorted(occupied)` 生成 ⇒ 确定性保持；唯一差异 = 浮点累加序（末位）。
- **重基线证据（机器精度）**：标准审账 `identity error`：**-1.579e-05 → -1.587e-05**（显示同为 -0.0000%）；其余全部展示精度读数不变（见 §3）。
- **新测试**：`test_inject_matches_reference_loop`（vs 测试内参考实现，rel ≤ 1e-12 + key 集相等）、`test_inject_overflow_split_and_determinism`、`test_inject_window_stays_in_age_bounds`；既有 overflow 两向（`test_cluster.py`）与遍历序不变性测试保持全绿。

## 3. 验收（全部实测）

| 项 | 结果 |
|---|---|
| `pytest -q` | **244 passed**（239 + 5 新） |
| `convergence --full-compare`（2000/5000/10000 × 4000） | 门槛全过；**显示精度与基线逐字相同**（exp 值 0.0347/0.0254/0.0263 等） |
| 四连审账（`--n 5000 --steps 8000` / `--clusters` / `--resolution` / `--wealth`） | 恒等误差 **0.0000%**（分别 -1.587e-05[显示 -0.0000%] / +0.000e+00 / 0 / 0） |
| **长跑审账**（`--wealth --n 3000 --steps 14400` = 40 年） | **83,622 个算子全中性**，identity 0；worst = `materialize_sample` ΔW=+8.9e-07（tol 0.32） |
| **长跑轨迹**（`bench.longrun`，base 20000，**36000 tick = 100 年**） | **底表 ≡ occupied 全程**；ms/tick **1.96–2.17 平线**（改前 2.84→4.83 上漂）——漂移消除，晚期 **~2.3×** |
| **cluster_fidelity 门禁**（`--gate`，仍是红的——但**门禁在本轮前已红**，三态实验见 §4） | 本轮前 `cbf343a` ≡ A-only `36c88a1`（数字**逐字相同**）⇒ A 在该口径也逐位不变；A+B 数字见 §4 |

**门槛对照（计划预注册）**：① 底表不随年份增长 ≡ occupied ✓；② 晚期 ≤ 3.0ms/tick ✓（实测 2.12）；③ 审账 0.0000% 不退 ✓。

## 4. `cluster_fidelity --gate`：**本轮前已红**（三态实验）

复跑踩线后按计划"停下评估"，用三态对照定位归因（同一台机器、同一天）：

| 状态 | age_l1（400/800/1600） | pop(R−C) 相对（400/800/1600） | 判定 |
|---|---|---|---|
| 本轮前 `cbf343a`（worktree） | 0.0412 / 0.0381 / 0.0433 | 5.10% / 3.23% / 0.91% | **FAIL**（age_l1 800→1600 上升；pop 400 > 5%） |
| A-only `36c88a1` | **与上逐字相同** | **与上逐字相同** | FAIL（同）——**A 在该口径也逐位不变**（再证） |
| A+B（当前） | 0.0668 / 0.0514 / 0.0501 | 13.08% / 7.55% / 4.79% | FAIL（pop 400/800 > 5%；但两条趋势均向下） |

**结论**：
1. **门禁不是本轮推红的**——`cbf343a` 已 FAIL（另一组失败项）。这是**遗留问题**，需要一次专门 triage（哪轮改动/哪个口径把它推红，或门槛本身在生产簇规模下的可判读性问题——注意 `bench/README` 的既有修订："真实系统性偏差 ≲0.05，与门槛同阶"）。
2. **A** 在该口径与基线**逐字相同**（三处独立证据：收敛 / 审账 / 簇保真全部 diff 为空）。
3. **B 的末位级浮点变化，在本口径被混沌放大**：簇/窗口路径（物化抽样权重 → 簇形成 → 注意力）对小扰动敏感 ⇒ 轨迹级指标整体移动。**守恒与单测全绿、收敛显示值不变**，但"B = display 级无感"的说法**只对 measure 口径成立**；簇口径必须承认轨迹发散（这本身就是一条值得记录的系统性质）。

**跟进建议（登记）**：① 一次 `cluster_fidelity` 门禁 triage 轮（在本轮提交后做基线即可二分）；② 若确认为混沌敏感性，考虑把门禁的 trial 数/时长提高或把"单次轨迹数值"类判据改成"配对分布的置信区间"类判据（属门槛口径决策，需 ADR 级讨论）。

## 5. 边界与登记（不在本轮范围）

- **长跑审账的 36000-tick 版本不现实**：`run_wealth_probe` 每个算子**前后各做一次全量 `total()`**（measure + 全部簇 mini + 窗口），且每 40 tick 强制全体换档 ⇒ op 数被放大；实测 36000 tick 跑 >35 分钟未完成，改用 14400（40 年）。**未来可优化**：探针按受影响结构做增量核对（而非两次全量扫描）。
- **人口 100 年 2 万 → 5 万**（≈+2.3%/年，出生 > 死亡）：模型层观察（B 的成本增长上游），是否校准预期另议。
- **继承池年末余量随年份累积**（4.6M → 30.5M，主要为整数支付的 floor 余量；相对总财富 ~0.1% 以内）——语义本就"余量留池下年再分"，长跑确认无泄漏（恒等式含池）；是否要更强支付纪律另议。
- **未动**：通道 / 窗口 / 簇路径（FamilyKind.flows 无 inheritance）；`cluster_fidelity --gate` 复跑见本轮提交附注。

## 5. 复跑

```bash
python -m pytest -q
python -m bench.convergence --full-compare --sizes 2000 5000 10000 --steps 4000
python -m bench.audit_ledger --n 5000 --steps 8000        # + --clusters / --resolution / --wealth
python -m bench.audit_ledger --wealth --n 3000 --steps 14400 --capacity 300   # 长跑审账（~3 min）
python -m bench.longrun --population 20000 --ticks 36000  # 长跑轨迹（~2 min）
```
