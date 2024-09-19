


class MarryEvent:
    def __init__(self, character):
        self.character = character
        self.relationships = character.relationships
        self.relation_record = character.relation_record

    def happen(self, other):
        self.self_event(other)
        # 通知有关人员
        for friend in self.relationships['friend']:
            friend.marry_event.notify_friend(self.character)

        for parent in self.relationships['parent']:
            parent.marry_event.notify_parent(self.character)

    def self_event(self, other):
        self.relationships['spouse'].append(other)
        if other in self.relationships['friend']:
            self.relationships['friend'].remove(other)
        elif other in self.relationships['familiarity']:
            self.relationships['familiarity'].remove(other)

    def notify_friend(self, friend):
        #print(f"{self.character.name}的朋友{friend.name}结婚了")
        return
    
    def notify_parent(self, child):
        #print(f"{self.character.name}的{parent.gender}父母{parent.name}结婚了")
        return