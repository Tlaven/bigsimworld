"""生产样态注意力轨迹观测（测量轮；**不改行为**）。

跑与 runner 同构的 measure 运行（窗口 + 分辨率），逐 tick 采样每个共演单元的注意力与分辨率，
回答"滞回（`theta_down`）该不该默认开"的前置问题。

**观察模式**（`--observer`）：

- `production`：与 runner 同构——内生凝视（`endogenous_scale = max(6, capacity/25)`）+ 显要
  （`notable_fraction = 0.01`）；
- `none`：只有衰减（无外部观察、无内生凝视、无显要）——对照。

**读数**（每个 seed / 模式）：

- 注意力分布（p10/p50/p90）与**分带占用**（<0.40 / [0.40,0.45) / [0.45,0.50) / [0.50,0.55) / ≥0.55）；
- **θ 穿越**：相邻采样跨过 0.5 的次数（每簇累计）；
- **降档归因（关键拆分）**：总降档数，以及降档时注意力的三个区间——
  `≥0.5`（策略不会因注意力降档 ⇒ **预算/名额挤压**）、
  `[k,0.5)`（**滞回相关**：θ_down=k 会否决这些降档）、`<k`（注意力已明确跌落）；
- 并发簇数（末值/峰值）、切换/驻留（`ResolutionManager` 计数器）。

**预注册判读**（v3；修订链见模块底部注释）：θ_down=k（k∈{0.45,0.40}）**值得默认启用** ⇔
**`[k, 0.5)` 带内的降档事件** ≥ 5、占全部降档 ≥ 10%，**且上行穿越 θ 的次数 ≥ 5**
（滞回的价值是"抑振荡"；没有上行的单向下穿只是把一次性降档推迟 ~10 tick，是纯成本）。

> 判据修订链（每次都朝更保守方向，原始数据全量报告）：
> v1 把"降档时注意力 ≥ k"整段当命中——把预算挤压（≥θ）也算进去（误报）；v2 拆出 [k,θ) 带；
> v3 加必要条件"上行穿越 ≥5"——**带内事件是平滑衰减的必然产物，不能单独作为振荡证据**。

边界：bench 无观察者 pin、无墙钟负载反馈（`feedback` 的边际抖动**不在**本仪器的测量范围，
需在 live runner 上采）；结论只覆盖"衰减 + 内生凝视 + 显要"这三路注意力。

用法：
    python -m bench.attention_trace --ticks 2000 --capacity 1000 --population 5000 --seeds 1 7
"""

import argparse
import random
import statistics

from app.core.measure.engine import MeanFieldEngine
from app.core.measure.transitions import FULL_FLOWS
from app.core.measure.window import WindowEngine
from bench.world import make_characters

THETA = 0.5
BANDS = [(0.0, 0.40), (0.40, 0.45), (0.45, 0.50), (0.50, 0.55), (0.55, 1.01)]


def _engine(population, capacity, seed, observer):
    random.seed(seed)
    mf = MeanFieldEngine(characters=make_characters(population, seed=seed), flows=FULL_FLOWS)
    engine = WindowEngine(mf, capacity=capacity, window=capacity, resolution=True,
                          rng=random.Random(seed))
    mgr = engine.resolution
    if observer == "production":
        mgr.endogenous_scale = max(6.0, capacity / 25.0)
        mgr.set_notable_fraction(0.01)
    return engine, mgr


