
from app.core.generation.human import generate_character


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

        self.relationships['child'].append(newborn)
        other.relationships['child'].append(newborn)
    
    def self_event(self, other):
        if self.character.gender == 'male':
            xing = self.character.xing
        else:
            xing = other.xing
        newborn_dict = generate_character(xing = xing, DOB = self.model.UTC)
        newborn = self.model.create_character(newborn_dict)
        newborn.relationships['parent'] = [self.character, other]

        return newborn

    def notify_child(self, newborn):
        self.relationships['sibling'].append(newborn)
        newborn.relationships['sibling'].append(self.character)

    def notify_friend(self, friend):
        pass

    def notify_parent(self, child):
        pass

    def notify_sibling(self, sibling):
        pass