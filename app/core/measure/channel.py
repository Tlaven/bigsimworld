"""跨分辨率直接交互通道（InteractionChannel）。

契约与步骤级规格见 `docs/modules/interaction-channel.md`（L3）。本文件只实现
"意图 → 守恒且确定的现实"这一转换，**不含任何交互语义**——"什么意图"由
`InteractionRule`（第 9 缝）声明，本期 `RULES` 为空（通道惰性）。

守恒律（**人头**）：身份侧操作（`bind` / `unbind`）不改变
``Σmeasure + ΣCoarse + len(window)``。
守恒律（**财富**）：质量侧 `transfer`（R→C / C→R / 清算 / 投递）不改变
``Σ count×桶中心 + Σ transfer_pool + Σ yearly_inherited + Σ 窗口 wealth``（见 N2-6 / ADR-005）。

确定性：随机源只有一个 —— `window.rng`（`ClusterStore.rng` / `TickContext.rng` 是它的同一实例）。
"""

from __future__ import annotations

import math
import random
from collections import deque
from dataclasses import dataclass, field
from typing import Iterable, Protocol

from app.core.generation.human import generate_character
from app.core.measure.measure import record_conversion
from app.core.measure.transitions import _shift_age_wealth
from app.core.person.links import link, unlink

# 可重建的桶维度：`extract` 之后能被重建的维度。
# `marital` 自 2026-10-17 起**可寻址**，但**只能成对析出**（N2-5）：个体引擎里"已婚"是
# `relationships["spouse"]`（一条双向边），不是属性 ⇒ 从已婚桶单独析出会造出**假单身**。
# 注：字段名 `wealth_bucket` 对应维度名 `wealth`。
RECONSTRUCTIBLE = frozenset({"age", "gender", "wealth", "marital"})

_FIELD_DIMENSION = {"age": "age", "gender": "gender",
                    "wealth_bucket": "wealth", "marital": "marital"}

_ORIGIN_SIDE = {"character": 0, "cluster": 1, "measure": 2}
_SCOPE_TYPE = {"cluster": 0, "window": 1, "measure": 2}


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
    """通道的唯一输入形态。``origin`` = 发起者，``scope`` = 对手侧范围。

    粗侧有两种形态：共演单元（``("cluster", cid)``）与全局测度（``("measure",)``，N2-8）。
    ``op`` 选定原子：``"bind"``（缺省，有身份，N2-1）/ ``"transfer"``（无身份质量移动，N2-6）。
    """

    kind: str
    origin: tuple                      # ("character", rid) | ("cluster", cid) | ("measure",)
    scope: tuple                       # ("cluster", cid)  | ("window",)      | ("measure",)
    match: Match
    payload: dict = field(default_factory=dict)
    op: str = "bind"                   # "bind" | "transfer"


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
    coarse_id: int | None = None        # 析出源簇；None = 全局测度（N2-8）或簇已回收 ⇒ unbind 折回全局测度
    spouse_cell: int | None = None      # 仅双人析出的 `unbind`：配偶的折算目标桶
    op: str = "bind"                    # "bind" | "transfer"（N2-6）
    wealth_delta: float = 0.0           # transfer ok：以**窗口个体**为口径（付 = 负、收 = 正）
    pool_after: float = 0.0             # transfer ok：目标粗侧 `transfer_pool` 余额；其余无定义
    note: str = ""


# ---------------------------------------------------------------- 规则缝（第 9 缝）

@dataclass(frozen=True)
class ChannelContext:
    """规则发起意图时可见的上下文（只读；规则**不得**在此写任何状态）。

    ``rng`` = 通道的唯一随机源（`window.rng` 的同一实例）——规则做任何抽样都必须用它，
    否则"同 seed 同发展"不成立（不变量 5）。
    """

    tick: int
    window: object
    store: object
    rng: object = None


class InteractionRule(Protocol):
    """规则**只声明"发起什么意图"**；建边由通道统一执行（`link`），规则不碰边。"""

    name: str

    def offers(self, context: ChannelContext) -> Iterable[Intent]: ...


RULES: dict = {}


def register(rule: InteractionRule) -> None:
    RULES[rule.name] = rule


# ---------------------------------------------------------------- 通道

