from app.core.statistics import func
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



# 随机抽取配对：避免对整份广场做 O(m) 洗牌，只做 O(配对数) 的抽样腾挪
def random_pairing(lst) -> list[tuple[any, any]]:
    pairs_count = len(lst) // 4
    pair_list = []
    for _ in range(pairs_count):
        i = random.randrange(len(lst))
        p1 = lst[i]
        lst[i] = lst[-1]
        lst.pop()
        j = random.randrange(len(lst))
        p2 = lst[j]
        lst[j] = lst[-1]
        lst.pop()
        pair_list.append((p1, p2))
    return pair_list, lst