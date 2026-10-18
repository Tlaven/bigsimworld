"""共演单元（Cluster）与分辨率：Phase 0 实现。

契约见 `docs/cluster-contract.md`。本文件定义数据模型、扩展缝与通用算子：
机制通用、策略可插拔——kind / 调度 / ρ / 合并分裂切法均经注册表或参数注入。

MVP：唯一 kind = family（以 parent/child/spouse 为身份敏感边），两档分辨率
（0 = 聚合, 1 = 个体），水位线调度，身份质量 ρ，自动合并/分裂策略留空。

coarse 共演单元的聚合态 = 一个 **mini `MeanFieldEngine`**（同一 StateSpace；流集合 = 族内版：
aging / income + **整数语义发放**的 death / marriage + birth，见 `docs/decisions/adr-010-mini-integer-semantics.md`）：
族内遗产池天然作用域在共演单元内，复用 `transitions` 全部算子，无需新机制。
（MVP 近似：族内也会发生婚配/生育；跨共演单元边留待 interface。）

守恒律：`Σ measure.counts + Σ_coarse size + len(window.characters) == 初始 + 出生 − 死亡`
（分辨率切换恒等守恒：计数只移动，不产生/销毁）。
"""

from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Protocol

from app.core.generation.human import generate_character
from app.core.person.links import neighbors
from app.core.measure.channel import ChannelContext, InteractionChannel, RULES
from app.core.measure.engine import MeanFieldEngine
from app.core.measure.measure import (fold_pools, measure_from_characters,
                                      measure_from_payload, measure_to_payload,
                                      record_conversion)
from app.core.measure.transitions import (aging, birth, distribute_pool, income,
                                          inject_inherited, integer_death,
                                          integer_marriage, settle_transfer_pool)
from app.core.measure.transitions import (BIRTH_RATE, DEATH_RATE, MARRIAGE_MEAN_DEG,
                                          MARRIAGE_RATE)

# 换档/通量遥测的滚动窗（tick）。≈ 2 年：既覆盖多次换档周期，又让窗内计数不至于跨 regime。
FLUX_WINDOW = 720


# ---------------------------------------------------------------- 数据模型

@dataclass
class InterfaceEdge:
    """跨共演单元的身份敏感边（未内化的对外作用）。"""

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
    """共演单元的种类：定义成员边界、聚合态与聚合演化。"""

    name: str

    def membership_edges(self) -> set:
        """哪些关系算身份敏感边界（决定成员与切法）。"""

    def aggregate(self, members: dict, space) -> object:
        """resolved 成员 → 聚合态（coarsen 时调用）。"""

    def init_coarse(self, aggregate: object) -> dict:
        """由聚合态初始化 coarse 状态（一个 open dict）。"""

    def step_coarse(self, state: dict, ctx: TickContext) -> None:
        """coarse 共演单元每 tick 的批量演化（原地修改 state）。"""

    def cost(self, level: int, size: float) -> float:
        """该共演单元在给定分辨率下的预算成本。"""


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
    """MVP ρ：收编时按被遗忘的身份质量计（1 + 关系度）；合并/分裂暂返回 0。

    关系度来自 `links.neighbors`（`relationships` 的并集），**不是**已删除的死字段
    `relatives`——后者构造后从不更新，会让 ρ 退化为"簇成员数"（见 `docs/history.md` Stage 1 编注）。
    """

    def on_coarsen(self, kind: str, members: dict) -> float:
        return float(sum(1 + len(neighbors(c)) for c in members.values()))

    def on_merge(self, kind: str, coupling: float) -> float:
        return 0.0

    def on_split(self, kind: str, cut_weight: float) -> float:
        return 0.0


class WealthNotability:
    """默认显要判据：个体财富落在**全人口财富分布的高位分位**之上。

    可审计：阈值由全局测度分布确定性推出（可复现、可解释——"此人财富高于全人口 top q"）；
    ``fraction`` 越小越"极端"（0.01 = top 1%）。策略可插拔：替换本对象即换判据。
    """

    name = "wealth"

    def threshold(self, measure, space, fraction):
        """全人口财富降序累计到 ``fraction`` 人口处的桶中心；空分布返回 None。"""
        counts = measure.counts
        by_wealth = {}
        for index in measure.occupied:
            wealth = space.decode(index)[2]
            by_wealth[wealth] = by_wealth.get(wealth, 0.0) + counts[index]
        if not by_wealth:
            return None
        target = max(1.0, sum(by_wealth.values()) * max(float(fraction), 0.0))
        acc = 0.0
        for wealth in sorted(by_wealth, reverse=True):
            acc += by_wealth[wealth]
            if acc >= target:
                return space.wealth_value(wealth)
        return space.wealth_value(min(by_wealth))

    def is_notable(self, character, threshold):
        return threshold is not None and getattr(character, "wealth", 0.0) >= threshold


