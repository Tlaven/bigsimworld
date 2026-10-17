

from app.core.person.links import unlink


class DeathEvent:
    def __init__(self, model, character):
        self.model = model
        self.publish_list = model.publish_list
        self.character = character
        self.relationships = character.relationships
        self.relation_record = character.relation_record

    def happen(self):
        # 必须按**快照**迭代：notify_* 经 `unlink` 会**双向**解除边，因而会改到本列表；
        # 边遍历边改会跳过元素并制造"单边残留"（原实现只单向移除，侥幸没暴露）。
        for acquaintance in list(self.relationships['acquaintance']):
            acquaintance.death_event.notify_acquaintance(self.character)

        for familiarity in list(self.relationships['familiarity']):
            familiarity.death_event.notify_familiarity(self.character)

        for friend in list(self.relationships['friend']):
            friend.death_event.notify_friend(self.character)

        for spouse in list(self.relationships['spouse']):
            spouse.death_event.notify_spouse(self.character)

        for parent in list(self.relationships['parent']):
            parent.death_event.notify_parent(self.character)

        for sibling in list(self.relationships['sibling']):
            sibling.death_event.notify_sibling(self.character)

        for child in list(self.relationships['child']):
            child.death_event.notify_child(self.character)

        self.self_event()


    def self_event(self):
        self.character.status = 'dead'
        self.relationships.clear()
            
        self.model.remove_character(self.character.id, self.character)
        cell_plaza = self.model.event_plaza['acquaintance'][self.character.cell]
        cell_plaza[:] = [character for character in cell_plaza if character.id != self.character.id]

    def notify_acquaintance(self, acquaintance):
        unlink(self.character, acquaintance, 'acquaintance')

    def notify_familiarity(self, familiarity):
        unlink(self.character, familiarity, 'familiarity')

    def notify_friend(self, friend):
        unlink(self.character, friend, 'friend', record=True)

    def notify_spouse(self, spouse):
        unlink(self.character, spouse, 'spouse', record=True)

    def notify_parent(self, child):
        unlink(self.character, child, 'child', 'parent', record=True)

    def notify_sibling(self, sibling):
        unlink(self.character, sibling, 'sibling', record=True)

    def notify_child(self, parent):
        # 平分10%的遗产
        # 注意：分母 `len(parent.relationships['child'])` 必须在解除边**之前**取，故顺序不可调换。
        self.character.wealth += parent.wealth * 0.1 / len(parent.relationships['child'])
        unlink(self.character, parent, 'parent', 'child', record=True)


