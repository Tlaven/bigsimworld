"""测度层：状态空间上的稀疏计数分布。

计数用**稀疏容器**存储（只记非零桶），因此内存与每 tick 工作量都
正比于"占用桶数"，**与状态空间大小、人口 N 无关**。
"""


class SparseCounts:
    """桶索引 → 计数 的稀疏容器：读空桶返回 0.0（不写入），写零清位。"""

    __slots__ = ("_data",)

    def __init__(self):
        self._data = {}

    def __getitem__(self, index):
        return self._data.get(index, 0.0)

    def __setitem__(self, index, value):
        self._data[index] = float(value)

    def __delitem__(self, index):
        self._data.pop(index, None)

    def __contains__(self, index):
        return index in self._data

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)

    def keys(self):
        return self._data.keys()

    def values(self):
        return self._data.values()

    def items(self):
        return self._data.items()

    def sum(self):
        # 按索引升序求和：浮点累加序影响末位，遍历序纪律见 transitions.py 模块文档
        return sum(self._data[index] for index in sorted(self._data))


class Measure:
    def __init__(self, space):
        self.space = space
        self.counts = SparseCounts()
        self.occupied = set()
        self.recent_deaths = []  # 本 tick 死亡记录 [(age, wealth_bucket, amount)]，供继承算子使用
        self.yearly_inherited = {}  # 遗产池（按子女年龄段，财富单位）：年内累积，每年清算分配，余量留池
        # 通道池（质量侧 transfer 的量化残差/流动性）：**每个粗侧各自持有**（全局 + 每个簇的 mini）。
        # 归属规则与不变量见 docs/decisions/adr-005-transfer-quality-side.md 与 L3 N2-6。
        self.transfer_pool = 0.0
        # 折算残差（符号账）：具名个体折回桶中心时的 `wealth − 桶中心`（可正可负）。
        # **不可花费**——只用于财富恒等式；见 docs/decisions/adr-006-conversion-residual.md / L4 N2-5。
        self.conversion_residual = 0.0
        # 整数语义发放器的信用（仅 mini 的 integer_* 流使用；**非质量**、不进守恒恒等式）。
        # mini 合并求和、快照往返、回流体区（折入全局）作废。见 docs/decisions/adr-010-mini-integer-semantics.md。
        self.marriage_credit = 0.0
        self.death_credit = 0.0

    # ---------------------------------------------------------------- 基本

    def add(self, index, amount):
        value = self.counts[index] + amount
        if value > 0.0:
            self.counts[index] = value
            self.occupied.add(index)
        else:
            if index in self.counts:
                self.counts[index] = 0.0
            self.occupied.discard(index)

    def inflow(self, index, amount):
        self.add(index, amount)

    def total(self):
        return float(self.counts.sum())

    def mass(self):
        """分布里的财富质量 = ``Σ count × 桶中心``（不含池）。O(占用桶数)。"""
        space = self.space
        total = 0.0
        for index in sorted(self.occupied):
            total += self.counts[index] * space.wealth_value(space.decode(index)[2])
        return total

    def wealth(self):
        """全部财富（**审计口径**，不是可花费量）= 分布质量 + 通道池 + 折算残差 + 继承段池。

        恒等式与符号约定见 `docs/decisions/adr-006-conversion-residual.md`。
        """
        return (self.mass() + self.transfer_pool + self.conversion_residual
                + float(sum(self.yearly_inherited[age] for age in sorted(self.yearly_inherited))))

    def iter_occupied(self):
        for index in self.occupied:
            yield index, self.counts[index]

    # ---------------------------------------------------------------- 流出

    def outflow(self, predicate, rate):
        """对所有满足 predicate 的占用桶，移出 count*rate，返回移出的总量。"""
        removed = 0.0
        for index in sorted(self.occupied):
            if predicate(index):
                amount = self.counts[index] * rate
                self.add(index, -amount)
                removed += amount
        return removed


def _field(character, name, default=None):
    if isinstance(character, dict):
        return character.get(name, default)
    return getattr(character, name, default)


