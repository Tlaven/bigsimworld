"""个体/测度引擎的收敛对比与基线导出。

用法：
    python -m bench.convergence --individual 1000 10000 --steps 500
"""

import argparse
import json
import os
import time

import numpy as np

from bench.fingerprint import fingerprint, measure_fingerprint
from bench.world import build_engine, make_characters


def _norm_hist(hist):
    a = np.asarray(hist, dtype=np.float64)
    total = a.sum()
    return a / total if total else a


def _l1(hist_a, hist_b):
    n = max(len(hist_a), len(hist_b))
    a = np.pad(_norm_hist(hist_a), (0, n - len(hist_a)))
    b = np.pad(_norm_hist(hist_b), (0, n - len(hist_b)))
    return float(np.abs(a - b).sum() / 2.0)


def _wealth_rel(fp_a, fp_b):
    qa = np.asarray(fp_a.get("wealth_quantiles", []), dtype=np.float64)
    qb = np.asarray(fp_b.get("wealth_quantiles", []), dtype=np.float64)
    if qa.size == 0 or qb.size == 0:
        return 0.0
    scale = max(float(qa[-1]), float(qb[-1]), 1e-9)
    return float(min(1.0, np.abs(qa - qb).mean() / scale))


def _wealth_ks(fp_a, fp_b):
    qa = np.asarray(fp_a.get("wealth_quantiles", []), dtype=np.float64)
    qb = np.asarray(fp_b.get("wealth_quantiles", []), dtype=np.float64)
    if qa.size == 0 or qb.size == 0:
        return 0.0
    scale = max(float(qa[-1]), float(qb[-1]), 1e-9)
    return float(min(1.0, np.abs(qa - qb).max() / scale))


def compare_fingerprint(fp_a, fp_b):
    """返回归一化到 [0,1] 的各分量差异；完全一致时全为 0。

    `degree_l1` **只在双方都有图**（即 `degree_hist` 非 None）时有定义：
    测度层是状态空间上的稀疏计数分布、**不含度维度**，与它比"度分布"是**类别错误**
    （不是"差异为 0"）。图保真度请用 `--graph-compare`（窗口 ↔ 个体，双方都有图）。
    """
    result = {
        "age_l1": _l1(fp_a["age_hist"], fp_b["age_hist"]),
        "gini_diff": float(abs(fp_a["gini_wealth"] - fp_b["gini_wealth"])),
        "wealth_rel": _wealth_rel(fp_a, fp_b),
        "wealth_ks": _wealth_ks(fp_a, fp_b),
        "married_diff": float(abs(fp_a.get("married_frac", 0.0) - fp_b.get("married_frac", 0.0))),
    }
    if fp_a.get("degree_hist") is not None and fp_b.get("degree_hist") is not None:
        result["degree_l1"] = _l1(fp_a["degree_hist"], fp_b["degree_hist"])
    else:
        result["degree_l1"] = None
    return result


def run_individual(n, steps, seed):
    engine = build_engine(n, seed=seed)
    for _ in range(steps):
        engine.step()
    return fingerprint(engine)


def run_reduced(n, steps, seed, run_seed=7):
    import random as _random
    from bench.reduced_model import ReducedModel

    model = ReducedModel(n, seed=seed)
    _random.seed(run_seed)
    model.run_until(steps)
    return fingerprint(model)


def run_measure(n, steps, seed):
    from app.core.measure.engine import MeanFieldEngine

    engine = MeanFieldEngine(characters=make_characters(n, seed=seed))
    engine.run_until(steps)
    return measure_fingerprint(engine.measure, engine.space)


def run_measure_full(n, steps, seed):
    from app.core.measure.engine import MeanFieldEngine
    from app.core.measure.transitions import FULL_FLOWS

    engine = MeanFieldEngine(characters=make_characters(n, seed=seed), flows=FULL_FLOWS)
    engine.run_until(steps)
    return measure_fingerprint(engine.measure, engine.space)


def run_window_fingerprint(n, steps, capacity, seed=42, window=1000):
    """窗口层的指纹（**图-bearing 的一方**）。

    与同规模个体引擎对照，用于度 / 婚配的收敛检查——这是取代
    "测度 vs 个体 的 `degree_l1`（类别错误、恒为 0）"的真指标。
    """
    from app.core.measure.engine import MeanFieldEngine
    from app.core.measure.transitions import FULL_FLOWS
    from app.core.measure.window import WindowEngine

    mf = MeanFieldEngine(characters=make_characters(n, seed=seed), flows=FULL_FLOWS)
    engine = WindowEngine(mf, capacity=capacity, window=min(window, capacity))
    for _ in range(steps):
        engine.step()
    return fingerprint(engine.window)


