from app.models import crud
from app.core.person.character import Character
from app.core.simulation.events import PeopleEvents
from app.utils.decorators import time_limit
from app.utils.cache import py_cache


class SimulationEngine:
    def __init__(self, db_queues):
        self.simulation_time = 0
        self.characters = {}
        self.characters_to_do = {
            'male_marry': [],
            'female_marry': [],
            'have_child': []
        }
        
        self.create_characters_from_db()
        self.create_characters_to_do()

        # 数据库修改进程的共享队列
        self.insert_queue = db_queues['insert']
        self.update_queue = db_queues['update']
        self.delete_queue = db_queues['delete']

    # 通过 crud.Table 对象来创建多个 Character 对象
    def create_characters_from_db(self):
        with crud.get_session() as session:
            # 查询User表中的数据条数
            self.max_id = session.query(crud.Table).count()
            query = crud.get_characters(session, filters={'status': 'active'})
            # 查询结果并创建 Character 对象
            self.characters.update({
                character_table.id: Character(
                    self, 
                    **{col.name: getattr(character_table, col.name) for col in crud.Table.__mapper__.c}
                )
                for character_table in query
            })
        print(f"Created {len(self.characters)} characters.")

    # 通过 character.to_do 来创建 self.characters_to_do 字典
    def create_characters_to_do(self):
        for character in self.characters.values():
            if 'marry' in character.to_do:
                if character.gender == 'male':
                    self.characters_to_do['male_marry'].append(character)
                elif character.gender == 'female':
                    self.characters_to_do['female_marry'].append(character)

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
        PeopleEvents(self.characters_to_do)
        
    # 更新数据库中的状态
    def update_status_in_db(self):
        crud.update_multiple_characters(self.characters)
        print("Updated character status in database.")



