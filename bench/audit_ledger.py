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


def main():
    parser = argparse.ArgumentParser(description="Wealth conservation audit for mean-field engine")
    parser.add_argument("--n", type=int, default=5000)
    parser.add_argument("--steps", type=int, default=8000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

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
