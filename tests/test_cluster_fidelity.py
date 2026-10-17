"""`bench.cluster_fidelity` 的结构性冒烟。

**刻意不设阈值门禁**：首次量化结果是 `age_l1 ≈ 0.23–0.26`（100% 同号），远高于测度层的
`age_l1 < 0.06`；要不要给分辨率层定门槛、定多少，属**待拍板**（见 `AGENTS.md` 开放问题）。
在拍板之前用测试钉死某个数字，会把"未决"伪造成"已定"——故本文件只守**结构**。
"""

from bench.cluster_fidelity import METRICS, make_family, run_trial


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
