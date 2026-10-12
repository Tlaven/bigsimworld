"""财富守恒审计：核对 mf 期末报告财富 == 初始 + 收入 + 出生桶值 - 死亡蒸发(90%)。

体感意义：transfer 类算子（继承/婚配/衰老）只应移动桶，不得改变总量；
任何"注水/重复记账"都会在这个恒等式上现形。继承算子的支付账本等
改动后的第一件事就是跑它。

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


def main():
    parser = argparse.ArgumentParser(description="Wealth conservation audit for mean-field engine")
    parser.add_argument("--n", type=int, default=5000)
    parser.add_argument("--steps", type=int, default=8000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    space = StateSpace()
    random.seed(args.seed)
    measure = measure_from_characters(make_characters(args.n, seed=args.seed), space)
    mf = MeanFieldEngine(space=space, measure=measure, flows=T.FULL_FLOWS)

    audit = {"income": 0.0, "evap": 0.0, "birth_value": 0.0, "birth_count": 0.0}
    original_inheritance = T.inheritance
    original_birth = T.birth

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

    mf.flows = (T.aging, T.income, T.death, T.marriage, birth_wrapped, inheritance_wrapped)

    initial = wealth_total(mf.measure, space)
    for tick in range(1, args.steps + 1):
        if tick % T.INCOME_PERIOD == 0:
            for index in list(mf.measure.occupied):
                age, gender, wealth, marital = space.decode(index)
                if 18 < age < 60:
                    audit["income"] += mf.measure.counts[index] * T.INCOME_AMOUNT
        mf.step()

    final = wealth_total(mf.measure, space)
    expected = initial + audit["income"] + audit["birth_value"] - audit["evap"]
    pool_residual = float(sum(mf.measure.yearly_inherited.values()))
    error = final - expected + pool_residual

    print(f"initial = {initial:.6e}")
    print(f"income  = {audit['income']:.6e}")
    print(f"births  = {audit['birth_count']:.1f} (value {audit['birth_value']:.6e})")
    print(f"evap(90%) = {audit['evap']:.6e}")
    print(f"expected= {expected:.6e}")
    print(f"final   = {final:.6e}")
    print(f"pool residual(不做账) = {pool_residual:.6e}")
    print(f"identity error = {error:+.3e}  ({error / final:+.4%})")
    if abs(error / final) > 1e-3:
        raise SystemExit("!! wealth ledger leak detected (>0.1%)")


if __name__ == "__main__":
    main()
