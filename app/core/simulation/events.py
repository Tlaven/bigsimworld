from app.core.probability import func
import random

class PeopleEvents:
    def __init__(self, characters_to_do):
        self.characters_to_do = characters_to_do
        self.random_event()

    
    def random_event(self):
        # 随机事件结婚
        if len(self.characters_to_do['male_marry']) > 0 and len(self.characters_to_do['female_marry']) > 0:
            # 确定结婚数
            marry_count = func.random_number_by_expection(0, min(len(self.characters_to_do['male_marry']), len(self.characters_to_do['female_marry'])))
            males = random.sample(self.characters_to_do['male_marry'], k=marry_count)
            females = random.sample(self.characters_to_do['female_marry'], k=marry_count)
            for male, female in zip(males, females):
                male.marry(female)
                male.to_do.remove('marry')
                female.to_do.remove('marry')
                self.characters_to_do['male_marry'].remove(male)
                self.characters_to_do['female_marry'].remove(female)
                #print(f"Character {male.name} and {female.name} have married.")

        # 随机事件生孩子
        if len(self.characters_to_do['have_child']) > 0:
            # 确定生孩子数
            child_count = func.random_number_by_expection(0, len(self.characters_to_do['have_child']))
            parents = random.sample(self.characters_to_do['have_child'], k=child_count)
            for p1,p2 in parents:
                p1.have_child(p2)
                self.characters_to_do['have_child'].remove((p1,p2))
