from collections import defaultdict

from app.models import crud
from app.models.table import Table
from app.core.generation.human import generate_character
from app.core.person.events import IndividualEvents
from app.core.person.marry import MarryEvent
from app.core.person.childbirth import ChildbirthEvent
from app.core.person.death import DeathEvent


class Character:
    def __init__(self, model, **kwargs):
        self.model = model
        # 定义允许的属性
        allowed_keys = Table.__table__.columns.keys()
        
        # 初始化属性
        for key in allowed_keys:
            setattr(self, key, kwargs.get(key, None))
        
        
        temp_pedometer = defaultdict(int)
        for key, value in self.pedometer.items():
            temp_pedometer[key] = value
        self.pedometer = temp_pedometer
        
        #relationship_keys = {"acquaintance","familiarity","friend","spouse", "ex-spouses", "father","mother", "child"}
        self.relatives = set()

        temp_ralationships = defaultdict(list)
        for key, value in self.relationships.items():
            temp_ralationships[key] = value
            self.relatives.update(value)
        self.relationships = temp_ralationships

        self.relation_record = defaultdict(list, self.relation_record)

        
        self.publish_keys = ["id", "name", "gender", "age", "wealth"]
        self.publish_relationship_keys = ["friend", "spouse","parent", "child"]

        # init 一些需要的类
        self.events = IndividualEvents(self.model, self)
        self.marry_event = MarryEvent(self)
        self.childbirth_event = ChildbirthEvent(self.model, self)
        self.death_event = DeathEvent(self.model, self)

    # 将人物关系的索引 id 转换为对象
    def init_relationships(self):
        for key, value in self.relationships.items():
            ids = []
            for id in value:
                if id not in self.model.characters:
                    print(f"Character {id} not found in database.")
                else:
                    ids.append(id)
            self.relationships[key] = [self.model.characters[id] for id in ids]
                
    # 基本属性变化
    def change_attribute(self):
        self.pedometer["step"] += 1
        if self.pedometer["step"] % 360 == 0:
            self.age += 1



    def step(self):
        self.change_attribute()
        if self.pedometer["step"] % self.pedometer["step_threshold"] == 0:
            self.events.possible_events()

    @property
    def __dict__(self):
        output_dict = {key: getattr(self, key) for key in Table.__table__.columns.keys()}
        output_dict["relationships"] = {key: [character.id for character in value if isinstance(character, Character)] for key, value in self.relationships.items()}
        return output_dict
    
    @property
    def __publish_dict__(self):
        output_dict = {"atr": [getattr(self, key) for key in self.publish_keys]}
        output_dict["relationships"] = [[(character.id, character.name) for character in self.relationships[key] if isinstance(character, Character)] for key in  self.publish_relationship_keys]
        return output_dict