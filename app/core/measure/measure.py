"""测度层：状态空间上的稀疏计数分布。

计数用 `numpy` 数组存储，`occupied` 只记录非零桶，因此每 tick 的工作量
正比于"占用桶数"，**与人口 N 无关**。
"""

import numpy as np


class Measure:
    def __init__(self, space):
        self.space = space
        self.counts = np.zeros(space.size, dtype=np.float64)
        self.occupied = set()

    # ---------------------------------------------------------------- 基本

    def add(self, index, amount):
        self.counts[index] += amount
        if self.counts[index] > 0.0:
            self.occupied.add(index)
        else:
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
                self.counts[index] -= amount
                removed += amount
                if self.counts[index] <= 0.0:
                    self.occupied.discard(index)
        return removed


def measure_from_characters(characters, space):
    """把一批 Character 按 (age, gender, 财富段, 婚配状态) 落桶。"""
    measure = Measure(space)
    for character in characters:
        marital = 1 if character.relationships["spouse"] else 0
        index = space.encode(
            character.age, 0 if character.gender == "male" else 1,
            space.wealth_bucket(character.wealth), marital,
        )
        measure.add(index, 1.0)
    return measure
