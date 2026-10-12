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

    def load_characters(self, character_dicts):
        """从快照的窗口 payload 直接注入真个体（保留原 id 与关系图）。"""
        self.characters = {}
        self.max_id = 0
        for character_dict in character_dicts:
            character_dict = dict(character_dict)
            cid = character_dict.get("id")
            if cid is None:
                cid = self.max_id + 1
                character_dict["id"] = cid
            self.max_id = max(self.max_id, cid)
            self.characters[cid] = Character(self, **character_dict)
            self.characters[cid].cell = cid % self.n_cells
        # 先建齐全部个体，再把关系 id 解析为对象
        for character in self.characters.values():
            character.init_relationships()

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
        """从测度引出 1 个真个体（测度 -1，窗口 +1）。

        来历种子：成年人（age≥6）入窗时与至多 3 位窗口内成年人互认 acquaintance，
        避免"空图老人"式凭空物化（社交漏斗随后照常运转）。
        """
        index = self.space.encode(age, gender, wealth_bucket, marital)
        if self.measure.counts[index] < 1.0:
            return None
        self.measure.add(index, -1.0)
        data = generate_character(
            age=age, gender="male" if gender == 0 else "female",
            wealth=self.space.wealth_value(wealth_bucket),
        )
        character = self._make_character(data)
        if character.age >= 6:
            adults = [c for c in self.characters.values()
                      if c is not character and 18 <= c.age < 60]
            for other in random.sample(adults, min(3, len(adults))):
                character.relationships["acquaintance"].append(other)
                other.relationships["acquaintance"].append(character)
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
        """把窗口个体折算回测度（窗口 -1，测度 +1）。

        退场断链（Stage 9）：先按"非死亡离场"语义解除所有关系
        （双方移除 + relation_record 记档；**不**触发死亡结算——子女不继承），
        并把本人从广场格清掉，然后才把 (age,gender,财富,婚配) 折算回测度。
        """
        character = self.characters.pop(character_id, None)
        if character is None:
            return False
        self._sever_relationships(character)
        self._strip_plaza(character)
        marital = 1 if character.relationships["spouse"] else 0
        index = self.space.encode(
            character.age, 0 if character.gender == "male" else 1,
            self.space.wealth_bucket(character.wealth), marital,
        )
        self.measure.add(index, 1.0)
        self.stats["dematerialized"] += 1
        return True

    def _sever_relationships(self, character):
        """解除该个体的全部关系并双向记档。

        DeathEvent 的 notify_* 语义是"在对方的事件对象上、以离场者为参数"——
        它把本人从对方的列表里移除（并双向写 relation_record）。
        child 边不适用死亡的 notify_child（会触发遗产结算），离场手工断链。
        """
        for other in list(character.relationships["acquaintance"]):
            other.death_event.notify_acquaintance(character)
        for other in list(character.relationships["familiarity"]):
            other.death_event.notify_familiarity(character)
        for other in list(character.relationships["friend"]):
            other.death_event.notify_friend(character)
        for other in list(character.relationships["spouse"]):
            other.death_event.notify_spouse(character)
        for other in list(character.relationships["parent"]):
            other.death_event.notify_parent(character)
        for other in list(character.relationships["sibling"]):
            other.death_event.notify_sibling(character)
        for child in list(character.relationships["child"]):
            child.relationships["parent"].remove(character)
            child.relation_record["parent"].append(character.id)
            character.relation_record["child"].append(child.id)

    def _strip_plaza(self, character):
        cell_plaza = self.event_plaza["acquaintance"][character.cell]
        cell_plaza[:] = [c for c in cell_plaza if c.id != character.id]

    @staticmethod
    def _embedding(character):
        """社交嵌入度：配偶权重最高（家庭故事优先留在窗口），朋友次之。"""
        rels = character.relationships
        return (2 * len(rels.get("spouse", []))
                + len(rels.get("friend", []))
                + len(rels.get("familiarity", []))
                + len(rels.get("acquaintance", [])))

    def enforce_capacity(self):
        """超容量时按"最小嵌入优先"退场（Family 连续性：已婚者最后离场）。"""
        while len(self.characters) > self.capacity:
            victim = min(self.characters, key=lambda cid: self._embedding(self.characters[cid]))
            self.dematerialize(victim)

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

    # ------------------------------------------------------------ 快照恢复

    @classmethod
    def restore(cls, snapshot, capacity=1000):
        """从 models.snapshot 的 payload 重建整个世界：测度 + 真个体窗口。

        save_snapshot 存的测度**不含**窗口个体（窗口与之守恒互斥），
        窗口 payload 存的是真 Character 全量状态（含 id/关系图 id），
        因此恢复后 population == 存档时 population。
        """
        from app.core.measure.engine import MeanFieldEngine
        from app.core.measure.measure import measure_from_payload
        from app.core.measure.space import StateSpace

        space = StateSpace()
        measure = measure_from_payload(snapshot["measure"], space)
        measure_engine = MeanFieldEngine(space=space, measure=measure)
        measure_engine.simulation_time = snapshot["simulation_time"]

        engine = cls(measure_engine, capacity=capacity, window=0)
        engine.window.load_characters(snapshot.get("window") or [])
        return engine