class FamilyKind:
    """MVP 唯一 kind：以 parent/child/spouse 为身份敏感边的家族共演单元。

    聚合态 = mini `MeanFieldEngine`；继承由 ``step_coarse`` 手动处理（含溢出口），
    其余流算子复用 `transitions`。``overflow_fraction``：族内继承中改注入全局池
    的比例（0 = 完全内化，即"富族恒富"）。
    """

    name = "family"
    overflow_fraction = 0.0
    # 整数语义（adr-010）：mini 在个人尺度用信用发放的婚配/死亡（期望同率、整人发放），
    # 不把整人桶削到 (0,1)；继承仍由 `family_inheritance` 手动处理。
    flows = (aging, income, integer_death, integer_marriage, birth)

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


def _expected_flux(members) -> dict:
    """粗模型对**成员聚合**的每 tick 期望事件人-次（只读；不消耗随机数）。

    单位 = 人-次：一桩婚事 = 2（两人各得配偶边）；一次出生 = 1；一次死亡 = 1。
    速率与 `transitions` 的算子**同源**（`BIRTH_RATE` / `DEATH_RATE` /
    婚配可用性闭合 `q = 1-(1-p_elig)**MARRIAGE_MEAN_DEG`），即"若这簇现在是 coarse，
    mini 引擎每 tick 会对它做多少事"。生产簇规模下逐 tick 期望极小（~1e-4 量级），
    要判读需跨窗/跨簇聚合。
    """
    births = deaths = 0.0
    singles = adults = 0.0
    for character in members:
        age = character.age
        if age >= 60:
            deaths += DEATH_RATE
        if character.relationships.get("spouse"):
            if 18 <= age <= 50:
                births += BIRTH_RATE
        elif 18 <= age < 60:
            singles += 1.0
        if 18 <= age < 60:
            adults += 1.0
    marriages = 0.0
    if singles > 1.0 and adults > 0.0:
        p_elig = singles / adults
        availability = 1.0 - (1.0 - p_elig) ** MARRIAGE_MEAN_DEG
        marriages = min(MARRIAGE_RATE * singles * availability * 2.0, singles)
    return {"births": births, "deaths": deaths, "marriages": marriages}


