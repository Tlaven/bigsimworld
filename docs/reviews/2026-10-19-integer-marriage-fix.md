# 2026-10-19 · 修复：`integer_marriage` 发放选人（最年轻优先 → 确定性加权均匀）

> 承接 [`2026-10-19-cluster-gate-triage.md`](2026-10-19-cluster-gate-triage.md)（红根 = `d739304`；消融 → `integer_marriage`）。
> 拍板 = **A 修因**；ADR-010 的跟进条款（"系统性恶化 ⇒ 回滚或收窄"）⇒ 本修复 = **收窄**（四条性质全保留，改选人分布）。

## 1. 机制（假说 → 实证）

假说：旧选人 `sorted(whole, key=(-count, index))` 的平局规则被 `space.encode` 的布局放大——**索引升序 = 年龄升序**（age 为最高位）⇒ coarsened family（count==1 桶为主）里 = **最年轻单身优先** ⇒ 婚配人群年龄结构偏移 ⇒ 生育闭合放大 ⇒ 人口超产。

三臂实证（members=400, trial seed=1；"≤30 岁份额" = 已婚 18–50 中 ≤30 岁占比）：

| t | resolved（真值） | coarse fluid（pre-fix） | coarse int_marr（台阶） |
|---|---:|---:|---:|
| 500 | 0.389 | 0.323 | **0.500** |
| 1500 | 0.260 | 0.240 | **0.424** |
| 2000 | 0.213 | 0.210 | **0.320** |
| 2500 | 0.188 | 0.195 | **0.267** |

已婚 18–50 总量（t=4000）：int_marr **264** vs fluid 211.5 vs resolved 228（高 ~25%）。⇒ 假说成立。

## 2. 修复（只碰 `integer_marriage`）

- 选人 = **确定性加权均匀抽样**：`位置 = _mix32(tick, 2·pair / 2·pair+1) % 整人数总权重（Σ int(count)）`，沿**索引升序**按整人数累计定位（整数算术）；期望 ≡ 对整人单身总体均匀抽人（= 流体版"按桶占比摊派"的等价过程）。
- 同桶双取仅当 `count ≥ 2.0`（与旧规则一致；防止从分数余量桶取走两整人而销毁质量——实现中曾自查出一版缺陷并修正）。
- 信用累积公式、整人发放、无 rng（`_mix32` 纯整数、与 `random` 零接触）、只碰 mini——**四条性质全保留**。
- **2026-10-19 复核收窄（teach-back 触发）**：权重从 `count` 实数改为桶内**整人数** `int(count)`（整数算术）——浮点权重 + `int(Σ)` 位置网格会让分数桶系统性偏向索引靠前的桶（三个 `count=1.2` 桶时第三桶恒不被抽中），与"均匀"矛盾；改后门禁/消融数字**逐位不变**（该场景候选多为整人桶）。新测试 `test_integer_marriage_fractional_weights_are_uniform` 钉住该性质。
- `integer_death` **未动**（消融证明与台阶无关；其平局排序同样是索引升序 = 年龄升序 ⇒ **较年轻 60+ 优先移除**——与婚配旧规则同构，但不触生育通道，登记为观察项）。
- 边界（新测试守）：发放计数中性；同桶双取；不消耗 rng；均匀池上年龄覆盖均匀（max/mean < 2；旧规则 ≈ 40× 集中）。

## 3. 验收（全部实测）

| 项 | 改前 | 改后 | 判据 |
|---|---|---|---|
| 消融夹具（n=400, t=4000, 20 trials） | 5.10% | **1.23%** | ≤ 2.5% ✓（`int_marr` 变体 4.95% → **1.09%**；参照 fluid 1.62%——**低于 pre-fix 水平**） |
| `--gate --ticks 4000`（快速预检口径） | FAIL | **PASS**（pop 1.23/1.57/0.06%；age 0.0416/0.0379/0.0418） | PASS ✓；`--seed0 101` 复现 PASS（0.84/0.57/0.40%） |
| `--gate`（缺省口径 t=8000，口径确权后） | FAIL（13.08/7.55/4.79%） | **PASS**（3.52/1.56/1.03%；age 0.0615/0.0528/0.0518） | PASS ✓ |
| `resolution_switch --ticks 600` | blocked 0 | **blocked 0**（四臂：noop/default/hysteresis/dwell60） | ADR-010 正产保留 ✓ |
| 全局回归护栏 | — | `convergence --full-compare` **逐行 diff 空**；`audit_ledger` 与 A+B 值**逐字相同**（-1.587e-05）。（2026-10-19 复核轮后：N2-3 合并超付修正使全局审计值变为 **-1.399e-05**、convergence 一处显示值 0.0350→0.0351——总账不变，见 [`2026-10-19-delta-teachback.md`](2026-10-19-delta-teachback.md)） | 全局路径零接触 ✓ |
| 单测 | — | **247 passed**（+3 新）；ruff ✓ | 全绿 ✓ |

## 4. 重基线与登记

- cluster 侧读数（cluster_fidelity / resolution_switch 等）已按新规则重基线；全局侧逐位不变。
- `t=8000` 口径 age_l1@400 = 0.0615（> 0.06）——门禁规则只在最大 n 处卡 0.06（0.0518 ✓），**不构成违规**；记录备查。
- **口径确权（同日完成）**：`--gate` 缺省改为 **t=8000**（与 ADR-004 文字对齐；实现原缺省 4000），非 gate 模式仍 4000，CI job 超时 25→45 min；`--ticks 4000` 保留为快速预检。详见 triage §4。
- 残余系统性偏差 ~1.0–1.2%（低于 pre-fix 的 ~1.6%）属 ADR-004「需要跟进的：pop 系统性多产的机制未定」范围。

## 5. 复跑

```bash
python -m pytest -q
python -m bench.cluster_fidelity --gate                  # PASS（缺省口径 t=8000）
python -m bench.cluster_fidelity --gate --ticks 4000     # PASS（快速预检口径）
python -m bench.resolution_switch --ticks 600            # blocked 0
python -m bench.convergence --full-compare --sizes 2000 5000 10000 --steps 4000   # 全局不变
```
