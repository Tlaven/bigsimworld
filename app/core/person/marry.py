


class MarryEvent:
    def __init__(self, character):
        self.character = character
        self.relationships = character.relationships

    def happen(self, other):
        self.self_event(other)
        # 通知有关人员
        for friend in self.relationships['friend']:
            friend.marry_event.notify_friend(friend)

        for parent in self.character.relationships['father'] + self.character.relationships['mother']:
            parent.marry_event.notify_parent(parent)

    def self_event(self, other):
        self.character.relationships['spouse'].append(other)
        if other in self.relationships['friend']:
            self.relationships['friend'].remove(other)
        elif other in self.relationships['familiarity']:
            self.relationships['familiarity'].remove(other)
        return

    def notify_friend(self, friend):
        #print(f"{self.character.name}的朋友{friend.name}结婚了")
        return
    
    def notify_parent(self, parent):
        #print(f"{self.character.name}的{parent.gender}父母{parent.name}结婚了")
        return