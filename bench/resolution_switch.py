"""换档动力学与通量遥测（描述性；**无门槛**——读数供判读，不作证据级结论）。

场景 = 「抖动观测者」：每 tick 把一个确定性的抖动值刷进每个共演单元的注意力
（`jitter + amp×(u−0.5)`，`u` 由 `(seed, tick, cid)` 唯一决定 ⇒ 三臂共享"同一个观测量"）。
三臂对照：

- `baseline`：缺省（无滞回、无驻留）——抖动场景下的换档压力上界；
- `hysteresis`：`theta_down=0.4`（已 resolved 的簇在 [0.4, 0.5) 区间保持）；
- `dwell`：`min_dwell_ticks=60`（同一簇两次换档至少隔 60 tick）。

指标：换档总数（≈ 身份重采样次数）、每簇平均、驻留（min/中位）、通量遥测样例
（`expected` = 粗模型对该聚合的速率、`real` = 实测人-次）。

用法：
    python -m bench.resolution_switch --ticks 600 --families 4 --jitter 0.45
"""

import argparse
import random
import statistics

from app.core.measure.cluster import WaterlinePolicy
from app.core.measure.engine import MeanFieldEngine
from app.core.measure.transitions import FULL_FLOWS
from app.core.measure.window import WindowEngine
from bench.world import make_characters


def _build(seed, capacity, population, families):
    """固定种子的世界 + `families` 个家庭共演单元（每族一对夫妻）。"""
    random.seed(seed)
    mf = MeanFieldEngine(characters=make_characters(population, seed=seed), flows=FULL_FLOWS)
    engine = WindowEngine(mf, capacity=capacity, window=capacity,
                          resolution=True, rng=random.Random(seed))
    mgr = engine.resolution
    mgr.form_interval = 1
    chars = list(engine.window.characters.values())
    for index in range(families):
        a, b = chars[2 * index], chars[2 * index + 1]
        a.age = b.age = 30          # 成年样本对：让通量遥测样例非零、可判读
        a.marry_event.happen(b)
        b.marry_event.happen(a)
    engine.step()                       # 形成共演单元
    return engine, mgr


def _run(arm, ticks, jitter, amp, seed, capacity, population, families):
    engine, mgr = _build(seed, capacity, population, families)
    if arm == "hysteresis":
        mgr.policy = WaterlinePolicy(theta_base=mgr.policy.theta_base,
                                     budget_leaves=mgr.policy.budget_leaves,
                                     theta_down=0.4)
    elif arm == "dwell":
        mgr.min_dwell_ticks = 60

    history = {}
    gaps = []
    for tick in range(1, ticks + 1):
        for cid in sorted(mgr.store.clusters):
            draw = random.Random(f"{seed}:{tick}:{cid}").random()
            mgr.set_attention(cid, max(0.0, min(1.0, jitter + amp * (draw - 0.5))))
        engine.step()
        for cid, when in mgr._last_switch.items():
            if history.get(cid) != when:
                if cid in history:
                    gaps.append(when - history[cid])
                history[cid] = when

    tel = mgr.telemetry()
    totals = {"real": [0.0, 0.0, 0.0], "expected": [0.0, 0.0, 0.0]}
    blocked = 0
    for entry in tel.values():
        blocked += entry.get("blocked", 0)
        for i, key in enumerate(("births", "deaths", "marriages")):
            totals["real"][i] += entry["real"][key]
            totals["expected"][i] += entry["expected"][key]
    clusters_with_switches = sum(1 for entry in tel.values() if entry.get("switches"))
    return {
        "switches": mgr.switch_total,
        "blocked": blocked,
        "clusters_with_switches": clusters_with_switches,
        "gaps": gaps,
        "telemetry": totals,
        "tel_entries": len(tel),
        "population": engine.population(),
    }


def main():
    parser = argparse.ArgumentParser(description="分辨率换档动力学（描述性）")
    parser.add_argument("--ticks", type=int, default=600)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--capacity", type=int, default=120)
    parser.add_argument("--population", type=int, default=2000)
    parser.add_argument("--families", type=int, default=4, help="初始家庭共演单元数")
    parser.add_argument("--jitter", type=float, default=0.45, help="抖动观测的中心值")
    parser.add_argument("--jitter-amp", type=float, default=0.12, help="抖动幅值")
    args = parser.parse_args()

    print(f"换档动力学（抖动观测者；ticks={args.ticks}，families={args.families}，"
          f"jitter={args.jitter}±{args.jitter_amp / 2:.2f}，θ=0.5）\n")
    print(f"  {'arm':<12}{'switches':>10}{'blocked':>9}{'有换档簇':>10}{'驻留min':>9}{'驻留中位':>10}"
          f"{'遥测 real(b/d/m)':>20}{'expected(b/d/m)':>20}")
    for arm in ("baseline", "hysteresis", "dwell"):
        result = _run(arm, args.ticks, args.jitter, args.jitter_amp, args.seed,
                      args.capacity, args.population, args.families)
        gaps = result["gaps"]
        gap_min = min(gaps) if gaps else None
        gap_med = statistics.median(gaps) if gaps else None
        real = "/".join(f"{v:.0f}" for v in result["telemetry"]["real"])
        expected = "/".join(f"{v:.1f}" for v in result["telemetry"]["expected"])
        gap_min_s = "—" if gap_min is None else str(gap_min)
        gap_med_s = "—" if gap_med is None else f"{gap_med:.0f}"
        print(f"  {arm:<12}{result['switches']:>10}{result['blocked']:>9}"
              f"{result['clusters_with_switches']:>10}"
              f"{gap_min_s:>9}{gap_med_s:>10}{real:>20}{expected:>20}")
    print()
    print("判读提示：一次换档 = 一次身份重采样（materialize 生成新代表）+ 池/残差簿记；")
    print("`blocked` = 物化被卡（mini 里没有可析出的整人桶）；adr-010 整数语义修复后生产路径期望 ≈ 0。")
    print("本工具描述性——三臂同一抖动观测流，差异只来自换档纪律；不作门槛、不作证据级结论。")


if __name__ == "__main__":
    main()
