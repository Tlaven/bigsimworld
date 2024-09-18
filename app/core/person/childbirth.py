
from app.core.generation.human import generate_character


class ChildbirthEvent:
    def __init__(self, model, character):
        self.model = model
        self.publish_list = model.publish_list
        self.character = character
        self.relationships = character.relationships
        self.relation_record = character.relation_record


    def happen(self, other):
        self.self_event(other)

        for friend in self.character.relationships['friend']:
            friend.childbirth_event.notify_friend(friend)

        for parent in self.character.relationships['parent']:
            parent.childbirth_event.notify_parent(parent)

        for sibling in self.character.relationships['sibling']:
            sibling.childbirth_event.notify_sibling(sibling)

    
    def self_event(self, other):
        if self.character.gender == 'male':
            xing = self.character.xing
        else:
            xing = other.xing
        child_dict = generate_character(xing = xing, DOB = self.model.UTC, relationships = {'parent': [self.character, other]}, relation_record = {'parent': [self.character, other]})
        child = self.model.create_character(child_dict)
        self.relationships['child'].append(child)
        other.relationships['child'].append(child)
        self.relation_record['child'].append(child.id)
        other.relation_record['child'].append(child.id)

    def notify_friend(self, friend):
        pass

    def notify_parent(self, parent):
        pass

    def notify_sibling(self, sibling):
        pass