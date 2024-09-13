from app.core.probability import func
import random

class PeopleEvents:
    def __init__(self, event_plaza):
        self.event_plaza = event_plaza
        self.acquaintance_plaza = event_plaza['acquaintance']
        self.possible_events()

    
    def possible_events(self):
        if len(self.acquaintance_plaza) > 1:
            self.acquaintance()

    def acquaintance(self):
        paire_plaza = random_pairing(self.acquaintance_plaza)
        self.acquaintance_plaza = self.acquaintance_plaza[-1]
        for (p1, p2) in paire_plaza:
            p1.relationships['acquaintance'].add(p2.id)
            p2.relationships['acquaintance'].add(p1.id)



def random_pairing(lst):
    if len(lst) % 2 != 0:
        lst = lst[:-1]

    shuffled = lst[:]
    random.shuffle(shuffled)
    return list(zip(shuffled[::2], shuffled[1::2]))