def _sort_key(intent: Intent) -> tuple:
    """确定性处理序：`(origin_side, origin_id, op, kind, scope_type, scope_id)` 升序。"""
    origin_side = _ORIGIN_SIDE.get(intent.origin[0], 9)
    origin_id = intent.origin[1] if len(intent.origin) > 1 else 0
    scope_type = _SCOPE_TYPE.get(intent.scope[0], 9)
    scope_id = intent.scope[1] if len(intent.scope) > 1 else 0
    return (origin_side, origin_id, intent.op, intent.kind, scope_type, scope_id)


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

    def _ordered_intents(self) -> tuple:
        """→ ``(ordered, duplicates)``。去重键含 ``op``（bind 与 transfer 不得互撞）。"""
        seen = set()
        ordered = []
        duplicates = []
        for intent in sorted(self._queue, key=_sort_key):
            key = (intent.op, intent.origin, intent.kind, intent.scope)
            if key in seen:            # 去重：同一 (op, origin, kind, scope) 只留第一条
                duplicates.append(intent)
                continue
            seen.add(key)
            ordered.append(intent)
        self._queue = []
        return ordered, duplicates

    # ------------------------------------------------------------ 主循环

    def run(self, ctx) -> dict:
        per_cluster: dict = {}
        made_total = 0
        transferred = 0.0
        by_status: dict = {}
        ordered, duplicates = self._ordered_intents()
        for intent in duplicates:       # 不变量 8：含丢弃在内，每条意图都有记录
            record = ChannelRecord(ctx.tick, "dropped:duplicate", intent.kind,
                                   intent.origin, intent.scope, op=intent.op)
            self.ledger.append(record)
            by_status[record.status] = by_status.get(record.status, 0) + 1
        for intent in ordered:
            record, made = self._process(intent, ctx, per_cluster, made_total)
            self.ledger.append(record)
            by_status[record.status] = by_status.get(record.status, 0) + 1
            made_total += made          # **按人计**（单人 = 1，成对 = 2）；丢弃 = 0
            if record.status == "ok" and intent.op == "transfer":
                transferred += abs(record.wealth_delta)
        report = {"tick": ctx.tick, "made": made_total, "transferred": transferred,
                  "by_status": by_status, "ledger": len(self.ledger),
                  "reserved": self._reserved}
        self.last_report = report
        return report

    def _process(self, intent: Intent, ctx, per_cluster: dict, made_total: int):
        """→ ``(record, made)``；``made`` = 本次**实际析出的人数**（0 / 1 / 2），供 tick 级配额计数。"""
        tick = ctx.tick

        def drop(status, cell=None, note=""):
            return (ChannelRecord(tick, status, intent.kind, intent.origin, intent.scope,
                                  cell=cell, op=intent.op, note=note), 0)

        if intent.op not in ("bind", "transfer"):
            return drop("dropped:bad_op")

        # 解析两侧：coarse 侧（簇且必须 level==0，或**全局测度**——N2-8）+ 窗口侧角色
        sides = self._resolve_sides(intent)
        if sides is None:
            return drop("dropped:stale")
        cluster, counterpart = sides      # cluster=None ⇒ 全局测度（N2-8）
        if cluster is None:
            mini = self.window.measure
        else:
            engine = cluster.state.get("engine")
            if engine is None:
                return drop("dropped:stale")
            mini = engine.measure

        if intent.op == "transfer":          # —— 质量侧（N2-6）：不占配额、不建边 ——
            if cluster is None:              # 范围声明：transfer 不支持全局测度寻址（N2-8 / ADR-008）
                return drop("dropped:stale")
            return self._process_transfer(intent, tick, cluster, counterpart, mini, drop)

        initiator = counterpart
        # 「一人一意图」守卫（adr-012）：`bind` 且 `origin="character"` 时复检发起者婚配态。
        # 多规则并存（`both`）时同一人可能被两条不同 `scope` 的意图命中；按 N2-1 第 2 步的
        # 确定性顺序依次处理（簇侧先于全局测度）：先成功者建边、后者在此被拒。
        # 单规则下不触发（规则在 `offers()` 时已过滤）。
        if intent.origin[0] == "character" and initiator.relationships.get("spouse"):
            return drop("dropped:initiator_married")
        # 配额闸（**`amount` 感知**，必须在 reserve 之前；N2-1 第 4 步）
        # 按"1 个"判会让双人析出在只剩 1 个名额时挤进来，事后 += 2 直接破坏不变量 7。
        # `cap_per_cluster` 只管簇寻址；全局测度豁免它（无簇语义，N2-8 第 3 步），`cap_per_tick`/headroom 仍是硬上界。
        amount = intent.match.extraction_amount()
        if cluster is not None and per_cluster.get(cluster.id, 0) + amount > self.cap_per_cluster:
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
        if cluster is not None:
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
            if cluster is not None:
                cluster.state["size"] = mini.total()
            self._reserved -= amount
            return drop("dropped:error", cell=cell, note=f"{type(exc).__name__}: {exc}")

        # 宽限期登记（**建边成功之后**：失败的意图不该给簇一段宽限期）；全局测度不登记（N2-8 第 5 步）
        if cluster is not None:
            self.recently_active[cluster.id] = tick
            per_cluster[cluster.id] = per_cluster.get(cluster.id, 0) + amount
        self._reserved -= amount
        return (ChannelRecord(tick, "ok", intent.kind, intent.origin, intent.scope,
                              cell=cell, delta_mass=-float(amount),
                              initiator_id=initiator.id, new_id=head.id,
                              spouse_id=made[1].id if amount == 2 else None,
                              coarse_id=cluster.id if cluster is not None else None), amount)

    # ------------------------------------------------------------ 质量侧 transfer（N2-6）

    @staticmethod
    def _transfer_amount(intent: Intent):
        """`payload["amount"]` → 正有限浮点；非法返回 None（⇒ `dropped:bad_amount`）。"""
        amount = (intent.payload or {}).get("amount")
        if type(amount) not in (int, float):     # 排除 bool（它是 int 的子类）
            return None
        amount = float(amount)
        if not math.isfinite(amount) or amount <= 0.0:
            return None
        return amount

    def _process_transfer(self, intent, tick, cluster, counterpart, mini, drop):
        """`op="transfer"`：R→C 精确借记入池；C→R 精确支付（必要时向下整桶清算）。

        守恒口径与零副作用纪律见 `docs/modules/interaction-channel.md` N2-6 / `adr-005`。
        """
        amount = self._transfer_amount(intent)
        if amount is None:
            return drop("dropped:bad_amount")

        if intent.origin[0] == "character":      # R→C：个体付给粗侧池
            if intent.match.used_dimensions():   # 对手方是显式 cluster，没有粗侧寻址需求
                return drop("dropped:unsupported_match")
            if amount > counterpart.wealth + 1e-12:
                return drop("dropped:insufficient_funds")
            counterpart.wealth -= amount
            mini.transfer_pool += amount
            return (ChannelRecord(tick, "ok", intent.kind, intent.origin, intent.scope,
                                  op="transfer", wealth_delta=-amount,
                                  pool_after=mini.transfer_pool,
                                  initiator_id=counterpart.id,
                                  coarse_id=cluster.id), 0)

        # C→R：粗侧池付给具名个体（`counterpart` = 接收者）
        total = mini.mass() + mini.transfer_pool
        if amount > total + 1e-9:
            return drop("dropped:insufficient_funds")
        minted = 0.0
        if amount - mini.transfer_pool > 1e-9:
            plan = self._liquidation_plan(mini, amount - mini.transfer_pool)
            if plan is None:
                return drop("dropped:illiquid")
            space = self.window.space
            # **升序应用**（源桶财富）：低桶先动，高桶才不会把低桶刚收到的质量再搬一次（防级联）
            for index, steps in sorted(plan, key=lambda item: space.decode(item[0])[2]):
                paid = _shift_age_wealth(mini, space, [index], -steps)
                if paid < 0.0:
                    minted += -paid
            mini.transfer_pool += minted
        if mini.transfer_pool + 1e-9 < amount:   # 计划必须保守；保险丝（不得在此钳制造币）
            return drop("dropped:illiquid", note="liquidation_undershoot")
        mini.transfer_pool -= amount
        counterpart.wealth += amount
        cluster.state["size"] = mini.total()
        note = f"liquidated:{minted:.6f}" if minted > 0.0 else ""
        return (ChannelRecord(tick, "ok", intent.kind, intent.origin, intent.scope,
                              op="transfer", wealth_delta=amount,
                              pool_after=mini.transfer_pool,
                              initiator_id=counterpart.id, coarse_id=cluster.id,
                              note=note), 0)

    def _liquidation_plan(self, mini, shortfall):
        """向下清算的**只算不改**计划：``[(index, steps)]``；不可行返回 None。

        - 候选按 `(count, −wealth_bucket, index)` 升序（**人数最少优先**——减少被触及的桶）；
        - `steps ≤ wealth_bucket`（**正确性前提**：越界会把桶索引串到别的 age/gender 桶）；
        - 浮点保守：宁可多移一步，绝不欠付（第二段补足循环）。
        """
        space = self.window.space
        width = space.wealth_width
        candidates = sorted((index for index in mini.occupied
                             if mini.counts[index] > 0.0 and space.decode(index)[2] > 0),
                            key=lambda index: (mini.counts[index], -space.decode(index)[2], index))
        planned: dict = {}
        remaining = float(shortfall)
        for index in candidates:
            if remaining <= 1e-9:
                break
            unit = mini.counts[index] * width
            if unit <= 0.0:
                continue
            steps = min(int(math.ceil(remaining / unit)), space.decode(index)[2])
            if steps <= 0:
                continue
            planned[index] = planned.get(index, 0) + steps
            remaining -= unit * steps
        guard = 0
        while remaining > 1e-9:                  # 浮点补足：绝不欠付
            progressed = False
            for index in candidates:
                if planned.get(index, 0) < space.decode(index)[2]:
                    planned[index] = planned.get(index, 0) + 1
                    remaining -= mini.counts[index] * width
                    progressed = True
                    break
            guard += 1
            if not progressed or guard > len(candidates) + 2:
                return None
        return list(planned.items())

    # ------------------------------------------------------------ 两侧解析

    def _resolve_sides(self, intent: Intent):
        """→ ``(coarse | None, counterpart)``；解析不出返回 None。

        析出永远发生在 **coarse 侧**（唯一没有身份的一侧）：R→C 析出对手方；C→R 析出发起者。
        粗侧有两种形态（N2-8）：共演单元（``cluster``）与**全局测度**（``None``）——
        **元组内的 ``None`` = 全局测度；整个返回值 ``None`` = 解析失败**（这两个 None 别混）。
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
            counterpart = self._pick_window_counterpart(intent.match)
            if counterpart is None:
                return None
            return cluster, counterpart

        if origin_kind == "character":
            initiator = self.window.characters.get(origin_id)
            if initiator is None:
                return None
            if scope_kind == "cluster":
                cluster = self.store.clusters.get(scope_id)
                if cluster is None or cluster.level != 0:
                    return None
                return cluster, initiator
            if scope_kind == "measure":            # N2-8：R→M —— 对手侧是全局测度（析出对手方）
                return None, initiator
            return None

        if origin_kind == "measure":               # N2-8：M→R —— 发起方是全局测度（析出发起者代表）
            if scope_kind != "window":
                return None
            counterpart = self._pick_window_counterpart(intent.match)
            if counterpart is None:
                return None
            return None, counterpart

        return None

    def _pick_window_counterpart(self, match: Match):
        """按 `Match` 从窗口角色中选对手方：**`Character.id` 升序取第一个匹配**（C→R / M→R 共用）。

        不得依赖窗口 `dict` 的迭代序（不变量 5）。无匹配 ⇒ 返回 None。
        """
        pred = compile_match(match, self.window.space)
        candidates = sorted((c for c in self.window.characters.values()
                             if pred(self._bucket_of(c))), key=lambda c: c.id)
        return candidates[0] if candidates else None

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
        for who, index in folded:
            target = engine.measure if engine is not None else self.window.measure
            # 簇在 ⇒ 折回簇；已回收 / `coarse_id=None`（measure 寻址，N2-8）⇒ 折回全局测度（人头不变）
            target.add(index, 1.0)
            # 精确 wealth → 桶中心：残差记到**同一个**目标测度（符号账，ADR-006 / N2-5）
            record_conversion(target, self.window.space, who.wealth)
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
        """给通道预留的窗口名额：**无（会 bind 的）规则时恒为 0**（惰性路径零影响）。

        `WindowEngine._refill` 会把窗口补满到 `capacity`；若不预留，`bind` 会被
        `dropped:window` 永久饿死（窗口恒满 ⇒ 通道在生产里是死的）。
        只发 `transfer` 的规则可声明 `emits_bind = False` 来不占名额（transfer 不用窗口名额）。
        """
        if not RULES:
            return 0
        if any(getattr(rule, "emits_bind", True) for rule in RULES.values()):
            return self.cap_per_tick
        return 0

    # ------------------------------------------------------------ 观测

    def pool_total(self) -> float:
        """全世界的通道池余额（全局测度 + 每个簇的 mini）。"""
        total = float(self.window.measure.transfer_pool)
        for cluster in self.store.clusters.values():
            engine = cluster.state.get("engine")
            if engine is not None:
                total += float(engine.measure.transfer_pool)
        return total

    def summary(self, last: int = 8) -> dict:
        return {
            "cap_per_cluster": self.cap_per_cluster,
            "cap_per_tick": self.cap_per_tick,
            "grace_ticks": self.grace_ticks,
            "reserved": self._reserved,
            "pool_total": self.pool_total(),
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
