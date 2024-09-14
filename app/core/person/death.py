


class DeathEvent:
    def __init__(self, model, character):
        self.model = model
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

    def self_event(self):
        self.character.status = 'dead'
        for relationship, characters in self.relationships.items():
            for character in characters:
                character.relationships[relationship].remove(self.character)
        self.model.remove_character(self.character.id, self.character)

    def notify_friend(self, friend):
        pass

    def notify_spouse(self, spouse):
        spouse.relationships['ex-spouse'].append(self.character.id)

    def notify_parent(self, parent):
        parent.relationships['ex-child'].append(self.character.id)

    def notify_sibling(self, sibling):
        pass













