"""C3：族级继承 vs 全局池——"富族恒富"的量化。

同一笔遗产、同一批接收者的**年龄窗口**，唯一区别是池的作用域：
- family：接收池只落在家族成员（8 人）→ 人均留存高；
- global：接收池摊到同龄全体（8×(1+peers) 人）→ 人均被稀释。

于是人均留存比 ≈ 接收人数比。这直接对应"共演单元内继承保住族间相关、全局池摊平"。
"""
import argparse
import random

from app.core.measure import transitions as T
from app.core.measure.measure import Measure
from app.core.measure.space import StateSpace

FAM_AGES = [20, 22, 25, 27, 30, 32, 35, 37]
DEAD_AGE = 55  # → 子女窗口 u ∈ [5, 37]，覆盖 FAM_AGES


def _wealth_total(measure, space):
    return sum(measure.counts[index] * space.wealth_value(space.decode(index)[2])
               for index in measure.occupied)


def _per_capita_gain(space, peers_per_age, dead_wealth, base_bucket=1):
    """让一个死者的 10% 遗产进池并清算一年，返回接收窗口的人均新增财富。"""
    measure = Measure(space)
    for age in FAM_AGES:
        measure.add(space.encode(age, 0, base_bucket, 0), 1.0 + peers_per_age)
    measure.recent_deaths = [(DEAD_AGE, space.wealth_bucket(dead_wealth), 1.0)]

    before = _wealth_total(measure, space)
    count = measure.total()
    T.inheritance(measure, 360)  # 年度清算
    after = _wealth_total(measure, space)
    return (after - before) / count


def run_comparison(peers=120, dead_wealth=100_000_000, seed=42):
    space = StateSpace()
    random.seed(seed)
    family = _per_capita_gain(space, 0, dead_wealth)
    global_ = _per_capita_gain(space, peers, dead_wealth)
    return {
        "family_per_capita": family,
        "global_per_capita": global_,
        "ratio": family / global_ if global_ else float("inf"),
        "family_recipients": len(FAM_AGES),
        "global_recipients": len(FAM_AGES) * (1 + peers),
    }


def main():
    parser = argparse.ArgumentParser(description="Family vs global inheritance concentration")
    parser.add_argument("--peers", type=int, default=120)
    parser.add_argument("--dead-wealth", type=int, default=100_000_000)
    args = parser.parse_args()
    result = run_comparison(peers=args.peers, dead_wealth=args.dead_wealth)
    print(f"family recipients = {result['family_recipients']}  per-capita = {result['family_per_capita']:.1f}")
    print(f"global recipients = {result['global_recipients']}  per-capita = {result['global_per_capita']:.1f}")
    print(f"concentration ratio = {result['ratio']:.1f}x")


if __name__ == "__main__":
    main()
