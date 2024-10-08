from json import dumps

from app.models import crud
from app.core.person.character import Character
from app.core.simulation.events import PeopleEvents
from app.utils.decorators import time_limit
from app.utils.cache import py_cache
from app.utils.later import LaterDeque


class SimulationEngine:
    def __init__(self, db_queues):
        self.simulation_time = 0
        self.characters = {}
        self.event_plaza = {
            "acquaintance": [],
        }
        self.publish_list = []  # 需要 publish 对象的集合，根据是否更新关系来决定是否加入
        self.later_queue = LaterDeque()
        
        self.create_characters_from_db()

        # 数据库修改进程的共享队列
        self.insert_queue = db_queues['insert']
        self.update_queue = db_queues['update']
        self.delete_queue = db_queues['delete']

    # 通过 crud.Table 对象来创建多个 Character 对象
    def create_characters_from_db(self):
        with crud.get_session() as session:
            # 获得数据库中最大的 id
            self.max_id = session.query(crud.Table).order_by(crud.Table.id.desc()).first().id
            query = crud.get_characters(session, filters={'status': 'active'})
            # 查询结果并创建 Character 对象
            self.characters.update({
                character_tuple[0]: Character(self, **dict(zip(
            crud.Table.__table__.columns.keys(),
              character_tuple))) for character_tuple in query
            })
        print(f"Created {len(self.characters)} characters.")
        
        for character in self.characters.values():
            character.init_relationships()

    def create_character(self, character_dict) -> Character:
        # character_dict['id'] = crud.insert_character(**character_dict)

        id = self.max_id + 1
        character_dict['id'] = id
        self.max_id += 1
        character = Character(self, **character_dict)
        self.later_queue.add_later(self.characters.update, {id: character})
        self.insert_queue.put(character.__dict__)

        return character

    def remove_character(self, character_id, character):
        self.later_queue.add_later(self.characters.pop, character_id)
        self.later_queue.add_later(self.update_queue.put, character.__dict__)


    def create_characters(self, characters_list):
        character_ids = crud.insert_multiple_characters(characters_list)
        # self.characters.update({character_id: Character(self, **character_dict, id = character_id) for character_id, character_dict in zip(character_ids, characters_list)})
        return character_ids
    
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

    @property
    def __publish_json__(self):
        # publish_json = dumps(self.publish_list)
        # self.publish_list.clear()
        return dumps(self.characters[1].__publish_dict__)

