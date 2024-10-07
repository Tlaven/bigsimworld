import random


class IndividualEvents:
    """
    这个类负责处理个体的各种事件，通过 possible_events() 方法判定是否可以发生事件，并进行调用。
    当事件需要牵扯到相关的人时，只判断是否发生事件，将具体事务交给 Character 类方法处理。
    """
    def __init__(self, model, character):
        self.characters = model.characters
        self.event_plaza = model.event_plaza
        self.publish_list = model.publish_list
        self.character = character
        self.relationships = character.relationships
        self.relation_record = character.relation_record
        self.step_threshold = character.pedometer['step_threshold']


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
        temp_num = len(self.relationships['acquaintance'])
        if (count := round_up_probability(0.1 * self.step_threshold / (temp_num + 12) * 12)):
            self.event_plaza['acquaintance'].extend([self.character] * count)
        if temp_num > 12:
            # 数量太多删除一些最早的
            split_index = random.randint(0, temp_num - 12)
            self.relationships['acquaintance'], temp_list = self.relationships['acquaintance'][split_index:], self.relationships['acquaintance'][:split_index]
            for temp_c in temp_list:
                temp_c.relationships['acquaintance'].remove(self.character)
        
    def familiarity_event(self):
        temp_num1, temp_num2 = len(self.relationships['familiarity']), len(self.relationships['acquaintance'])
        if (count := round_up_probability(0.01 * self.step_threshold * temp_num2 / (temp_num1 + 6) * 6 / 12)):
            count = min(count, temp_num2)
            self.move_temp_set(self.relationships['acquaintance'], self.relationships['familiarity'], count, 'acquaintance', 'familiarity')
        if (temp_num := temp_num1 + count) > 6:
            # 数量太多随机降级几个关系
            self.move_temp_set(self.relationships['familiarity'], self.relationships['acquaintance'], random.randint(0, temp_num - 6), 'familiarity', 'acquaintance')

    def friend_event(self):
        temp_num1, temp_num2 = len(self.relationships['friend']), len(self.relationships['familiarity'])
        if (count := round_up_probability(0.001 * self.step_threshold * temp_num2 / (temp_num1 + 3) * 3 / 6)):
            count = min(count, temp_num2)
            temp_set = self.move_temp_set(self.relationships['familiarity'], self.relationships['friend'], count, 'familiarity', 'friend')

        if (temp_num := temp_num1 + count) > 3:
            # 数量太多随机降级几个关系
            temp_set = self.move_temp_set(self.relationships['friend'], self.relationships['acquaintance'], random.randint(0, temp_num - 3), 'friend', 'acquaintance')
            

    def spouse_event(self):
        if round_up_probability(0.1 * self.step_threshold / 360) and (temp_p := self.relationships['friend'] + self.relationships['familiarity']):
            if (temp_p := [p for p in temp_p if 18 <= p.age < 60 and not p.relationships['spouse']]):
                temp_c = random.choices(temp_p, [0.1 for id in temp_p], k=1)[0]
                # 重要事件，即需要联系有关人员的事件
                self.character.marry_event.happen(temp_c)
                temp_c.marry_event.happen(self.character)
                

    def childbirth_event(self):
        if (count := round_up_probability(0.1 * 0.1 / 2 * self.step_threshold / 32)):
            for _ in range(count):
                spouse = self.relationships['spouse'][0]
                self.character.childbirth_event.happen(spouse)

    def death_event(self):
        if round_up_probability(0.05 * self.step_threshold / 360):
            self.character.death_event.happen()
            




    # 根据 from_list 里的元素的权重属性，随机将 list 里的 count 个元素移动到另一个 list 里
    def move_temp_set(self, from_list: list[object], to_list: list[object], count, from_relation_type, to_relation_type) -> set[object]:
        temp_set = set(random.choices(from_list, [0.1 for temp_c in from_list], k=count))
        for temp_c in temp_set:
            temp_c.relationships[from_relation_type].remove(self.character)
            temp_c.relationships[to_relation_type].append(self.character)
            from_list.remove(temp_c)
            to_list.append(temp_c)
        return temp_set


# 输入一个 float 值，进行随机取整
def round_up_probability(value: float) -> int:
    remainder = value % 1
    return int(value + 1) if remainder > random.random() else int(value)
