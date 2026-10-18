# 2026-10-18 · 大众婚配正式化（采纳 + 规格 + 实现 + 验收）

> 上一轮：[`2026-10-18-mass-marriage-measurement.md`](2026-10-18-mass-marriage-measurement.md)（测量台账）。
> 决策：[`adr-009-mass-marriage.md`](../decisions/adr-009-mass-marriage.md)（accepted：扩展类规则、默认关、单值互斥开关）。

## 1. 规格增量（N2-7）

- 「候选侧（`target`）」段：两值 `cluster`（缺省）/ `measure`；mass 模式 = 房源检查（无房源 ⇒ `offers → []`，不产噪声、不耗随机流）→ 逐单身掷 `rate` → 直接产 `scope=("measure",)`（与簇侧同形、只换目标）；配额/宽限按 N2-8；**单值互斥**；非法 `target` ⇒ 构造时 `ValueError`；未识别开关取值 ⇒ **不注册**。
- 危险实现清单 +2 行（第 9：`cluster`+`measure` 并发 / 双规则 ⇒ 同一人双婚；第 10：mass 跳过房源检查 ⇒ `no_match` 噪声）；验收 +3 具名测试 + 复跑命令。
- 同步：`engineering-spec`（env 表 / §9 交互规则 / 已知边界）、`glossary`（跨分辨率婚配改述 + 新词条「大众婚配」）、L1「边界外」的开关口径。
- bench 探针 `bench/probe_rules.py` 提升进 `rules.py` 后**删除**（测量轮的原始形态保存在提交 `fa78301`）。

## 2. teach-back（1 轮，判定=通过）

4 条非阻断，**全部采纳**：① 文首开关口径改 `=1|mass`；② 补 mass 意图的逐字形状（`kind`/`match` 同簇侧、房源检查用同一谓词）；③ 未识别开关取值写死为"不注册" + 清单第 9 行补"单一注册键 + 幂等"层；④（低优先）基准数字存放处——**未采纳**（台账在对账记录里，验收命令可复跑）。

验证者关键核对（全部成立）：第 9/10 行遮挡关系逐条可挡（单值互斥 + `ValueError` + `RULES["cross_marriage"]` 单一注册键；房源检查 + 具名测试）；mass 模式"每个合格单身每次只消耗 1 个随机数"可从规格唯一推出。

## 3. 实现

- `app/core/measure/rules.py`：`MarriageRule(rate, rng, target="cluster")` + `TARGETS` 校验；`_offers_measure`（房源检查 + 逐单身单次掷骰）；`register_marriage_rule(..., target=...)`。
- `app/core/simulation/runner.py`：`SIM_CHANNEL_MARRIAGE` 单值互斥（`1/true/on/yes` = 簇；`mass` = 大众；其余不注册）。
- 测试 +3（`tests/test_rule_marriage.py` 12 passed）：`test_mass_target_emits_measure_scope`（同形意图 + R→M 人头守恒）、`test_mass_target_no_eligible_mass_is_silent`、`test_invalid_target_raises`。

## 4. 验收（复跑与测量台账对齐）

| 项 | 结果 |
|---|---|
| `calibrate --scope measure`（同配置同 seed） | **逐位一致**：off 0.5503 / null 0.5603 / 0.05× 0.5582 / 0.10× 0.5632 / 0.25× 0.5778 / 0.50× 0.5914 / 1.00× 0.6245；crossings **2.5 / 5.5 / 12.5 / 24.5 / 51.2** |
| `calibrate --scope cluster`（回归） | 与 Stage 20 一致（0.5503 / 0.5603 / crossings 0）——簇侧行为未变 |
| `channel_marriage --scope measure` | crossings 63、`worst |Δpop| = 0`、`worst |ΔW| = 1.49e-8`、identity 1.49e-08——与台账一致 |
| `pytest` / `ruff` / 文档检查器 | 全绿 |

（生产默认关 ⇒ 全部权威数字不受影响。）

## 5. 边界 / 备注

- `bench/channel_marriage` 的 on 臂仍用共享窗口随机流（Stage 20 之前的既有口径；该工具用于机制 A/B + 守恒断言，不用于语义读数）——本轮未动，记已知口径。
- `target="both"` 未做（ADR-009 方案 C：需要"一人一意图"守卫，属另一设计）。
- 测量轮与正式化分两个提交：`fa78301`（测量）+ 本提交（正式化）。
