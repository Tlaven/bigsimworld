# bench —— 无头基准与验证层

完全 **不依赖 Web / Redis / DB 写入进程**：用空队列 `SinkQueue` 顶替写入，直接驱动引擎。这一层回答两个问题：**成本为什么这样扩展**（run_scaling/profile_step）、**测度层是否收敛于个体引擎**（fingerprint/convergence/diagnose_tail/audit_ledger）。

阶段性数字、负结果与教训都在 `docs/history.md`（工程日志）。本文件只维护"怎么跑"与"当前权威数字"。

## 工具

| 工具 | 用途 | 示例 |
| --- | --- | --- |
| `bench.world` | 固定种子构造角色/引擎（可复现），`engine="legacy"|"event"` | `from bench.world import build_engine; build_engine(1000, seed=42, engine="event")` |
| `bench.measure` | 逐步计时 + RSS 采样（avg/p50/p95/max） | `from bench.measure import measure_steps` |
| `bench.run_scaling` | 人口规模扫描，输出扩展曲线 CSV | `python -m bench.run_scaling --engine legacy --sizes 1000 5000 10000 --steps 30 --warmup 5` |
| `bench.profile_step` | cProfile 找热点 | `python -m bench.profile_step --n 10000 --steps 30 --top 20` |
| `bench.fingerprint` | 分布指纹（年龄直方图/财富 21 分位/基尼/**度**/婚配）。度由**真实关系**算；测度层**无图** ⇒ `degree_hist = None` | 库函数 |
| `bench.convergence` | 指纹对比 `compare_fingerprint` + 基线导出 / 测度-个体对照 / **窗口-个体图对照** / 窗口 N 无关性 | 见下 |
| `bench.diagnose_tail` | 财富分位偏差归因（KS vs p100 噪声、多种子） | `python -m bench.diagnose_tail --n 5000 --steps 8000 --seeds 1 7 42` |
| `bench.audit_ledger` | 财富守恒审计（初始+收入+出生-蒸发 == 期末+池余） | `python -m bench.audit_ledger --n 5000 --steps 8000` |
| `bench.audit_ledger --clusters` | 窗口+共演单元 的**分辨率守恒**审计（materialize/coarsen/dissolve/refill 逐一守恒） | `python -m bench.audit_ledger --clusters --n 3000 --steps 2000` |
| `bench.audit_ledger --resolution` | 分辨率算子守恒探针（**生产口径**，coarse 流含 death/birth） | `python -m bench.audit_ledger --resolution --n 3000 --steps 2000` |
| `bench.audit_ledger --wealth` | **分辨率折算的财富恒等式**（含池与折算残差，ADR-006）逐算子 W 探针 | `python -m bench.audit_ledger --wealth --n 1500 --steps 2500 --capacity 250` |
| `bench.cluster_inheritance` | 族内池 vs 全局池的继承集中度（"富族恒富"） | `python -m bench.cluster_inheritance --peers 120` |
| `bench.channel_marriage` | **跨分辨率婚配规则 A/B**（`RULES` 关 / 开）：跨婚配次数、已婚比例、逐次守恒；`--scope measure` = 大众婚配（候选 = 全局测度）；`--scope both` = 两条并存（adr-012；crossings 按族/众拆分） | `python -m bench.channel_marriage --ticks 1500` |
| `bench.calibrate_marriage` | **婚配规则校准**：参照（个体引擎）vs measure 关/null/各 rate；null 臂隔离 headroom 与共流混淆；`--scope measure` = 大众靶；`--scope both` = 两条并存（汇总表含族/众拆分） | `python -m bench.calibrate_marriage --population 1200 --ticks 2000 --seeds 1 2 3 4` |
| `bench.audit_transfer` | **质量侧 transfer 的财富恒等**：R→C / C→R / 清算 / 投递 / 生命周期折叠逐次核对 W | `python -m bench.audit_transfer` |
| `bench.cluster_fidelity` | **共演单元保真度 A/B**：coarse vs 保持 resolved（配对试验 + 跨 trial 汇总，误差包络） | `python -m bench.cluster_fidelity --members 8 --ticks 8000 --trials 40` |
| `bench.cluster_fidelity --gate` | **分层门槛**（ADR-004）：跨规模（n≥400）趋势 + `pop` 相对偏差；违反 ⇒ exit 1（CI 慢跑） | `python -m bench.cluster_fidelity --gate` |
| `bench.diagnose_cluster_bias` | 保真度偏差**归因**：相位对照 / 规模扫描 / 消融（消融只作必要条件检查） | `python -m bench.diagnose_cluster_bias --ticks 8000 --trials 20` |
| `bench.resolution_switch` | **换档动力学**（抖动观测者四臂：noop / 缺省驻留 30 / 滞回 / 驻留 60）：有效换档、**被卡物化（blocked）**、驻留、通量遥测样例（描述性） | `python -m bench.resolution_switch --ticks 600` |
| `bench.residual_correlation` | **误差触发研究**（配对世界：观察→粗化 vs 孪生全程 resolved）：`flux_z` / `phase_disp` 与粗化伤害的相关 + **预注册可用性判据**（描述性） | `python -m bench.residual_correlation --trials 12` |

