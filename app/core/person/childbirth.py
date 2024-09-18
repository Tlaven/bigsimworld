
from app.core.generation.human import generate_character


class ChildbirthEvent:
    def __init__(self, model, character):
        self.model = model
        self.publish_list = model.publish_list
        self.character = character
        self.relationships = character.relationships


    def happen(self, other):
        self.self_event(other)

        for friend in self.character.relationships['friend']:
            friend.childbirth_event.notify_friend(friend)

        for parent in self.character.relationships['father'] + self.character.relationships['mother']:
            parent.childbirth_event.notify_parent(parent)

        for sibling in self.character.relationships['sibling']:
            sibling.childbirth_event.notify_sibling(sibling)

    
    def self_event(self, other):
        if self.character.gender == 'male':
            child_dict = generate_character(xing = self.character.xing,relationships = {'father': [self.character],'mother': [other]})            
            child = self.model.create_character(child_dict)
            self.publish_list.append(("father-child", self.character.id, child.id))
        else:
            child_dict = generate_character(xing = other.xing,relationships = {'father': [other],'mother': [self.character]})
            child = self.model.create_character(child_dict)
            self.publish_list.append(("mother-child", self.character.id, child.id))
        self.relationships['child'].append(child)
        other.relationships['child'].append(child)
        self.publish_list.append(("add-character", child.__publish_dict__))

    def notify_friend(self, friend):
        pass

    def notify_parent(self, parent):
        pass

    def notify_sibling(self, sibling):
        pass