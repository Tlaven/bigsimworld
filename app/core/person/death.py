


class DeathEvent:
    def __init__(self, model, character):
        self.model = model
        self.publish_list = model.publish_list
        self.character = character
        self.relationships = character.relationships

    def happen(self):
        for friend in self.character.relationships['friend']:
            friend.death_event.notify_friend(friend)

        for spouse in self.character.relationships['spouse']:
            spouse.death_event.notify_spouse(spouse)
            
        for parent in self.character.relationships['parent']:
            parent.death_event.notify_parent(parent)

        for sibling in self.character.relationships['sibling']:
            sibling.death_event.notify_sibling(sibling)

        for child in self.character.relationships['child']:
            child.death_event.notify_child(child)

        self.self_event()


    def self_event(self):
        self.character.status = 'dead'
        for relationship, others in self.relationships.items():
            for other in others:
                other.relationships[relationship].remove(self.character)
        self.relationships.clear()
            

        self.model.remove_character(self.character.id, self.character)
        self.model.event_plaza['acquaintance'] = [character for character in self.model.event_plaza['acquaintance'] if character.id != self.character.id]

    def notify_friend(self, friend):
        pass

    def notify_spouse(self, spouse):
        pass

    def notify_parent(self, parent):
        pass

    def notify_sibling(self, sibling):
        pass

    def notify_child(self, child):
        pass













