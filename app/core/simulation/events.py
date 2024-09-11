from app.core.probability import func
import random

class PeopleEvents:
    def __init__(self, characters_to_do):
        self.characters_to_do = characters_to_do
        self.random_event()

    # 随机事件结婚
    def random_event(self):
        if len(self.characters_to_do['male_marry']) > 0 and len(self.characters_to_do['female_marry']) > 0:
            # 确定结婚数
            marry_count = func.random_number_by_expection(0, min(len(self.characters_to_do['male_marry']), len(self.characters_to_do['female_marry'])))
            males = random.sample(self.characters_to_do['male_marry'], k=marry_count)
            females = random.sample(self.characters_to_do['female_marry'], k=marry_count)
            for i in range(marry_count):
                male = males[i]
                female = females[i]
                male.marry(female)
                male.to_do.remove('marry')
                female.to_do.remove('marry')
                self.characters_to_do['male_marry'].remove(male)
                self.characters_to_do['female_marry'].remove(female)
                #print(f"Character {male.name} and {female.name} have married.")