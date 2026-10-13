# Phase 0 接口契约：团（Cluster）与分辨率

本文是**契约**：团的数据模型、七个扩展缝、通用算子与不变量。实现骨架见 `app/core/measure/cluster.py`。

> 原则：**机制通用、策略可插拔**。MVP 只给每个策略一个实现（单 kind、两档分辨率、水位线调度、身份质量 ρ），但接口从第一天留好，后续规则不得因 MVP 而被限死。

## 1. 数据模型

```python
@dataclass
class InterfaceEdge:
    kind: str                # "inherit" | "marry" | ...（随 kind 扩展）
    other_ref: tuple         # ("cluster", id) | ("character", id)
    rate: float              # 期望强度/率
    since: int

@dataclass
class Cluster:
    id: int
    kind: str                # 注册表键，MVP = "family"
    level: int               # 分辨率：0 = coarse，1 = individual（整数，可扩展）
    member_ids: set[int]     # resolved：window 内 id；coarse：空
    state: dict              # coarse 聚合态（kind 自定，开放容器）；resolved = {}
    interface: list[InterfaceEdge]
    rho: float
    parent_id: int | None
```

## 2. 七个扩展缝

| # | 缝 | 接口 | MVP 实现 | 后续可换 |
| --- | --- | --- | --- | --- |
| 1 | 团的定义 | `ClusterKind` | `FamilyKind` | 世代团、公会、结识团… |
| 2 | 分辨率阶梯 | `Cluster.level` + `ClusterKind.cost` | `{0,1}` | 加中间档 / 连续 |
| 3 | 聚合演化 | `ClusterKind.step_coarse` | 复用 measure 流 + 族内继承池 | 各 kind 自定 |
| 4 | 合并 / 分裂 | 通用算子 + 切法注入 | 算子实现，**自动策略留空** | 谱系切 / 规模切 / 注意力切 |
| 5 | 注意力 → 分辨率 | `ResolutionPolicy.allocate` | 水位线 `θ` | 其他调度器 |
| 6 | ρ 度量 | `RhoMetric` | 身份质量 `Σ(1+degree)` | 分布散度 |
| 7 | 边界边 | `InterfaceEdge` + 处理 | 记录；婚配抽入 / 继承溢出 | 各类边自定 |

### 缝 1 · `ClusterKind`

```python
class ClusterKind(Protocol):
    name: str
    def membership_edges(self) -> set[str]: ...
        # 哪些关系算身份敏感边界（决定成员与切法）。MVP: {"parent","child","spouse"}
    def aggregate(self, members: dict[int, "Character"], space) -> object: ...
        # resolved 成员 → 聚合态（coarsen 时调用）
    def init_coarse(self, aggregate: object) -> dict: ...
        # 聚合态 → coarse 状态（一个 open dict）
    def step_coarse(self, state: dict, ctx: "TickContext") -> None: ...
        # coarse 团每 tick 批量演化（原地改 state）
    def cost(self, level: int, size: float) -> float: ...
        # 该团在给定分辨率下的预算成本
```

### 缝 2 · `ResolutionPolicy`

```python
class ResolutionPolicy(Protocol):
    def allocate(self, clusters: list[Cluster],
                 attention: dict[int, float],
                 budget: float) -> dict[int, int]: ...
        # 返回 {cluster_id: target_level}
        # MVP = 水位线：level = 1 if attention[cid] >= theta else 0
        # theta 由外部（runner）按实测 load 反馈调整
```

### 缝 3 · `RhoMetric`

```python
class RhoMetric(Protocol):
    def on_coarsen(self, kind: str, members: dict[int, "Character"]) -> float: ...
    def on_merge(self, kind: str, coupling: float) -> float: ...   # 通常 ≤ 0
    def on_split(self, kind: str, cut_weight: float) -> float: ...  # 通常 ≥ 0
```

## 3. Store（通用算子，策略无关）

```python
class ClusterStore:
    def __init__(self, measure: "Measure", window: "IndividualWindow"): ...
    def create(self, kind: str, member_ids: set[int]) -> Cluster: ...
    def materialize(self, cid: int, n: int) -> None: ...   # 聚合 → n 个新叶子（经 window）
    def coarsen(self, cid: int) -> None: ...               # 叶子 → 聚合（经 window 移出）
    def merge(self, a: int, b: int) -> int: ...            # 两团并一（通用）
    def split(self, cid: int, groups: list[set[int]]) -> list[int]: ...  # 按给定 groups 切
    def size(self) -> float: ...      # Σ coarse 团成员数（resolved 计入 window，不重复）
    def rho(self) -> float: ...
```

## 4. `TickContext`（注入，隔离引擎依赖）

```python
@dataclass
class TickContext:
    tick: int
    measure: "Measure"
    rng: random.Random
    on_resolve: Callable[[int], None]   # 事件钩子（供 life-log / L1 后续挂载）
    on_coarsen: Callable[[int], None]
```

## 5. 注册表

```python
KINDS: dict[str, ClusterKind] = {}
def register(kind: ClusterKind) -> None: ...
register(FamilyKind())   # MVP 唯一实现
```

## 6. 不变量

- `Σ measure.counts + Σ_coarse size + len(window.characters) == 初始 + 出生 − 死亡`
- 分辨率切换**计数中性**（只移动，不产生 / 销毁）：`materialize` 只从计数 ≥ 1.0 的桶析出整人（分数残量留在团内）；`coarsen` 须并入团内残留。**身份不守恒**（重采样新代表）。
- `rho ≥ 0`，coarsen 单调增，merge 可减；无悬空边（`other_ref` 必须可解析）。

## 7. 扩展约定（防限死）

1. `level` 是 `int`（新增档位只改 `cost` + policy）。
2. `kind` 只经 `KINDS` 注册表查询。
3. `state` 是开放 `dict`（各 kind 自定变量）。
4. `merge` / `split` 是通用算子；切法 / 策略单独注入（MVP 不接自动策略，只留算子）。
5. 分辨率变化只经 `on_resolve` / `on_coarsen` 钩子，不改核心。

## 8. 阶段计划

- **Phase 0（本契约）**：resolved ↔ coarse 切换、单 kind、水位线调度、ρ 代理、快照守恒。
- **Phase 1**：族级继承模型（全局池 → 族内池，验"富族恒富"）。
- **Phase 2**：开放合并 / 分裂算子。
- **Phase 3**：接自动策略（切法、水位反馈、防分层）。
