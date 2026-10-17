"""财富守恒审计：核对 mf 期末报告财富 == 初始 + 收入 + 出生桶值 - 死亡蒸发(90%)。

体感意义：transfer 类算子（继承/婚配/衰老）只应移动桶，不得改变总量；
任何"注水/重复记账"都会在这个恒等式上现形。继承算子的支付账本等
改动后的第一件事就是跑它（tests 里也有小规模门禁版）。

用法：
    python -m bench.audit_ledger --n 5000 --steps 8000 --seed 42
"""
import argparse
import random

from app.core.measure import transitions as T
from app.core.measure.engine import MeanFieldEngine
from app.core.measure.measure import measure_from_characters
from app.core.measure.space import StateSpace
from bench.world import make_characters


def wealth_total(measure, space):
    total = 0.0
    for index in measure.occupied:
        age, gender, wealth, marital = space.decode(index)
        total += measure.counts[index] * space.wealth_value(wealth)
    return total


def run_audit(n, steps, seed=42, max_error_frac=1e-3):
    """跑一遍 mf 全流并核对守恒恒等式；返回账本 dict。

    identity：final + 段池余量 == 初始 + Σ收入 + Σ出生桶值 - 死者×0.9。
    收入/出生按"流前后财富差分"计量（与生产算子同一口径，边界相位无歧义）；
    账面误差超过 max_error_frac 时抛 RuntimeError（测试门禁与 CI 共用）。
    """
    space = StateSpace()
    random.seed(seed)
    measure = measure_from_characters(make_characters(n, seed=seed), space)
    mf = MeanFieldEngine(space=space, measure=measure, flows=T.FULL_FLOWS)

    audit = {"income": 0.0, "evap": 0.0, "birth_value": 0.0, "birth_count": 0.0}
    original_inheritance = T.inheritance
    original_income = T.income
    original_birth = T.birth

    def income_wrapped(measure_, tick):
        before = wealth_total(measure_, measure_.space)
        result = original_income(measure_, tick)
        after = wealth_total(measure_, measure_.space)
        audit["income"] += after - before
        return result

    def birth_wrapped(measure_, tick):
        before = measure_.total()
        result = original_birth(measure_, tick)
        delta = measure_.total() - before
        audit["birth_count"] += delta
        audit["birth_value"] += delta * 500.0  # bucket 0 的中心值
        return result

    def inheritance_wrapped(measure_, tick):
        for age, wealth, amount in (measure_.recent_deaths or []):
            audit["evap"] += amount * measure_.space.wealth_value(wealth) * 0.9
        return original_inheritance(measure_, tick)

    mf.flows = (T.aging, income_wrapped, T.death, T.marriage, birth_wrapped, inheritance_wrapped)

    initial = wealth_total(mf.measure, space)
    for _ in range(steps):
        mf.step()

    final = wealth_total(mf.measure, space)
    expected = initial + audit["income"] + audit["birth_value"] - audit["evap"]
    pool_residual = float(sum(mf.measure.yearly_inherited.values()))
    error = final - expected + pool_residual
    error_frac = error / final if final else 0.0

    result = {
        "initial": initial, "final": final, "expected": expected,
        "income": audit["income"], "evap": audit["evap"],
        "birth_value": audit["birth_value"], "birth_count": audit["birth_count"],
        "pool_residual": pool_residual, "error": error, "error_frac": error_frac,
    }
    if abs(error_frac) > max_error_frac:
        raise RuntimeError(f"wealth ledger leak: {error_frac:+.4%} (audit={result})")
    return result


def run_cluster_audit(n=2000, steps=3000, capacity=300, seed=42, max_error=1e-6):
    """窗口 + 共演单元 的分辨率守恒审计。

    关闭全局测度流算子，并把 coarse 共演单元的流算子限制为**质量保持**集合
    （aging/income/marriage/inheritance；去掉 birth/death），于是唯一改变总量的
    是窗口个体引擎的出生/死亡：

        measure + Σ_coarse size + len(window) == 初始 + 窗口出生 − 窗口死亡

    分辨率操作（materialize / coarsen / dissolve / merge / refill）必须逐一守恒。
    """
    from app.core.measure.cluster import KINDS
    from app.core.measure.window import WindowEngine

    space = StateSpace()
    random.seed(seed)
    mf = MeanFieldEngine(space=space, characters=make_characters(n, seed=seed), flows=())
    engine = WindowEngine(mf, capacity=capacity, window=capacity, resolution=True)

    saved = KINDS["family"].flows
    KINDS["family"].flows = (T.aging, T.income, T.marriage)  # 质量保持（继承在 step_coarse 内处理）
    try:
        def total():
            return (mf.measure.total() + engine.resolution.store.size()
                    + len(engine.window.characters))

        initial = total()
        for _ in range(steps):
            engine.step()
        final = total()
        expected = initial + engine.window.stats["births"] - engine.window.stats["deaths"]
        error = final - expected
        error_frac = error / final if final else 0.0
        result = {
            "initial": initial, "final": final, "expected": expected,
            "window_births": engine.window.stats["births"],
            "window_deaths": engine.window.stats["deaths"],
            "error": error, "error_frac": error_frac,
            "rho": engine.resolution.store.rho(),
            "clusters": len(engine.resolution.store.clusters),
        }
        if abs(error_frac) > max_error:
            raise RuntimeError(f"cluster mass leak: {error_frac:+.4%} (audit={result})")
        return result
    finally:
        KINDS["family"].flows = saved


