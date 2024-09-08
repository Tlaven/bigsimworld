from base import crud
from generate.human import generate_character
from person.events import IndividualEvents
import gc



class Character:
    def __init__(self, model, **kwargs):
        self.model = model
        # 定义允许的属性
        allowed_keys = {'id', 'name', 'age', 'gender', 'xing', 'property', 'relationships', 'status', 'to_do'}
        
        # 初始化属性
        for key in allowed_keys:
            setattr(self, key, kwargs.get(key, None))

        # 定义默认属性
        if self.to_do is None:
            self.to_do = []

    def die(self):
        self.status = 'dead'
        crud.update_character(self.id, {'status': 'dead'})
        print(f"Character {self.name} has died.")
        del self.model.characters[self.id]  # 显式删除对象引用，帮助释放内存
        gc.collect()  # 强制进行垃圾回收

    def have_child(self, other):
        if self.gender == 'male':
            child = generate_character(xing = self.xing)
            child['relationships'] = {'father': self.id, 'mother': other.id}
        else:
            child = generate_character(xing = other.xing)
            child['relationships'] = {'father': other.id,'mother': self.id}
        if not 'children' in self.relationships:
            self.relationships['children'] = []
        if not 'children' in other.relationships:
            other.relationships['children'] = []
        child_id = self.model.create_character(child)
        
        self.relationships['children'].append(child_id)
        other.relationships['children'].append(child_id)

    def marry(self, other):
        if 'spouse' not in self.relationships and 'spouse' not in other.relationships:
            self.relationships['spouse'] = other.id
            other.relationships['spouse'] = self.id
        else:
            print("Cannot marry, already married.")

    def divorce(self, other):
        if self.relationships['spouse'] == other.id and other.relationships['spouse'] == self.id:
            del self.relationships['spouse']
            del other.relationships['spouse']
            if not 'ex-spouses' in self.relationships:
                self.relationships['ex-spouses'] = []
            if not 'ex-spouses' in other.relationships:
                other.relationships['ex-spouses'] = []
            self.relationships['ex-spouses'].append(other.id)
            other.relationships['ex-spouses'].append(self.id)
        else:
            print("Cannot divorce, not married.")

    def step(self):
        IndividualEvents(self.model, self)


