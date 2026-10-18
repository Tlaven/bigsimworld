"""真个体窗口：把 `Character`（含关系图/家谱）接进物化层。

窗口是一小块"域分解"的个体子世界：内部按个体引擎的完整事件逻辑演化
（结识/熟络/结友/婚配/生育/死亡/继承），外部由测度层统计演化；两层通过
materialize / dematerialize 交换成员并保持守恒。

守恒律：``Σ测度计数 + len(窗口角色) == 初始总量 + 窗口出生 - 窗口死亡``。
"""

import random
from collections import deque

from app.core.generation.human import generate_character
from app.core.measure.measure import record_conversion
from app.core.person.character import Character
from app.core.person.links import link, unlink
from app.core.simulation.events import PeopleEvents


class IndividualWindow:
    def __init__(self, measure, capacity=1000, n_cells=1, rng=None):
        self.measure = measure
        self.space = measure.space
        self.capacity = capacity
        self.n_cells = n_cells
        # 随机源：默认用模块级 random（保持"全局 seed 即复现"的既有行为），
        # 可注入独立 Random 以隔离随机流（通道 / 测试）。
        self.rng = rng or random

        # —— 作为 Character 的 model 接口 ——
        self.characters = {}
        self.event_plaza = {"acquaintance": [[] for _ in range(n_cells)]}
        self.publish_list = []
        self.max_id = 0
        self.UTC = "0-0-0"
        self.simulation_time = 0

        self.stats = {"births": 0, "deaths": 0, "materialized": 0, "dematerialized": 0}

        # 受保护 id 提供者（共演单元成员不参与容量逐出）；None 时退回原行为。
        self.protected_provider = None

        # 个体生命轨迹（有界）：id -> deque[(tick, age, wealth, n_friend, n_spouse)]
        self.life_log = {}
        self.life_log_len = 300

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

    def attach(self, character_dict):
        """直接注入一个真个体（不计数出生、不动测度）；供共演单元物化等使用。"""
        return self._make_character(dict(character_dict))

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
            for other in self.rng.sample(adults, min(3, len(adults))):
                link(character, other, "acquaintance")
        self.stats["materialized"] += 1
        return character.id

    def materialize_sample(self, n):
        """按测度分布无放回抽取 n 个个体，物化为真角色。"""
        space = self.space
        # 按索引升序取候选：采样消耗随机数，候选顺序必须 canonical（遍历序纪律）
        ids = sorted(self.measure.occupied)
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
            if weights[chosen] < 1.0:
                ids.pop(chosen)
                weights.pop(chosen)
        return made

    def detach(self, character_id):
        """解除该个体全部关系、清广场格、移出窗口；**不**折算回测度。

        供共演单元收编等使用（收编把成员折进共演单元的聚合态，而非测度）。
        """
        character = self.characters.pop(character_id, None)
        if character is None:
            return None
        self._sever_relationships(character)
        self._strip_plaza(character)
        return character

    def dematerialize(self, character_id):
        """把窗口个体折算回测度（窗口 -1，测度 +1）。

        退场断链（Stage 9）：先按"非死亡离场"语义解除所有关系
        （双方移除 + relation_record 记档；**不**触发死亡结算——子女不继承），
        并把本人从广场格清掉，然后才把 (age,gender,财富,婚配) 折算回测度。
        """
        character = self.detach(character_id)
        if character is None:
            return False
        marital = 1 if character.relationships["spouse"] else 0
        index = self.space.encode(
            character.age, 0 if character.gender == "male" else 1,
            self.space.wealth_bucket(character.wealth), marital,
        )
        self.measure.add(index, 1.0)
        # 精确 wealth → 桶中心：差额记入折算残差（符号账，ADR-006 / N2-5）。**不可漏**。
        record_conversion(self.measure, self.space, character.wealth)
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
            unlink(character, child, "child", "parent", record=True)

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

    def enforce_capacity(self, protected=None):
        """超容量时按"最小嵌入优先"退场（Family 连续性：已婚者最后离场）。

        `protected`：不参与逐出的 id（共演单元成员由其分辨率管理器管辖）。
        """
        protected = set(protected or ())
        while len(self.characters) > self.capacity:
            candidates = [cid for cid in self.characters if cid not in protected]
            if not candidates:
                break
            victim = min(candidates, key=lambda cid: self._embedding(self.characters[cid]))
            self.dematerialize(victim)

    # ------------------------------------------------------------ 演化

    def step(self, tick):
        self.simulation_time = tick
        year, remainder = divmod(tick, 360)
        month, day = divmod(remainder, 30)
        self.UTC = f"{year}-{month}-{day}"
        for character in list(self.characters.values()):
            character.step()
            self._log_life(character, tick)
        PeopleEvents(self.event_plaza, self.rng)
        protected = self.protected_provider() if self.protected_provider else None
        self.enforce_capacity(protected)
        if self.life_log:
            self.life_log = {cid: log for cid, log in self.life_log.items() if cid in self.characters}

    def _log_life(self, character, tick):
        log = self.life_log.get(character.id)
        if log is None:
            log = deque(maxlen=self.life_log_len)
            self.life_log[character.id] = log
        log.append((tick, character.age, character.wealth,
                    len(character.relationships["friend"]), len(character.relationships["spouse"])))


