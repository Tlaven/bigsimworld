"""真个体窗口：把 `Character`（含关系图/家谱）接进物化层。

窗口是一小块"域分解"的个体子世界：内部按个体引擎的完整事件逻辑演化
（结识/熟络/结友/婚配/生育/死亡/继承），外部由测度层统计演化；两层通过
materialize / dematerialize 交换成员并保持守恒。

守恒律：``Σ测度计数 + len(窗口角色) == 初始总量 + 窗口出生 - 窗口死亡``。
"""

import random

from app.core.generation.human import generate_character
from app.core.person.character import Character
from app.core.simulation.events import PeopleEvents


class IndividualWindow:
    def __init__(self, measure, capacity=1000, n_cells=1):
        self.measure = measure
        self.space = measure.space
        self.capacity = capacity
        self.n_cells = n_cells

        # —— 作为 Character 的 model 接口 ——
        self.characters = {}
        self.event_plaza = {"acquaintance": [[] for _ in range(n_cells)]}
        self.publish_list = []
        self.max_id = 0
        self.UTC = "0-0-0"
        self.simulation_time = 0

        self.stats = {"births": 0, "deaths": 0, "materialized": 0, "dematerialized": 0}

    # ------------------------------------------------------- model 接口

    def _make_character(self, character_dict):
        cid = self.max_id + 1
        character_dict["id"] = cid
        self.max_id += 1
        character = Character(self, **character_dict)
        character.cell = cid % self.n_cells
        self.characters[cid] = character
        return character

    def create_character(self, character_dict):
        """新生儿（由 ChildbirthEvent 调用）。"""
        character = self._make_character(character_dict)
        self.stats["births"] += 1
        return character

    def remove_character(self, character_id, character):
        self.characters.pop(character_id, None)
        self.stats["deaths"] += 1

    # ------------------------------------------------------------ 守恒

    def population(self):
        return self.measure.total() + len(self.characters)

    def materialize(self, age, gender, wealth_bucket, marital):
        """从测度引出 1 个真个体（测度 -1，窗口 +1）。"""
        index = self.space.encode(age, gender, wealth_bucket, marital)
        if self.measure.counts[index] < 1.0:
            return None
        self.measure.add(index, -1.0)
        data = generate_character(
            age=age, gender="male" if gender == 0 else "female",
            wealth=self.space.wealth_value(wealth_bucket),
        )
        character = self._make_character(data)
        self.stats["materialized"] += 1
        return character.id

    def materialize_sample(self, n):
        """按测度分布无放回抽取 n 个个体，物化为真角色。"""
        space = self.space
        ids = list(self.measure.occupied)
        weights = [self.measure.counts[i] for i in ids]
        total = sum(weights)
        made = 0
        while made < n and total >= 1.0 and ids:
            r = random.random() * total
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
            if weights[chosen] < 1.0:
                ids.pop(chosen)
                weights.pop(chosen)
        return made

    def dematerialize(self, character_id):
        """把窗口个体折算回测度（窗口 -1，测度 +1），丢弃其关系。"""
        character = self.characters.pop(character_id, None)
        if character is None:
            return False
        marital = 1 if character.relationships["spouse"] else 0
        index = self.space.encode(
            character.age, 0 if character.gender == "male" else 1,
            self.space.wealth_bucket(character.wealth), marital,
        )
        self.measure.add(index, 1.0)
        self.stats["dematerialized"] += 1
        return True

    def enforce_capacity(self):
        while len(self.characters) > self.capacity:
            oldest = max(self.characters, key=lambda cid: self.characters[cid].age)
            self.dematerialize(oldest)

    # ------------------------------------------------------------ 演化

    def step(self, tick):
        self.simulation_time = tick
        year, remainder = divmod(tick, 360)
        month, day = divmod(remainder, 30)
        self.UTC = f"{year}-{month}-{day}"
        for character in list(self.characters.values()):
            character.step()
        PeopleEvents(self.event_plaza)
        self.enforce_capacity()


class WindowEngine:
    """测度引擎 + 真个体窗口：总体统计演化，窗口内是带关系图的真角色。"""

    def __init__(self, measure_engine, capacity=1000, window=0):
        self.measure_engine = measure_engine
        self.window = IndividualWindow(measure_engine.measure, capacity=capacity)
        self.simulation_time = measure_engine.simulation_time
        if window:
            self.window.materialize_sample(window)

    def population(self):
        return self.window.population()

    @property
    def UTC(self):
        year, remainder = divmod(self.simulation_time, 360)
        month, day = divmod(remainder, 30)
        return f"{year}-{month}-{day}"

    def sample_people(self, k=20):
        """取窗口内若干真个体（用于前端/SSE 展示）。"""
        characters = list(self.window.characters.values())
        return [character.__publish_dict__ for character in characters[:k]]

    def step(self):
        self.measure_engine.step()
        self.simulation_time = self.measure_engine.simulation_time
        self.window.step(self.simulation_time)


