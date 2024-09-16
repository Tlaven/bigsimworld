from app.core.probability import func
import random

class PeopleEvents:
    def __init__(self, event_plaza):
        self.event_plaza = event_plaza
        self.acquaintance_plaza = event_plaza['acquaintance']
        self.possible_events()

    
    def possible_events(self):
        if len(self.acquaintance_plaza) > 1:
            self.acquaintance_event()
        

    def acquaintance_event(self):
        paire_plaza, self.event_plaza['acquaintance'] = random_pairing(self.acquaintance_plaza)
        for (p1, p2) in paire_plaza:
            if p1 not in p2.relatives and p2 not in p1.relatives and p1.id != p2.id:
                p1.relationships['acquaintance'].append(p2)
                p2.relationships['acquaintance'].append(p1)



# 随机配对一部分取出
def random_pairing(lst) -> list[tuple[any, any]]:
    # 分割索引两半，并保证一个列表长度为偶数
    split_index = len(lst) // 2

    random.shuffle(lst)
    pair_list, left_list = lst[:split_index], lst[split_index:]
    return list(zip(pair_list[::2], pair_list[1::2])), left_list