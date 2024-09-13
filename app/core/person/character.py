from app.models import crud
from app.core.generation.human import generate_character
from app.core.person.events import IndividualEvents



class Character:
    def __init__(self, model, **kwargs):
        self.model = model
        # 定义允许的属性
        allowed_keys = {'id', 'name', 'age', 'gender', 'xing', 'property', 'relationships', 'status'}
        
        # 初始化属性
        for key in allowed_keys:
            setattr(self, key, kwargs.get(key, None))

        relationship_keys = {'acquaintance','familiarity','friend','spouse', 'ex-spouses', 'father','mother', 'children'}
        temp_relationship = {}

        for key in relationship_keys:
            value = self.relationships.get(key, set())
            setattr(self, key, value)
            temp_relationship[key] = value

        self.relationships = temp_relationship


    def step(self):
        IndividualEvents(self.model, self)


