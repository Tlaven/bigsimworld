"""离散事件驱动的仿真引擎。

与 `SimulationEngine` 复用同一套 `Character` 与事件类，只把"每 tick 全量遍历
所有角色"替换为"最小堆调度：只处理到点的事件"。

事件堆的排序键为 ``(time, seq, priority, counter)``：

- ``seq`` 是角色的插入序（与旧引擎 dict 迭代序一致），保证"按角色分组"；
- 每个角色在堆中只有**一个**待办事件（下一次 wake）；wake 时刻是三路周期的并集
  （个体事件周期 ``step_threshold``、财富周期 30、年龄周期 360）；
- 广场配对（PLZ）以一个大 ``seq`` 排在同一 tick 的所有角色事件之后。

因为三类周期共用同一相位、且属性变更没有随机调用，因此只要个体事件的集合与
顺序一致，随机数流即与原引擎一致（见 tests/test_event_engine.py 的逐位一致性测试）。
"""

import heapq
import random

from sqlalchemy import func

from app.models import crud
from app.core.person.character import Character
from app.core.simulation.events import PeopleEvents
from app.utils.logger import setup_logger

logger = setup_logger()

WAKE = 0
PLZ = 1

_PLAZA_SEQ = 10 ** 18

AGE_PERIOD = 360
WEALTH_PERIOD = 30


class EventEngine:
    def __init__(self, db_queues, characters=None, rare_stride=1, n_cells=1, rng=None):
        self.simulation_time = 0
        self.characters = {}
        self.n_cells = n_cells
        # 随机源：默认模块级 random（保持"全局 seed 即复现"与逐位一致性测试），可注入以隔离随机流。
        self.rng = rng or random
        self.event_plaza = {
            "acquaintance": [[] for _ in range(n_cells)],
        }
        self.publish_list = []
        self.max_id = 0
        # 稀有事件评估的降频倍数：=1 时与原引擎逐位一致；>1 时评估次数降到 1/K、概率放大 K 倍
        self.rare_stride = rare_stride

        # 数据库修改进程的共享队列
        self.insert_queue = db_queues["insert"]
        self.update_queue = db_queues["update"]

        # 事件堆与辅助计数
        self._heap = []
        self._counter = 0
        self._seq = 0
        self._plaza_scheduled_at = None

        self.UTC = "0-0-0"
        self._update_utc()

        if characters is None:
            self.create_characters_from_db()
        else:
            self.load_characters(characters)

    # ------------------------------------------------------------------ 加载

    def load_characters(self, character_dicts):
        """从 dict 列表构建 Character（不经过数据库）。按 id 序调度事件。"""
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
        logger.info(f"Created {len(self.characters)} characters.")

        for character in self.characters.values():
            character.init_relationships()

        for cid in sorted(self.characters):
            self._schedule_character(self.characters[cid])

    def create_characters_from_db(self):
        with crud.get_session() as session:
            self.max_id = session.query(func.max(crud.Table.id)).scalar() or 0
            query = crud.get_characters(session, filters={"status": "active"})
            columns = crud.Table.__table__.columns.keys()
            rows = [dict(zip(columns, character_tuple)) for character_tuple in query]
        self.load_characters(rows)

    # ------------------------------------------------------------------ 调度

    def _schedule_character(self, character):
        base = int(character.pedometer["step"])
        character._base_step = base
        character._spawn_time = self.simulation_time
        character._seq = self._next_seq()
        character._roll = 0
        character._next_life = self._first_time(base, int(character.pedometer["step_threshold"]))
        character._next_wealth = self._first_time(base, WEALTH_PERIOD)
        character._next_age = self._first_time(base, AGE_PERIOD)
        self._push(min(character._next_life, character._next_wealth, character._next_age), WAKE, character)

    def _first_time(self, base, period):
        offset = (-base) % period
        if offset == 0:
            offset = period
        return self.simulation_time + offset

    def _next_seq(self):
        self._seq += 1
        return self._seq

    def _push(self, when, priority, character):
        seq = _PLAZA_SEQ if character is None else character._seq
        self._counter += 1
        heapq.heappush(self._heap, (when, seq, priority, self._counter, character))

    def _ensure_plaza(self, when):
        if self._plaza_scheduled_at is not None and self._plaza_scheduled_at <= when:
            return
        self._plaza_scheduled_at = when
        self._push(when, PLZ, None)

    # ------------------------------------------------------------------ 驱动

    def step(self):
        self.run_until(self.simulation_time + 1)

    def run_until(self, target):
        self._run_until(target)
        if self.simulation_time < target:
            self.simulation_time = target
        self._update_utc()

    def _run_until(self, target):
        heap = self._heap
        characters = self.characters
        while heap and heap[0][0] <= target:
            when, _seq, priority, _counter, character = heapq.heappop(heap)
            self.simulation_time = when
            if priority == PLZ:
                self._dispatch_plaza(when)
                continue
            current = characters.get(character.id)
            if current is None:
                continue

            if current._next_age == when:
                current.age += 1
                current._next_age += AGE_PERIOD
            if current._next_wealth == when:
                if 18 < current.age < 60:
                    current.wealth += 1000
                current._next_wealth += WEALTH_PERIOD
            if current._next_life == when:
                current.pedometer["step"] = current._base_step + (
                    when - current._spawn_time
                )
                if self.rare_stride > 1 and current._roll % self.rare_stride:
                    current.events.acquaintance_only()
                else:
                    current.events.possible_events(self.rare_stride)
                current._roll += 1
                self._ensure_plaza(when)
                current._next_life += int(current.pedometer["step_threshold"])

            self._push(min(current._next_life, current._next_wealth, current._next_age), WAKE, current)

    def _dispatch_plaza(self, when):
        self._plaza_scheduled_at = None
        plaza = self.event_plaza["acquaintance"]
        if any(len(cell_plaza) > 1 for cell_plaza in plaza):
            PeopleEvents(self.event_plaza, self.rng)
        if any(len(cell_plaza) > 1 for cell_plaza in plaza):
            self._ensure_plaza(when + 1)

    def _update_utc(self):
        year, step = divmod(self.simulation_time, 360)
        month, day = divmod(step, 30)
        self.UTC = f"{year}-{month}-{day}"

    # ------------------------------------------------------------ 角色增删

    def create_character(self, character_dict) -> Character:
        cid = self.max_id + 1
        character_dict["id"] = cid
        self.max_id += 1
        character = Character(self, **character_dict)
        character.cell = cid % self.n_cells
        self.characters[cid] = character
        self.insert_queue.put(character.__dict__)
        self._schedule_character(character)
        return character

    def remove_character(self, character_id, character):
        self.characters.pop(character_id, None)
        self.update_queue.put(character.__dict__)
