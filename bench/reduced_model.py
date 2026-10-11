"""精简个体参照模型（Stage 1）：只含 年龄 / 性别 / 财富 / 死亡 / 收入。

生育依赖婚姻（关系图），故不在此模型内——Stage 1 的测度层同样无生育
（初始全是未婚）。本模型是测度引擎在有限 N 下的随机参照，N→∞ 时其分布
应收敛到测度引擎。
"""

import random
from types import SimpleNamespace

from app.core.measure.transitions import (
    AGE_PERIOD,
    DEATH_RATE,
    INCOME_AMOUNT,
    INCOME_PERIOD,
)
from bench.world import make_characters


class ReducedModel:
    def __init__(self, n, seed=None):
        self.simulation_time = 0
        self.characters = {}
        for i, data in enumerate(make_characters(n, seed=seed), start=1):
            self.characters[i] = SimpleNamespace(
                age=data["age"], gender=data["gender"],
                wealth=data["wealth"], relatives=set(), relationships={},
            )

    def step(self):
        self.simulation_time += 1
        tick = self.simulation_time
        age_up = (tick % AGE_PERIOD == 0)
        income = (tick % INCOME_PERIOD == 0)
        survivors = {}
        for cid, person in self.characters.items():
            if age_up:
                person.age += 1
            if income and 18 < person.age < 60:
                person.wealth += INCOME_AMOUNT
            if person.age >= 60 and random.random() < DEATH_RATE:
                continue
            survivors[cid] = person
        self.characters = survivors

    def run_until(self, target):
        while self.simulation_time < target:
            self.step()
