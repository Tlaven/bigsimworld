"""共演单元保真度基准（A/B）：**coarse vs 保持 resolved**。

第三章的核心主张是"coarsen 一个家族 ≈ 保留这个家族"。此前**没有任何度量**——
`bench.cluster_inheritance` 量的是继承**浓度比**（族内池 vs 全局池），不是保真度。

## 设计（为什么是这样比）

1. **同一批人、同一个隔离环境**：两侧都只在族内交互，唯一差别 = 分辨率。
   隔离掉"窗口里还能遇到别人"这个混淆项，剩下的就是"分辨率"本身。
2. **身份不守恒**（coarsen 是重采样新代表，见 `docs/engineering-spec.md` §9）⇒ **不比个体轨迹**。
3. **配对试验 + 跨 trial 汇总**（沿 `bench.diagnose_tail` 的多种子纪律）：
   生产簇规模 ≤ `max_members=12`，此时**分布型指标被离散噪声主导**
   （k=8 ⇒ 分位数一格 = 12.5%；实测单 trial 的 `wealth_ks` 能到 0.9 —— 那是噪声不是偏差）。
   故主指标取**稳健标量**，并以 `(R − C)` 的**跨 trial 均值 ± 标准差 + 符号计数**
   把"系统性偏差"从"采样噪声"里分出来。**单次读数不作结论。**
4. **coarse 侧的财富必须含继承池余量**：段池（`yearly_inherited`）是"已欠未付"的财富，
   不计入就等于凭空消失（`bench.audit_ledger` 的 `pool_residual` 同口径）。
5. **度指标在 coarse 侧无定义**（测度层无图）⇒ `degree_l1 = None`，输出标 `n/a`。这是**类别错误**，不是缺陷。

## 已知会暴露的近似（正是要量的东西）

1. 族内婚配/生育在 mini 均值场里**闭合**，而 resolved 侧走真实的"关系漏斗 + 广场"事件链；
2. 年龄 / 财富的**桶离散化**；
3. 继承：族内**段池 + 整数桶支付** vs 真实的**指名继承**。

用法：
    python -m bench.cluster_fidelity --members 8 --ticks 4000 --trials 30
"""

import argparse
import copy
import json
import os
import random
import statistics

from app.core.generation.human import generate_character
from app.core.measure import transitions as T
from app.core.measure.cluster import KINDS, ClusterStore, TickContext
from app.core.measure.measure import Measure
from app.core.measure.space import StateSpace
from app.core.measure.window import IndividualWindow
from bench.convergence import compare_fingerprint
from bench.fingerprint import fingerprint, measure_fingerprint

METRICS = ("population", "mean_age", "married_frac", "gini_wealth",
           "wealth_per_capita", "pool_frac", "age_l1")


# ---------------------------------------------------------------- 家族构造

def make_family(k, seed=1, age_range=(20, 50), wealth_mean=10000.0, wealth_sd=3000.0,
                aligned_phase=False):
    """确定性的合成家族：成年、男女交替、各带随机个人相位（两条臂共用同一批）。

    `aligned_phase=True` 把所有个人相位压成 0 —— 此时 resolved 臂的"变老"与 coarse 臂的
    `aging`（`tick % 360 == 0`）**同相**。用于把"相位错位"这个混淆项单独摘出来（见
    `bench/diagnose_cluster_bias`）。
    """
    rng = random.Random(seed)
    random.seed(seed)                      # `generate_character` 取名字用模块级 random
    people = []
    for i in range(k):
        person = generate_character(
            age=rng.randint(*age_range),
            gender="male" if i % 2 == 0 else "female",
            wealth=max(0.0, rng.gauss(wealth_mean, wealth_sd)),
        )
        person["pedometer"] = {"step": 0 if aligned_phase else rng.randint(0, 359),
                               "step_threshold": 10}
        people.append(person)
    return people


# ---------------------------------------------------------------- 两条臂

