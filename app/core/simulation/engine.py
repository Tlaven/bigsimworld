from app.models import crud
from app.core.person.character import Character
from app.core.simulation.events import PeopleEvents
from app.utils.decorators import time_limit
from app.utils.cache import py_cache


class SimulationEngine:
    def __init__(self, db_queues):
        self.simulation_time = 0
        self.characters = {}
        self.event_plaza = {
            "acquaintance": [],
        }
        
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
            ('id', 'name', 'age', 'gender', 'xing', 'property', 'relationships', 'start_time', 'end_time','status'),
              character_tuple))) for character_tuple in query
            })
        print(f"Created {len(self.characters)} characters.")

    def create_character(self, character_dict) -> Character:
        # character_dict['id'] = crud.insert_character(**character_dict)
        temp_dict = character_dict.copy()
        self.insert_queue.put(temp_dict)
        
        character_dict['id'] = self.max_id + 1
        self.max_id += 1
        character = Character(self, **character_dict)
        self.characters[character_dict['id']] =  character
        return character
    
    def create_characters(self, characters_list):
        character_ids = crud.insert_multiple_characters(characters_list)
        # self.characters.update({character_id: Character(self, **character_dict, id = character_id) for character_id, character_dict in zip(character_ids, characters_list)})
        return character_ids

    @time_limit(1, record_name = "simulation_step/s")
    def step(self):
        print(f"Step {self.simulation_time}:{py_cache.get('simulation_step/s')[-1]} people:{len(self.characters)}")
        self.simulation_time += 1
        for character in self.characters.values():
            character.step()
        PeopleEvents(self.event_plaza)
        
    # 更新数据库中的状态
    def update_status_in_db(self):
        crud.update_multiple_characters(self.characters)
        print("Updated character status in database.")



