"""跨分辨率婚配规则的校准实验（ADR-007 跟进项）。

问题：规则开启 = **新增一条婚配通量**（窗口自己的婚配事件照常跑）⇒ 全人口已婚比例会被抬高。
本工具扫 rate，回答两件事：

1. 关规则时，measure 模式（测度 + 共演单元 + 窗口）的已婚比例与**个体引擎参照**差多少？
2. 开规则后，这个差是变大还是变小？哪个 rate 最接近参照？

口径（**成年人** `18 ≤ age < 60`，三个臂同规模同 seed）：
- 参照 = `EventEngine`（个体引擎，语义真值）在 `N` 人上跑 `ticks`；
- measure = `MeanFieldEngine(N) + WindowEngine(capacity=C)`，**合并**统计
  （全局测度 + 各簇 mini + 窗口角色）；规则按 rate 注册 / 不注册。

注意：这不是"开规则必须收敛"的验收——规则是**扩展**；本工具只给数字，供拍板
"要不要开、开到什么强度"。

`--scope measure` = **大众婚配测量臂**：候选 = 全局测度（匿名大众）而非 coarse 簇
（实验脚手架 `bench/probe_rules.py::MassMarriageRule`；采纳与否属独立决策）。

用法：
    python -m bench.calibrate_marriage --population 1500 --capacity 300 --ticks 2000
"""
import argparse
import random

from app.core.measure.channel import RULES
from app.core.measure.engine import MeanFieldEngine
from app.core.measure.rules import MarriageRule
from app.core.measure.transitions import FULL_FLOWS, MARRIAGE_RATE
from app.core.measure.window import WindowEngine
from bench.probe_rules import MassMarriageRule
from bench.world import build_engine, make_characters


def _adult(age):
    return 18 <= age < 60


def individual_stats(engine):
    """个体引擎（语义真值）的人口 / 成年已婚比例。"""
    population = adults = married = 0
    for character in engine.characters.values():
        population += 1
        if _adult(character.age):
            adults += 1
            if character.relationships.get("spouse"):
                married += 1
    return _pack(population, adults, married)


def _measure_headcount(measure, acc):
    space = measure.space
    for index in measure.occupied:
        count = measure.counts[index]
        if count <= 0:
            continue
        age, _gender, _wealth, marital = space.decode(index)
        acc["population"] += count
        if _adult(age):
            acc["adults"] += count
            acc["married"] += count if marital == 1 else 0.0


def measure_stats(engine):
    """measure 模式：全局测度 + 各簇 mini + 窗口角色 的**合并**人口。"""
    acc = {"population": 0.0, "adults": 0.0, "married": 0.0,
           "window": len(engine.window.characters), "window_married": 0,
           "clusters": len(engine.resolution.store.clusters)}
    _measure_headcount(engine.measure_engine.measure, acc)
    for cluster in engine.resolution.store.clusters.values():
        inner = cluster.state.get("engine")
        if inner is not None:
            _measure_headcount(inner.measure, acc)
    for character in engine.window.characters.values():
        acc["population"] += 1
        if _adult(character.age):
            acc["adults"] += 1
            if character.relationships.get("spouse"):
                acc["married"] += 1
                acc["window_married"] += 1
    acc["married_frac_adults"] = acc["married"] / acc["adults"] if acc["adults"] else 0.0
    return acc


def _pack(population, adults, married):
    return {"population": float(population), "adults": float(adults),
            "married": float(married),
            "married_frac_adults": (married / adults) if adults else 0.0}


def run_reference(population, ticks, seed, verbose=True):
    random.seed(seed)
    engine = build_engine(population, seed=seed, engine="event")
    for _ in range(ticks):
        engine.step()
    stats = individual_stats(engine)
    if verbose:
        print(f"  reference   pop={stats['population']:.0f} adults={stats['adults']:.0f} "
              f"married_frac(adults)={stats['married_frac_adults']:.4f}")
    return stats


class _NullRule:
    """对照：**会占 headroom**（`emits_bind=True`）但一个意图都不发。

    用来把"规则注册"的两个效应分开：`off` vs `null` = `headroom_reserve` 效应；
    `null` vs `on` = **规则语义**效应（真正的通量）。
    """

    name = "null_bind"
    emits_bind = True

    def offers(self, context):
        return []


def _seed_family_pool(engine, size, space):
    """预置一个 coarse 族（未婚成年人），作为"部落内可婚配对象"的合成代理。"""
    if size <= 0:
        return None
    mgr = engine.resolution
    cluster = mgr.store.create("family", set())
    mgr.store.coarsen(cluster.id)
    mini = cluster.state["engine"].measure
    mini.add(space.encode(30, 0, 10, 0), float(size))
    cluster.state["size"] = mini.total()
    mgr.attention[cluster.id] = 0.2
    mgr.gamma = 1.0
    return cluster


