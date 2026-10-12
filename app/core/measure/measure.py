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
        return sum(self._data.values())


class Measure:
    def __init__(self, space):
        self.space = space
        self.counts = SparseCounts()
        self.occupied = set()
        self.recent_deaths = []  # 本 tick 死亡记录 [(age, wealth_bucket, amount)]，供继承算子使用
        self.yearly_inherited = {}  # 遗产池（按子女年龄段，财富单位）：年内累积，每年清算分配，余量留池

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

    def iter_occupied(self):
        for index in self.occupied:
            yield index, self.counts[index]

    # ---------------------------------------------------------------- 流出

    def outflow(self, predicate, rate):
        """对所有满足 predicate 的占用桶，移出 count*rate，返回移出的总量。"""
        removed = 0.0
        for index in list(self.occupied):
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
    """序列化为可持久化的紧凑结构（只存非零桶）。"""
    return {
        "size": measure.space.size,
        "cells": [[index, round(float(measure.counts[index]), 6)]
                  for index in measure.occupied if measure.counts[index] > 0],
    }


def measure_from_payload(payload, space):
    measure = Measure(space)
    for index, count in payload["cells"]:
        measure.add(int(index), float(count))
    return measure


