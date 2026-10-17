from app.core.measure import transitions as T
from app.core.measure.measure import Measure
from app.core.measure.space import StateSpace


def test_aging_on_boundary():
    space = StateSpace()
    m = Measure(space)
    origin = space.encode(30, 1, space.wealth_bucket(5000), 0)
    m.add(origin, 10)
    T.aging(m, 360)
    assert m.counts[space.encode(31, 1, space.wealth_bucket(5000), 0)] == 10
    assert m.total() == 10
    assert origin not in m.occupied


def test_aging_off_boundary_noop():
    space = StateSpace()
    m = Measure(space)
    origin = space.encode(30, 1, 0, 0)
    m.add(origin, 5)
    T.aging(m, 359)
    assert origin in m.occupied
    assert m.total() == 5


def test_death_rate():
    space = StateSpace()
    m = Measure(space)
    m.add(space.encode(70, 1, space.wealth_bucket(5000), 0), 1000)
    T.death(m, 1)
    assert abs(m.total() - 1000 * (1 - T.DEATH_RATE)) < 1e-6


def test_death_ignores_young():
    space = StateSpace()
    m = Measure(space)
    m.add(space.encode(30, 1, space.wealth_bucket(5000), 0), 1000)
    T.death(m, 1)
    assert abs(m.total() - 1000) < 1e-9


def test_birth_rate():
    space = StateSpace()
    m = Measure(space)
    m.add(space.encode(30, 1, space.wealth_bucket(5000), 1), 1000)
    before = m.total()
    T.birth(m, 1)
    assert abs(m.total() - before - 1000 * T.BIRTH_RATE) < 1e-6


def test_income_moves_wealth_up():
    space = StateSpace()
    m = Measure(space)
    origin_bucket = space.wealth_bucket(5000)
    m.add(space.encode(30, 0, origin_bucket, 0), 1)
    T.income(m, 30)
    assert m.total() == 1
    new_index = next(iter(m.occupied))
    age, gender, wealth, marital = space.decode(new_index)
    assert age == 30 and gender == 0 and wealth >= origin_bucket


def _wealth_mass(m, space):
    """财富质量 = Σ 桶质量（count × 桶中心值）+ 段池余量（与 audit_ledger 同口径）。"""
    return (sum(m.counts[i] * space.wealth_value(space.decode(i)[2]) for i in m.occupied)
            + sum(m.yearly_inherited.values()))


def test_inheritance_pays_integer_buckets_and_leaves_remainder_in_pool():
    """段池整数分配：只付 floor 的整桶位移，余量留池；财富质量守恒。"""
    space = StateSpace()
    m = Measure(space)
    bucket = space.wealth_bucket(5000.0)
    index = space.encode(30, 0, bucket, 0)
    m.add(index, 1.0)
    m.yearly_inherited[30] = 2500.0
    before = _wealth_mass(m, space)

    T.distribute_pool(m)

    assert index not in m.occupied                        # 整桶平移（不拆桶内计数）
    assert m.counts[space.encode(30, 0, bucket + 2, 0)] == 1.0
    assert m.yearly_inherited[30] == 500.0                # 付了 2 桶（2000），余 500 留池
    assert abs(_wealth_mass(m, space) - before) < 1e-9


def test_inheritance_keeps_mass_when_recipient_is_at_wealth_ceiling():
    """接收桶触顶（无法上移）⇒ 不支付、份额留池。

    曾经的缺陷：`_shift_age_wealth` 触顶时提前返回，调用方却仍按 count×k×w 扣池
    ⇒ 池减少而桶未动，**凭空销毁质量**。真实世界里占用桶最高 ~551/60000，
    这个分支不可达 ⇒ `bench.audit_ledger` 看不见它，只能靠这条强制触顶的测试守。
    """
    space = StateSpace()
    m = Measure(space)
    top = space.wealth_bins - 1
    index = space.encode(30, 0, top, 0)
    m.add(index, 1.0)
    m.yearly_inherited[30] = 2500.0
    before = _wealth_mass(m, space)

    T.distribute_pool(m)

    assert m.counts[index] == 1.0                          # 桶没动（触顶）
    assert m.yearly_inherited[30] == 2500.0                # 未支付 ⇒ 全额留池
    assert abs(_wealth_mass(m, space) - before) < 1e-9     # 质量守恒（曾在此损失 2000）
