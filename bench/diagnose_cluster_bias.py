"""归因实验：coarse 臂的 `age_l1` 偏高（`docs/history.md` Stage 16，≈0.23–0.26）到底来自哪儿？

## 先记一条**失败的方法**（免得后人重踩）

第一版做的是**单臂消融**（只改 coarse 臂的流集合）与**婚姻率扫描**。实测**全部无效**：

| 配置 | age_l1 | 判定 |
| --- | ---: | --- |
| baseline | 0.2556 | — |
| no_marriage（≡ no_birth） | **0.3681** | 更差 |
| marry_x0.5 / x0.2 / x0.1 | 0.2625 / 0.2581 / **0.3567** | **不单调** |

- **单臂消融在这里不是归因手段**：resolved 臂照旧结婚生育，掐掉 coarse 臂的某条流只是**强行制造**
  一个新差异，而不是"移除"既有偏差。⇒ 消融**只能当必要条件检查**，不能当因果归因。
- **婚姻率不单调** ⇒ "均值场婚配太快"这个假设**被证伪**：降率不降偏差。

## 现在跑的两个决定性实验

- **T1 · 相位**：把两臂的个人相位对齐（`aligned_phase`）——resolved 的"变老"与 coarse 的
  `aging`（`tick % 360 == 0`）同相。若偏差塌回 ⇒ 偏差来自**相位错位 + 分箱离散**，不是分辨率。
- **T2 · 规模**：`members` 从 8 扫到 200。若 `age_l1` 随 n 衰减（≈1/n）⇒ **离散噪声**主导
  （n 人的 5 年分箱直方图上，换 3 个箱就够 0.25）；若在某个正值上**平台化** ⇒ 才是**结构**偏差。

用法：
    python -m bench.diagnose_cluster_bias --ticks 8000 --trials 20
"""

import argparse
import statistics

from bench.cluster_fidelity import run_trial

# 消融用的流集合（仅作**必要条件检查**，见上文"失败的方法"）。
# 单一出处：与生产 coarse 臂（FamilyKind）同源（adr-010 起为整数语义发放流）。
from app.core.measure.cluster import KINDS

COARSE_FLOWS = tuple(KINDS["family"].flows)


def flows_without(*names):
    return tuple(flow for flow in COARSE_FLOWS if flow.__name__ not in names)


PHASE_CONFIGS = [
    ("baseline（相位错位）", dict()),
    ("aligned_phase（同相）", dict(aligned_phase=True)),
]

ABLATION_CONFIGS = [
    ("baseline",                  dict()),
    ("no_marriage（≡无出生）",    dict(coarse_flows=flows_without("integer_marriage"))),
    ("no_death",                  dict(coarse_flows=flows_without("integer_death"))),
    ("marry_x0.5",                dict(marriage_scale=0.5)),
    ("marry_x0.2",                dict(marriage_scale=0.2)),
]


def _stats(rows, metric):
    values = [row["diff"][metric] for row in rows]
    return {"mean": statistics.mean(values),
            "sd": statistics.pstdev(values) if len(values) > 1 else 0.0,
            "r_gt_c": sum(1 for v in values if v > 0),
            "n": len(values)}


def run_config(kwargs, members, ticks, trials, seed0):
    rows = [run_trial(seed0 + i, members, [ticks], **kwargs)[ticks] for i in range(trials)]
    return {metric: _stats(rows, metric)
            for metric in ("age_l1", "population", "married_frac")}


def print_rows(label, configs, members, ticks, trials, seed0):
    print(f"{label}（members={members}, t={ticks}, trials={trials}）")
    header = f"  {'config':<24}{'age_l1 mean±sd':>22}{'R>C':>7}{'pop(R−C)':>10}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for name, kwargs in configs:
        stat = run_config(kwargs, members, ticks, trials, seed0)
        age = stat["age_l1"]
        print(f"  {name:<24}{age['mean']:>15.4f} ± {age['sd']:<5.4f}"
              f"{age['r_gt_c']:>4}/{age['n']:<2}{stat['population']['mean']:>10.2f}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Attribution for the coarse-arm age_l1 gap")
    parser.add_argument("--ticks", type=int, default=8000)
    parser.add_argument("--trials", type=int, default=20)
    parser.add_argument("--seed0", type=int, default=1)
    parser.add_argument("--members", type=int, default=8)
    parser.add_argument("--sections", nargs="+", default=["t1", "abl", "sweep"],
                        choices=["t1", "abl", "sweep"])
    parser.add_argument("--sweep", type=int, nargs="+", default=[8, 25, 80, 200],
                        help="T2 规模扫描的 members 取值")
    parser.add_argument("--sweep-trials", type=int, default=12)
    args = parser.parse_args()

    print("coarse 臂 age_l1 归因（**resolved 臂不动**；单臂消融只作必要条件检查）\n")
    if "t1" in args.sections:
        print_rows("T1 · 相位对照", PHASE_CONFIGS, args.members, args.ticks, args.trials, args.seed0)
    if "abl" in args.sections:
        print_rows("必要条件检查（消融 / 速率；**不作因果归因**）",
                   ABLATION_CONFIGS, args.members, args.ticks, args.trials, args.seed0)
    if "sweep" not in args.sections:
        return

    print("T2 · 规模扫描（如果 age_l1 随 n 衰减 ⇒ 离散噪声；平台化 ⇒ 结构偏差）")
    header = f"  {'members':>8}{'age_l1 mean±sd':>22}{'R>C':>7}{'pop(R−C)':>10}{'age_l1 × n':>12}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for members in args.sweep:
        stat = run_config(dict(), members, args.ticks, args.sweep_trials, args.seed0)
        age = stat["age_l1"]
        print(f"  {members:>8}{age['mean']:>15.4f} ± {age['sd']:<5.4f}"
              f"{age['r_gt_c']:>4}/{age['n']:<2}{stat['population']['mean']:>10.2f}"
              f"{age['mean'] * members:>12.1f}")


if __name__ == "__main__":
    main()
