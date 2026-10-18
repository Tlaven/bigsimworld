"""误差触发研究：候选指示器能否预测「粗化伤害」？（审计 #5/#10 的前置）

设计（配对世界，隔离"只有分辨率不同"）：

- 每 trial 同一 seed 构造两份 `_IsolatedWindowEngine`（`resolution=True`；`capacity=k`；
  **关闭回填** ⇒ 窗口里只有这个家族；**关闭边界维护** ⇒ 簇手工建立、不被 split/merge 干扰）。
- **处理臂**：resolved 观察 `W` tick（注意力钉 1.0，采集指示器）→ 转入 coarse 跑 `T` tick
  （每 tick 把注意力刷新到 0.2：低于 θ、高于 `dissolve_floor`，防回收）。
- **孪生臂**：同 seed，全程 resolved 跑 `W + T`。
- **指示器**（t = W 读；都是 resolved 可测量）：
  1. `flux_z` = `(Σreal − Σexp) / sqrt(Σexp + 0.5)`（telemetry 滚动窗，births/deaths/marriages 合并）；
  2. `phase_disp` = 成员相位的圆离散度 `1 − |mean(e^{iθ})|`（0 = 同相，1 ≈ 均匀）。
- **结局**（t = W + T，处理臂 vs 孪生臂）：`age_l1`（`compare_fingerprint`）、`pop` 相对差、
  `married_frac` 差。
- **已知轴**：`aligned_phase ∈ {False, True}`——相位错位是 Stage 16 记录的主导混淆项，
  用来检验指示器至少能"看见"已知误差。

**可用性判据（先写死，防事后挑选）**——某指示器"可用"须满足其一：

- ① 生产样态内（`aligned_phase=False` 组）：与 `age_l1` 的 Pearson `|r| ≥ 0.5`，且符号一致率 ≥ 0.8；
- ② 已知轴分离：指示器与结局在两组间**同向**分离（各 |Cohen's d| ≥ 1，且方向一致）。
- 否则 = 不可用 ⇒ 记"为什么不"、**不接线**。

用法：
    python -m bench.residual_correlation --trials 12
"""

import argparse
import math
import random
import statistics

from app.core.measure.engine import MeanFieldEngine
from app.core.measure.window import WindowEngine
from bench.cluster_fidelity import make_family
from bench.convergence import compare_fingerprint
from bench.fingerprint import fingerprint, measure_fingerprint


class _IsolatedWindowEngine(WindowEngine):
    """研究用：容量 = 家族人数且**不回填**——窗口里只有这个家族。"""

    def _refill(self) -> None:
        return None


def _build(seed, members, aligned_phase):
    random.seed(seed)
    measure_engine = MeanFieldEngine()
    engine = _IsolatedWindowEngine(measure_engine, capacity=members, window=0,
                                   resolution=True, rng=random.Random(seed))
    window = engine.window
    for person in make_family(members, seed=seed, aligned_phase=aligned_phase):
        window.attach(person)
    ids = sorted(window.characters)
    mgr = engine.resolution
    mgr.form_interval = 10 ** 9          # 关闭边界维护：簇手工建立，不做 split/merge
    cluster = mgr.store.create("family", set(ids))
    mgr.attention[cluster.id] = 1.0
    return engine, mgr, cluster.id


def _indicators(mgr, cid, window):
    tel = mgr.telemetry().get(cid, {})
    real = sum(tel.get("real", {}).values())
    expected = sum(tel.get("expected", {}).values())
    flux_z = (real - expected) / math.sqrt(expected + 0.5)
    cluster = mgr.store.clusters[cid]
    members = [window.characters[mid] for mid in cluster.member_ids
               if mid in window.characters]
    phases = [character.pedometer["step"] % 360 for character in members]
    if phases:
        re = sum(math.cos(2 * math.pi * p / 360) for p in phases) / len(phases)
        im = sum(math.sin(2 * math.pi * p / 360) for p in phases) / len(phases)
        phase_disp = 1.0 - math.hypot(re, im)
    else:
        phase_disp = None
    return {"flux_z": flux_z, "phase_disp": phase_disp,
            "flux_real": real, "flux_expected": expected}


def _outcome(mgr, cid, window):
    cluster = mgr.store.clusters[cid]
    if cluster.level == 0:
        mini = cluster.state["engine"].measure
        fp = measure_fingerprint(mini, window.space)
        pool = float(sum(mini.yearly_inherited.values()))
        per_capita = (fp["total_wealth"] + pool) / cluster.state["size"]
    else:
        fp = fingerprint(window)
        per_capita = fp["total_wealth"] / max(1, fp["population"])
    return fp, per_capita


