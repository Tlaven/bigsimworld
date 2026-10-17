"""跨分辨率直接交互通道（InteractionChannel）。

契约与步骤级规格见 `docs/modules/interaction-channel.md`（L3）。本文件只实现
"意图 → 守恒且确定的现实"这一转换，**不含任何交互语义**——"什么意图"由
`InteractionRule`（第 9 缝）声明，本期 `RULES` 为空（通道惰性）。

守恒律（**人头**）：身份侧操作（`bind` / `unbind`）不改变
``Σmeasure + ΣCoarse + len(window)``。财富守恒是另一条账（属下期的 `transfer`）。

确定性：随机源只有一个 —— `window.rng`（`ClusterStore.rng` / `TickContext.rng` 是它的同一实例）。
"""

from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field
from typing import Iterable, Protocol

from app.core.generation.human import generate_character
from app.core.person.links import link, unlink

# 可重建的桶维度：`extract` 之后能被重建的维度。
# `marital` 自 2026-10-17 起**可寻址**，但**只能成对析出**（N2-5）：个体引擎里"已婚"是
# `relationships["spouse"]`（一条双向边），不是属性 ⇒ 从已婚桶单独析出会造出**假单身**。
# 注：字段名 `wealth_bucket` 对应维度名 `wealth`。
RECONSTRUCTIBLE = frozenset({"age", "gender", "wealth", "marital"})

_FIELD_DIMENSION = {"age": "age", "gender": "gender",
                    "wealth_bucket": "wealth", "marital": "marital"}

_ORIGIN_SIDE = {"character": 0, "cluster": 1}
_SCOPE_TYPE = {"cluster": 0, "window": 1}


# ---------------------------------------------------------------- 匹配 / 意图

@dataclass(frozen=True)
class Match:
    """声明式可匹配性（**闭区间**，两端都含）。``None`` = 不限。

    - ``age`` 单位是**岁**（年龄桶 1:1，0..120）。
    - ``wealth_bucket`` 单位是**桶索引**（线性宽 1000），不是财富值。
    - ``marital`` 是**标量 0/1**（桶空间里只有两档）。``= 1`` ⇒ **成对析出**（N2-5）：
      `extract(amount=2)` + `link(a, b, "spouse")`，因为"已婚"是 `relationships["spouse"]` 而非属性。
    - ``marital=None``（不限）在**析出**域自动排除已婚桶（单人析出不得造假单身，见 `compile_match`）。
    """

    age: tuple | None = None
    gender: int | None = None
    wealth_bucket: tuple | None = None
    marital: int | None = None

    def used_dimensions(self) -> set:
        return {dim for fld, dim in _FIELD_DIMENSION.items()
                if getattr(self, fld) is not None}

    def extraction_amount(self) -> int:
        """本次意图在 coarse 侧需要的析出量：``marital=1`` ⇒ 2（成对），否则 ⇒ 1。

        **只由 `marital` 决定** ⇒ 配额闸可在 `reserve` **之前**判定（N2-1 第 4 步）。
        """
        return 2 if self.marital == 1 else 1


def compile_match(match: Match, space, extraction: bool = False):
    """`Match` → 桶索引谓词 ``pred(index) -> bool``。

    引用 ∉ `RECONSTRUCTIBLE` 的维度 ⇒ **立即抛错**（不在运行期静默失配）。
    R→C 时作用于 coarse 的 `occupied` 桶；C→R 时作用于窗口角色折算出的桶索引——同一谓词、两个域。

    ``extraction=True``（**析出域**）时额外施加 N2-5 的硬规则：``marital=None``（不限）
    **不得命中 `marital=1` 桶**——单人析出已婚桶 = 造假单身。"已婚者不得单独析出"是硬规则，
    不因谓词缺省而失效。C→R 的**窗口侧对手选取**传 ``extraction=False``：窗口角色本就是真个体，
    其 `marital` 由 `relationships["spouse"]` 折算，不存在假单身问题。
    """
    forbidden = match.used_dimensions() - RECONSTRUCTIBLE
    if forbidden:
        raise ValueError(
            f"Match 引用不可寻址维度 {sorted(forbidden)}；"
            f"可重建维度 RECONSTRUCTIBLE = {sorted(RECONSTRUCTIBLE)}")

    age_rng, gender_v, wealth_rng = match.age, match.gender, match.wealth_bucket
    marital_v = match.marital

    def pred(index: int) -> bool:
        age, gender, wealth, marital = space.decode(index)
        if age_rng is not None and not (age_rng[0] <= age <= age_rng[1]):
            return False
        if gender_v is not None and gender != gender_v:
            return False
        if wealth_rng is not None and not (wealth_rng[0] <= wealth <= wealth_rng[1]):
            return False
        if marital_v is not None:
            if marital != marital_v:
                return False
        elif extraction and marital != 0:
            return False           # N2-5：缺省（不限）不得单人析出已婚桶
        return True

    return pred