def run_measure(population, capacity, ticks, seed, rate=None, null_rule=False,
                family_pool=0, scope="cluster", verbose=True):
    """rate=None ⇒ 不注册婚配规则；``null_rule=True`` ⇒ 注册占名额但不发意图的对照规则。

    ``scope="measure"`` ⇒ 用大众婚配探针规则（候选 = 全局测度，实验臂）；默认 ``"cluster"``。
    """
    random.seed(seed)
    mf = MeanFieldEngine(characters=make_characters(population, seed=seed), flows=FULL_FLOWS)
    engine = WindowEngine(mf, capacity=capacity, window=capacity, resolution=True,
                          rng=random.Random(seed))
    _seed_family_pool(engine, family_pool, engine.window.space)
    rule = None
    if null_rule:
        rule = _NullRule()
    elif rate is not None:
        # 规则用**自有**流（不与窗口个体事件争 rng），否则 A/B 被随机流偏移污染（2026-10-18）。
        rule_cls = MassMarriageRule if scope == "measure" else MarriageRule
        rule = rule_cls(rate=rate, rng=random.Random(f"calib-marriage:{seed}"))
    if rule is not None:
        RULES[rule.name] = rule
    try:
        for _ in range(ticks):
            engine.step()
        stats = measure_stats(engine)
        crossings = sum(1 for r in engine.resolution.channel.ledger
                        if r.status == "ok" and r.kind == "spouse")
        drops = {}
        for record in engine.resolution.channel.ledger:
            if record.status.startswith("dropped"):
                drops[record.status] = drops.get(record.status, 0) + 1
    finally:
        if rule is not None:
            RULES.pop(rule.name, None)
    stats["crossings"] = crossings
    stats["drops"] = drops
    if verbose:
        if null_rule:
            label = "null（占名额不发意图）"
        elif rate is None:
            label = "off（生产口径）"
        else:
            label = f"rate={rate:.2e} ({rate / MARRIAGE_RATE:.2f}×)"
        print(f"  measure {label:<22} pop={stats['population']:.0f} "
              f"married_frac(adults)={stats['married_frac_adults']:.4f} "
              f"window_married={stats['window_married']}/{stats['window']} "
              f"clusters={stats['clusters']} crossings={crossings} "
              f"drops={drops or '{}'}")
    return stats


def main():
    parser = argparse.ArgumentParser(description="Cross-resolution marriage rule calibration")
    parser.add_argument("--population", type=int, default=1500)
    parser.add_argument("--capacity", type=int, default=300)
    parser.add_argument("--ticks", type=int, default=2000)
    parser.add_argument("--seeds", type=int, nargs="+", default=[1, 2])
    parser.add_argument("--rates", type=float, nargs="+", default=None,
                        help="相对 MARRIAGE_RATE 的倍数（默认 0.25 0.5 1 2）")
    parser.add_argument("--family-pool", type=int, default=200,
                        help="measure 臂预置的 coarse 族未婚成年人数（合成代理；0=不预置）")
    parser.add_argument("--scope", choices=["cluster", "measure"], default="cluster",
                        help="婚配候选侧：cluster=coarse 簇（生产规则）；"
                             "measure=全局测度（大众婚配测量臂）")
    args = parser.parse_args()
    multipliers = args.rates or [0.25, 0.5, 1.0, 2.0]

    ref, off, null = [], [], []
    arms = {m: [] for m in multipliers}
    for seed in args.seeds:
        print(f"seed={seed}  N={args.population} C={args.capacity} ticks={args.ticks} "
              f"family_pool={args.family_pool} scope={args.scope}")
        ref.append(run_reference(args.population, args.ticks, seed))
        off.append(run_measure(args.population, args.capacity, args.ticks, seed, rate=None,
                               family_pool=args.family_pool))
        null.append(run_measure(args.population, args.capacity, args.ticks, seed,
                                null_rule=True, family_pool=args.family_pool))
        for m in multipliers:
            arms[m].append(run_measure(args.population, args.capacity, args.ticks, seed,
                                       rate=m * MARRIAGE_RATE,
                                       family_pool=args.family_pool, scope=args.scope))

    def mean(rows, key):
        return sum(r[key] for r in rows) / len(rows)

    ref_mf = mean(ref, "married_frac_adults")
    off_mf = mean(off, "married_frac_adults")
    null_mf = mean(null, "married_frac_adults")
    print(f"\n参考（个体引擎）已婚比例(成年人) = {ref_mf:.4f}")
    print(f"{'arm':<24}{'married_frac':>14}{'Δ vs ref':>12}{'Δ vs null':>12}{'crossings':>12}")
    for label, rows_ in ([("off（生产口径）", off), ("null（占名额不发意图）", null)]
                         + [(f"{m:.2f}× MARRIAGE_RATE", arms[m]) for m in multipliers]):
        mf = mean(rows_, "married_frac_adults")
        print(f"{label:<24}{mf:>14.4f}{mf - ref_mf:>+12.4f}{mf - null_mf:>+12.4f}"
              f"{mean(rows_, 'crossings'):>12.1f}")
    print()
    print(f"→ headroom 效应（null − off）      = {null_mf - off_mf:+.4f}"
          "（只注册规则、不发意图就会有的偏移）")
    print(f"→ 规则语义效应（on − null，看各档）= 见 Δ vs null 列（真正的婚配通量）")
    if off_mf >= ref_mf:
        print("→ 关规则时 measure 已婚比例已 **不低于** 参照：正 rate 只会把它推得更高")
    else:
        print("→ 关规则时 measure 已婚比例 **低于** 参照：正 rate 是「补差」方向")


if __name__ == "__main__":
    main()
