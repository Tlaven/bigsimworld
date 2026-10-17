
from app.core.generation.human import generate_character
from app.core.person.links import link


class ChildbirthEvent:
    # self and other is parent
    def __init__(self, model, character):
        self.model = model
        self.publish_list = model.publish_list
        self.character = character
        self.relationships = character.relationships
        self.relation_record = character.relation_record


    def happen(self, other):
        newborn = self.self_event(other)

        for child in self.relationships['child']:
            child.childbirth_event.notify_child(newborn)

        for friend in self.relationships['friend'] + other.relationships['friend']:
            friend.childbirth_event.notify_friend(newborn)

        for parent in self.relationships['parent'] + other.relationships['parent']:
            parent.childbirth_event.notify_parent(newborn)

        for sibling in self.relationships['sibling'] + other.relationships['sibling']:
            sibling.childbirth_event.notify_sibling(newborn)

        # 子/亲边必须在通知循环**之后**建立：若先建，上面的
        # `for child in self.relationships['child']` 会把新生儿也当成"已有的孩子"通知一遍
        # （notify_child 会给它自己加 sibling 边）。顺序是语义的一部分。
        link(self.character, newborn, 'child', 'parent')
        link(other, newborn, 'child', 'parent')

    def self_event(self, other):
        if self.character.gender == 'male':
            xing = self.character.xing
        else:
            xing = other.xing
        newborn_dict = generate_character(xing = xing, DOB = self.model.UTC)
        newborn = self.model.create_character(newborn_dict)

        return newborn

    def notify_child(self, newborn):
        link(self.character, newborn, 'sibling')

    def notify_friend(self, friend):
        pass

    def notify_parent(self, child):
        pass

    def notify_sibling(self, sibling):
        pass