def run_window(n, steps, capacity, seed=42, window=1000):
    from app.core.measure.engine import MeanFieldEngine
    from app.core.measure.transitions import FULL_FLOWS
    from app.core.measure.window import WindowEngine

    base = min(n, 10000)
    mf = MeanFieldEngine(characters=make_characters(base, seed=seed), flows=FULL_FLOWS)
    if n > base:
        scale = n / base  # 只放大计数（稀疏容器：逐桶乘），占用桶数不变
        for index in list(mf.measure.occupied):
            mf.measure.counts[index] = mf.measure.counts[index] * scale
    engine = WindowEngine(mf, capacity=capacity, window=min(window, capacity))
    start = time.perf_counter()
    for _ in range(steps):
        engine.step()
    ms = (time.perf_counter() - start) / steps * 1000
    friends = sum(len(c.relationships["friend"]) for c in engine.window.characters.values())
    married = sum(1 for c in engine.window.characters.values() if c.relationships["spouse"])
    return ms, engine.population(), len(engine.window.characters), friends, married


def main():
    parser = argparse.ArgumentParser(description="Convergence baselines / comparison")
    parser.add_argument("--individual", type=int, nargs="+")
    parser.add_argument("--measure-compare", action="store_true")
    parser.add_argument("--full-compare", action="store_true")
    parser.add_argument("--graph-compare", action="store_true")
    parser.add_argument("--window", action="store_true")
    parser.add_argument("--capacity", type=int, default=1000)
    parser.add_argument("--sizes", type=int, nargs="+", default=[1000, 10000, 50000])
    parser.add_argument("--steps", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default="bench/results/fingerprints")
    args = parser.parse_args()

    if args.window:
        print(f"capacity={args.capacity}（窗口内为真角色/真关系）")
        print(f"{'N':>12} {'ms/step':>10} {'pop':>14} {'window':>7} {'friend_edges':>13} {'married':>8}")
        for n in args.sizes:
            ms, pop, window, friends, married = run_window(
                n, args.steps, args.capacity, args.seed)
            print(f"{n:>12} {ms:>10.4f} {round(pop):>14} {window:>7} {friends:>13} {married:>8}")
        return

    if args.full_compare:
        print(f"{'N':>8} {'age_l1':>9} {'gini_diff':>10} {'wealth_ks':>10} "
              f"{'married_diff':>13} {'gini_ind':>9} {'gini_mf':>9}")
        for n in args.sizes:
            ind = run_individual(n, args.steps, args.seed)
            mf = run_measure_full(n, args.steps, args.seed)
            diff = compare_fingerprint(ind, mf)
            print(f"{n:>8} {diff['age_l1']:>9.4f} {diff['gini_diff']:>10.4f} "
                  f"{diff['wealth_ks']:>10.4f} {diff['married_diff']:>13.4f} "
                  f"{ind['gini_wealth']:>9.4f} {mf['gini_wealth']:>9.4f}")
        return

    if args.graph_compare:
        # 度指标只在**双方都有图**时有定义：窗口 ↔ 个体。测度层无图（见 compare_fingerprint）。
        print(f"{'N':>8} {'steps':>6} {'degree_l1':>10} {'married_diff':>13} "
              f"{'age_l1':>9} {'gini_diff':>10}")
        for n in args.sizes:
            ind = run_individual(n, args.steps, args.seed)
            win = run_window_fingerprint(n, args.steps, args.capacity, args.seed)
            diff = compare_fingerprint(ind, win)
            print(f"{n:>8} {args.steps:>6} {diff['degree_l1']:>10.4f} "
                  f"{diff['married_diff']:>13.4f} {diff['age_l1']:>9.4f} "
                  f"{diff['gini_diff']:>10.4f}")
        return

    if args.measure_compare:
        print(f"{'N':>8} {'age_l1':>10} {'degree_l1':>10} {'gini_diff':>10} {'wealth_rel':>10}")
        for n in args.sizes:
            ind = run_reduced(n, args.steps, args.seed)
            mf = run_measure(n, args.steps, args.seed)
            diff = compare_fingerprint(ind, mf)
            degree = diff["degree_l1"]
            degree_str = "n/a" if degree is None else f"{degree:.4f}"   # 测度层无图：类别错误
            print(f"{n:>8} {diff['age_l1']:>10.4f} {degree_str:>10} "
                  f"{diff['gini_diff']:>10.4f} {diff['wealth_rel']:>10.4f}")
        return

    if not args.individual:
        parser.error("provide --individual N [N ...]  or  use --measure-compare")

    os.makedirs(args.out, exist_ok=True)
    for n in args.individual:
        fp = run_individual(n, args.steps, args.seed)
        path = os.path.join(args.out, f"individual_{n}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(fp, f, indent=2)
        print(f"individual n={n} steps={args.steps} pop={fp['population']} "
              f"gini={fp['gini_wealth']} -> {path}")


if __name__ == "__main__":
    main()