def _observables(fp, wealth, pool, population):
    total = wealth + pool
    return {
        "population": float(population),
        "mean_age": fp["mean_age"],
        "married_frac": fp["married_frac"],
        "gini_wealth": fp["gini_wealth"],
        "wealth_per_capita": (total / population) if population else 0.0,
        "pool_frac": (pool / total) if total else 0.0,
    }


def build_arm(kind, people, space, capacity):
    """返回 ``(步进函数, 快照函数)``。两条臂共用同一批人（深拷贝防串扰）。"""
    window = IndividualWindow(Measure(space), capacity=capacity, rng=random.Random(0))

    if kind == "resolved":
        for person in copy.deepcopy(people):
            window.attach(person)

        def step(tick):
            window.step(tick)

        def snapshot():
            fp = fingerprint(window)
            return fp, _observables(fp, fp["total_wealth"], 0.0, len(window.characters))

        return step, snapshot

    store = ClusterStore(window.measure, window)
    ids = [window.attach(copy.deepcopy(person)).id for person in people]
    cluster = store.create("family", set(ids))
    store.coarsen(cluster.id)              # 走真实路径：成员 → mini 均值场（计数中性）

    def step(tick):
        store.step_coarse(TickContext(tick=tick, measure=window.measure, rng=window.rng))

    def snapshot():
        mini = cluster.state["engine"].measure
        fp = measure_fingerprint(mini, space)
        pool = float(sum(mini.yearly_inherited.values()))
        return fp, _observables(fp, fp["total_wealth"], pool, fp["population"])

    return step, snapshot


def run_arm(kind, people, space, checkpoints, capacity):
    """跑一条臂到最后一个 checkpoint，逐点取样 ⇒ ``{tick: (指纹, 观测)}``。"""
    step, snapshot = build_arm(kind, people, space, capacity)
    snaps = {}
    last = max(checkpoints)
    wanted = set(checkpoints)
    for tick in range(1, last + 1):
        step(tick)
        if tick in wanted:
            snaps[tick] = snapshot()
    return snaps


# ---------------------------------------------------------------- 一个 trial

def run_trial(seed, members, checkpoints, capacity=None,
              coarse_flows=None, marriage_scale=None, aligned_phase=False):
    """一个配对 trial：同一批人 + 同一隔离环境，只有分辨率不同。

    `coarse_flows` / `marriage_scale` / `aligned_phase` 供**归因实验**
    （`bench/diagnose_cluster_bias`）注入。前两个只改 coarse 臂；
    `aligned_phase` 同时作用于两臂（把"相位错位"这个混淆项摘掉）。
    """
    space = StateSpace()
    people = make_family(members, seed=seed, aligned_phase=aligned_phase)
    capacity = capacity or (members * 60)

    saved_flows = KINDS["family"].flows
    saved_rate = T.MARRIAGE_RATE
    if coarse_flows is not None:
        KINDS["family"].flows = tuple(coarse_flows)
    if marriage_scale is not None:
        T.MARRIAGE_RATE = saved_rate * marriage_scale
    try:
        raw = {"resolved": run_arm("resolved", people, space, checkpoints, capacity),
               "coarse": run_arm("coarse", people, space, checkpoints, capacity)}
    finally:
        KINDS["family"].flows = saved_flows
        T.MARRIAGE_RATE = saved_rate

    rows = {}
    for tick in checkpoints:
        fp_r, obs_r = raw["resolved"][tick]
        fp_c, obs_c = raw["coarse"][tick]
        diff = {m: obs_r[m] - obs_c[m] for m in METRICS if m != "age_l1"}
        dist = compare_fingerprint(fp_r, fp_c)
        diff["age_l1"] = dist["age_l1"]
        rows[tick] = {"resolved": obs_r, "coarse": obs_c, "diff": diff,
                      "degree_l1": dist["degree_l1"]}
    return rows