class WindowEngine:
    """测度引擎 + 真个体窗口：总体统计演化，窗口内是带关系图的真角色。"""

    def __init__(self, measure_engine, capacity=1000, window=0, resolution=False,
                 endogenous_scale=None, rng=None):
        self.measure_engine = measure_engine
        self.rng = rng or random
        self.window = IndividualWindow(measure_engine.measure, capacity=capacity, rng=self.rng)
        self.simulation_time = measure_engine.simulation_time
        self.endogenous_scale = endogenous_scale  # L1 社会凝视（None=关）
        self.resolution = None
        if resolution:
            self._enable_resolution()
        if window:
            self.window.materialize_sample(window)

    def _enable_resolution(self):
        if self.resolution is None:
            from app.core.measure.cluster import ResolutionManager
            self.resolution = ResolutionManager(self.window, budget_leaves=self.window.capacity,
                                                endogenous_scale=self.endogenous_scale,
                                                rng=self.rng)
            self.window.protected_provider = self.resolution.protected_ids  # 共演单元成员不参与逐出
        return self.resolution

    def _refill(self):
        """从测度补位，维持窗口可见人口（coarsen 让窗口缩水时回填）。

        另有规则注册时，预留 `cap_per_tick` 个名额给交互通道——否则窗口恒满
        （`_refill` 每 tick 补满），`bind` 会被 `dropped:window` **永久饿死**。
        **无规则时预留为 0 ⇒ 行为与从前完全一致。**
        """
        reserve = 0
        if self.resolution is not None:
            reserve = self.resolution.channel.headroom_reserve()
        missing = self.window.capacity - len(self.window.characters) - reserve
        if missing > 0:
            self.window.materialize_sample(missing)

    def population(self):
        total = self.window.population()
        if self.resolution is not None:
            total += self.resolution.store.size()
        return total

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
        if self.resolution is not None:
            from app.core.measure.cluster import TickContext
            ctx = TickContext(tick=self.simulation_time,
                              measure=self.measure_engine.measure, rng=self.rng)
            self.resolution.step(ctx)
            self._refill()

    def feedback(self, cost, budget):
        """把实测负载反馈给分辨率调度（水位线 θ）。"""
        if self.resolution is not None:
            self.resolution.feedback(cost, budget)

    # ------------------------------------------------------------ 观察者接口

    def resolution_summary(self):
        return self.resolution.summary() if self.resolution is not None else None

    def set_cluster_attention(self, cluster_id, value):
        if self.resolution is None or cluster_id not in self.resolution.store.clusters:
            return False
        self.resolution.set_attention(cluster_id, value)
        return True

    def set_person_attention(self, person_id, value):
        """person id → 其所属共演单元 → 置注意度；返回共演单元 id（无共演单元则 None）。"""
        if self.resolution is None:
            return None
        cluster_id = self.resolution.cluster_of(person_id)
        if cluster_id is None:
            return None
        self.resolution.set_attention(cluster_id, value)
        return cluster_id

    def notables(self, k=12):
        """显名者：**显要个体**（自身世界影响 = 财富高位分位）优先 + 其余被注视的 resolved 个体。

        每个条目附 ``notable`` 标志与 ``cluster_id``/``attention``（未纳入共演单元者为 None/0）。
        显要者由分辨率层保护（不逐出、不粗化），故即使无人注视也持续具名。
        """
        if self.resolution is None:
            return []
        mgr = self.resolution
        attention = mgr.attention
        notable_ids = mgr.notable_ids()

        def entry(character, cluster_id):
            item = character.__publish_dict__
            item["cluster_id"] = cluster_id
            item["attention"] = round(attention.get(cluster_id, 0.0), 3)
            item["notable"] = character.id in notable_ids
            return item

        entries = {}
        for cid in notable_ids:                        # 显要者（含未纳入共演单元的浮层个体）
            character = self.window.characters.get(cid)
            if character is not None:
                entries[cid] = entry(character, mgr.cluster_of(cid))
        for cluster in sorted(mgr.store.clusters.values(),
                              key=lambda c: attention.get(c.id, 0.0), reverse=True):
            if cluster.level != 1:
                continue
            for mid in cluster.member_ids:             # 其余被注视的 resolved 成员
                if mid in entries:
                    continue
                character = self.window.characters.get(mid)
                if character is not None:
                    entries[mid] = entry(character, cluster.id)
        ranked = sorted(entries.values(),
                        key=lambda e: (not e["notable"], -e["wealth"], -e["attention"], e["id"]))
        return ranked[:k]

    def life_log(self, person_id):
        """某人的生命轨迹（tick/age/wealth/friends/spouses）；无则 None。"""
        log = self.window.life_log.get(person_id)
        if log is None:
            return None
        return [{"tick": t, "age": a, "wealth": w, "friends": f, "spouses": s}
                for (t, a, w, f, s) in log]

    # ------------------------------------------------------------ 快照恢复

    def snapshot_payload(self):
        """窗口快照 payload：字符 + （若开分辨率）共演单元/注意力/水位。

        顶层是对象；旧版是字符 list，`restore` 两者都认。
        """
        payload = {
            "characters": [character.__dict__ for character in self.window.characters.values()],
            "resolution": self.resolution is not None,
        }
        if self.resolution is not None:
            payload.update(self.resolution.to_payload())
        return payload

    @classmethod
    def restore(cls, snapshot, capacity=1000):
        """从 models.snapshot 的 payload 重建整个世界：测度 + 真个体窗口 + 共演单元。

        save_snapshot 存的测度**不含**窗口个体（窗口与之守恒互斥），
        窗口 payload 存的是真 Character 全量状态（含 id/关系图 id），
        因此恢复后 population == 存档时 population。旧版 list payload 仍兼容。
        """
        from app.core.measure.engine import MeanFieldEngine
        from app.core.measure.measure import measure_from_payload
        from app.core.measure.space import StateSpace

        space = StateSpace()
        measure = measure_from_payload(snapshot["measure"], space)
        measure_engine = MeanFieldEngine(space=space, measure=measure)
        measure_engine.simulation_time = snapshot["simulation_time"]

        engine = cls(measure_engine, capacity=capacity, window=0)
        window_payload = snapshot.get("window")
        if isinstance(window_payload, dict):
            engine.window.load_characters(window_payload.get("characters") or [])
            if window_payload.get("resolution"):
                engine._enable_resolution()
                engine.resolution.load_payload(window_payload, space)
        else:
            engine.window.load_characters(window_payload or [])
        return engine


