"""跨分辨率婚配规则 A/B（ADR-007 / L3 N2-7）。

同一 seed 跑两遍：
- **off**：`RULES` 空（默认，生产口径）；
- **on**：注册 `MarriageRule`。

输出跨婚配次数、窗口已婚比例、人口、丢弃分布；并在 **on** 臂上逐次核对通道操作的
人头守恒与财富守恒（`W = Σ_测度 wealth() + Σ 窗口 wealth`，见 ADR-006）。

`--scope measure` = 大众婚配（候选 = 全局测度；生产规则 `MarriageRule(target="measure")`）。

用法：
    python -m bench.channel_marriage --ticks 1500 --capacity 200 --population 1200
    python -m bench.channel_marriage --scope measure --seed-family 0 --ticks 3000
"""
import argparse
import random

from app.core.measure.channel import RULES
from app.core.measure.engine import MeanFieldEngine
from app.core.measure.rules import MarriageRule
from app.core.measure.transitions import FULL_FLOWS
from app.core.measure.window import WindowEngine
from bench.world import make_characters


def _build(seed, capacity, population, seed_family=0):
    """构造世界；``seed_family>0`` 时**预置一个 coarse 族**（A/B 两臂相同），保证规则有靶子。

    预置是"直接塞进 mini"的**合成基线**（两侧等价），只为让 A/B 有意义；不是生产路径。
    """
    random.seed(seed)
    mf = MeanFieldEngine(characters=make_characters(population, seed=seed), flows=FULL_FLOWS)
    engine = WindowEngine(mf, capacity=capacity, window=capacity, resolution=True,
                          rng=random.Random(seed))
    if seed_family > 0:
        space = engine.window.space
        mgr = engine.resolution
        cluster = mgr.store.create("family", set())
        mgr.store.coarsen(cluster.id)
        mini = cluster.state["engine"].measure
        mini.add(space.encode(30, 0, 10, 0), float(seed_family))   # 未婚成年人
        cluster.state["size"] = mini.total()
        mgr.attention[cluster.id] = 0.2     # < theta_base：保持 coarse
        mgr.gamma = 1.0                     # 关衰减：靶子不自行消失
    return engine


def _population(engine):
    return (engine.measure_engine.measure.total()
            + engine.resolution.store.size()
            + len(engine.window.characters))


def _wealth(engine):
    total = engine.measure_engine.measure.wealth()
    for cluster in engine.resolution.store.clusters.values():
        inner = cluster.state.get("engine")
        if inner is not None:
            total += inner.measure.wealth()
    total += sum(c.wealth for c in engine.window.characters.values())
    return total


def _run(ticks, seed, capacity, population, enable, rate=None, seed_family=0,
         scope="cluster", verbose=True):
    engine = _build(seed, capacity, population, seed_family=seed_family)
    rules = []
    if enable:
        targets = {"cluster": ("cluster",), "measure": ("measure",),
                   "both": ("cluster", "measure")}[scope]
        for target in targets:
            rules.append(MarriageRule(rate=rate, target=target))
        for rule in rules:
            RULES[rule.name] = rule
    channel = engine.resolution.channel
    worst = {"pop": 0.0, "wealth": 0.0, "calls": 0}
    original_run = channel.run

    def checked(ctx):
        pop0, wealth0 = _population(engine), _wealth(engine)
        result = original_run(ctx)
        dev_pop = _population(engine) - pop0
        dev_wealth = _wealth(engine) - wealth0
        worst["calls"] += 1
        worst["pop"] = max(worst["pop"], abs(dev_pop))
        worst["wealth"] = max(worst["wealth"], abs(dev_wealth))
        assert abs(dev_pop) < 1e-6, f"channel.run 泄漏人头 {dev_pop:+.6g}"
        assert abs(dev_wealth) < 1e-6 * max(1.0, abs(wealth0)), \
            f"channel.run 泄漏财富 {dev_wealth:+.6g}"
        return result

    channel.run = checked
    try:
        for _ in range(ticks):
            engine.step()
    finally:
        for rule in rules:
            RULES.pop(rule.name, None)

    ledger = list(channel.ledger)
    crossings = [r for r in ledger if r.status == "ok" and r.kind == "spouse"]
    crossings_cluster = sum(1 for r in crossings if r.scope[0] == "cluster")
    crossings_measure = sum(1 for r in crossings if r.scope[0] == "measure")
    married = sum(1 for c in engine.window.characters.values()
                  if c.relationships.get("spouse"))
    drops = {}
    for record in ledger:
        if record.status.startswith("dropped"):
            drops[record.status] = drops.get(record.status, 0) + 1
    result = {
        "crossings": len(crossings),
        "crossings_cluster": crossings_cluster,
        "crossings_measure": crossings_measure,
        "married_frac": married / max(1, len(engine.window.characters)),
        "population": _population(engine),
        "window": len(engine.window.characters),
        "clusters": len(engine.resolution.store.clusters),
        "drops": drops,
        "worst_pop": worst["pop"],
        "worst_wealth": worst["wealth"],
        "calls": worst["calls"],
    }
    if verbose:
        print(f"  crossings={result['crossings']}（族 {crossings_cluster} / 众 {crossings_measure}） "
              f"married_frac={result['married_frac']:.3f} "
              f"pop={result['population']:.0f} window={result['window']} "
              f"clusters={result['clusters']} drops={drops or '{}'}")
        print(f"  channel ops={result['calls']}  worst |Δpop|={worst['pop']:.2e}  "
              f"worst |ΔW|={worst['wealth']:.2e}")
    return result


def main():
    parser = argparse.ArgumentParser(description="Cross-resolution marriage rule A/B")
    parser.add_argument("--ticks", type=int, default=1500)
    parser.add_argument("--capacity", type=int, default=200)
    parser.add_argument("--population", type=int, default=1200)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--rate", type=float, default=None, help="覆盖 MARRIAGE_RATE")
    parser.add_argument("--seed-family", type=int, default=50,
                        help="预置 coarse 族的未婚成年人数（A/B 两臂相同；0 = 不预置）")
    parser.add_argument("--scope", choices=["cluster", "measure", "both"], default="cluster",
                        help="婚配候选侧：cluster=coarse 簇（生产规则）；measure=全局测度（大众）；"
                             "both=两条并存（adr-012）")
    args = parser.parse_args()

    print(f"ticks={args.ticks} capacity={args.capacity} population={args.population} "
          f"seed={args.seed} seed_family={args.seed_family} scope={args.scope}")
    print("off（RULES 空，生产口径）:")
    off = _run(args.ticks, args.seed, args.capacity, args.population, enable=False,
               seed_family=args.seed_family)
    print("on（SIM_CHANNEL_MARRIAGE=1 等价）:")
    on = _run(args.ticks, args.seed, args.capacity, args.population, enable=True,
              rate=args.rate, seed_family=args.seed_family, scope=args.scope)

    print(f"Δcrossings = {on['crossings'] - off['crossings']}   "
          f"Δmarried_frac = {on['married_frac'] - off['married_frac']:+.3f}   "
          f"Δpop = {on['population'] - off['population']:+.1f}")
    if on["crossings"] == 0:
        print("⚠️  开启臂没有产出跨婚配（窗口/族结构不足）——调大 --ticks 或 --capacity")
    identity = max(on["worst_pop"], on["worst_wealth"])
    print(f"identity (on 臂逐次操作) = {identity:.3e}（人头 + 财富，浮点级）")


if __name__ == "__main__":
    main()