# ---------------------------------------------------------------- 汇总

def summarize(per_trial):
    """``[trial][tick] -> rows`` → ``{tick: {metric: {mean, sd, r_gt_c, n}}}``。"""
    out = {}
    ticks = sorted({t for rows in per_trial for t in rows})
    for tick in ticks:
        out[tick] = {}
        for metric in METRICS:
            values = [rows[tick]["diff"][metric] for rows in per_trial]
            out[tick][metric] = {
                "mean": statistics.mean(values),
                "sd": statistics.pstdev(values) if len(values) > 1 else 0.0,
                "r_gt_c": sum(1 for v in values if v > 0),
                "n": len(values),
            }
    return out


# ---------------------------------------------------------------- CLI

def main():
    parser = argparse.ArgumentParser(description="Coarse vs resolved cluster fidelity (A/B)")
    parser.add_argument("--members", type=int, default=8, help="家族规模（生产簇 ≤12）")
    parser.add_argument("--ticks", type=int, default=4000, help="最后一个 checkpoint")
    parser.add_argument("--trials", type=int, default=30, help="配对试验数（跨 trial 汇总）")
    parser.add_argument("--seed0", type=int, default=1, help="首个 trial 的种子（随后 +1）")
    parser.add_argument("--checkpoints", type=int, nargs="+", default=None,
                        help="误差包络取样点（默认：ticks 的四等分）")
    parser.add_argument("--capacity", type=int, default=None)
    parser.add_argument("--out", default=None, help="结果写 JSON（证据，可提交）")
    args = parser.parse_args()

    checkpoints = sorted(set(args.checkpoints or
                            [max(1, args.ticks * i // 4) for i in (1, 2, 3, 4)]))

    print(f"coarse vs resolved 家族保真度（members={args.members}，隔离环境，"
          f"唯一差别 = 分辨率；trials={args.trials}，ticks={checkpoints[-1]}）")
    print("主指标 = 配对差 (R − C) 的跨 trial 均值 ± 标准差 + 符号计数；"
          "**单次读数不作结论**（k≤12 时分布型指标被离散噪声主导）\n")

    per_trial = [run_trial(args.seed0 + i, args.members, checkpoints, args.capacity)
                 for i in range(args.trials)]
    summary = summarize(per_trial)

    for tick in checkpoints:
        print(f"t={tick}")
        print(f"  {'metric':<18}{'mean(R−C)':>12}{'sd':>10}{'R>C':>8}{'n':>5}")
        for metric in METRICS:
            stat = summary[tick][metric]
            print(f"  {metric:<18}{stat['mean']:>12.4f}{stat['sd']:>10.4f}"
                  f"{stat['r_gt_c']:>8}{stat['n']:>5}")
        print(f"  {'degree_l1':<18}{'n/a':>12}   （coarse 侧无图 ⇒ 类别错误）")
        print()

    last = summary[checkpoints[-1]]
    print("--- 末 tick 判读提示 ---")
    print("  系统性偏差：|mean| 明显大于 sd/√n 且符号计数一边倒；否则视为噪声。")
    for metric in ("population", "wealth_per_capita", "married_frac", "age_l1"):
        stat = last[metric]
        noise = stat["sd"] / max(1.0, stat["n"] ** 0.5)
        verdict = "系统性" if abs(stat["mean"]) > 3 * noise and noise >= 0 and stat["n"] > 1 else "未定/噪声级"
        print(f"  {metric:<18} mean={stat['mean']:+.4f}  sd={stat['sd']:.4f}  "
              f"R>C {stat['r_gt_c']}/{stat['n']}  ⇒ {verdict}")

    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as handle:
            json.dump({"params": vars(args), "checkpoints": checkpoints,
                       "summary": summary,
                       "per_trial": per_trial},
                      handle, ensure_ascii=False, indent=2)
        print(f"\n→ {args.out}")


if __name__ == "__main__":
    main()