结果写入 `bench/results/`；结果文件是**证据**，提交。

## 常用命令

```bash
# 个体引擎扩展性（legacy | event；--rare-stride 10 可选）
python -m bench.run_scaling --engine legacy --sizes 1000 5000 10000 20000 --steps 30 --warmup 5

# 测度引擎 vs 个体引擎收敛（FULL_FLOWS：衰老/收入/死亡/婚配/生育/继承）
python -m bench.convergence --full-compare --sizes 2000 5000 10000 --steps 4000

# 真个体窗口：N 无关性 + 窗口内真关系
python -m bench.convergence --window --sizes 10000 100000 1000000 --capacity 1000 --steps 3000

# 图保真度：窗口 ↔ 个体（双方都有图；测度层无图，别用它比"度分布"）
python -m bench.convergence --graph-compare --sizes 1000 3000 --steps 1500 --capacity 1000

# 改动继承/账本类算子之前与之后都跑这两条
python -m bench.diagnose_tail --n 5000 --steps 8000 --seeds 1 7 42
python -m bench.audit_ledger --n 5000 --steps 8000

# 改动共演单元/分辨率层之后都跑这条（材料/粗化/回收/回填必须逐一守恒）
python -m bench.audit_ledger --clusters --n 3000 --steps 2000 --capacity 300

# 改动 transfer / 通道池 / 共演单元池折叠之后必跑（财富口径，见 adr-005）
python -m bench.audit_transfer

# 改动任何分辨率算子（materialize/coarsen/merge/split/dissolve/dematerialize/回填）之后必跑（adr-006）
python -m bench.audit_ledger --wealth --n 1500 --steps 2500 --capacity 250

# 共演单元**保真度**：coarse vs 保持 resolved（配对 A/B + 跨 trial 噪声带；约 12s/20 trials）
python -m bench.cluster_fidelity --members 8 --ticks 8000 --trials 40

# 分辨率层**门槛**（分层；ADR-004）：跨规模趋势 + pop 相对偏差，违反 ⇒ exit 1（分钟级，CI 慢跑）
python -m bench.cluster_fidelity --gate

# 保真度偏差**归因**（相位对照 / 规模扫描 / 消融——消融只作必要条件检查）
python -m bench.diagnose_cluster_bias --ticks 8000 --trials 20

# 大众婚配「语义双解」测量（2026-10-18；候选 = 全局测度，生产规则 target="measure"）
python -m bench.calibrate_marriage --scope measure --family-pool 0 --population 1200 --capacity 240 \
    --ticks 2000 --seeds 1 2 3 4 --rates 0.05 0.1 0.25 0.5 1.0
python -m bench.channel_marriage --scope measure --seed-family 0 --ticks 3000 --population 1200 --capacity 240
python -m bench.channel_marriage --scope both --ticks 3000 --population 1200 --capacity 240   # 两条并存（adr-012）

# 换档动力学（描述性；四臂对照：noop / 缺省驻留 30 / 滞回 / 驻留 60）
python -m bench.resolution_switch --ticks 600

# 误差触发研究（指示器 vs 粗化伤害；预注册可用性判据）
python -m bench.residual_correlation --trials 12
```

## 当前权威数字（2026-10-12）

> 基线文件 `bench/results/fingerprints/*.json` 曾于 **2026-10-17 因度指标修复而重新生成**
> （旧文件的 `degree_hist` 是伪单桶 `[pop]`，见 `docs/history.md` Stage 1 编注）；
> 生成命令 = `python -m bench.convergence --individual 1000 10000 100000 --steps 500`。

**个体引擎（legacy）扩展性**：约线性且略超线性，~3.2KB/人（详细表见 `docs/history.md` Phase 1）。

