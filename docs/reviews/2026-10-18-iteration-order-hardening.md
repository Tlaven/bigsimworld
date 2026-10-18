# 2026-10-18 · 遍历序加固（"清算支付顺序依赖遍历序" 严整改）

> 背景：该隐患以"严整改方向"登记过一次（下次触碰 `transitions.py` 时提升为硬规则）。本轮因 integer 语义已触碰该文件，故把规则落地并加红→绿测试。
> 判据：**同一分布、不同构造顺序 ⇒ 演化后逐位一致**（`SIM_SEED` 复现与快照接续的隐性前提）。

## 1. 隐患（实测坐实）

- `distribute_pool` 按遍历序消耗池（`available` 递减：先付的桶拿得多、后付的桶拿得少），而遍历序来自 `measure.occupied`（**set**）。
- 实测探测：`asc` / `desc` 两种落桶顺序构造同一个键集合，**set 迭代序不同**（同槽碰撞键、混合 96 键、随机 200 键三种探测均不同）⇒ 同一分布可以有不同未来。
- 首版测试用"常规键 + 小池"没抓到（迭代序恰好一致、且池小到全落 k=0 分支）——**红测试要连构造都得对准敏感点**。

## 2. 红 → 绿

- 强化测试（`tests/test_measure_transitions.py::test_flows_are_construction_order_invariant`）：同槽碰撞键（wealth 步长 64）+ **大池（1e6）** 强制清算走整数支付分支；先断言 `list(asc.occupied) != list(desc.occupied)`（测试有效性），再跑 `FULL_FLOWS` 720 tick + `settle_transfer_pool`，比较**逐位相等**。
- 修复前：**红**——差异为 ulp 级（如 `0.024266419805584458` vs `…465`；浮点累加序），结构支付在本配置下恰好同 k。
- 修复后：**绿**。

## 3. 修复内容（遍历序纪律）

- `transitions.py`：凡迭代 `occupied` 的循环一律 `sorted(...)`（`aging` / `income` / `death` / `distribute_pool` / `_shift_age_wealth` / `birth` / `marriage` / `integer_death` / `integer_marriage`）；批量 `moves` 按目标索引升序插入；模块文档写死规则。
- `measure.py`：`SparseCounts.sum()` 按索引序求和；`Measure.mass()` 按索引序；`measure_to_payload` 的 `cells` 按索引序（快照 canonical）。
- `window.py`：`materialize_sample` 候选按索引序（采样喂随机数，候选顺序必须 canonical）。
- 规则入档：`engineering-spec.md` §9「遍历序纪律（算子级）」+ `bench/README` 守恒纪律第 6 条。

## 4. 重基线（A/B：stash 旧算子 vs 新算子，同口径）

| 基准 | 旧算子 | 新算子 | 判定 |
| --- | --- | --- | --- |
| `convergence --full-compare --sizes 2000 5000 10000 --steps 4000` | age_l1 0.0347/0.0254/0.0263；gini_diff 0.0068/0.0025/0.0069；KS 0.0351/0.0516/0.0533；married_diff 0.0154/0.0164/0.0201 | **逐行一致** | 本改动对收敛基准是 no-op；门槛（gini<0.02 / KS<0.06 / age_l1<0.06 / married<0.10）全过 |
| `diagnose_tail --n 5000 --steps 8000 --seeds 1 7 42` | KS median **1.90%**（[2.64, 1.25, 1.90]） | KS median **2.23%**（[2.63, 1.25, 2.23]） | seed 42 的尾部随遍历序移动；仍在门槛内，属"顺序敏感的有限分辨率"而非恶化 |
| `audit_ledger --n 5000 --steps 8000` | — | identity error **−1.579e-05（−0.0000%**，相对 ~2e-14） | 守恒不回归 |
| `audit_ledger --clusters --n 3000 --steps 2000 --capacity 300` | — | identity error **0.0000%** | 分辨率层不回归 |

- `bench/README` 的收敛权威行同步为最新复测（KS 中位 2.23%；加固前 1.90%），并注明该值随历史阶段漂移、以最新复测为准。

## 5. 备注

- 本次加固**不改变任何默认**，仅把"碰巧可复现"变成"构造无关地逐位可复现"。
- 未覆盖（登记）：`ClusterStore` 的成员集合遍历（`member_ids` 为 set）里含**浮点累加**的路径（`record_conversion` 逐成员叠加、`fold_pools` 的逐段相加）——同一构造历史下确定，但跨构造顺序未加固；如将来要给"mini 层构造无关"立证，再按同一规则处理（排序 `member_ids` / 按段排序折叠）。

> **跟进（同日）**：上述登记项已按同规则加固——`coarsen`/`merge`/`split`/`dissolve` 的拷贝与逐成员折算按 id/索引升序；`fold_pools` 按段升序；`_scan_flux` 成员按 id 升序（观测值也 canonical）。折叠规范序由 `tests/test_cluster.py::test_fold_pools_canonicalizes_age_order` 守。
