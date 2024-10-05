


class DeathEvent:
    def __init__(self, model, character):
        self.model = model
        self.publish_list = model.publish_list
        self.character = character
        self.relationships = character.relationships
        self.relation_record = character.relation_record

    def happen(self):
        for acquaintance in self.relationships['acquaintance']:
            acquaintance.death_event.notify_acquaintance(self.character)

        for familiarity in self.relationships['familiarity']:
            familiarity.death_event.notify_familiarity(self.character)

        for friend in self.relationships['friend']:
            friend.death_event.notify_friend(self.character)

        for spouse in self.relationships['spouse']:
            spouse.death_event.notify_spouse(self.character)
            
        for parent in self.relationships['parent']:
            parent.death_event.notify_parent(self.character)

        for sibling in self.relationships['sibling']:
            sibling.death_event.notify_sibling(self.character)
 
        for child in self.relationships['child']:
            child.death_event.notify_child(self.character)

        self.self_event()


    def self_event(self):
        self.character.status = 'dead'
        self.relationships.clear()
            
        self.model.remove_character(self.character.id, self.character)
        self.model.event_plaza['acquaintance'] = [character for character in self.model.event_plaza['acquaintance'] if character.id != self.character.id]

    def notify_acquaintance(self, acquaintance):
        self.relationships['acquaintance'].remove(acquaintance)

    def notify_familiarity(self, familiarity):
        self.relationships['familiarity'].remove(familiarity)

    def notify_friend(self, friend):
        self.relationships['friend'].remove(friend)
        self.relation_record['friend'].append(friend.id)
        friend.relation_record['friend'].append(self.character.id)

    def notify_spouse(self, spouse):
        self.relationships['spouse'].remove(spouse)
        self.relation_record['spouse'].append(spouse.id)
        spouse.relation_record['spouse'].append(self.character.id)

    def notify_parent(self, child):
        self.relationships['child'].remove(child)
        self.relation_record['child'].append(child.id)
        child.relation_record['parent'].append(self.character.id)

    def notify_sibling(self, sibling):
        self.relationships['sibling'].remove(sibling)
        self.relation_record['sibling'].append(sibling.id)
        sibling.relation_record['sibling'].append(self.character.id)

    def notify_child(self, parent):
        self.relationships['parent'].remove(parent)
        self.relation_record['parent'].append(parent.id)
        parent.relation_record['child'].append(self.character.id)