**测度引擎（FULL_FLOWS）N 无关性**（稀疏计数，Stage 10 实测）：

| N | ms/step | occupied | 备注 |
| ---: | ---: | ---: | --- |
| 100,000 | 0.98 | 794 | counts 放大口径 |
| 1,000,000 | 1.75 | 1,379 | 人口 1e6；内存 ∝ 占用桶数，不随 N/bins 增长 |

**收敛水平（vs 完整个体引擎，N=5000, t=8000, seeds 1/7/42）**：gini 差 ~0.01、KS 中位 **2.23%**（2026-10-18 遍历序加固后复测；加固前 1.90%——该值随历史阶段漂移，以最新复测为准）、p70–p95 逐分位 ±1%；p100 相对偏差 **+2.2%** 属**有界采样噪声**（跨种子 ±0.6% 摆动），不作调优目标（归因方案见 `docs/history.md` Stage 7）。

**共演单元保真度（coarse vs 保持 resolved，配对 A/B，`members=8`/40 trials，t=8000）**：

| 指标 | mean(R−C) ± sd | R>C | 判定 |
| --- | ---: | ---: | --- |
| age_l1 | +0.2595 ± 0.0873 | 40/40 | **见下方修订：生产规模下该数字不可读作粗化误差** |
| population | −0.35 ± 2.65 | 15/40 | 噪声级（`members=12` 时系统性：coarse 多 ~2.5 人） |
| wealth_per_capita | +8991 ± 33245 | 24/40 | 噪声级 |
| married_frac | +0.011 ± 0.182 | 23/40 | 噪声级 |
| pool_frac | −0.0066 ± 0.0026 | 0/40 | coarse 侧恒有 ~0.7% 财富滞留继承段池 |

> **修订（Stage 16 修订 + 2026-10-17 渐近扫描，见 `docs/history.md`）**：`age_l1` 在生产簇规模（≤12）上被
> **分箱离散 + 相位错位**主导，**不是**粗化误差。规模扫描（`bench.diagnose_cluster_bias`，20 trials/t=8000）：
> `n=8 → 0.2556`、`25 → 0.1514`、`80 → 0.0899`、`200 → 0.0566`、`400 → 0.0454`、`800 → 0.0412`、**`1600 → 0.0359`**
> （全部 20/20 同号；**仍未平台化**，且 `age_l1 × n` 一路涨 ⇒ 衰减远慢于 1/n）。
> 相位对照：**t=600 时相位解释 100%**（`age_l1` 0.2361 → 0.0000）、**t=8000 时只剩 16%**（0.2556 → 0.2163）
> ——**分解本身依赖时长**。真实系统性偏差 **≲0.05**（与门槛同阶）。
> **`pop(R−C)`：不是"随 n 放大"**——n≈400 见顶（−18.25 ≈ −4.6%）后**回落**（800: −1.0%、1600: −0.66%）；
> 仍系统性（多 trial 同号）但**有界**。
> 解读与"失败的方法"（单臂消融不是归因手段）见 `docs/history.md` Stage 16 修订。
> **门槛（ADR-004，分层）**：`python -m bench.cluster_fidelity --gate` 断言
> `age_l1` 不随 n 升且最大 n ≤ 0.06、`pop` 相对偏差 ≤ 5% 且不随 n 增长。
> **注意**：`members≤12` 时分布型指标（KS/gini/age 直方图）被离散噪声主导，**必须**用
> **跨规模扫描 + 配对试验 + 多时长**判读；单点、单次、单时长读数不作结论。

## 守恒纪律（改动算子前必读）

1. 均值场算子的账本/欠账**禁止挂在桶索引上**（桶会换主人/被合并 → 注水）；
2. 不允许"分数桶位移"（拆分桶计数 → occupied 碎片化，Stage 3 教训：77ms/step）；
3. 财富转移只能"段池 + 整数桶支付 + 余量留池"（Stage 7 设计）；
4. 任何"概率×周期压缩"（稀有事件降频）必须概率同倍放大，`rare_stride=1` 保持逐位一致；
5. 改动后必跑：`pytest`（守恒/等价测试）+ `bench.convergence --full-compare` + `bench.audit_ledger`。
6. **遍历序纪律**：凡迭代 `occupied` 的算子一律 `sorted(...)`（按桶索引升序），批量移动按目标索引插入——结算按序消耗池、浮点累加序影响末位；同一分布换构造顺序必须**逐位一致**（`tests/test_measure_transitions.py`）。