@dataclass(frozen=True)
class Intent:
    """通道的唯一输入形态。``origin`` = 发起者，``scope`` = 对手侧范围。"""

    kind: str
    origin: tuple                      # ("character", rid) | ("cluster", cid)
    scope: tuple                       # ("cluster", cid)  | ("window",)
    match: Match
    payload: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ChannelRecord:
    """账本记录：``ok`` 与 ``dropped:*`` 同一结构（不变量 8）。"""

    tick: int
    status: str
    kind: str
    origin: tuple
    scope: tuple
    cell: int | None = None
    delta_mass: float = 0.0
    initiator_id: int | None = None
    new_id: int | None = None
    spouse_id: int | None = None        # 仅双人析出（N2-5）：配偶 id（`new_id` 记 `a`）
    coarse_id: int | None = None
    spouse_cell: int | None = None      # 仅双人析出的 `unbind`：配偶的折算目标桶
    note: str = ""


# ---------------------------------------------------------------- 规则缝（第 9 缝）

@dataclass(frozen=True)
class ChannelContext:
    """规则发起意图时可见的上下文（只读）。"""

    tick: int
    window: object
    store: object


class InteractionRule(Protocol):
    """规则**只声明"发起什么意图"**；建边由通道统一执行（`link`），规则不碰边。"""

    name: str

    def offers(self, context: ChannelContext) -> Iterable[Intent]: ...


RULES: dict = {}


def register(rule: InteractionRule) -> None:
    RULES[rule.name] = rule


# ---------------------------------------------------------------- 通道

def _sort_key(intent: Intent) -> tuple:
    """确定性处理序：`(origin_side, origin_id, kind, scope_type, scope_id)` 升序。"""
    origin_side = _ORIGIN_SIDE.get(intent.origin[0], 9)
    origin_id = intent.origin[1] if len(intent.origin) > 1 else 0
    scope_type = _SCOPE_TYPE.get(intent.scope[0], 9)
    scope_id = intent.scope[1] if len(intent.scope) > 1 else 0
    return (origin_side, origin_id, intent.kind, scope_type, scope_id)


