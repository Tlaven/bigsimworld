"""物化层：在"测度为主体"的世界里，保留 ≤ capacity 个**真个体**作为可观察窗口。

守恒律：`Σ测度计数 + len(agents)` 在 materialize / dematerialize 下保持不变；
个体自身的出生/死亡则与测度层同样地改变总量（不重复计数）。

个体在这里用轻量状态（年龄/性别/财富/婚配）按个体模型速率随机演化；
真正的"关系图/家谱"只在物化层内维护（Stage 4 先实现守恒与窗口一致性）。
"""

import random

from app.core.measure.transitions import (
    AGE_PERIOD,
    BIRTH_RATE,
    DEATH_RATE,
    INCOME_AMOUNT,
    INCOME_PERIOD,
)


class MaterializationLayer:
    def __init__(self, measure, capacity=1000, focus=None, rng=None):
        self.measure = measure
        self.capacity = capacity
        self.focus = focus if focus is not None else (lambda state: True)
        self.rng = rng or random
        self.agents = {}
        self._next_id = 1
        self.stats = {"materialized": 0, "dematerialized": 0, "births": 0, "deaths": 0}

    # ---------------------------------------------------------------- 守恒

    def population(self):
        return self.measure.total() + len(self.agents)

    def in_focus(self, state):
        return self.focus(state)

    def materialize(self, age, gender, wealth_bucket, marital):
        """从测度搬 1 个到物化层（测度 -1，个体 +1）。返回 id 或 None。"""
        state = (age, gender, wealth_bucket, marital)
        if not self.focus(state):
            return None
        index = self.measure.space.encode(age, gender, wealth_bucket, marital)
        if self.measure.counts[index] < 1.0:
            return None
        self.measure.add(index, -1.0)
        aid = self._next_id
        self._next_id += 1
        self.agents[aid] = {
            "age": age, "gender": gender,
            "wealth": self.measure.space.wealth_value(wealth_bucket),
            "marital": marital,
        }
        self.stats["materialized"] += 1
        return aid

    def materialize_sample(self, n):
        """按测度分布**无放回**抽取 n 个个体物化（用于构造"观察窗口"）。"""
        space = self.measure.space
        ids = list(self.measure.occupied)
        if not ids:
            return 0
        weights = [self.measure.counts[i] for i in ids]
        total = sum(weights)
        made = 0
        while made < n and total >= 1.0 and ids:
            r = self.rng.random() * total
            acc = 0.0
            chosen = 0
            for k, weight in enumerate(weights):
                acc += weight
                if acc >= r:
                    chosen = k
                    break
            age, gender, wealth, marital = space.decode(ids[chosen])
            if self.materialize(age, gender, wealth, marital) is not None:
                made += 1
            weights[chosen] -= 1.0
            total -= 1.0
        return made

    def dematerialize(self, aid):
        """把物化个体折算回测度（个体 -1，测度 +1）。"""
        agent = self.agents.pop(aid, None)
        if agent is None:
            return False
        space = self.measure.space
        bucket = space.wealth_bucket(agent["wealth"])
        index = space.encode(agent["age"], agent["gender"], bucket, agent["marital"])
        self.measure.add(index, 1.0)
        self.stats["dematerialized"] += 1
        return True

    def enforce_capacity(self):
        """超容量时按"最老优先"退料，直到 ≤ capacity。"""
        while len(self.agents) > self.capacity:
            oldest = max(self.agents, key=lambda aid: self.agents[aid]["age"])
            self.dematerialize(oldest)

    # ---------------------------------------------------------------- 演化

    def _spawn(self, age, gender):
        """新生儿：优先留在物化层，否则进入测度。"""
        if self.focus((age, gender, 0, 0)) and len(self.agents) < self.capacity:
            aid = self._next_id
            self._next_id += 1
            self.agents[aid] = {"age": age, "gender": gender, "wealth": 0.0, "marital": 0}
        else:
            self.measure.add(self.measure.space.encode(age, gender, 0, 0), 1.0)
        self.stats["births"] += 1

    def step(self, tick):
        age_up = (tick % AGE_PERIOD == 0)
        income = (tick % INCOME_PERIOD == 0)
        for aid in list(self.agents):
            agent = self.agents[aid]
            if age_up:
                agent["age"] += 1
            if income and 18 < agent["age"] < 60:
                agent["wealth"] += INCOME_AMOUNT
            if agent["age"] >= 60 and self.rng.random() < DEATH_RATE:
                del self.agents[aid]
                self.stats["deaths"] += 1
                continue
            if agent["marital"] == 1 and 18 <= agent["age"] <= 50 \
                    and self.rng.random() < BIRTH_RATE:
                self._spawn(0, self.rng.randint(0, 1))
            if agent["marital"] == 0 and 18 <= agent["age"] < 60 \
                    and self.rng.random() < 0.1 / 360:
                agent["marital"] = 1
        self.enforce_capacity()


class MaterializedEngine:
    """测度引擎 + 物化层：总体按分布演化，同时保留 ≤ capacity 个真个体窗口。"""

    def __init__(self, measure_engine, capacity=1000, focus=None, window=0, rng=None):
        self.measure_engine = measure_engine
        self.layer = MaterializationLayer(measure_engine.measure, capacity, focus, rng)
        self.simulation_time = measure_engine.simulation_time
        if window:
            self.layer.materialize_sample(window)

    def population(self):
        return self.layer.population()

    def step(self):
        self.measure_engine.step()
        self.simulation_time = self.measure_engine.simulation_time
        self.layer.step(self.simulation_time)

