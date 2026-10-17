"""边（关系）的唯一入口 —— 建立 / 解除一条关系边。

背景：关系边目前散落在多处写入（广场配对、婚配、生育、死亡通知、物化建网、退场断链），
**任一处漏写另一侧就会造出幽灵边**（`docs/history.md` Stage 9 的教训：退场不解除关系 →
留在窗口的配偶/朋友/子女继续持有已消失对象的引用）。本模块把"建立 / 解除一条边"
收成两个函数，供所有调用点使用，并由 `tests/test_infra.py` 守住双向对称性。

约定：

- ``link(a, b, kind, reverse=None)``：在 ``a`` 上写 ``kind``、在 ``b`` 上写 ``reverse or kind``。
  - 对称关系（acquaintance / familiarity / friend / sibling / spouse）省略 ``reverse``。
  - 非对称关系（parent / child）：``link(parent, child, "child", "parent")``。
- ``unlink`` 是 ``link`` 的逆；``record=True`` 时按死亡通知的语义双向追加 ``relation_record``。

**本模块不改 `Character.relatives`——该字段已被删除**。它原先只在 `Character.__init__` 填充、
构造后从不更新，导致三处依赖失真（广场配对去重失效、收敛指纹度指标恒为 0、ρ 退化为簇成员数）。
关系人的唯一真相源是 `relationships`，求"关系度"请用本模块的 `neighbors`。
"""


def neighbors(character) -> set:
    """该个体的**关系人集合**（所有关系桶的并集，去重）。

    取代已删除的死字段 `Character.relatives`——详见模块文档字符串。
    """
    relationships = getattr(character, "relationships", None) or {}
    seen = set()
    for values in relationships.values():
        for other in values or ():
            seen.add(other)
    return seen


def link(a, b, kind, reverse=None):
    """建立 a↔b 的边（a 侧写 ``kind``，b 侧写 ``reverse or kind``）。

    重复调用会重复追加，故调用方负责避免（与既有各类事件的行为一致）。
    """
    a.relationships[kind].append(b)
    b.relationships[reverse or kind].append(a)


def unlink(a, b, kind, reverse=None, record=False):
    """解除 a↔b 的边；边不存在则忽略。``record=True`` 时双向追加 ``relation_record``。"""
    _remove(a.relationships[kind], b)
    _remove(b.relationships[reverse or kind], a)
    if record:
        a.relation_record[kind].append(b.id)
        b.relation_record[reverse or kind].append(a.id)


def _remove(seq, item):
    try:
        seq.remove(item)
    except ValueError:
        pass
