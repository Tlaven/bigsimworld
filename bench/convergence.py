"""个体/测度引擎的收敛对比与基线导出。

用法：
    python -m bench.convergence --individual 1000 10000 --steps 500
"""

import argparse
import json
import os

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
    """返回归一化到 [0,1] 的各分量差异；完全一致时全为 0。"""
    return {
        "age_l1": _l1(fp_a["age_hist"], fp_b["age_hist"]),
        "degree_l1": _l1(fp_a["degree_hist"], fp_b["degree_hist"]),
        "gini_diff": float(abs(fp_a["gini_wealth"] - fp_b["gini_wealth"])),
        "wealth_rel": _wealth_rel(fp_a, fp_b),
        "wealth_ks": _wealth_ks(fp_a, fp_b),
        "married_diff": float(abs(fp_a.get("married_frac", 0.0) - fp_b.get("married_frac", 0.0))),
    }


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


def main():
    parser = argparse.ArgumentParser(description="Convergence baselines / comparison")
    parser.add_argument("--individual", type=int, nargs="+")
    parser.add_argument("--measure-compare", action="store_true")
    parser.add_argument("--full-compare", action="store_true")
    parser.add_argument("--sizes", type=int, nargs="+", default=[1000, 10000, 50000])
    parser.add_argument("--steps", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default="bench/results/fingerprints")
    args = parser.parse_args()

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

    if args.measure_compare:
        print(f"{'N':>8} {'age_l1':>10} {'degree_l1':>10} {'gini_diff':>10} {'wealth_rel':>10}")
        for n in args.sizes:
            ind = run_reduced(n, args.steps, args.seed)
            mf = run_measure(n, args.steps, args.seed)
            diff = compare_fingerprint(ind, mf)
            print(f"{n:>8} {diff['age_l1']:>10.4f} {diff['degree_l1']:>10.4f} "
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
