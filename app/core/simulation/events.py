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
        paire_plaza = random_pairing(self.acquaintance_plaza)
        self.acquaintance_plaza = self.acquaintance_plaza[-1]
        for (p1, p2) in paire_plaza:
            if p1.id not in p2.relatives and p2.id not in p1.relatives and p1.id!= p2.id:
                p1.acquaintance.append(p2.id)
                p2.acquaintance.append(p1.id)






# 随机配对
def random_pairing(lst) -> list[tuple[any, any]]:
    if len(lst) % 2 != 0:
        lst = lst[:-1]

    shuffled = lst[:]
    random.shuffle(shuffled)
    return list(zip(shuffled[::2], shuffled[1::2]))