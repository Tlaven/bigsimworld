"""小规模守恒门禁：任何触碰 mean-field 转移算子的改动都必须过这条。"""
from bench.audit_ledger import run_audit, run_cluster_audit


def test_wealth_conservation_identity_small():
    # 收入/出生按流差分计量后，恒等式应为精确闭合（仅浮点噪声级）
    result = run_audit(n=1000, steps=720, seed=7, max_error_frac=1e-6)
    assert result["birth_count"] > 0
    assert result["evap"] > 0
    assert result["income"] > 0


def test_cluster_mass_conservation_small():
    # 窗口+共演单元 的分辨率操作（materialize/coarsen/dissolve/refill）必须逐一守恒
    result = run_cluster_audit(n=800, steps=600, capacity=120, seed=3, max_error=1e-6)
    assert result["error_frac"] == 0.0 or abs(result["error_frac"]) < 1e-6
