"""个体/测度引擎的收敛对比与基线导出。

用法：
    python -m bench.convergence --individual 1000 10000 --steps 500
"""

import argparse
import json
import os

import numpy as np

from bench.fingerprint import fingerprint
from bench.world import build_engine


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


def compare_fingerprint(fp_a, fp_b):
    """返回归一化到 [0,1] 的各分量差异；完全一致时全为 0。"""
    return {
        "age_l1": _l1(fp_a["age_hist"], fp_b["age_hist"]),
        "degree_l1": _l1(fp_a["degree_hist"], fp_b["degree_hist"]),
        "gini_diff": float(abs(fp_a["gini_wealth"] - fp_b["gini_wealth"])),
        "wealth_rel": _wealth_rel(fp_a, fp_b),
    }


def run_individual(n, steps, seed):
    engine = build_engine(n, seed=seed)
    for _ in range(steps):
        engine.step()
    return fingerprint(engine)


def main():
    parser = argparse.ArgumentParser(description="Convergence baselines / comparison")
    parser.add_argument("--individual", type=int, nargs="+")
    parser.add_argument("--steps", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default="bench/results/fingerprints")
    args = parser.parse_args()

    if not args.individual:
        parser.error("provide --individual N [N ...]")

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
