import random



class IndividualEvents:
    """
    这个类负责处理个体的各种事件，通过 possible_events() 方法判定是否可以发生事件，并进行调用。
    当事件需要牵扯到相关的人时，只判断是否发生事件，将具体事务交给 Character 类方法处理。
    """
    def __init__(self, model, character):
        self.characters = model.characters
        self.event_plaza = model.event_plaza
        self.character = character
        self.relationships = character.relationships


    def possible_events(self):
        if self.character.age >= 6:
            self.acquaintance_event()
            self.familiarity_event()
            self.friend_event()

        if 18 <= self.character.age < 60 and not self.relationships['spouse']:
            self.spouse_event()

        if self.relationships['spouse'] and self.character.age <= 50:
            self.childbirth_event()

        if self.character.age >= 60:
            self.death_event()


    def acquaintance_event(self):
        if (acquaintance_ratio := 1 / (len(self.relationships['acquaintance']) * 10 + 200) * 200) < 0.5:
            # 数量太多删除最早的一个
            temp_c = self.relationships['acquaintance'].pop(0)
            temp_c.relationships['acquaintance'].remove(self.character)
        else:
            if (count := round_up_probability(0.1 * acquaintance_ratio)):
                self.event_plaza['acquaintance'].extend([self.character] * count)
        
    def familiarity_event(self):
        if (familiarity_ratio := 1 / (len(self.relationships['familiarity']) * 10 + 100) * 100) < 0.5:
            # 数量太多随机降级一个关系
            self.move_temp_set(self.relationships['familiarity'], self.relationships['acquaintance'], 1, 'familiarity', 'acquaintance')
        else:
            if (count := round_up_probability(0.1 * len(self.relationships['acquaintance']) * familiarity_ratio)):
                self.move_temp_set(self.relationships['acquaintance'], self.relationships['familiarity'], count, 'acquaintance', 'familiarity')

    def friend_event(self):
        if (friend_ratio := 1 / (len(self.relationships['friend']) * 100 + 500) * 500) < 0.5:
            self.move_temp_set(self.relationships['friend'], self.relationships['acquaintance'], 1, 'friend', 'acquaintance')
        else:
            if (count := round_up_probability(0.1 * len(self.relationships['familiarity']) * friend_ratio)):
                self.move_temp_set(self.relationships['familiarity'], self.relationships['friend'], count, 'familiarity', 'friend')

    def spouse_event(self):
        if round_up_probability(0.1) and (temp_p := self.relationships['friend'] + self.relationships['familiarity']):
            if (temp_p := [p for p in temp_p if 18 <= p.age < 60 and not p.relationships['spouse']]):
                temp_c = random.choices(temp_p, [0.1 for id in temp_p], k=1)[0]
                # 重要事件，即需要联系有关人员的事件
                self.character.marry_event.happen(temp_c)
                temp_c.marry_event.happen(self.character)

    def childbirth_event(self):
        if (count := round_up_probability(0.1 * 0.1 / 2)):
            for _ in range(count):
                self.character.childbirth_event.happen(self.relationships['spouse'][0])

    def death_event(self):
        if round_up_probability(0.05):
            self.character.death_event.happen()




    # 根据 from_list 里的元素的权重属性，随机将 list 里的 count 个元素移动到另一个 list 里
    def move_temp_set(self, from_list: list[object], to_list: list[object], count, from_relation_type, to_relation_type) -> set[object]:
        temp_set = set(random.choices(from_list, [0.1 for obj in from_list], k=count))
        for obj in temp_set:
            obj.relationships[from_relation_type].remove(self.character)
            obj.relationships[to_relation_type].append(self.character)
            from_list.remove(obj)
            to_list.append(obj)
        return temp_set


# 输入一个 float 值，进行随机取整
def round_up_probability(value: float) -> int:
    remainder = value % 1
    return int(value + 1) if remainder > random.random() else int(value)
