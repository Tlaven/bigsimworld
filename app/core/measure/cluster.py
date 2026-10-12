"""团（Cluster）与分辨率：Phase 0 实现。

契约见 `docs/cluster-contract.md`。本文件定义数据模型、扩展缝与通用算子：
机制通用、策略可插拔——kind / 调度 / ρ / 合并分裂切法均经注册表或参数注入。

MVP：唯一 kind = family（以 parent/child/spouse 为身份敏感边），两档分辨率
（0 = 聚合, 1 = 个体），水位线调度，身份质量 ρ，自动合并/分裂策略留空。

coarse 团的聚合态 = 一个 **mini `MeanFieldEngine`**（同一 StateSpace + FULL_FLOWS）：
族内遗产池天然作用域在团内，复用 `transitions` 全部算子，无需新机制。
（MVP 近似：族内也会发生婚配/生育；跨团边留待 interface。）

守恒律：`Σ measure.counts + Σ_coarse size + len(window.characters) == 初始 + 出生 − 死亡`
（分辨率切换恒等守恒：计数只移动，不产生/销毁）。
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable, Protocol

from app.core.generation.human import generate_character
from app.core.measure.engine import MeanFieldEngine
from app.core.measure.measure import measure_from_characters, measure_from_payload, measure_to_payload
from app.core.measure.transitions import FULL_FLOWS, distribute_pool, inject_inherited
from app.core.measure.transitions import inheritance as _mf_inheritance


# ---------------------------------------------------------------- 数据模型

@dataclass
class InterfaceEdge:
    """跨团的身份敏感边（未内化的对外作用）。"""

    kind: str
    other_ref: tuple
    rate: float
    since: int


@dataclass
class Cluster:
    id: int
    kind: str
    level: int = 0
    member_ids: set = field(default_factory=set)
    state: dict = field(default_factory=dict)
    interface: list = field(default_factory=list)
    rho: float = 0.0
    parent_id: int | None = None


@dataclass
class TickContext:
    """注入式上下文，隔离 store 对具体引擎的依赖。"""

    tick: int
    measure: object
    rng: random.Random
    on_resolve: Callable[[int], None] = lambda cid: None
    on_coarsen: Callable[[int], None] = lambda cid: None


# ---------------------------------------------------------------- 扩展缝

class ClusterKind(Protocol):
    """团的种类：定义成员边界、聚合态与聚合演化。"""

    name: str

    def membership_edges(self) -> set:
        """哪些关系算身份敏感边界（决定成员与切法）。"""

    def aggregate(self, members: dict, space) -> object:
        """resolved 成员 → 聚合态（coarsen 时调用）。"""

    def init_coarse(self, aggregate: object) -> dict:
        """由聚合态初始化 coarse 状态（一个 open dict）。"""

    def step_coarse(self, state: dict, ctx: TickContext) -> None:
        """coarse 团每 tick 的批量演化（原地修改 state）。"""

    def cost(self, level: int, size: float) -> float:
        """该团在给定分辨率下的预算成本。"""


class ResolutionPolicy(Protocol):
    """注意力 + 预算 → 目标分辨率。"""

    def allocate(self, clusters: list, attention: dict, budget: float) -> dict:
        """返回 {cluster_id: target_level}。"""


class RhoMetric(Protocol):
    """分辨率操作的近似量度量（ρ）。"""

    def on_coarsen(self, kind: str, members: dict) -> float: ...

    def on_merge(self, kind: str, coupling: float) -> float: ...

    def on_split(self, kind: str, cut_weight: float) -> float: ...


# ---------------------------------------------------------------- MVP 实现

class IdentityMassRho:
    """MVP ρ：收编时按被遗忘的身份质量计（1 + 关系度）；合并/分裂暂返回 0。"""

    def on_coarsen(self, kind: str, members: dict) -> float:
        return float(sum(1 + len(getattr(c, "relatives", ()) or ()) for c in members.values()))

    def on_merge(self, kind: str, coupling: float) -> float:
        return 0.0

    def on_split(self, kind: str, cut_weight: float) -> float:
        return 0.0


class FamilyKind:
    """MVP 唯一 kind：以 parent/child/spouse 为身份敏感边的家族团。

    聚合态 = mini `MeanFieldEngine`；继承由 ``step_coarse`` 手动处理（含溢出口），
    其余流算子复用 `transitions`。``overflow_fraction``：族内继承中改注入全局池
    的比例（0 = 完全内化，即"富族恒富"）。
    """

    name = "family"
    overflow_fraction = 0.0
    flows = tuple(flow for flow in FULL_FLOWS if flow is not _mf_inheritance)

    def membership_edges(self) -> set:
        return {"parent", "child", "spouse"}

    def aggregate(self, members: dict, space) -> object:
        return measure_from_characters(members.values(), space)

    def init_coarse(self, aggregate: object) -> dict:
        engine = MeanFieldEngine(measure=aggregate, flows=self.flows)
        return {"engine": engine, "size": aggregate.total()}

    def step_coarse(self, state: dict, ctx: TickContext) -> None:
        engine = state["engine"]
        engine.simulation_time = ctx.tick - 1  # 与全局时钟对齐（period 取模）
        engine.step()
        family_inheritance(engine.measure, ctx.tick,
                           global_measure=ctx.measure, overflow=self.overflow_fraction)
        state["size"] = engine.measure.total()

    def cost(self, level: int, size: float) -> float:
        # MVP 成本模型：resolved 按人数计，coarse 视为常数 1。
        return float(size) if level >= 1 else 1.0


def family_inheritance(measure, tick, global_measure=None, overflow=0.0) -> None:
    """族内继承：注入（``overflow`` 份额改注入全局池）+ 年清算（整数桶位移）。"""
    inject_inherited(measure, overflow=overflow, global_measure=global_measure)
    if tick % 360 == 0:
        distribute_pool(measure)


class WaterlinePolicy:
    """MVP 调度：**基线 θ + leaf 数预算**。

    - `theta_base`（基线，固定）：注意力 < 基线即粗化——内在冷却，保证不刷新必降温；
    - `budget_leaves`（叶子预算）：最多保留多少叶子；按注意力降序分配，超预算的低注意团降档；
    - `feedback`（负载反馈）：实测超预算则收紧叶子预算、有余量则放宽（区间 [1, max_leaves]）。
    """

    def __init__(self, theta_base: float = 0.5, budget_leaves: int | None = None, alpha: float = 0.1):
        self.theta_base = theta_base
        self.max_leaves = budget_leaves
        self.budget_leaves = budget_leaves
        self.alpha = alpha

    def allocate(self, clusters: list, attention: dict, budget_leaves: int | None = None) -> dict:
        budget = self.budget_leaves if budget_leaves is None else budget_leaves
        ranked = sorted(clusters, key=lambda c: attention.get(c.id, 0.0), reverse=True)
        targets = {}
        remaining = budget
        for cluster in ranked:
            cost = self._leaf_cost(cluster)
            if attention.get(cluster.id, 0.0) < self.theta_base:
                targets[cluster.id] = 0
            elif remaining is None or remaining >= cost:
                targets[cluster.id] = 1
                if remaining is not None:
                    remaining -= cost
            else:
                targets[cluster.id] = 0
        return targets

    @staticmethod
    def _leaf_cost(cluster) -> int:
        if cluster.level == 1:
            return max(1, len(cluster.member_ids))
        return max(1, int(cluster.state.get("size", 0.0)))

    def feedback(self, cost: float, budget: float) -> None:
        if self.max_leaves is None or budget <= 0:
            return
        if cost > budget:
            self.budget_leaves = max(1, int(self.budget_leaves * 0.9))
        else:
            self.budget_leaves = min(self.max_leaves, int(self.budget_leaves * 1.05) + 1)



def decay(attention: dict, gamma: float = 0.99) -> dict:
    """注意度衰减：不刷新则降温。"""
    for key in list(attention):
        attention[key] *= gamma
    return attention


# ---------------------------------------------------------------- 注册表

KINDS: dict = {}


def register(kind: ClusterKind) -> None:
    KINDS[kind.name] = kind


register(FamilyKind())


# ---------------------------------------------------------------- Store

class ClusterStore:
    """团容器与通用算子（策略无关）。成员为 resolved 时计入 window，不重复计数。"""

    def __init__(self, measure: object, window: object, rho_metric: RhoMetric | None = None):
        self.measure = measure
        self.window = window
        self.space = getattr(window, "space", None) or measure.space
        self.rho_metric = rho_metric or IdentityMassRho()
        self.clusters: dict = {}
        self._next_id = 0
        self.dissolved_rho = 0.0  # 已回收团的累计 ρ（回收不抹掉遗忘代价）

    # ------------------------------------------------------------ 建团

    def create(self, kind: str, member_ids: set) -> Cluster:
        self._next_id += 1
        cluster = Cluster(id=self._next_id, kind=kind, level=1, member_ids=set(member_ids))
        self.clusters[cluster.id] = cluster
        return cluster

    # ------------------------------------------------------------ 粗化 / 物化

    def coarsen(self, cid: int) -> None:
        """叶子 → 聚合：成员移出窗口、求和进 mini 引擎，累加 ρ。"""
        cluster = self.clusters[cid]
        if cluster.level == 0:
            return
        kind = KINDS[cluster.kind]
        members = {mid: self.window.characters[mid]
                   for mid in cluster.member_ids if mid in self.window.characters}
        aggregate = kind.aggregate(members, self.space)
        cluster.rho += self.rho_metric.on_coarsen(cluster.kind, members)
        for mid in list(members):
            self.window.detach(mid)
        cluster.member_ids = set()
        cluster.state = kind.init_coarse(aggregate)
        cluster.level = 0

    def materialize(self, cid: int, n: int | None = None) -> int:
        """聚合 → 若干新叶子（经 window 建真个体，新代表而非原人）。返回实际析出数。"""
        cluster = self.clusters[cid]
        if cluster.level >= 1:
            return 0
        mini = cluster.state["engine"].measure
        size = int(mini.total())
        count = size if n is None else min(n, size)
        made = 0
        for _ in range(count):
            cell = self._sample_cell(mini)
            if cell is None:
                break
            age, gender, wealth, _marital = self.space.decode(cell)
            mini.add(cell, -1.0)
            data = generate_character(
                age=age,
                gender="male" if gender == 0 else "female",
                wealth=self.space.wealth_value(wealth),
            )
            character = self.window.attach(data)
            cluster.member_ids.add(character.id)
            made += 1
        cluster.state["size"] = mini.total()
        if made > 0:
            cluster.level = 1
        return made

    def _sample_cell(self, mini):
        total = mini.total()
        if total < 1.0 or not mini.occupied:
            return None
        r = random.random() * total
        acc = 0.0
        for index in mini.occupied:
            acc += mini.counts[index]
            if acc >= r:
                return index
        return next(iter(mini.occupied))

    # ------------------------------------------------------------ 合并 / 分裂

    def merge(self, a: int, b: int) -> int:
        """两团并一。resolved+resolved 保留成员（免费）；否则先粗化再并 mini。"""
        ca, cb = self.clusters[a], self.clusters[b]
        if ca.level == 1 and cb.level == 1:
            ca.member_ids |= cb.member_ids
            ca.rho += self.rho_metric.on_merge(ca.kind, 0.0)
            del self.clusters[b]
            return a
        self.coarsen(a)
        self.coarsen(b)
        ma = ca.state["engine"].measure
        mb = cb.state["engine"].measure
        for index in list(mb.occupied):
            ma.add(index, mb.counts[index])
        ca.state["size"] = ma.total()
        ca.rho += self.rho_metric.on_merge(ca.kind, 0.0)
        del self.clusters[b]
        return a

    def split(self, cid: int, groups: list) -> list:
        """按给定 groups 切分（切法由策略注入）。MVP 只支持 resolved 团。"""
        cluster = self.clusters[cid]
        if cluster.level != 1:
            raise NotImplementedError("MVP 只支持 resolved 团的切分")
        del self.clusters[cid]
        new_ids = []
        share = cluster.rho / max(len(groups), 1)
        for group in groups:
            child = self.create(cluster.kind, group)
            child.rho = share
            new_ids.append(child.id)
        return new_ids

    # ------------------------------------------------------------ 聚合演化 / 统计

    def step_coarse(self, ctx: TickContext) -> None:
        for cluster in self.clusters.values():
            if cluster.level == 0:
                KINDS[cluster.kind].step_coarse(cluster.state, ctx)

    def size(self) -> float:
        """Σ coarse 态成员数；resolved 成员由 len(window.characters) 计。"""
        return float(sum(c.state.get("size", 0.0) for c in self.clusters.values()))

    def rho(self) -> float:
        return float(self.dissolved_rho + sum(c.rho for c in self.clusters.values()))

    def dissolve(self, cid: int) -> bool:
        """把 **coarse** 团折回全局测度：释放槽位、质量守恒、ρ 记入累计。

        （resolved 团不直接溶解——成员还在窗口；策略应先粗化或跳过。）
        """
        cluster = self.clusters.get(cid)
        if cluster is None or cluster.level != 0:
            return False
        engine = cluster.state.get("engine")
        if engine is not None:
            mini = engine.measure
            for index in list(mini.occupied):
                self.measure.add(index, mini.counts[index])
        self.dissolved_rho += cluster.rho
        del self.clusters[cid]
        return True

    # ------------------------------------------------------------ 序列化

    def to_payload(self) -> dict:
        """紧凑保存：resolved 存成员 id，coarse 存 mini 引擎的测度。"""
        items = []
        for cluster in self.clusters.values():
            engine = cluster.state.get("engine")
            items.append({
                "id": cluster.id,
                "kind": cluster.kind,
                "level": cluster.level,
                "member_ids": sorted(cluster.member_ids),
                "rho": cluster.rho,
                "measure": measure_to_payload(engine.measure) if engine is not None else None,
            })
        return {"clusters": items, "dissolved_rho": self.dissolved_rho}

    def load_payload(self, payload, space) -> None:
        self.clusters = {}
        self._next_id = 0
        self.dissolved_rho = 0.0
        if isinstance(payload, dict):           # 新格式
            items = payload.get("clusters") or []
            self.dissolved_rho = float(payload.get("dissolved_rho", 0.0))
        else:                                    # 兼容旧 list 格式
            items = payload or []
        for item in items:
            cluster = Cluster(
                id=item["id"], kind=item["kind"], level=item["level"],
                member_ids=set(item.get("member_ids") or []), rho=item.get("rho", 0.0),
            )
            if item.get("measure") is not None:
                mini = measure_from_payload(item["measure"], space)
                cluster.state = {"engine": MeanFieldEngine(measure=mini, flows=KINDS[item["kind"]].flows),
                                 "size": mini.total()}
            self.clusters[cluster.id] = cluster
            self._next_id = max(self._next_id, cluster.id)


# ---------------------------------------------------------------- 分辨率管理

class ResolutionManager:
    """把团存储 + 注意力 + 水位线调度 + 预算反馈绑成一个每 tick 的闭环。

    成团 = 每 `form_interval` tick，对**尚未入团的浮层个体**做 parent/child/spouse
    连通分量（>= min_size 建一团）；分辨率由水位线决定；注意力随时间衰减
    （不刷新则团自动粗化）；观察者 `set_attention` 可钉住（高注意力）或放掉（低）。
    注意度按 **团 id** 记，故团在 coarsen/materialize 间保持身份、注意力不丢。
    """

    def __init__(self, window, measure=None, policy=None, gamma=0.99,
                 form_kind="family", min_size=2, max_members=12, max_clusters=64,
                 initial_attention=0.8, form_interval=30, budget_leaves=None, dissolve_floor=0.1,
                 endogenous_scale=None):
        self.window = window
        self.measure = measure or window.measure
        self.store = ClusterStore(self.measure, window)
        self.policy = policy or WaterlinePolicy(budget_leaves=budget_leaves)
        self.gamma = gamma
        self.form_kind = form_kind
        self.min_size = min_size
        self.max_members = max_members
        self.max_clusters = max_clusters
        self.initial_attention = initial_attention
        self.form_interval = form_interval
        self.dissolve_floor = dissolve_floor
        self.endogenous_scale = endogenous_scale  # L1 社会凝视：None=关
        self.attention = {}
        self._formed = False
        self._next_form = 0

    # ------------------------------------------------------------ 受保护成员

    def protected_ids(self) -> set:
        ids = set()
        for cluster in self.store.clusters.values():
            if cluster.level == 1:
                ids |= cluster.member_ids
        return ids

    # ------------------------------------------------------------ 观察者接口

    def set_attention(self, cluster_id: int, value: float) -> None:
        self.attention[cluster_id] = float(value)

    def cluster_of(self, person_id: int):
        """person id → 其所属团 id（resolved 团成员）；无则 None。"""
        for cluster in self.store.clusters.values():
            if cluster.level == 1 and person_id in cluster.member_ids:
                return cluster.id
        return None

    def summary(self, max_entries: int = 64) -> dict:
        """观测面摘要（有界）：水位/预算/ρ/团数 + 团条目。"""
        entries = []
        for cluster in list(self.store.clusters.values())[:max_entries]:
            size = len(cluster.member_ids) if cluster.level == 1 else round(cluster.state.get("size", 0.0), 3)
            entries.append({
                "id": cluster.id,
                "kind": cluster.kind,
                "level": cluster.level,
                "size": size,
                "rho": round(cluster.rho, 3),
                "attention": round(self.attention.get(cluster.id, 0.0), 3),
            })
        return {
            "theta_base": getattr(self.policy, "theta_base", None),
            "budget_leaves": getattr(self.policy, "budget_leaves", None),
            "rho": round(self.store.rho(), 3),
            "cluster_count": len(self.store.clusters),
            "resolved_count": sum(1 for c in self.store.clusters.values() if c.level == 1),
            "clusters": entries,
        }

    def feedback(self, cost: float, budget: float) -> None:
        if hasattr(self.policy, "feedback"):
            self.policy.feedback(cost, budget)

    def _endogenous_attention(self) -> dict:
        """L1 社会凝视：团被窗口内**非成员**认识的程度（外部入边数）→ [0,1] 注意力。

        被认识者自身得以维系（无需外部观察者）；无人问津者自然降温。
        """
        chars = self.window.characters
        scale = float(self.endogenous_scale)
        result = {}
        for cid, cluster in self.store.clusters.items():
            if cluster.level != 1:
                continue
            members = cluster.member_ids
            degree = 0
            for mid in members:
                character = chars.get(mid)
                if character is None:
                    continue
                for key in ("friend", "spouse", "parent", "child"):  # 只算强关系（被"认识"）
                    for other in character.relationships.get(key, ()) or ():
                        if getattr(other, "id", None) not in members:
                            degree += 1
            result[cid] = min(1.0, degree / scale)
        return result

    # ------------------------------------------------------------ 序列化

    def to_payload(self) -> dict:
        return {
            "clusters": self.store.to_payload(),
            "attention": {str(k): v for k, v in self.attention.items()},
            "theta_base": getattr(self.policy, "theta_base", 0.5),
            "budget_leaves": getattr(self.policy, "budget_leaves", None),
            "formed": self._formed,
        }

    def load_payload(self, payload: dict, space) -> None:
        self.store.load_payload(payload.get("clusters"), space)
        self.attention = {int(k): float(v) for k, v in (payload.get("attention") or {}).items()}
        if "theta_base" in payload and hasattr(self.policy, "theta_base"):
            self.policy.theta_base = payload["theta_base"]
        if "budget_leaves" in payload and hasattr(self.policy, "budget_leaves"):
            self.policy.budget_leaves = payload["budget_leaves"]
        self._formed = bool(payload.get("formed", True))

    # ------------------------------------------------------------ 闭环

    def step(self, ctx: TickContext) -> None:
        if ctx.tick >= self._next_form:
            self._reconcile()
            self._next_form = ctx.tick + self.form_interval
        self.store.step_coarse(ctx)
        decay(self.attention, self.gamma)
        if self.endogenous_scale:
            for cid, value in self._endogenous_attention().items():
                self.attention[cid] = max(self.attention.get(cid, 0.0), value)  # L1 社会凝视
        targets = self.policy.allocate(list(self.store.clusters.values()), self.attention)
        for cid, level in targets.items():
            cluster = self.store.clusters.get(cid)
            if cluster is None:
                continue
            if level >= 1 and cluster.level == 0:
                self.store.materialize(cid)
            elif level == 0 and cluster.level == 1:
                self.store.coarsen(cid)
        self._recycle()

    def _recycle(self) -> None:
        """回收：长期无注意的 coarse 团折回全局测度，释放槽位（防团数饱和）。"""
        if self.dissolve_floor is None:
            return
        for cid in list(self.store.clusters):
            cluster = self.store.clusters[cid]
            if cluster.level == 0 and self.attention.get(cid, 0.0) < self.dissolve_floor:
                if self.store.dissolve(cid):
                    self.attention.pop(cid, None)

    def _reconcile(self) -> None:
        """边界维护（C1）：抽入浮层亲属、记录跨团接口边；另为浮层家庭新建团。

        有界：单团成员上限 ``max_members``；**不自动合并团**（合并属 D1）；
        跨团身份敏感边记入 ``cluster.interface``（供 coarse 模型/C2 使用）。
        """
        chars = self.window.characters
        window_ids = set(chars)

        # 1) 剪掉离场成员 / 删除空团
        for cid in list(self.store.clusters):
            cluster = self.store.clusters[cid]
            if cluster.level != 1:
                continue
            cluster.member_ids &= window_ids
            if not cluster.member_ids:
                del self.store.clusters[cid]
                self.attention.pop(cid, None)

        owner = {}
        for cid, cluster in self.store.clusters.items():
            if cluster.level == 1:
                for mid in cluster.member_ids:
                    owner[mid] = cid

        # 2) 已入团的：抽入一跳浮层亲属；跨团的记接口边
        for cid in list(self.store.clusters):
            cluster = self.store.clusters.get(cid)
            if cluster is None or cluster.level != 1:
                continue
            for mid in list(cluster.member_ids):
                character = chars.get(mid)
                if character is None:
                    continue
                for key in ("spouse", "parent", "child"):
                    for other in list(character.relationships.get(key, ()) or ()):
                        oid = getattr(other, "id", None)
                        if oid is None or oid not in window_ids or oid in cluster.member_ids:
                            continue
                        other_cid = owner.get(oid)
                        if other_cid is not None and other_cid != cid:
                            self._record_interface(cluster, oid, key)   # 跨团（合并留 D1）
                        elif len(cluster.member_ids) < self.max_members:
                            cluster.member_ids.add(oid)                 # 抽入浮层
                            owner[oid] = cid

        # 3) 未入团的浮层：连通分量（有界）新建团
        unassigned = [cid for cid in chars if cid not in owner]
        root = {cid: cid for cid in unassigned}

        def find(x):
            while root[x] != x:
                root[x] = root[root[x]]
                x = root[x]
            return x

        for cid in unassigned:
            for key in ("parent", "child", "spouse"):
                for other in chars[cid].relationships.get(key, ()) or ():
                    oid = getattr(other, "id", None)
                    if oid in root:
                        ra, rb = find(cid), find(oid)
                        if ra != rb:
                            root[ra] = rb

        components = {}
        for cid in unassigned:
            components.setdefault(find(cid), []).append(cid)

        for members in components.values():
            if not (self.min_size <= len(members) <= self.max_members):
                continue
            if len(self.store.clusters) >= self.max_clusters:
                break
            cluster = self.store.create(self.form_kind, set(members))
            self.attention[cluster.id] = self.initial_attention
        self._merge_coupled()
        self._split_fragmented()
        self._formed = True

    def _window_components(self):
        """窗口全体按身份敏感边的连通分量；返回 (分量列表, person→团 owner)。"""
        chars = self.window.characters
        root = {cid: cid for cid in chars}

        def find(x):
            while root[x] != x:
                root[x] = root[root[x]]
                x = root[x]
            return x

        for cid in chars:
            for key in ("parent", "child", "spouse"):
                for other in chars[cid].relationships.get(key, ()) or ():
                    oid = getattr(other, "id", None)
                    if oid in root:
                        ra, rb = find(cid), find(oid)
                        if ra != rb:
                            root[ra] = rb

        components = {}
        for cid in chars:
            components.setdefault(find(cid), []).append(cid)
        owner = {}
        for cid, cluster in self.store.clusters.items():
            if cluster.level == 1:
                for mid in cluster.member_ids:
                    owner[mid] = cid
        return list(components.values()), owner

    def _merge_coupled(self) -> None:
        """D1 合并：同一连通分量内、合并后不超过 ``max_members`` 的多个团并一（治愈 ρ）。"""
        components, owner = self._window_components()
        for members in components:
            touched = []
            for member in members:
                cid = owner.get(member)
                if cid is not None and cid not in touched:
                    touched.append(cid)
            if len(touched) < 2:
                continue
            total = sum(len(self.store.clusters[c].member_ids)
                        for c in touched if c in self.store.clusters)
            if total > self.max_members:
                continue
            base = touched[0]
            for other in touched[1:]:
                if other in self.store.clusters:
                    self.store.merge(base, other)
                    self.attention[base] = max(self.attention.get(base, 0.0),
                                               self.attention.get(other, 0.0))
                    self.attention.pop(other, None)
            self.store.clusters[base].interface = []  # 原跨团边已内化，待下轮重记

    def _split_fragmented(self) -> None:
        """D1 分裂：团内身份图断连时，按最小连通分量切开（>= min_size 才独立成团）。"""
        chars = self.window.characters
        for cid in list(self.store.clusters):
            cluster = self.store.clusters[cid]
            if cluster.level != 1 or len(cluster.member_ids) <= self.min_size:
                continue
            ids = [m for m in cluster.member_ids if m in chars]
            root = {i: i for i in ids}

            def find(x):
                while root[x] != x:
                    root[x] = root[root[x]]
                    x = root[x]
                return x

            for i in ids:
                for key in ("parent", "child", "spouse"):
                    for other in chars[i].relationships.get(key, ()) or ():
                        oid = getattr(other, "id", None)
                        if oid in root:
                            ra, rb = find(i), find(oid)
                            if ra != rb:
                                root[ra] = rb
            groups = {}
            for i in ids:
                groups.setdefault(find(i), []).append(i)
            splits = [g for g in groups.values() if len(g) >= self.min_size]
            if len(splits) < 2:
                continue
            cluster.member_ids = set(splits[0])
            for group in splits[1:]:
                if len(self.store.clusters) >= self.max_clusters:
                    break
                child = self.store.create(self.form_kind, set(group))
                self.attention[child.id] = self.attention.get(cid, self.initial_attention)

    def _record_interface(self, cluster, other_id, kind="link", cap=32) -> None:
        """记录跨团身份敏感边（去重 + 封顶）。"""
        ref = ("character", other_id)
        for edge in cluster.interface:
            if edge.other_ref == ref:
                return
        if len(cluster.interface) >= cap:
            return
        cluster.interface.append(InterfaceEdge(kind=kind, other_ref=ref, rate=1.0,
                                               since=self.window.simulation_time))


