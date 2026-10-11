from app.core.statistics import func
import random

class PeopleEvents:
    def __init__(self, event_plaza):
        self.event_plaza = event_plaza
        self.possible_events()

    def possible_events(self):
        # event_plaza['acquaintance'] 是按"空间格子"分区的列表的列表：
        # 只在同一格子内部配对，实现局部化（n_cells=1 时等价于原全局行为）。
        for cell_plaza in self.event_plaza['acquaintance']:
            if len(cell_plaza) > 1:
                self.acquaintance_event(cell_plaza)

    def acquaintance_event(self, cell_plaza):
        paire_plaza, _left = random_pairing(cell_plaza)
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