def measure_from_characters(characters, space):
    """把一批个体（Character 对象或 dict）按 (age, gender, 财富段, 婚配状态) 落桶。"""
    measure = Measure(space)
    for character in characters:
        relationships = _field(character, "relationships", {}) or {}
        marital = 1 if relationships.get("spouse") else 0
        gender = _field(character, "gender")
        index = space.encode(
            _field(character, "age"), 0 if gender == "male" else 1,
            space.wealth_bucket(_field(character, "wealth", 0.0)), marital,
        )
        measure.add(index, 1.0)
    return measure


def measure_to_payload(measure):
    """序列化为可持久化的紧凑结构（只存非零桶 + 两个池）。

    池必须一起往返：否则 ``SIM_RESUME=1`` 从快照恢复时财富会出现断点（见 ADR-005）。
    """
    return {
        "size": measure.space.size,
        "cells": [[index, round(float(measure.counts[index]), 6)]
                  for index in sorted(measure.occupied) if measure.counts[index] > 0],
        "transfer_pool": round(float(measure.transfer_pool), 6),
        "conversion_residual": round(float(measure.conversion_residual), 6),
        "marriage_credit": round(float(measure.marriage_credit), 6),
        "death_credit": round(float(measure.death_credit), 6),
        "inherited": [[int(age), round(float(amount), 6)]
                      for age, amount in sorted(measure.yearly_inherited.items())
                      if amount > 0],
    }


def measure_from_payload(payload, space):
    """反序列化；缺账字段的旧档按 0 读（兼容，不抛错）。"""
    measure = Measure(space)
    for index, count in payload["cells"]:
        measure.add(int(index), float(count))
    measure.transfer_pool = float(payload.get("transfer_pool", 0.0))
    measure.conversion_residual = float(payload.get("conversion_residual", 0.0))
    measure.marriage_credit = float(payload.get("marriage_credit", 0.0))
    measure.death_credit = float(payload.get("death_credit", 0.0))
    for age, amount in payload.get("inherited", []):
        measure.yearly_inherited[int(age)] = float(amount)
    return measure


def record_conversion(measure, space, wealth):
    """记一次"精确财富 → 桶中心"的折算残差（符号账）：`+= wealth − 桶中心`。

    **只在具名个体离场、其财富改由桶表示时调用**（`dematerialize` / `coarsen` / `unbind`）。
    `materialize` / `bind` / `extract` 是"移走 c、造出 c"的精确点，**不得**调用。
    正 = 该测度欠世界（把高于桶中心的个体折低了）；见 `docs/core-code.md` N2-5 / ADR-006。
    """
    bucket = space.wealth_bucket(wealth)
    measure.conversion_residual += float(wealth) - space.wealth_value(bucket)


def fold_pools(source, target):
    """把 ``source`` 的质量账并进 ``target`` 并清空 source。

    都要折：`transfer_pool`（逐值）、`yearly_inherited`（逐段）、`conversion_residual`（逐值）、
    两个**整数语义信用**（adr-010，发放器状态、非质量；mini→mini 合并要带信用；回流体区前调用方
    先作废）。共演单元的生命周期算子（`coarsen`/`merge`/`dissolve`/`split`）必须调用它。
    **只折 `counts` 会丢财富**——这是 ADR-005/006 记录并修掉的既有漏洞。
    """
    target.transfer_pool += float(source.transfer_pool)
    target.conversion_residual += float(source.conversion_residual)
    target.marriage_credit += float(source.marriage_credit)
    target.death_credit += float(source.death_credit)
    for age in sorted(source.yearly_inherited):          # 按段升序（遍历序纪律）
        target.yearly_inherited[age] = (target.yearly_inherited.get(age, 0.0)
                                        + source.yearly_inherited[age])
    source.transfer_pool = 0.0
    source.conversion_residual = 0.0
    source.marriage_credit = 0.0
    source.death_credit = 0.0
    source.yearly_inherited = {}


