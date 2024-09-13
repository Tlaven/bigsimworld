from app.models import crud
from app.models.table import Table
from app.core.generation.human import generate_character
from app.core.person.events import IndividualEvents



class Character:
    def __init__(self, model, **kwargs):
        self.model = model
        # 定义允许的属性
        allowed_keys = Table.__table__.columns.keys()
        
        # 初始化属性
        for key in allowed_keys:
            setattr(self, key, kwargs.get(key, None))

        relationship_keys = {'acquaintance','familiarity','friend','spouse', 'ex-spouses', 'father','mother', 'children'}
        self.relatives = set()
        temp_relationship = {}

        for key in relationship_keys:
            value = self.relationships.get(key, [])
            setattr(self, key, value)
            temp_relationship[key] = value
            self.relatives.update(value)

        self.relationships = temp_relationship

    # 将人物关系的索引 id 转换为对象
    def init_relationships(self):
        for key, value in self.relationships.items():
            self.relationships[key] = [self.model.characters[id] for id in value]
 

    def step(self):
        IndividualEvents(self.model, self)

    @property
    def __dict__(self):
        output_dict = {key: getattr(self, key) for key in Table.__table__.columns.keys()}
        output_dict['relationships'] = {key: [character.id for character in value] for key, value in self.relationships.items()}
        return output_dict