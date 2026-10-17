"""质量侧 `transfer` 的财富恒等审计（ADR-005 / L3 N2-6）。

脚本化地跑一遍 transfer 的全部路径，并在**每一步前后**核对

    W = 全局 measure + Σ 簇 mini + Σ transfer_pool + Σ yearly_inherited + Σ 窗口 wealth
        （每项 count×桶中心）

R→C → C→R（池够）→ C→R（需清算）→ 账户不足 / 无流动性丢弃 → 年度投递 → dissolve 折叠。

注意：族群是**预先播种**的（直接 `mini.add` 造已知桶），基线 W 取播种之后的值——
本工具核对的是"transfer 及其结算是否守恒"，不是模型的其他流。

用法：
    python -m bench.audit_transfer
"""
import argparse
import math
import random

from app.core.measure.channel import Intent, Match
from app.core.measure.cluster import TickContext
from app.core.measure.engine import MeanFieldEngine
from app.core.measure.space import StateSpace
from app.core.measure.transitions import FULL_FLOWS
from app.core.measure.window import WindowEngine
from bench.world import make_characters


def world_wealth(engine):
    total = engine.measure_engine.measure.wealth()
    for cluster in engine.resolution.store.clusters.values():
        obj = cluster.state.get("engine")
        if obj is not None:
            total += obj.measure.wealth()
    total += sum(c.wealth for c in engine.window.characters.values())
    return total


def _build(seed=3, n=400, capacity=60, window=20):
    space = StateSpace()
    mf = MeanFieldEngine(characters=make_characters(n, seed=seed), flows=FULL_FLOWS)
    engine = WindowEngine(mf, capacity=capacity, window=window, resolution=True,
                          rng=random.Random(7))
    store = engine.resolution.store
    cluster = store.create("family", set())
    store.coarsen(cluster.id)
    mini = cluster.state["engine"].measure
    mini.add(space.encode(30, 0, 10, 0), 3.0)     # 3 人 @ 10500
    mini.add(space.encode(31, 0, 5, 0), 1.0)      # 1 人 @ 5500
    cluster.state["size"] = mini.total()
    rich = max(engine.window.characters.values(), key=lambda c: c.wealth)
    rich.wealth = 1.0e7
    return engine, cluster, rich, space


def run(seed=3, tol=1e-6, verbose=True):
    engine, cluster, rich, space = _build(seed=seed)
    channel = engine.resolution.channel
    mini = cluster.state["engine"].measure
    checks = []

    def ctx(tick=0):
        return TickContext(tick=tick, measure=engine.measure_engine.measure, rng=engine.rng)

    def step(label, submit):
        before = world_wealth(engine)
        submit()
        report = channel.run(ctx())
        err = world_wealth(engine) - before
        checks.append((label, err, report.get("by_status", {})))
        return report

    step("R→C 2500", lambda: channel.submit(
        Intent(op="transfer", kind="gift", origin=("character", rich.id),
               scope=("cluster", cluster.id), match=Match(), payload={"amount": 2500.0})))
    step("C→R 500（池够）", lambda: channel.submit(
        Intent(op="transfer", kind="grant", origin=("cluster", cluster.id),
               scope=("window",), match=Match(age=(0, 120)), payload={"amount": 500.0})))
    step("C→R 6000（需清算）", lambda: channel.submit(
        Intent(op="transfer", kind="grant", origin=("cluster", cluster.id),
               scope=("window",), match=Match(age=(0, 120)), payload={"amount": 6000.0})))
    step("C→R 1e12（不足）", lambda: channel.submit(
        Intent(op="transfer", kind="grant", origin=("cluster", cluster.id),
               scope=("window",), match=Match(age=(0, 120)), payload={"amount": 1e12})))
    step("R→C 1e12（个体不足）", lambda: channel.submit(
        Intent(op="transfer", kind="gift", origin=("character", rich.id),
               scope=("cluster", cluster.id), match=Match(), payload={"amount": 1e12})))
    step("R→C 1500（备投递）", lambda: channel.submit(
        Intent(op="transfer", kind="gift", origin=("character", rich.id),
               scope=("cluster", cluster.id), match=Match(), payload={"amount": 1500.0})))

    # 年度投递（直接调内部结算，避免空跑整世界）
    before = world_wealth(engine)
    engine.resolution._settle_transfer_pools(360)
    checks.append(("年度投递 (t=360)", world_wealth(engine) - before, {}))

    # dissolve 折叠
    before = world_wealth(engine)
    assert engine.resolution.store.dissolve(cluster.id) is True
    checks.append(("dissolve 折叠", world_wealth(engine) - before, {}))

    worst = max((abs(err) for _, err, _ in checks), default=0.0)
    pool_ok = channel.pool_total() >= -1e-9

    if verbose:
        print(f"seed = {seed}   rich.wealth = {rich.wealth:.1f}")
        for label, err, status in checks:
            print(f"  {label:<22} ΔW = {err:+.3e}    {status or ''}")
        print(f"worst |ΔW| = {worst:.3e}   pool_total = {channel.pool_total():.6f}   "
              f"pool ≥ 0: {pool_ok}")

    if worst > tol:
        raise RuntimeError(f"transfer wealth ledger leak: worst |ΔW| = {worst:.3e}")
    if not pool_ok:
        raise RuntimeError("transfer pool went negative")
    if math.isnan(worst):
        raise RuntimeError("transfer wealth ledger produced NaN")
    return {"worst": worst, "checks": checks, "pool_total": channel.pool_total()}


def main():
    parser = argparse.ArgumentParser(description="Wealth conservation audit for the transfer atom")
    parser.add_argument("--seed", type=int, default=3)
    parser.add_argument("--tol", type=float, default=1e-6)
    args = parser.parse_args()
    result = run(seed=args.seed, tol=args.tol)
    print(f"identity error = {result['worst']:+.3e} (tol {args.tol:g})")


if __name__ == "__main__":
    main()
