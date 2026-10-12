"""财富尾部诊断：找出测度引擎 vs 个体引擎的财富分位偏差来源。

用法：
    python -m bench.diagnose_tail --n 5000 --steps 8000 --seed 42

输出：
    - 21 个分位的 ind vs mf 对照（KS 的来源定位到具体分位）
    - 顶部财富占比（top 5% / top 10%）
    - 两引擎的最大财富与测度层最高占用桶（检查 3000 桶溢出）
    - 遗产相关结构：死者财富向子女段的转移是否是主要放大项
"""

import argparse

import numpy as np

from app.core.measure.engine import MeanFieldEngine
from app.core.measure.transitions import FULL_FLOWS
from bench.fingerprint import fingerprint, measure_fingerprint
from bench.world import make_characters


def run_individual(n, steps, seed):
    import random
    random.seed(seed)
    from bench.sinks import SinkQueue
    from app.core.simulation.engine import SimulationEngine
    random.seed(seed)
    characters = make_characters(n, seed=seed)
    engine = SimulationEngine(
        {"insert": SinkQueue(), "update": SinkQueue(), "delete": SinkQueue()},
        characters=characters)
    for _ in range(steps):
        engine.step()
    return fingerprint(engine)


def run_measure(n, steps, seed):
    engine = MeanFieldEngine(characters=make_characters(n, seed=seed), flows=FULL_FLOWS)
    engine.run_until(steps)
    return measure_fingerprint(engine.measure, engine.space), engine


def top_share_fp(fp, share=0.05):
    """wealth_quantiles 是 21 点 0..1 分位；用分位差近似 top-x 占总财富比。"""
    qs = np.asarray(fp["wealth_quantiles"], dtype=np.float64)
    total = qs.mean()
    tail_mean = qs[int((1 - share) * 20):].mean()
    return float(tail_mean / total)


def main():
    parser = argparse.ArgumentParser(description="Wealth tail diagnostics")
    parser.add_argument("--n", type=int, default=5000)
    parser.add_argument("--steps", type=int, default=8000)
    parser.add_argument("--seeds", type=int, default=[42], nargs="+")
    args = parser.parse_args()

    rows_tail = []
    rows_mid = []
    for seed in args.seeds:
        print(f"---- seed={seed} (n={args.n} steps={args.steps}) ----")
        ind = run_individual(args.n, args.steps, seed)
        mf, mf_engine = run_measure(args.n, args.steps, seed)

        qs_ind = np.asarray(ind["wealth_quantiles"], dtype=np.float64)
        qs_mf = np.asarray(mf["wealth_quantiles"], dtype=np.float64)
        scale = max(qs_ind[-1], qs_mf[-1], 1e-9)
        rels = (qs_mf - qs_ind) / scale

        print(f"{'q':>5} {'ind':>12} {'mf':>12} {'rel':>8}")
        for i, q in enumerate(np.linspace(0, 1, 21)):
            print(f"{q:>5.2f} {qs_ind[i]:>12.1f} {qs_mf[i]:>12.1f} {rels[i] * 100:>+7.2f}%")

        ks = float(np.abs(qs_mf - qs_ind).max() / scale)
        ks_mid = float(np.abs(qs_mf[:19] - qs_ind[:19]).max() / scale)  # 排除 p95/p100 两点
        print(f"KS={ks * 100:.2f}%  KS(p<=0.9)={ks_mid * 100:.2f}%  "
              f"p100_rel={rels[-1] * 100:+.2f}%  "
              f"total: ind={ind['total_wealth']:.3e} mf={mf['total_wealth']:.3e}  "
              f"gini: ind={ind['gini_wealth']} mf={mf['gini_wealth']}  "
              f"pop: ind={ind['population']} mf={mf['population']}")
        rows_tail.append(ks * 100)
        rows_mid.append(ks_mid * 100)

    print(f"\n== summary over seeds {args.seeds} ==")
    print(f"KS    : median={np.median(rows_tail):.2f}%  list={[round(x, 2) for x in rows_tail]}")
    print(f"KS<=.9: median={np.median(rows_mid):.2f}%  list={[round(x, 2) for x in rows_mid]}")


if __name__ == "__main__":
    main()