def run_trial(seed, members, aligned_phase, observe_ticks, coarse_ticks):
    treated, mgr_t, cid_t = _build(seed, members, aligned_phase)
    for _ in range(observe_ticks):
        mgr_t.set_attention(cid_t, 1.0)
        treated.step()
    indicators = _indicators(mgr_t, cid_t, treated.window)

    for _ in range(coarse_ticks):
        mgr_t.set_attention(cid_t, 0.2)      # 低于 θ、高于 dissolve_floor：降档且不被回收
        treated.step()
    assert mgr_t.store.clusters[cid_t].level == 0

    twin, mgr_w, cid_w = _build(seed, members, aligned_phase)
    for _ in range(observe_ticks + coarse_ticks):
        mgr_w.set_attention(cid_w, 1.0)
        twin.step()

    fp_treated, pc_treated = _outcome(mgr_t, cid_t, treated.window)
    fp_twin, pc_twin = _outcome(mgr_w, cid_w, twin.window)
    dist = compare_fingerprint(fp_twin, fp_treated)
    return {
        "seed": seed, "members": members, "aligned": aligned_phase,
        **indicators,
        "age_l1": dist["age_l1"],
        "pop_rel": (fp_treated["population"] - fp_twin["population"]) / members,
        "married_diff": fp_treated["married_frac"] - fp_twin["married_frac"],
        "per_capita_rel": (pc_treated - pc_twin) / (pc_twin or 1.0),
    }


def _pearson(xs, ys):
    n = len(xs)
    if n < 2:
        return 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
    return num / den if den else 0.0


def _sign_agreement(xs, ys):
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    pairs = [(x - mx, y - my) for x, y in zip(xs, ys)
             if x != mx and y != my]
    if not pairs:
        return 0.0
    return sum(1 for dx, dy in pairs if (dx > 0) == (dy > 0)) / len(pairs)


def _separation(a, b):
    if len(a) < 2 or len(b) < 2:
        return 0.0
    pooled = math.sqrt((statistics.pvariance(a) + statistics.pvariance(b)) / 2.0) or 1e-12
    return (statistics.mean(a) - statistics.mean(b)) / pooled


def _verdict(rows):
    """先写死的可用性判据。返回 (可用列表, 报告行)。"""
    lines = []
    nonaligned = [row for row in rows if not row["aligned"]]
    aligned = [row for row in rows if row["aligned"]]
    age_all = [row["age_l1"] for row in nonaligned]

    def axis(name):
        vals_a = [row[name] for row in aligned if row[name] is not None]
        vals_n = [row[name] for row in nonaligned if row[name] is not None]
        return _separation(vals_a, vals_n)

    sep_phase = axis("phase_disp")
    sep_flux = axis("flux_z")
    sep_age = axis("age_l1")
    lines.append(f"已知轴分离（Cohen's d，aligned − nonaligned）：phase_disp={sep_phase:+.2f} "
                 f"flux_z={sep_flux:+.2f} age_l1={sep_age:+.2f}")

    usable = []
    for name in ("flux_z", "phase_disp"):
        xs = [row[name] for row in nonaligned if row[name] is not None]
        ys = [row["age_l1"] for row in nonaligned if row[name] is not None]
        r = _pearson(xs, ys)
        agree = _sign_agreement(xs, ys)
        sep = sep_phase if name == "phase_disp" else sep_flux
        same_axis = (abs(sep) >= 1.0 and abs(sep_age) >= 1.0
                     and (sep > 0) == (sep_age > 0))
        ok = (abs(r) >= 0.5 and agree >= 0.8) or same_axis
        lines.append(f"{name}: 组内 r(age_l1)={r:+.3f} 符号一致={agree:.0%} 轴分离 d={sep:+.2f} "
                     f"同向={same_axis} ⇒ {'可用' if ok else '不可用'}")
        if ok:
            usable.append(name)
    return usable, lines


def main():
    parser = argparse.ArgumentParser(description="误差触发研究（指示器 vs 粗化伤害）")
    parser.add_argument("--trials", type=int, default=12, help="每格 trial 数")
    parser.add_argument("--sizes", type=int, nargs="+", default=[6, 8, 10, 12])
    parser.add_argument("--observe-ticks", type=int, default=720, help="W：resolved 观察窗")
    parser.add_argument("--coarse-ticks", type=int, default=2000, help="T：coarse 演化时长")
    args = parser.parse_args()

    rows = []
    for members in args.sizes:
        for aligned in (False, True):
            for index in range(args.trials):
                rows.append(run_trial(index + 1, members, aligned,
                                      args.observe_ticks, args.coarse_ticks))

    print(f"误差触发研究（W={args.observe_ticks} 观察 + T={args.coarse_ticks} coarse；"
          f"sizes={args.sizes}，trials/格={args.trials}）\n")
    print(f"  {'members':>8}{'aligned':>8}{'n':>4}{'age_l1':>10}{'pop_rel':>9}"
          f"{'married':>9}{'flux_z':>9}{'phase_disp':>11}")
    for members in args.sizes:
        for aligned in (False, True):
            cell = [row for row in rows if row["members"] == members
                    and row["aligned"] == aligned]
            age = statistics.mean(row["age_l1"] for row in cell)
            pop = statistics.mean(row["pop_rel"] for row in cell)
            married = statistics.mean(row["married_diff"] for row in cell)
            flux = statistics.mean(row["flux_z"] for row in cell)
            phase = statistics.mean(row["phase_disp"] for row in cell
                                    if row["phase_disp"] is not None)
            print(f"  {members:>8}{str(aligned):>8}{len(cell):>4}{age:>10.4f}{pop:>9.4f}"
                  f"{married:>9.4f}{flux:>9.3f}{phase:>11.3f}")

    usable, lines = _verdict(rows)
    print()
    print("可用性判定（先写死的判据，见模块文档）：")
    for line in lines:
        print(f"  {line}")
    print(f"  ⇒ 可用指示器：{usable if usable else '无（记录为什么不，不接线）'}")


if __name__ == "__main__":
    main()