def run_resolution_probe(n=1500, steps=2500, capacity=250, seed=5, tol=1e-6):
    """分辨率算子守恒探针（**生产口径**：coarse 流含 death/birth）。

    与 ``run_cluster_audit`` 互补：后者把 coarse 流限成质量保持集合以简化恒等式，
    因而**结构上**看不到"分数桶物化"泄漏；本探针在真实流算子下对每个分辨率算子
    （materialize / coarsen / merge / dissolve / materialize_sample）逐次断言：
    它们不产生/销毁个体、只移动计数 ⟹ 每次调用前后
    ``global_measure + Σ_coarse + window`` 必须不变（浮点容差内）。

    为覆盖"粗化 → coarse 演化出分数桶 → 再物化"这条路径，周期性地在 0.3（粗化但不回收）
    与 1.0（再物化）之间切换注意力。返回 ``{calls, worst_op, worst_dev}``；泄漏即抛错。
    """
    from app.core.measure.window import WindowEngine

    space = StateSpace()
    random.seed(seed)
    mf = MeanFieldEngine(space=space, characters=make_characters(n, seed=seed))
    engine = WindowEngine(mf, capacity=capacity, window=capacity, resolution=True)
    engine.resolution.endogenous_scale = None   # 由探针显式驱动注意力
    window = engine.window
    store = engine.resolution.store

    def total():
        return mf.measure.total() + store.size() + len(window.characters)

    worst = {"calls": 0, "worst_op": None, "worst_dev": 0.0}

    def instrument(obj, name):
        original = getattr(obj, name)

        def checked(*args, **kwargs):
            before = total()
            result = original(*args, **kwargs)
            dev = total() - before
            worst["calls"] += 1
            if abs(dev) > abs(worst["worst_dev"]):
                worst["worst_op"], worst["worst_dev"] = name, dev
            if abs(dev) > tol:
                raise RuntimeError(f"resolution op '{name}' leaked {dev:+.6g} mass")
            return result

        setattr(obj, name, checked)

    targets = [(store, "materialize"), (store, "coarsen"), (store, "merge"),
               (store, "dissolve"), (window, "materialize_sample"), (window, "materialize")]
    saved = [(obj, name, getattr(obj, name)) for obj, name in targets]
    try:
        for obj, name in targets:
            instrument(obj, name)
        for step in range(steps):
            engine.step()
            if step % 40 == 0:                     # 驱动 粗化 ⇄ 再物化 循环
                level = 0.3 if (step // 40) % 2 == 0 else 1.0
                for cid in list(store.clusters):
                    engine.resolution.set_attention(cid, level)
    finally:
        for obj, name, original in saved:
            setattr(obj, name, original)
    if worst["calls"] == 0:
        raise RuntimeError("resolution probe exercised no operations")
    return worst


def run_wealth_probe(n=1200, steps=2000, capacity=200, seed=5, tol_abs=1e-6, tol_rel=1e-9):
    """分辨率折算的财富恒等式探针（ADR-006 / L4 N2-5）。

    对每个分辨率算子（materialize / materialize_sample / coarsen / merge / split / dissolve /
    dematerialize / refill 经 materialize_sample / channel.run / unbind）逐次断言

        W = Σ_测度 wealth() + Σ_窗口 wealth

    前后不变（`measure.wealth()` 已含桶质量 + 两个池 + 折算残差），容差
    ``max(tol_abs, tol_rel·W)``（浮点级）。返回 ``{calls, worst_op, worst_dev}``；泄漏即抛错。
    """
    from app.core.measure.window import WindowEngine

    space = StateSpace()
    random.seed(seed)
    mf = MeanFieldEngine(space=space, characters=make_characters(n, seed=seed))
    engine = WindowEngine(mf, capacity=capacity, window=capacity, resolution=True)
    window = engine.window
    mgr = engine.resolution
    store = mgr.store

    def total():
        acc = mf.measure.wealth()
        for cluster in store.clusters.values():
            inner = cluster.state.get("engine")
            if inner is not None:
                acc += inner.measure.wealth()
        acc += sum(character.wealth for character in window.characters.values())
        return acc

    worst = {"calls": 0, "worst_op": None, "worst_dev": 0.0, "worst_tol": 0.0}

    def instrument(obj, name):
        original = getattr(obj, name)

        def checked(*args, **kwargs):
            before = total()
            result = original(*args, **kwargs)
            after = total()
            dev = after - before
            tol = max(tol_abs, tol_rel * max(1.0, abs(before)))
            worst["calls"] += 1
            if abs(dev) / tol > worst["worst_dev"] / max(worst["worst_tol"], tol):
                worst["worst_op"] = f"{type(obj).__name__}.{name}"
                worst["worst_dev"] = dev
                worst["worst_tol"] = tol
            if abs(dev) > tol:
                raise RuntimeError(
                    f"resolution wealth leak at {name}: ΔW={dev:+.6g} (tol {tol:.3g})")
            return result

        setattr(obj, name, checked)

    targets = [(store, "materialize"), (store, "coarsen"), (store, "merge"),
               (store, "dissolve"), (window, "materialize"),
               (window, "materialize_sample"), (window, "dematerialize"),
               (mgr.channel, "run"), (mgr.channel, "unbind")]
    saved = [(obj, name, getattr(obj, name)) for obj, name in targets]
    try:
        for obj, name in targets:
            instrument(obj, name)
        for step in range(steps):
            engine.step()
            if step % 40 == 0:                     # 驱动 粗化 ⇄ 再物化 循环
                level = 0.3 if (step // 40) % 2 == 0 else 1.0
                for cid in list(store.clusters):
                    mgr.set_attention(cid, level)
    finally:
        for obj, name, original in saved:
            setattr(obj, name, original)
    if worst["calls"] == 0:
        raise RuntimeError("wealth probe exercised no operations")
    return worst


def main():
    parser = argparse.ArgumentParser(description="Wealth conservation audit for mean-field engine")
    parser.add_argument("--n", type=int, default=5000)
    parser.add_argument("--steps", type=int, default=8000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--clusters", action="store_true", help="改跑 窗口+共演单元 的分辨率守恒审计")
    parser.add_argument("--resolution", action="store_true", help="改跑分辨率算子守恒探针（生产口径）")
    parser.add_argument("--wealth", action="store_true",
                        help="改跑分辨率折算的财富恒等式探针（ADR-006，逐算子 W）")
    parser.add_argument("--capacity", type=int, default=300)
    args = parser.parse_args()

    if args.wealth:
        result = run_wealth_probe(n=args.n, steps=args.steps, capacity=args.capacity, seed=args.seed)
        print(f"resolution wealth ops checked = {result['calls']}")
        print(f"worst = {result['worst_op']}   ΔW = {result['worst_dev']:+.3e}   "
              f"tol = {result['worst_tol']:.3e}")
        print("identity error = 0 (逐算子 W 中性，容差 = max(1e-6, 1e-9·W))")
        return

    if args.resolution:
        result = run_resolution_probe(n=args.n, steps=args.steps, capacity=args.capacity, seed=args.seed)
        print(f"resolution ops checked = {result['calls']}")
        print(f"worst = {result['worst_op']}   dev = {result['worst_dev']:+.3e}")
        print("identity error = 0 (每个算子逐次守恒)")
        return

    if args.clusters:
        result = run_cluster_audit(n=args.n, steps=args.steps, capacity=args.capacity, seed=args.seed)
        print(f"initial = {result['initial']:.6e}")
        print(f"window births/deaths = {result['window_births']:.0f}/{result['window_deaths']:.0f}")
        print(f"expected= {result['expected']:.6e}")
        print(f"final   = {result['final']:.6e}")
        print(f"clusters = {result['clusters']}   rho = {result['rho']:.3f}")
        print(f"identity error = {result['error']:+.3e}  ({result['error_frac']:+.4%})")
        return

    result = run_audit(args.n, args.steps, args.seed)
    print(f"initial = {result['initial']:.6e}")
    print(f"income  = {result['income']:.6e}")
    print(f"births  = {result['birth_count']:.1f} (value {result['birth_value']:.6e})")
    print(f"evap(90%) = {result['evap']:.6e}")
    print(f"expected= {result['expected']:.6e}")
    print(f"final   = {result['final']:.6e}")
    print(f"pool residual = {result['pool_residual']:.6e}")
    print(f"identity error = {result['error']:+.3e}  ({result['error_frac']:+.4%})")


if __name__ == "__main__":
    main()
