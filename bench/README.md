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
| `bench.fingerprint` | 分布指纹（年龄直方图/财富 21 分位/基尼/度/婚配） | 库函数 |
| `bench.convergence` | 指纹对比 `compare_fingerprint` + 基线导出 / 测度-个体对照 / 窗口 N 无关性 | 见下 |
| `bench.diagnose_tail` | 财富分位偏差归因（KS vs p100 噪声、多种子） | `python -m bench.diagnose_tail --n 5000 --steps 8000 --seeds 1 7 42` |
| `bench.audit_ledger` | 财富守恒审计（初始+收入+出生-蒸发 == 期末+池余） | `python -m bench.audit_ledger --n 5000 --steps 8000` |
| `bench.audit_ledger --clusters` | 窗口+共演单元 的**分辨率守恒**审计（materialize/coarsen/dissolve/refill 逐一守恒） | `python -m bench.audit_ledger --clusters --n 3000 --steps 2000` |
| `bench.cluster_inheritance` | 族内池 vs 全局池的继承集中度（"富族恒富"） | `python -m bench.cluster_inheritance --peers 120` |

结果写入 `bench/results/`；结果文件是**证据**，提交。

## 常用命令

```bash
# 个体引擎扩展性（legacy | event；--rare-stride 10 可选）
python -m bench.run_scaling --engine legacy --sizes 1000 5000 10000 20000 --steps 30 --warmup 5

# 测度引擎 vs 个体引擎收敛（FULL_FLOWS：衰老/收入/死亡/婚配/生育/继承）
python -m bench.convergence --full-compare --sizes 2000 5000 10000 --steps 4000

# 真个体窗口：N 无关性 + 窗口内真关系
python -m bench.convergence --window --sizes 10000 100000 1000000 --capacity 1000 --steps 3000

# 改动继承/账本类算子之前与之后都跑这两条
python -m bench.diagnose_tail --n 5000 --steps 8000 --seeds 1 7 42
python -m bench.audit_ledger --n 5000 --steps 8000

# 改动共演单元/分辨率层之后都跑这条（材料/粗化/回收/回填必须逐一守恒）
python -m bench.audit_ledger --clusters --n 3000 --steps 2000 --capacity 300
```

## 当前权威数字（2026-10-12）

**个体引擎（legacy）扩展性**：约线性且略超线性，~3.2KB/人（详细表见 `docs/history.md` Phase 1）。

**测度引擎（FULL_FLOWS）N 无关性**（稀疏计数，Stage 10 实测）：

| N | ms/step | occupied | 备注 |
| ---: | ---: | ---: | --- |
| 100,000 | 0.98 | 794 | counts 放大口径 |
| 1,000,000 | 1.75 | 1,379 | 人口 1e6；内存 ∝ 占用桶数，不随 N/bins 增长 |

**收敛水平（vs 完整个体引擎，N=5000, t=8000, 多种子）**：gini 差 ~0.01、KS 中位 2.73%、p70–p95 逐分位 ±1%；p100 相对偏差 +1.9% 属**有界采样噪声**（跨种子 ±0.6% 摆动），不作调优目标（归因方案见 `docs/history.md` Stage 7）。

## 守恒纪律（改动算子前必读）

1. 均值场算子的账本/欠账**禁止挂在桶索引上**（桶会换主人/被合并 → 注水）；
2. 不允许"分数桶位移"（拆分桶计数 → occupied 碎片化，Stage 3 教训：77ms/step）；
3. 财富转移只能"段池 + 整数桶支付 + 余量留池"（Stage 7 设计）；
4. 任何"概率×周期压缩"（稀有事件降频）必须概率同倍放大，`rare_stride=1` 保持逐位一致；
5. 改动后必跑：`pytest`（守恒/等价测试）+ `bench.convergence --full-compare` + `bench.audit_ledger`。