class WaterlinePolicy:
    """MVP 调度：**基线 θ + leaf 数预算**（可选滞回带）。

    - `theta_base`（基线，固定）：未 resolved 的簇注意力 ≥ 该值即升级；内在冷却保证不刷新必降温；
    - `theta_down`（可选滞回下阈；缺省 `None` ⇒ = `theta_base`，与无滞回逐位一致）：
      已 resolved 的簇在 `attention ≥ theta_down` 时**保持**——注意力在
      `[theta_down, theta_base)` 区间抖动时不再来回换档（换档 = 身份重采样 + 簿记）；
    - `budget_leaves`（叶子预算）：最多保留多少叶子；按注意力降序分配，超预算的低注意共演单元降档；
    - `feedback`（负载反馈）：实测超预算则收紧叶子预算、有余量则放宽（区间 [1, max_leaves]）。
    """

    def __init__(self, theta_base: float = 0.5, budget_leaves: int | None = None, alpha: float = 0.1,
                 theta_down: float | None = None):
        self.theta_base = theta_base
        self.theta_down = None if theta_down is None else float(theta_down)
        self.max_leaves = budget_leaves
        self.budget_leaves = budget_leaves
        self.alpha = alpha

    def allocate(self, clusters: list, attention: dict, budget_leaves: int | None = None) -> dict:
        budget = self.budget_leaves if budget_leaves is None else budget_leaves
        theta_down = self.theta_base if self.theta_down is None else self.theta_down
        ranked = sorted(clusters, key=lambda c: attention.get(c.id, 0.0), reverse=True)
        targets = {}
        remaining = budget
        for cluster in ranked:
            cost = self._leaf_cost(cluster)
            score = attention.get(cluster.id, 0.0)
            threshold = theta_down if cluster.level == 1 else self.theta_base
            if score < threshold:
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
    """共演单元容器与通用算子（策略无关）。成员为 resolved 时计入 window，不重复计数。"""

    def __init__(self, measure: object, window: object, rho_metric: RhoMetric | None = None,
                 rng=None):
        self.measure = measure
        self.window = window
        self.space = getattr(window, "space", None) or measure.space
        self.rho_metric = rho_metric or IdentityMassRho()
        self.rng = rng or getattr(window, "rng", None) or random
        self.clusters: dict = {}
        self._next_id = 0
        self.dissolved_rho = 0.0  # 已回收共演单元的累计 ρ（回收不抹掉遗忘代价）
        # 结构版本号：成员集合每变一次 +1。消费方（person→cluster 反向索引）靠它做缓存失效，
        # 避免"改了成员却没被发现"的静默错索引。
        self.revision = 0

    # ------------------------------------------------------------ 建立共演单元

    def create(self, kind: str, member_ids: set) -> Cluster:
        self._next_id += 1
        cluster = Cluster(id=self._next_id, kind=kind, level=1, member_ids=set(member_ids))
        self.clusters[cluster.id] = cluster
        self.revision += 1
        return cluster

    def touch(self) -> None:
        """结构变更通知：凡**直接**改过 `cluster.member_ids` / `clusters` 的调用方都要调一次。"""
        self.revision += 1

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
        # 成员精确 wealth → 桶中心：差额逐个记入折算残差（ADR-006 / N2-5）。
        # 注意：**不能**复用 `dematerialize`（那会同时把本人折回全局测度 ⇒ 双记）。
        for character in members.values():
            record_conversion(aggregate, self.space, character.wealth)
        # 物化后残留的 coarse 质量（未析出的分数残量）必须一并折回：否则再次粗化会以
        # 窗口成员重建聚合态，把这部分残留丢掉（守恒漏洞）。
        leftover = (cluster.state or {}).get("engine")
        if leftover is not None:
            mini = leftover.measure
            for index in list(mini.occupied):
                aggregate.add(index, mini.counts[index])
            # 池（通道池 + 继承段池）必须一起折回，否则再次粗化会丢财富（ADR-005）
            fold_pools(mini, aggregate)
        cluster.rho += self.rho_metric.on_coarsen(cluster.kind, members)
        for mid in list(members):
            self.window.detach(mid)
        cluster.member_ids = set()
        cluster.state = kind.init_coarse(aggregate)
        cluster.level = 0
        self.revision += 1

    def materialize(self, cid: int, n: int | None = None) -> int:
        """聚合 → 若干新叶子（经 window 建真个体，新代表而非原人）。返回实际析出数。

        只从**计数 ≥ 1.0** 的桶析出整人（分数残量留在共演单元内），故质量恒等守恒：每个析出
        恰扣回 1.0。**身份不守恒**（物化是重采样新代表，见 docs/engineering-spec.md §9）。
        """
        cluster = self.clusters[cid]
        if cluster.level >= 1:
            return 0
        mini = cluster.state["engine"].measure
        size = int(mini.total())
        count = size if n is None else min(n, size)
        made = 0
        for _ in range(count):
            cell = self.extract(mini)
            if cell is None:
                break
            age, gender, wealth, _marital = self.space.decode(cell)
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
        self.revision += 1
        return made

    def extract(self, mini, predicate=None, amount: float = 1.0):
        """从 ``mini`` 选出一个**可整人取出**的桶并扣减 ``amount``；返回桶索引或 None。

        - ``predicate``：None = 任意桶；否则是"桶索引 → bool"的判定函数
          （**谓词式寻址**的落地形态——粗侧只有分布、没有 id）。
        - 只从 ``count ≥ amount`` 的桶取：``Measure.add`` 在结果 ≤0 时把桶夹零，强行取
          分数桶会**只扣分数、却生出一个完整的人**（质量泄漏）——见 `docs/engineering-spec.md` §9。
          分数残量留在共演单元内（物化上限随之收缩），随 ``dissolve`` 折回全局测度。
        - 候选集**排序**后再加权抽样：``occupied`` 是 set，直接迭代顺序不稳，
          会破坏确定性（`docs/history.md` Stage 15 的教训）。
        - 用注入的 ``rng``，**不得**用模块级 ``random``。
        """
        eligible = sorted(index for index in mini.occupied
                          if mini.counts[index] >= amount
                          and (predicate is None or predicate(index)))
        if not eligible:
            return None
        total = sum(mini.counts[index] for index in eligible)
        r = self.rng.random() * total
        acc = 0.0
        chosen = eligible[-1]
        for index in eligible:
            acc += mini.counts[index]
            if acc >= r:
                chosen = index
                break
        mini.add(chosen, -amount)
        return chosen

    # ------------------------------------------------------------ 合并 / 分裂

    def merge(self, a: int, b: int) -> int:
        """两共演单元并一。resolved+resolved 保留成员（免费）；否则先粗化再并 mini。"""
        ca, cb = self.clusters[a], self.clusters[b]
        if ca.level == 1 and cb.level == 1:
            # b 可能持有"物化后残留"的 mini（分数计数 + 池）——`del` 之前必须折走，否则财富/计数一起丢
            src_engine = cb.state.get("engine")
            if src_engine is not None:
                mb = src_engine.measure
                dst_engine = ca.state.get("engine")
                if dst_engine is not None:
                    ma = dst_engine.measure
                    for index in list(mb.occupied):
                        ma.add(index, mb.counts[index])
                    fold_pools(mb, ma)
                    ca.state["size"] = ma.total()
                else:
                    for index in list(mb.occupied):
                        self.measure.add(index, mb.counts[index])
                    mb.marriage_credit = mb.death_credit = 0.0   # 回流体区：信用作废（adr-010）
                    fold_pools(mb, self.measure)
            ca.member_ids |= cb.member_ids
            ca.rho += self.rho_metric.on_merge(ca.kind, 0.0)
            del self.clusters[b]
            self.revision += 1
            return a
        self.coarsen(a)
        self.coarsen(b)
        ma = ca.state["engine"].measure
        mb = cb.state["engine"].measure
        for index in list(mb.occupied):
            ma.add(index, mb.counts[index])
        fold_pools(mb, ma)
        ca.state["size"] = ma.total()
        ca.rho += self.rho_metric.on_merge(ca.kind, 0.0)
        del self.clusters[b]
        self.revision += 1
        return a

    def split(self, cid: int, groups: list) -> list:
        """按给定 groups 切分（切法由策略注入）。MVP 只支持 resolved 共演单元。"""
        cluster = self.clusters[cid]
        if cluster.level != 1:
            raise NotImplementedError("MVP 只支持 resolved 共演单元的切分")
        # 被切掉的簇可能持有"物化后残留"的 mini（分数计数 + 池）：没有"分给哪个孩子"的
        # 策略，故**折回全局测度**（不做猜测）——否则 `del` 会把它们一起丢掉。
        engine = cluster.state.get("engine")
        if engine is not None:
            mini = engine.measure
            for index in list(mini.occupied):
                self.measure.add(index, mini.counts[index])
            mini.marriage_credit = mini.death_credit = 0.0   # 回流体区：信用作废（adr-010）
            fold_pools(mini, self.measure)
        del self.clusters[cid]
        self.revision += 1
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
        """把 **coarse** 共演单元折回全局测度：释放槽位、质量守恒、ρ 记入累计。

        （resolved 共演单元不直接溶解——成员还在窗口；策略应先粗化或跳过。）
        """
        cluster = self.clusters.get(cid)
        if cluster is None or cluster.level != 0:
            return False
        engine = cluster.state.get("engine")
        if engine is not None:
            mini = engine.measure
            for index in list(mini.occupied):
                self.measure.add(index, mini.counts[index])
            mini.marriage_credit = mini.death_credit = 0.0   # 回流体区：信用作废（adr-010）
            fold_pools(mini, self.measure)
        self.dissolved_rho += cluster.rho
        del self.clusters[cid]
        self.revision += 1
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
        self.revision += 1
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
    """把共演单元存储 + 注意力 + 水位线调度 + 预算反馈绑成一个每 tick 的闭环。

    形成共演单元 = 每 `form_interval` tick，对**尚未纳入共演单元的浮层个体**做 parent/child/spouse
    连通分量（>= min_size 建一共演单元）；分辨率由水位线决定；注意力随时间衰减
    （不刷新则共演单元自动粗化）；观察者 `set_attention` 可钉住（高注意力）或放掉（低）。
    注意度按 **共演单元 id** 记，故共演单元在 coarsen/materialize 间保持身份、注意力不丢。
    """

    def __init__(self, window, measure=None, policy=None, gamma=0.99,
                 form_kind="family", min_size=2, max_members=12, max_clusters=64,
                 initial_attention=0.8, form_interval=30, budget_leaves=None, dissolve_floor=0.1,
                 endogenous_scale=None, notability=None, notable_fraction=None, rng=None,
                 grace_ticks=180, channel=None, min_dwell_ticks=30):
        self.window = window
        self.measure = measure or window.measure
        self.space = window.space
        self.rng = rng or getattr(window, "rng", None) or random
        self.store = ClusterStore(self.measure, window, rng=self.rng)
        self.grace_ticks = grace_ticks
        # 交互通道：本期 RULES 为空 ⇒ 惰性（不产生任何操作）。
        # 宽限期表（`channel.recently_active`）在 `allocate()` 之前被读取。
        self.channel = channel or InteractionChannel(self.window, self.store,
                                                     rng=self.rng, grace_ticks=grace_ticks)
        self._owner_cache = None   # person id → cluster id（惰性重建；按 store.revision 失效）
        self._owner_rev = None
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
        self.notability = notability               # 显要判据：None=关（策略可插拔）
        self.notable_fraction = None if notable_fraction is None else float(notable_fraction)
        if self.notability is None and self.notable_fraction is not None:
            self.notability = WealthNotability()
        self.notable_threshold = None
        self.attention = {}
        self._formed = False
        self._next_form = 0
        self._refresh_notability()
        # —— 换档纪律 / 通量遥测（规格见 `docs/cluster-contract.md` §9）——
        # 最小驻留闸**缺省启用**（adr-011）：同一簇两次换档至少隔 `min_dwell_ticks`；
        # 只延迟、不放行、不否决；构造参数传 0 即关闭（逐 tick 判定）。
        self.min_dwell_ticks = int(min_dwell_ticks)
        self._last_switch: dict = {}
        self._switch_count: dict = {}
        self._switch_total = 0
        self._switch_blocked: dict = {}  # cid → 物化尝试失败次数（无可析出的整人桶）
        self._flux: dict = {}            # cid → {"ids": set, "spouse": {mid: n}}（上 tick 末基线）
        self._flux_win: dict = {}        # cid → deque[(real_b, real_d, real_m, exp_b, exp_d, exp_m)]
        self._flux_window_ids = None     # 上 tick 末的窗口 id 集（用于识别"本 tick 新出现"）

    # ------------------------------------------------------------ 受保护成员

    def protected_ids(self) -> set:
        ids = set()
        for cluster in self.store.clusters.values():
            if cluster.level == 1:
                ids |= cluster.member_ids
        ids |= self.notable_ids()          # 显要者绝不逐出（即使未纳入共演单元）
        return ids

    # ------------------------------------------------------------ 显要（notability）

    def set_notable_fraction(self, fraction) -> None:
        """设置显要分位（``None`` = 关闭）并立即重算阈值。生产由 runner 经 env 开启。"""
        self.notable_fraction = None if fraction is None else float(fraction)
        if self.notable_fraction is not None and self.notability is None:
            self.notability = WealthNotability()
        self._refresh_notability()

    def _refresh_notability(self) -> None:
        """从全局测度分布重算显要阈值（每 ``form_interval`` 一次即可）。"""
        if self.notability is None or self.notable_fraction is None:
            self.notable_threshold = None
            return
        self.notable_threshold = self.notability.threshold(
            self.measure, self.space, self.notable_fraction)

    def notable_ids(self) -> set:
        """当前窗口内被判为"显要"的个体 id（自身世界影响 = 财富高位分位）。"""
        threshold = self.notable_threshold
        if threshold is None:
            return set()
        return {cid for cid, character in self.window.characters.items()
                if self.notability.is_notable(character, threshold)}

    # ------------------------------------------------------------ 观察者接口

    def set_attention(self, cluster_id: int, value: float) -> None:
        self.attention[cluster_id] = float(value)

    def _owner_index(self) -> dict:
        """person id → cluster id 的反向索引（惰性重建；`store.revision` 变了才重建）。"""
        revision = self.store.revision
        if self._owner_cache is None or self._owner_rev != revision:
            owner = {}
            for cluster in self.store.clusters.values():
                if cluster.level == 1:
                    for mid in cluster.member_ids:
                        owner[mid] = cluster.id
            self._owner_cache = owner
            self._owner_rev = revision
        return self._owner_cache

    def cluster_of(self, person_id: int):
        """person id → 其所属共演单元 id（resolved 共演单元成员）；无则 None。O(1)。"""
        return self._owner_index().get(person_id)

    def summary(self, max_entries: int = 64) -> dict:
        """观测面摘要（有界）：水位/预算/ρ/共演单元数 + 共演单元条目。"""
        entries = []
        for cluster in list(self.store.clusters.values())[:max_entries]:
            size = len(cluster.member_ids) if cluster.level == 1 else round(cluster.state.get("size", 0.0), 3)
            engine = cluster.state.get("engine")
            entries.append({
                "id": cluster.id,
                "kind": cluster.kind,
                "level": cluster.level,
                "size": size,
                "rho": round(cluster.rho, 3),
                "pool": round(engine.measure.transfer_pool, 1) if engine is not None else 0.0,
                "attention": round(self.attention.get(cluster.id, 0.0), 3),
                "switches": self._switch_count.get(cluster.id, 0),
                "blocked": self._switch_blocked.get(cluster.id, 0),
            })
        return {
            "theta_base": getattr(self.policy, "theta_base", None),
            "theta_down": getattr(self.policy, "theta_down", None),
            "budget_leaves": getattr(self.policy, "budget_leaves", None),
            "min_dwell_ticks": self.min_dwell_ticks,
            "switch_total": self._switch_total,
            "rho": round(self.store.rho(), 3),
            "cluster_count": len(self.store.clusters),
            "resolved_count": sum(1 for c in self.store.clusters.values() if c.level == 1),
            "notability": {
                "metric": getattr(self.notability, "name", None),
                "fraction": self.notable_fraction,
                "threshold": (round(self.notable_threshold, 1)
                              if self.notable_threshold is not None else None),
                "notable_count": len(self.notable_ids()),
            },
            "clusters": entries,
        }

    def feedback(self, cost: float, budget: float) -> None:
        if hasattr(self.policy, "feedback"):
            self.policy.feedback(cost, budget)

    # ------------------------------------------------------------ 交互通道

    def _collect_intents(self, ctx) -> list:
        """向规则征集本 tick 的意图。**默认 `RULES` 为空 ⇒ 恒返回 []**（通道惰性）。

        位置契约：在 `store.step_coarse()` + `_settle_transfer_pools()` **之后**、
        `channel.run()` **之前**调用 ⇒ 规则看到的 coarse 权重与同 tick 的 `extract` 同源。
        """
        if not RULES:
            return []
        context = ChannelContext(tick=ctx.tick, window=self.window, store=self.store,
                                 rng=self.rng)
        intents = []
        for rule in RULES.values():
            intents.extend(rule.offers(context) or ())
        return intents

    def _grace_ids(self, tick: int) -> set:
        """**宽限期 = 分辨率冻结**：这些簇不换档（不 `coarsen` 也不 `materialize`）、也不被回收。

        起初用"把注意力抬到 `theta_base`"来实现，但那会让 `allocate` 反过来**物化**该簇
        （注意力 ≥ 门槛 ⇒ `target=1`）——与"别扰动刚建好的关系"的意图相反。故改为显式冻结。
        """
        channel = self.channel
        for cid, when in list(channel.recently_active.items()):
            if tick - when >= channel.grace_ticks or cid not in self.store.clusters:
                channel.recently_active.pop(cid, None)
        return set(channel.recently_active)

    def channel_summary(self) -> dict:
        return self.channel.summary()

    # ------------------------------------------------------------ 换档纪律 / 通量遥测

    @property
    def switch_total(self) -> int:
        """累计换档次数（含已被回收的簇；只读观测面）。"""
        return self._switch_total

    def telemetry(self) -> dict:
        """换档与通量遥测（只读快照；**不参与任何决策**）。

        每簇：`switches` / `last_switch` / `dwell`（自上次换档的停留）+ 滚动窗内
        `real`（实测人-次）与 `expected`（粗模型期望）的求和。判读注意：生产簇规模
        （≤12）下窗内计数是个位量级——需跨簇/跨窗聚合，或在大簇上读。
        """
        now = self.window.simulation_time
        out = {}
        for cid in (set(self._flux_win) | set(self._switch_count)
                    | set(self._last_switch) | set(self._switch_blocked)):
            win = self._flux_win.get(cid)
            if win:
                real = [sum(x[i] for x in win) for i in range(3)]
                expected = [sum(x[i] for x in win) for i in range(3, 6)]
            else:
                real = [0.0, 0.0, 0.0]
                expected = [0.0, 0.0, 0.0]
            when = self._last_switch.get(cid)
            out[cid] = {
                "ticks": len(win) if win else 0,
                "real": {"births": real[0], "deaths": real[1], "marriages": real[2]},
                "expected": {"births": expected[0], "deaths": expected[1],
                             "marriages": expected[2]},
                "switches": self._switch_count.get(cid, 0),
                "blocked": self._switch_blocked.get(cid, 0),
                "last_switch": when,
                "dwell": None if when is None else now - when,
            }
        return out

    def _scan_flux(self) -> None:
        """通量遥测：对每个 resolved 共演单元逐 tick 记「实测 vs 粗模型期望」。

        **只读不变量**：不消耗任何随机数、不碰边/分布——只写自有的滚动窗。
        实测窗口 = 「上 tick 末基线 → 本处」之间：逐簇匹配（成员消失≈死亡，成员受保护；
        成员配偶数增加=婚姻，人-次；新出现的窗口个体若父母在成员集内=出生）。
        载入/重放顺序（`WindowEngine.step`）保证此处之前只有窗口事件发生。
        """
        if not self._flux:
            return
        window = self.window
        current_ids = set(window.characters)
        new_ids = (current_ids - self._flux_window_ids
                   if self._flux_window_ids is not None else set())
        for cid, entry in list(self._flux.items()):
            cluster = self.store.clusters.get(cid)
            if cluster is None or cluster.level != 1:
                continue
            members = [window.characters[mid] for mid in cluster.member_ids
                       if mid in window.characters]
            expected = _expected_flux(members)
            deaths = sum(1 for mid in entry["ids"] if mid not in current_ids)
            marriages = 0
            for mid, spouse_n in entry["spouse"].items():
                character = window.characters.get(mid)
                if character is None:
                    continue
                now = len(character.relationships.get("spouse", ()) or ())
                if now > spouse_n:
                    marriages += now - spouse_n
            births = 0
            if new_ids:
                member_ids = cluster.member_ids
                for new_id in new_ids:
                    character = window.characters.get(new_id)
                    if character is None:
                        continue
                    for parent in character.relationships.get("parent", ()) or ():
                        if getattr(parent, "id", None) in member_ids:
                            births += 1
                            break
            self._flux_win.setdefault(cid, deque(maxlen=FLUX_WINDOW)).append(
                (births, deaths, marriages,
                 expected["births"], expected["deaths"], expected["marriages"]))
        self._flux_window_ids = current_ids

    def _snapshot_flux(self) -> None:
        """记录/清理遥测基线（每 tick 末调用一次；只读事件，不改行为）。"""
        window = self.window
        self._flux = {cid: entry for cid, entry in self._flux.items()
                      if cid in self.store.clusters
                      and self.store.clusters[cid].level == 1}
        for cid, cluster in self.store.clusters.items():
            if cluster.level != 1:
                continue
            ids = {mid for mid in cluster.member_ids if mid in window.characters}
            self._flux[cid] = {
                "ids": ids,
                "spouse": {mid: len(window.characters[mid].relationships.get("spouse", ()) or ())
                           for mid in ids},
            }
        for book in (self._last_switch, self._switch_count, self._switch_blocked, self._flux_win):
            for cid in [cid for cid in book if cid not in self.store.clusters]:
                del book[cid]
        self._flux_window_ids = set(window.characters)

    def _endogenous_attention(self) -> dict:
        """L1 社会凝视：共演单元被窗口内**非成员**认识的程度（外部入边数）→ [0,1] 注意力。

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
            "last_switch": {str(k): int(v) for k, v in self._last_switch.items()},
            "switches": {str(k): int(v) for k, v in self._switch_count.items()},
            "blocked": {str(k): int(v) for k, v in self._switch_blocked.items()},
            "switch_total": int(self._switch_total),
        }

    def load_payload(self, payload: dict, space) -> None:
        self.store.load_payload(payload.get("clusters"), space)
        self.attention = {int(k): float(v) for k, v in (payload.get("attention") or {}).items()}
        if "theta_base" in payload and hasattr(self.policy, "theta_base"):
            self.policy.theta_base = payload["theta_base"]
        if "budget_leaves" in payload and hasattr(self.policy, "budget_leaves"):
            self.policy.budget_leaves = payload["budget_leaves"]
        self._formed = bool(payload.get("formed", True))
        self._last_switch = {int(k): int(v)
                             for k, v in (payload.get("last_switch") or {}).items()}
        self._switch_count = {int(k): int(v)
                              for k, v in (payload.get("switches") or {}).items()}
        self._switch_blocked = {int(k): int(v)
                                for k, v in (payload.get("blocked") or {}).items()}
        self._switch_total = int(payload.get("switch_total", 0))
        self._flux = {}                  # 遥测在恢复后重新开始（观测数据不参与决策）
        self._flux_win = {}
        self._flux_window_ids = None

    # ------------------------------------------------------------ 闭环

    def step(self, ctx: TickContext) -> None:
        self._scan_flux()               # 通量遥测：只读；须在边界维护/换档之前（见 _scan_flux）
        if ctx.tick >= self._next_form:
            self._reconcile()
            self._next_form = ctx.tick + self.form_interval
        self.store.step_coarse(ctx)
        # —— 年度投递（transfer 池，N2-6）：在 coarse 演化（含继承年清算）之后、意图之前 ——
        self._settle_transfer_pools(ctx.tick)
        # —— 交互通道：在 coarse 演化之后、分辨率调度之前 ——
        for intent in self._collect_intents(ctx):
            self.channel.submit(intent)
        self.channel.run(ctx)
        decay(self.attention, self.gamma)
        if self.endogenous_scale:
            for cid, value in self._endogenous_attention().items():
                self.attention[cid] = max(self.attention.get(cid, 0.0), value)  # L1 社会凝视
        notable = self.notable_ids()
        for cid, cluster in self.store.clusters.items():
            if cluster.level == 1 and cluster.member_ids & notable:
                self.attention[cid] = max(self.attention.get(cid, 0.0), 1.0)  # 显要：注意力地板
        grace = self._grace_ids(ctx.tick)   # 刚绑定的簇：宽限期内**分辨率冻结**（不换档、不回收）
        targets = self.policy.allocate(list(self.store.clusters.values()), self.attention)
        for cid, cluster in self.store.clusters.items():
            if cluster.level == 1 and cluster.member_ids & notable:
                targets[cid] = 1            # 显要所在共演单元无视预算，绝不粗化
        for cid, level in targets.items():
            cluster = self.store.clusters.get(cid)
            if cluster is None:
                continue
            if cid in grace:                # 宽限期：分辨率冻结
                continue
            if level >= 1 and cluster.level == 0:
                direction = 1
            elif level == 0 and cluster.level == 1:
                direction = 0
            else:
                continue
            if (self.min_dwell_ticks > 0
                    and ctx.tick - self._last_switch.get(
                        cid, ctx.tick - self.min_dwell_ticks) < self.min_dwell_ticks):
                continue                    # 最小驻留：两次换档之间至少隔 min_dwell_ticks
            if direction == 1:
                made = self.store.materialize(cid)
                if not made:
                    # 物化被卡：mini 里没有任何 count ≥ 1.0 的整人桶可析出。
                    # 历史成因（均值场 marriage 把单身桶削到 1.0 以下）已由 adr-010 的
                    # 整数语义发放修复；此计数保留为异常观测面（生产路径期望 ≈ 0）。
                    self._switch_blocked[cid] = self._switch_blocked.get(cid, 0) + 1
                    continue
            else:
                self.store.coarsen(cid)
            self._last_switch[cid] = ctx.tick
            self._switch_count[cid] = self._switch_count.get(cid, 0) + 1
            self._switch_total += 1
        self._recycle(grace)
        self._snapshot_flux()               # 记录本 tick 末的遥测基线（只读事件）

    def _settle_transfer_pools(self, tick: int) -> None:
        """每 360 tick：全局测度 + 每个簇 mini 的通道池按整桶投递回分布（N2-6 第 6 步）。

        `RULES` 为空时池恒 0，本调用是 O(簇数) 的空转，对惰性路径无行为影响。
        """
        settle_transfer_pool(self.measure, tick)
        for cluster in self.store.clusters.values():
            engine = cluster.state.get("engine")
            if engine is not None:
                settle_transfer_pool(engine.measure, tick)

    def _recycle(self, grace=frozenset()) -> None:
        """回收：长期无注意的 coarse 共演单元折回全局测度，释放槽位（防共演单元数饱和）。"""
        if self.dissolve_floor is None:
            return
        for cid in list(self.store.clusters):
            if cid in grace:                # 宽限期：不回收
                continue
            cluster = self.store.clusters[cid]
            if cluster.level == 0 and self.attention.get(cid, 0.0) < self.dissolve_floor:
                if self.store.dissolve(cid):
                    self.attention.pop(cid, None)

    def _reconcile(self) -> None:
        """边界维护（C1）：抽入浮层亲属、记录跨共演单元接口边；另为浮层家庭新建共演单元。

        有界：单个共演单元成员上限 ``max_members``；**不自动合并共演单元**（合并属 D1）；
        跨共演单元身份敏感边记入 ``cluster.interface``（供 coarse 模型/C2 使用）。
        """
        chars = self.window.characters
        window_ids = set(chars)

        # 1) 剪掉离场成员 / 删除空共演单元
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

        # 2) 已纳入共演单元的：抽入一跳浮层亲属；跨共演单元的记接口边
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
                            self._record_interface(cluster, oid, key)   # 跨共演单元（合并留 D1）
                        elif len(cluster.member_ids) < self.max_members:
                            cluster.member_ids.add(oid)                 # 抽入浮层
                            owner[oid] = cid

        # 3) 未纳入共演单元的浮层：连通分量（有界）新建共演单元
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
        self.store.touch()   # 本轮直接改过 member_ids（抽入 / 剪枝 / 切分）→ 通知反向索引失效
        self._formed = True
        self._refresh_notability()

    def _window_components(self):
        """窗口全体按身份敏感边的连通分量；返回 (分量列表, person→共演单元 owner)。"""
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
        """D1 合并：同一连通分量内、合并后不超过 ``max_members`` 的多个共演单元并一（治愈 ρ）。"""
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
            self.store.clusters[base].interface = []  # 原跨共演单元边已内化，待下轮重记

    def _split_fragmented(self) -> None:
        """D1 分裂：共演单元内身份图断连时，按最小连通分量切开（>= min_size 才独立形成共演单元）。"""
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
        """记录跨共演单元身份敏感边（去重 + 封顶）。"""
        ref = ("character", other_id)
        for edge in cluster.interface:
            if edge.other_ref == ref:
                return
        if len(cluster.interface) >= cap:
            return
        cluster.interface.append(InterfaceEdge(kind=kind, other_ref=ref, rate=1.0,
                                               since=self.window.simulation_time))