class InteractionChannel:
    """点对点、双向、可具名的 R↔C 交互通道。**不含交互语义**。"""

    def __init__(self, window, store, rng=None,
                 cap_per_cluster: int = 2, cap_per_tick: int = 8,
                 grace_ticks: int = 180, ledger_size: int = 4096):
        self.window = window
        self.store = store
        self.rng = rng or getattr(window, "rng", None) or random
        self.cap_per_cluster = cap_per_cluster
        self.cap_per_tick = cap_per_tick
        self.grace_ticks = grace_ticks
        self.ledger: deque = deque(maxlen=ledger_size)
        self.recently_active: dict = {}
        self.last_report: dict = {}
        self._queue: list = []
        self._reserved = 0

    # ------------------------------------------------------------ 收集

    def submit(self, intent: Intent) -> None:
        self._queue.append(intent)

    def _ordered_intents(self) -> list:
        seen = set()
        ordered = []
        for intent in sorted(self._queue, key=_sort_key):
            key = (intent.origin, intent.kind, intent.scope)
            if key in seen:            # 去重：同一 (origin, kind, scope) 只留第一条
                continue
            seen.add(key)
            ordered.append(intent)
        self._queue = []
        return ordered

    # ------------------------------------------------------------ 主循环

    def run(self, ctx) -> dict:
        per_cluster: dict = {}
        made_total = 0
        by_status: dict = {}
        for intent in self._ordered_intents():
            record, made = self._process(intent, ctx, per_cluster, made_total)
            self.ledger.append(record)
            by_status[record.status] = by_status.get(record.status, 0) + 1
            made_total += made          # **按人计**（单人 = 1，成对 = 2）；丢弃 = 0
        report = {"tick": ctx.tick, "made": made_total, "by_status": by_status,
                  "ledger": len(self.ledger), "reserved": self._reserved}
        self.last_report = report
        return report

    def _process(self, intent: Intent, ctx, per_cluster: dict, made_total: int):
        """→ ``(record, made)``；``made`` = 本次**实际析出的人数**（0 / 1 / 2），供 tick 级配额计数。"""
        tick = ctx.tick

        def drop(status, cell=None, note=""):
            return (ChannelRecord(tick, status, intent.kind, intent.origin, intent.scope,
                                  cell=cell, note=note), 0)

        # 解析两侧：coarse 簇（必须是 level==0）+ 发起者角色
        sides = self._resolve_sides(intent)
        if sides is None:
            return drop("dropped:stale")
        cluster, initiator = sides
        engine = cluster.state.get("engine")
        if engine is None:
            return drop("dropped:stale")
        mini = engine.measure

        # 配额闸（**`amount` 感知**，必须在 reserve 之前；N2-1 第 4 步）
        # 按"1 个"判会让双人析出在只剩 1 个名额时挤进来，事后 += 2 直接破坏不变量 7。
        amount = intent.match.extraction_amount()
        if per_cluster.get(cluster.id, 0) + amount > self.cap_per_cluster:
            return drop("dropped:quota_cluster")
        if made_total + amount > self.cap_per_tick:
            return drop("dropped:quota_tick")
        if len(self.window.characters) + self._reserved + amount > self.window.capacity:
            return drop("dropped:window")

        # reserve（`extract` 已按桶索引升序抽样 + 扣减 `amount`）
        pred = compile_match(intent.match, self.window.space, extraction=True)
        cell = self.store.extract(mini, predicate=pred, amount=float(amount))
        if cell is None:
            return drop("dropped:no_match")
        self._reserved += amount
        cluster.state["size"] = mini.total()

        # 析出（成对时两个）+ 建边；任一失败 ⇒ **逆序全撤**（只回滚测度会留下幽灵 + 破坏人头守恒）
        age, gender, wealth_bucket, _marital = self.window.space.decode(cell)
        made = []
        try:
            for _ in range(amount):
                data = generate_character(
                    age=age, gender="male" if gender == 0 else "female",
                    wealth=self.window.space.wealth_value(wealth_bucket))
                made.append(self.window.attach(data))
            head = made[0]                                  # `a`：承接意图边的那一个（先 attach）
            if amount == 2:                                 # N2-5：重建既有婚姻（不是新办婚事）
                link(head, made[1], "spouse")
            link(initiator, head, intent.kind)
        except Exception as exc:                       # noqa: BLE001 —— 规则/生成器可能抛任何东西
            for character in made:                     # detach 会断掉该角色两侧的边（含 spouse）
                self.window.detach(character.id)
            mini.add(cell, +float(amount))             # 回滚 reserve
            cluster.state["size"] = mini.total()
            self._reserved -= amount
            return drop("dropped:error", cell=cell, note=f"{type(exc).__name__}: {exc}")

        # 宽限期登记（**建边成功之后**：失败的意图不该给簇一段宽限期）
        self.recently_active[cluster.id] = tick
        per_cluster[cluster.id] = per_cluster.get(cluster.id, 0) + amount
        self._reserved -= amount
        return (ChannelRecord(tick, "ok", intent.kind, intent.origin, intent.scope,
                              cell=cell, delta_mass=-float(amount),
                              initiator_id=initiator.id, new_id=head.id,
                              spouse_id=made[1].id if amount == 2 else None,
                              coarse_id=cluster.id), amount)

    # ------------------------------------------------------------ 两侧解析

    def _resolve_sides(self, intent: Intent):
        """→ ``(coarse_cluster, initiator_character)``；解析不出返回 None。

        析出永远发生在 **coarse 侧**（唯一没有身份的一侧）：R→C 析出对手方；C→R 析出发起者。
        """
        origin_kind, scope_kind = intent.origin[0], intent.scope[0]
        origin_id = intent.origin[1] if len(intent.origin) > 1 else None
        scope_id = intent.scope[1] if len(intent.scope) > 1 else None

        if origin_kind == "cluster":
            if scope_kind != "window":
                return None
            cluster = self.store.clusters.get(origin_id)
            if cluster is None or cluster.level != 0:
                return None
            pred = compile_match(intent.match, self.window.space)
            candidates = sorted((c for c in self.window.characters.values()
                                 if pred(self._bucket_of(c))), key=lambda c: c.id)
            if not candidates:
                return None
            return cluster, candidates[0]

        if origin_kind == "character":
            if scope_kind != "cluster":
                return None
            initiator = self.window.characters.get(origin_id)
            cluster = self.store.clusters.get(scope_id)
            if initiator is None or cluster is None or cluster.level != 0:
                return None
            return cluster, initiator

        return None

    def _bucket_of(self, character) -> int:
        """把窗口角色折算成桶索引（C→R 域的谓词输入）。"""
        space = self.window.space
        marital = 1 if character.relationships.get("spouse") else 0
        return space.encode(character.age, 0 if character.gender == "male" else 1,
                            space.wealth_bucket(character.wealth), marital)

    # ------------------------------------------------------------ 逆操作

    def unbind(self, new_id: int, tick: int = 0) -> bool:
        """`bind` 的逆：断链 + 把该角色折算回 coarse（按**当前**属性，见 N2-4）。

        双人析出（N2-5）时**连配偶一起**：断两条边（意图边 + `spouse`），两人各自折算。

        **不保证逐桶复原**——coarse 侧在绑定期间持续演化（`aging`/`income` 会移动桶）。
        """
        record = self._find_ok_record(new_id)
        if record is None:
            return False
        character = self.window.characters.get(new_id)
        if character is None:
            return False

        # 断边：意图边（**不猜**，就是账本里那条）+ 双人析出的 spouse 边
        initiator = self.window.characters.get(record.initiator_id)
        if initiator is not None:
            unlink(initiator, character, record.kind, record=True)
        spouse = self.window.characters.get(record.spouse_id) if record.spouse_id else None
        if spouse is not None:
            unlink(character, spouse, "spouse", record=True)

        # 折算口径必须在 `detach` **之前**取（detach 会解除关系 ⇒ 改变婚配位）；
        # 按**当时**的 `relationships["spouse"]` 判婚配——绑定期间窗口内可能新结了婚，
        # 所以**不**能一律取 0（那会把已婚者折回单身桶）。
        space = self.window.space

        def _fold_cell(who):
            marital = 1 if who.relationships.get("spouse") else 0
            return space.encode(who.age, 0 if who.gender == "male" else 1,
                                space.wealth_bucket(who.wealth), marital)

        folded = [(character, _fold_cell(character))]
        if spouse is not None:
            folded.append((spouse, _fold_cell(spouse)))

        for who, _index in folded:
            self.window.detach(who.id)          # 断链（其余）+ 清广场；**不含**死亡结算

        cluster = self.store.clusters.get(record.coarse_id)
        engine = cluster.state.get("engine") if cluster is not None else None
        for _who, index in folded:
            if engine is not None:              # 簇还在 ⇒ 折算回簇
                engine.measure.add(index, 1.0)
            else:                               # 簇已被回收 ⇒ 折算回全局测度（人头不变）
                self.window.measure.add(index, 1.0)
        if engine is not None:
            cluster.state["size"] = engine.measure.total()

        note = "spouse_gone" if (record.spouse_id and spouse is None) else ""
        self.ledger.append(ChannelRecord(tick, "unbound", record.kind, record.origin,
                                        record.scope, cell=folded[0][1],
                                        delta_mass=float(len(folded)),
                                        initiator_id=record.initiator_id,
                                        new_id=new_id, spouse_id=record.spouse_id,
                                        coarse_id=record.coarse_id,
                                        spouse_cell=folded[1][1] if len(folded) > 1 else None,
                                        note=note))
        return True

    def _find_ok_record(self, new_id: int):
        for record in reversed(self.ledger):
            if record.status == "ok" and record.new_id == new_id:
                return record
        return None

    def headroom_reserve(self) -> int:
        """给通道预留的窗口名额：**无规则时恒为 0**（惰性路径零影响）。

        `WindowEngine._refill` 会把窗口补满到 `capacity`；若不预留，`bind` 会被
        `dropped:window` 永久饿死（窗口恒满 ⇒ 通道在生产里是死的）。
        """
        return self.cap_per_tick if RULES else 0

    # ------------------------------------------------------------ 观测

    def summary(self, last: int = 8) -> dict:
        return {
            "cap_per_cluster": self.cap_per_cluster,
            "cap_per_tick": self.cap_per_tick,
            "grace_ticks": self.grace_ticks,
            "reserved": self._reserved,
            "recently_active": len(self.recently_active),
            "ledger": len(self.ledger),
            "last_report": dict(self.last_report),
            "recent": [
                {"tick": r.tick, "status": r.status, "kind": r.kind,
                 "origin": list(r.origin), "cell": r.cell,
                 "new_id": r.new_id, "note": r.note}
                for r in list(self.ledger)[-last:]
            ],
        }
