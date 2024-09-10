from app.models import crud
from app.core.person.character import Character
from app.core.simulation.events import PeopleEvents
from app.core.simulation.later import ExecutionQueue
from app.utils.decorators import time_limit


class SimulationEngine:
    def __init__(self):
        self.simulation_time = 0
        self.characters = {}
        self.characters_to_do = {
            'male_marry': [],
            'female_marry': [],
        }
        self.create_characters_from_db()
        self.create_characters_to_do()
        

    # 通过 crud.Table 对象来创建多个 Character 对象
    def create_characters_from_db(self):
        with crud.get_session() as session:
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

    def create_character(self, character_dict):
        character_dict['id'] = crud.insert_character(**character_dict)
        # 加载人添加到加入执行队列
        self.execution_queue.enqueue(lambda: self.characters.update({character_dict['id']: Character(self, **character_dict)}))
        print(f"Created character {character_dict['name']}.")
        return character_dict['id']

    @time_limit(1, record_name = "simulation_step/s")
    def step(self):
        print(f"Step {self.simulation_time}:")
        self.simulation_time += 1
        self.execution_queue = ExecutionQueue()
        for character in self.characters.values():
            character.step()
        PeopleEvents(self.characters_to_do)
        self.execution_queue.execute_queued_commands()
        
    # 更新数据库中的状态
    def update_status_in_db(self):
        crud.update_multiple_characters(self.characters)
        print("Updated character status in database.")


