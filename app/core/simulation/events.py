import random

from app.core.person.links import link


class PeopleEvents:
    def __init__(self, event_plaza, rng=None):
        self.event_plaza = event_plaza
        self.rng = rng or random
        self.possible_events()

    def possible_events(self):
        # event_plaza['acquaintance'] 是按"空间格子"分区的列表的列表：
        # 只在同一格子内部配对，实现局部化（n_cells=1 时等价于原全局行为）。
        for cell_plaza in self.event_plaza['acquaintance']:
            if len(cell_plaza) > 1:
                self.acquaintance_event(cell_plaza)

    def acquaintance_event(self, cell_plaza):
        paire_plaza, _left = random_pairing(cell_plaza, self.rng)
        for (p1, p2) in paire_plaza:
            # 原实现还检查 `p1/p2 not in *.relatives`（"避免与亲属配对"），但那两个字段
            # 构造后恒为空 ⇒ 该检查从未生效。"亲属避让"**未实现**（见 L3 冻结面），
            # 此处只保留真正生效的同 id 保护（广场会把同一角色 push 多次）。
            if p1.id != p2.id:
                link(p1, p2, 'acquaintance')



# 随机抽取配对：避免对整份广场做 O(m) 洗牌，只做 O(配对数) 的抽样腾挪
def random_pairing(lst, rng=None) -> list[tuple[any, any]]:
    rng = rng or random
    pairs_count = len(lst) // 4
    pair_list = []
    for _ in range(pairs_count):
        i = rng.randrange(len(lst))
        p1 = lst[i]
        lst[i] = lst[-1]
        lst.pop()
        j = rng.randrange(len(lst))
        p2 = lst[j]
        lst[j] = lst[-1]
        lst.pop()
        pair_list.append((p1, p2))
    return pair_list, lst