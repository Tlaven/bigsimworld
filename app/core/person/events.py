import random



class IndividualEvents:
    def __init__(self, model, character):
        self.model = model
        self.character = character
        self.random_marry_requirement()
        self.random_have_child()

    # 随机事件结婚需求
    def random_marry_requirement(self):
        if random.random() < 0.1 and 'marry' not in self.character.to_do and 'spouse' not in self.character.relationships:
            self.character.to_do.append('marry')
            if self.character.gender == 'male':
                self.model.characters_to_do['male_marry'].append(self.character)
            elif self.character.gender == 'female':
                self.model.characters_to_do['female_marry'].append(self.character)

    # 随机事件生子
    def random_have_child(self):
        if random.random() < 0.1 and ( spouse_id := self.character.relationships.get('spouse') ):
            spouse = self.model.characters[spouse_id]
            if random.random() < 0.1 and spouse.relationships.get('spouse')  == self.character.id:
                #self.model.later_set.add_later(self.character.have_child, spouse)
                self.model.characters_to_do['have_child'].append((self.character, spouse))
    