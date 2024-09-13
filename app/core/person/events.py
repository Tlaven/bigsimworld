import random



class IndividualEvents:
    def __init__(self, model, character):
        self.model = model
        self.event_plaza = model.event_plaza
        self.character = character
        self.possible_events()


    def possible_events(self):
        # acquaintance 根据 character 属性决定 count
        count = 1
        for _ in range(count):
            self.acquaintance()

        # 同样


    def acquaintance(self):
        self.event_plaza['acquaintance'].append(self.character)

    
