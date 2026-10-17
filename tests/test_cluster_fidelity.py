"""`bench.cluster_fidelity` 的结构性冒烟 + **分层门槛判定**的单测。

**本文件仍不跑阈值门禁的慢扫描**（那是 CI 慢跑：`python -m bench.cluster_fidelity --gate`，
规格见 [`docs/decisions/adr-004-cluster-fidelity-gate.md`](../docs/decisions/adr-004-cluster-fidelity-gate.md)）。
这里只守两件事：① 工具的结构（能跑、字段齐、两臂拿到同一批人）；② **门槛判定函数本身**
（`evaluate_gate` 是纯函数 ⇒ 用合成扫描数据做正/反例，不必跑分钟级实验）。

> 生产簇规模（≤12）上的一切分布型读数都不是"粗化误差的度量"（分箱离散 + 相位错位）
> ⇒ **禁止**在那里设阈值；门槛只在跨规模（n ≥ 400）口径上定义。
"""

from bench.cluster_fidelity import METRICS, evaluate_gate, make_family, run_trial


def test_fidelity_tool_runs_and_reports_expected_shape():
    rows = run_trial(1, members=6, checkpoints=[200])
    row = rows[200]

    assert set(row["diff"]) == set(METRICS)
    assert row["degree_l1"] is None          # coarse 侧**无图** ⇒ 类别错误，不是 0
    assert row["resolved"]["population"] > 0
    assert row["coarse"]["population"] > 0


def test_make_family_is_deterministic_given_same_seed():
    first = make_family(6, seed=3)
    second = make_family(6, seed=3)
    assert [(p["age"], p["gender"]) for p in first] == [(p["age"], p["gender"]) for p in second]
    assert [p["pedometer"]["step"] for p in first] == [p["pedometer"]["step"] for p in second]


def test_two_arms_receive_the_same_people():
    """两条臂必须拿到**同一批人**（深拷贝），否则比的是两批人而不是分辨率。"""
    people = make_family(6, seed=5)
    before = [(p["age"], p["gender"], p["pedometer"]["step"]) for p in people]

    run_trial(5, members=6, checkpoints=[1])

    after = [(p["age"], p["gender"], p["pedometer"]["step"]) for p in people]
    assert after == before, "trial 跑完后原始 people 被改动了（串扰）"


def test_aligned_phase_makes_phases_identical():
    """T1 的注入点：`aligned_phase=True` ⇒ 所有个人相位为 0（与 coarse 的 `tick % 360` 同相）。"""
    family = make_family(6, seed=1, aligned_phase=True)
    assert {p["pedometer"]["step"] for p in family} == {0}


def test_flow_ablation_is_effective():
    from bench.diagnose_cluster_bias import flows_without

    ablated = flows_without("marriage")
    names = {flow.__name__ for flow in ablated}
    assert "marriage" not in names
    assert names == {"aging", "income", "death", "birth"}

    from app.core.measure import transitions as T

    rows = run_trial(1, members=6, checkpoints=[1], coarse_flows=ablated)
    assert rows[1]["coarse"]["married_frac"] == 0.0        # 无婚配流 ⇒ 无人已婚
    assert T.MARRIAGE_RATE > 0.0                           # 全局常数未被污染


# ---------------------------------------------------------------- 门槛判定（纯函数）

def _sweep(ages, pops, sizes=(400, 800, 1600)):
    return [{"members": n, "age_l1": a, "pop": p}
            for n, a, p in zip(sizes, ages, pops)]


def test_gate_passes_the_sweep_measured_on_2026_10_17():
    """门槛必须**通过**今天实测的扫描——否则它一上线就是红的。"""
    ok, reasons = evaluate_gate(_sweep((0.0454, 0.0412, 0.0359), (-18.25, -8.35, -10.50)))
    assert ok, reasons


def test_gate_rejects_age_l1_rising_with_n():
    ok, reasons = evaluate_gate(_sweep((0.0300, 0.0400, 0.0450), (-4.0, -4.0, -4.0)))
    assert not ok
    assert any("上升" in reason for reason in reasons)


def test_gate_rejects_age_l1_above_threshold_at_largest_n():
    ok, reasons = evaluate_gate(_sweep((0.0500, 0.0500, 0.0700), (-4.0, -4.0, -4.0)))
    assert not ok
    assert any("超门槛" in reason for reason in reasons)


def test_gate_rejects_population_bias_above_five_percent():
    ok, reasons = evaluate_gate(_sweep((0.0300, 0.0300), (-24.0, -48.0), sizes=(400, 800)))
    assert not ok
    assert any("相对偏差" in reason for reason in reasons)


def test_gate_rejects_population_bias_growing_with_n():
    """4.9% 仍在 5% 以内，但相对偏差**随 n 增长** ⇒ 也要拒。"""
    ok, reasons = evaluate_gate(_sweep((0.0300, 0.0300), (-4.0, -39.2), sizes=(400, 800)))
    assert not ok
    assert any("随 n 增长" in reason for reason in reasons)


def test_gate_requires_at_least_two_sizes():
    ok, reasons = evaluate_gate(_sweep((0.0300,), (-4.0,), sizes=(400,)))
    assert not ok
    assert any("至少" in reason for reason in reasons)
