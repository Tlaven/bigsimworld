import random



class IndividualEvents:
    def __init__(self, model, character):
        self.characters = model.characters
        self.event_plaza = model.event_plaza
        self.character = character
        self.id = character.id
        self.age = character.age
        self.acquaintance = character.relationships['acquaintance']
        self.familiarity = character.relationships['familiarity']
        self.friend = character.relationships['friend']
        self.spouse = character.relationships['spouse']
        self.possible_events()


    def possible_events(self):
        if self.age >= 6:
            self.acquaintance_event()
            self.familiarity_event()
            self.friend_event()

        if 18 <= self.age < 60 and not self.spouse:
            self.spouse_event()


    def acquaintance_event(self):
        if (acquaintance_ratio := 1 / (len(self.acquaintance) * 10 + 500) * 500) < random.random() * 0.1:
            # 数量太多删除最早的一个
            temp_c = self.acquaintance.pop(0)
            temp_c.relationships['acquaintance'].remove(self.id)
        else:
            if (count := random_int(0.1 * acquaintance_ratio)):
                self.event_plaza['acquaintance'].extend([self.character] * count)
        
    def familiarity_event(self):
        if (familiarity_ratio := 1 / (len(self.familiarity) * 10 + 100) * 100) < random.random() * 0.5:
            self.move_temp_set(self.familiarity, self.acquaintance, 1, 'familiarity', 'acquaintance')
        else:
            if (count := random_int(0.1 * len(self.acquaintance) * familiarity_ratio)):
                self.move_temp_set(self.acquaintance, self.familiarity, count, 'acquaintance', 'familiarity')

    def friend_event(self):
        if (friend_ratio := 1 / (len(self.friend) * 100 + 500) * 500) < random.random() * 0.5:
            self.move_temp_set(self.friend, self.acquaintance, 1, 'friend', 'acquaintance')
        else:
            if (count := random_int(0.1 * len(self.familiarity) * friend_ratio)):
                self.move_temp_set(self.familiarity, self.friend, count, 'familiarity', 'friend')

    def spouse_event(self):
        if random_int(0.1) and (temp_p := self.friend + self.familiarity):
            temp_c = random.choices(temp_p, [0.1 for id in temp_p], k=1)[0]
            if not temp_c.relationships['spouse']:
                if len(self.friend) <= temp_p.index(temp_c):
                    self.familiarity.remove(temp_c)
                    self.move_temp_set([temp_c], self.spouse, 1,'familiarity','spouse')
                else:
                    self.friend.remove(temp_c)
                    self.move_temp_set([temp_c], self.spouse, 1,'friend','spouse')

    # def possible_events(self):
    #     # acquaintance 根据 character 属性决定 count
    #     if (acquaintance_ratio := 1 / (len(self.acquaintance) * 10 + 500) * 500) < random.random() * 0.5:
    #         temp_c = self.acquaintance[-1]  
    #         self.acquaintance = self.acquaintance[:-1]
    #         self.characters[temp_c].acquaintance.remove(self.id)
    #     else:
    #         if (count := random_int(0.1 * acquaintance_ratio)):
    #             self.acquaintance_event(count)

    #     if (familiarity_ratio := 1 / (len(self.familiarity) * 10 + 100) * 100) < random.random() * 0.5:
    #         temp_set = move_temp_set(self.familiarity, self.acquaintance, [0.1 for id in self.familiarity], 1)
    #         for id in temp_set:
    #             self.characters[id].acquaintance.append(self.id)
    #             self.characters[id].familiarity.remove(self.id)
    #     else:
    #         if (count := random_int(0.1 * len(self.acquaintance) * familiarity_ratio)):
    #             self.familiarity_event(count)

    #     if random_int(0.1 * len(self.familiarity) / (len(self.friend) * 100 + 500) * 500):
    #         self.friend_event()

    #     if not self.spouse and random_int(0.1) and 18 < self.age < 60 and (temp_p := self.familiarity + self.friend):
    #         self.spouse_event(temp_p)

    # def acquaintance_event(self, count):
    #     self.event_plaza['acquaintance'].extend([self.character] * count)

    # def familiarity_event(self, count):
    #     temp_set = move_temp_set(self.acquaintance, self.familiarity, [0.1 for id in self.acquaintance], count)
    #     for id in temp_set:
    #         self.characters[id].acquaintance.remove(self.id)
    #         self.characters[id].familiarity.append(self.id)

    # def friend_event(self):
    #     temp_set = move_temp_set(self.familiarity, self.friend, [0.1 for id in self.familiarity], 1)
    #     for id in temp_set:
    #         self.characters[id].familiarity.remove(self.id)
    #         self.characters[id].friend.append(self.id)

    # def spouse_event(self, temp_p):
    #     self.spouse.append(random.choices(temp_p, [0.1 for id in temp_p], k=1)[0])
    #     self.characters[self.spouse[0]].spouse.append(self.id)
    #     if self.spouse[0] in self.friend:
    #         self.friend.remove(self.spouse[0])
    #         self.characters[self.spouse[0]].friend.remove(self.id)
    #     else:
    #         self.familiarity.remove(self.spouse[0])
    #         self.characters[self.spouse[0]].familiarity.remove(self.id)
        





    # 根据 from_list 里的元素的权重属性，随机将 list 里的 count 个元素移动到另一个 list 里
    def move_temp_set(self, from_list: list[object], to_list: list[object], count, from_relation_type, to_relation_type):
        temp_set = set(random.choices(from_list, [0.1 for obj in from_list], k=count))
        for obj in temp_set:
            obj.relationships[from_relation_type].remove(self.character)
            obj.relationships[to_relation_type].append(self.character)
            from_list.remove(obj)
            to_list.append(obj)
        return temp_set


# 输入一个 float 值，进行随机取整
def random_int(value) -> int:
    remainder = value%1
    if remainder > random.random():
        value += 1
    return int(value)