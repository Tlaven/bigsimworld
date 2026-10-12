from sqlalchemy import func

from app.models import crud
from app.core.person.character import Character
from app.core.simulation.events import PeopleEvents
from app.utils.later import LaterDeque


class SimulationEngine:
    def __init__(self, db_queues, characters=None, n_cells=1):
        self.simulation_time = 0
        self.characters = {}
        self.n_cells = n_cells
        self.event_plaza = {
            "acquaintance": [[] for _ in range(n_cells)],
        }
        self.publish_list = []  # 需要 publish 对象的集合，根据是否更新关系来决定是否加入
        self.later_queue = LaterDeque()

        # 数据库修改进程的共享队列
        self.insert_queue = db_queues['insert']
        self.update_queue = db_queues['update']
        self.delete_queue = db_queues['delete']

        if characters is None:
            self.create_characters_from_db()
        else:
            # 直接从显式给定的角色列表构建（不经过数据库），用于测试与基准测量
            self.load_characters(characters)

    # 从 dict 列表构建 Character 对象；id 缺失时自动分配
    def load_characters(self, character_dicts):
        self.characters = {}
        self.max_id = 0
        for character_dict in character_dicts:
            character_dict = dict(character_dict)
            cid = character_dict.get('id')
            if cid is None:
                cid = self.max_id + 1
                character_dict['id'] = cid
            self.max_id = max(self.max_id, cid)
            self.characters[cid] = Character(self, **character_dict)
            self.characters[cid].cell = cid % self.n_cells
        print(f"Created {len(self.characters)} characters.")

        for character in self.characters.values():
            character.init_relationships()

    # 通过 crud.Table 对象来创建多个 Character 对象
    def create_characters_from_db(self):
        with crud.get_session() as session:
            # 获得数据库中最大的 id（空库时为 0）
            self.max_id = session.query(func.max(crud.Table.id)).scalar() or 0
            query = crud.get_characters(session, filters={'status': 'active'})
            columns = crud.Table.__table__.columns.keys()
            rows = [dict(zip(columns, character_tuple)) for character_tuple in query]
        self.load_characters(rows)

    def create_character(self, character_dict) -> Character:
        id = self.max_id + 1
        character_dict['id'] = id
        self.max_id += 1
        character = Character(self, **character_dict)
        character.cell = id % self.n_cells
        self.later_queue.add_later(self.characters.update, {id: character})
        self.insert_queue.put(character.__dict__)

        return character

    def remove_character(self, character_id, character):
        self.later_queue.add_later(self.characters.pop, character_id)
        self.later_queue.add_later(self.update_queue.put, character.__dict__)

    # 基本属性变化
    def change_attribute(self):
        self.simulation_time += 1
        year, step = divmod(self.simulation_time, 360)
        month, day = divmod(step, 30)
        self.UTC = f"{year}-{month}-{day}"


    def step(self):
        self.change_attribute()
        for character in self.characters.values():
            character.step()
        PeopleEvents(self.event_plaza)
        self.later_queue.run_later()
        
    # 更新数据库中的状态
    def update_status_in_db(self):
        crud.update_multiple_characters(self.characters)
        print("Updated character status in database.")

