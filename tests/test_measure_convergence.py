from bench.convergence import compare_fingerprint, run_individual, run_measure, run_measure_full, run_reduced


def test_measure_converges_to_reduced_model():
    # 测度引擎（无生育，因为初始全未婚）应与"精简个体模型"在有限 N 下收敛。
    small = compare_fingerprint(run_reduced(1000, 800, 42), run_measure(1000, 800, 42))
    large = compare_fingerprint(run_reduced(8000, 800, 42), run_measure(8000, 800, 42))

    # 随 N 增大，年龄分布差异不上升（收敛）
    assert large["age_l1"] <= small["age_l1"] + 0.005
    # 大 N 下的绝对差异很小
    assert large["age_l1"] < 0.02
    assert large["gini_diff"] < 0.03
    assert large["wealth_rel"] < 0.05


def test_measure_full_matches_individual():
    # 带婚配/生育（FULL_FLOWS）的测度引擎应与完整个体引擎统计相近。
    steps = 2500
    ind = run_individual(3000, steps, 42)
    mf = run_measure_full(3000, steps, 42)
    diff = compare_fingerprint(ind, mf)
    assert diff["gini_diff"] < 0.03
    assert diff["wealth_rel"] < 0.05
    assert diff["married_diff"] < 0.10
    assert diff["age_l1"] < 0.06

