


class DeathEvent:
    def __init__(self, model, character):
        self.model = model
        self.publish_list = model.publish_list
        self.character = character
        self.relationships = character.relationships

    def happen(self):
        self.self_event()

        for friend in self.character.relationships['friend']:
            friend.death_event.notify_friend(friend)

        for spouse in self.character.relationships['spouse']:
            spouse.death_event.notify_spouse(spouse)
            
        for parent in self.character.relationships['father'] + self.character.relationships['mother']:
            parent.death_event.notify_parent(parent)

        for sibling in self.character.relationships['sibling']:
            sibling.death_event.notify_sibling(sibling)

        for child in self.character.relationships['child']:
            child.death_event.notify_child(child)

    def self_event(self):
        self.character.status = 'dead'
        self.publish_list.append(("dead", self.character.id))
        for relationship, others in self.relationships.items():
            for other in others:
                lst = other.relationships[relationship]
                if other in lst:
                    lst.remove(self.character)
            

        self.model.remove_character(self.character.id, self.character)
        self.model.event_plaza['acquaintance'] = [character for character in self.model.event_plaza['acquaintance'] if character.id != self.character.id]

    def notify_friend(self, friend):
        self.publish_list.append(("re-friend", friend.id, self.character.id))

    def notify_spouse(self, spouse):
        spouse.relationships['ex-spouse'].append(self.character.id)
        self.publish_list.append(("ex-spouse", spouse.id, self.character.id))
        self.publish_list.append(("re-spouse", spouse.id, self.character.id))

    def notify_parent(self, parent):
        parent.relationships['ex-child'].append(self.character.id)
        self.publish_list.append(("re-parent-child", parent.id, self.character.id))

    def notify_sibling(self, sibling):
        pass

    def notify_child(self, child):
        child.relationships['ex-parent'].append(self.character.id)













