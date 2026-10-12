"""小规模守恒门禁：任何触碰 mean-field 转移算子的改动都必须过这条。"""
from bench.audit_ledger import run_audit


def test_wealth_conservation_identity_small():
    # 收入/出生按流差分计量后，恒等式应为精确闭合（仅浮点噪声级）
    result = run_audit(n=1000, steps=720, seed=7, max_error_frac=1e-6)
    assert result["birth_count"] > 0
    assert result["evap"] > 0
    assert result["income"] > 0