def run(population, capacity, seed, ticks, observer):
    engine, mgr = _engine(population, capacity, seed, observer)
    samples = []            # 所有 (cluster, tick) 的注意力采样
    prev = {}               # cid → (attention, level)；只含**仍存在**的簇
    crossings_up = 0
    crossings_down = 0
    downgrades = 0
    downgrade_att = []      # 每次降档时的注意力（降档前分辨率=1）
    upgrades = 0
    concurrent = []
    for _ in range(ticks):
        engine.step()
        alive = set(mgr.store.clusters)
        for cid in [c for c in prev if c not in alive]:
            prev.pop(cid, None)
        concurrent.append(len(alive))
        for cid, attention in list(mgr.attention.items()):
            cluster = mgr.store.clusters.get(cid)
            if cluster is None:
                continue
            level = cluster.level
            samples.append(attention)
            before = prev.get(cid)
            if before is not None:
                if before[0] >= THETA and attention < THETA:
                    crossings_down += 1        # 单向抖动：滞回若有效，应主要拦这一类
                elif before[0] < THETA and attention >= THETA:
                    crossings_up += 1          # 回升（振荡的另一半）
                if before[1] == 1 and level == 0:
                    downgrades += 1
                    downgrade_att.append(attention)
                elif before[1] == 0 and level == 1:
                    upgrades += 1
            prev[cid] = (attention, level)

    tele = mgr.telemetry()
    dwells = [e["dwell"] for e in tele.values() if e.get("dwell") is not None]
    counts = {"samples": len(samples),
              "clusters_end": concurrent[-1] if concurrent else 0,
              "clusters_max": max(concurrent) if concurrent else 0}
    counts["p10"], counts["p50"], counts["p90"] = (
        statistics.quantiles(samples, n=10)[0] if samples else 0.0,
        statistics.median(samples) if samples else 0.0,
        statistics.quantiles(samples, n=10)[-1] if samples else 0.0,
    )
    counts["band"] = []
    for low, high in BANDS:
        n = sum(1 for a in samples if low <= a < high)
        counts["band"].append(n / max(1, len(samples)))
    counts["crossings_down"] = crossings_down
    counts["crossings_up"] = crossings_up
    counts["downgrades"] = downgrades
    counts["upgrades"] = upgrades
    counts["dg_ge_theta"] = sum(1 for a in downgrade_att if a >= THETA)
    for k in (0.45, 0.40):
        in_band = sum(1 for a in downgrade_att if k <= a < THETA)
        below = sum(1 for a in downgrade_att if a < k)
        counts[f"dg_band_{k}"] = in_band
        counts[f"dg_below_{k}"] = below
    counts["switches"] = mgr.switch_total
    counts["dwell_median"] = statistics.median(dwells) if dwells else None
    return counts


def main():
    parser = argparse.ArgumentParser(description="生产样态注意力轨迹观测（测量轮）")
    parser.add_argument("--population", type=int, default=5000)
    parser.add_argument("--capacity", type=int, default=1000)
    parser.add_argument("--ticks", type=int, default=2000)
    parser.add_argument("--seeds", type=int, nargs="+", default=[1, 7])
    parser.add_argument("--observer", choices=["production", "none"], default="production")
    args = parser.parse_args()

    print(f"注意力轨迹观测（observer={args.observer}，N={args.population}，C={args.capacity}，"
          f"ticks={args.ticks}）\n")
    rows = [run(args.population, args.capacity, seed, args.ticks, args.observer)
            for seed in args.seeds]
    for seed, counts in zip(args.seeds, rows):
        print(f"  seed={seed}  并发簇={counts['clusters_end']}（峰 {counts['clusters_max']}） "
              f"samples={counts['samples']}  p10/p50/p90="
              f"{counts['p10']:.3f}/{counts['p50']:.3f}/{counts['p90']:.3f}")
        bands = "  ".join(f"[{low:.2f},{high:.2f})={frac:.1%}"
                          for (low, high), frac in zip(BANDS, counts["band"]))
        print(f"    {bands}")
        print(f"    穿越θ 下/上={counts['crossings_down']}/{counts['crossings_up']}"
              f"（↑ 才是振荡）  降档={counts['downgrades']}"
              f"（注意力 ≥θ: {counts['dg_ge_theta']}；"
              f"[0.45,θ): {counts['dg_band_0.45']}；[0.40,θ): {counts['dg_band_0.4']}；"
              f"<0.40: {counts['dg_below_0.4']}）"
              f"  升档={counts['upgrades']}  switches={counts['switches']}"
              f"  驻留中位={counts['dwell_median']}")
    total = sum(r["downgrades"] for r in rows)
    up = sum(r["crossings_up"] for r in rows)
    print()
    print("预注册判读 v3（带内降档 ≥5 且占比 ≥10% **且上行穿越 ≥5** ⇒ 值得默认启用）：")
    for k in (0.45, 0.40):
        hits = sum(r[f"dg_band_{k}"] for r in rows)
        frac = (hits / total) if total else 0.0
        ok = hits >= 5 and frac >= 0.10 and up >= 5
        print(f"  θ_down={k}: 带内 {hits}/{total}（{frac:.0%}）、上行穿越 {up} ⇒ "
              f"{'值得默认启用' if ok else '维持 opt-in'}")


if __name__ == "__main__":
    main()
