# Phase 0 接口契约：共演单元（Cluster）与分辨率

本文是**契约**：共演单元的数据模型、七个扩展缝、通用算子与不变量。实现骨架见 `app/core/measure/cluster.py`。
跨分辨率**直接交互**（R↔C）的通道契约见 [`modules/interaction-channel.md`](modules/interaction-channel.md)；本节只描述共演单元自身。

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
    interface: list[InterfaceEdge]   # **预留字段**：无消费方 / 不随快照 / 粗化后不清理——启用前先定义消费语义并修数据面
    rho: float
    parent_id: int | None
```

## 2. 七个扩展缝

| # | 缝 | 接口 | MVP 实现 | 后续可换 |
| --- | --- | --- | --- | --- |
| 1 | 共演单元的定义 | `ClusterKind` | `FamilyKind` | 世代共演单元、公会、结识共演单元… |
| 2 | 分辨率阶梯 | `Cluster.level` + `ClusterKind.cost` | `{0,1}` | 加中间档 / 连续 |
| 3 | 聚合演化 | `ClusterKind.step_coarse` | 复用 measure 流 + 族内继承池 | 各 kind 自定 |
| 4 | 合并 / 分裂 | 通用算子 + 切法注入 | 算子实现，**自动策略留空** | 谱系切 / 规模切 / 注意力切 |
| 5 | 注意力 → 分辨率 | `ResolutionPolicy.allocate` | 水位线 `θ` | 其他调度器 |
| 6 | ρ 度量 | `RhoMetric` | 身份质量 `Σ(1+degree)` | 分布散度 |
| 7 | 边界边 | `InterfaceEdge` + 处理 | 记录；婚配抽入 / 继承溢出 | 各类边自定 |
| 8 | 显要判据 | `Notability`（`threshold` + `is_notable`） | `WealthNotability`（财富高位分位） | 影响力 / 关系枢纽 / 复合 |

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
        # coarse 共演单元每 tick 批量演化（原地改 state）
    def cost(self, level: int, size: float) -> float: ...
        # 该共演单元在给定分辨率下的预算成本
```

### 缝 2 · `ResolutionPolicy`

```python
class ResolutionPolicy(Protocol):
    def allocate(self, clusters: list[Cluster],
                 attention: dict[int, float],
                 budget: float) -> dict[int, int]: ...
        # 返回 {cluster_id: target_level}
        # MVP = 水位线：未 resolved 的簇 attention >= theta_base 升级；
        # 已 resolved 的簇 attention >= theta_down 保持（可选滞回；theta_down 缺省 = theta_base）
        # theta_base 固定（0.5）；runner 的负载反馈调的是**预算** budget_leaves，不是阈值。
        # 预算不足时按注意力降序分配、超出的簇降档（MVP 顺序）。
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
    def merge(self, a: int, b: int) -> int: ...            # 两共演单元并一（通用）
    def split(self, cid: int, groups: list[set[int]]) -> list[int]: ...  # 按给定 groups 切
    def size(self) -> float: ...      # Σ coarse 共演单元成员数（resolved 计入 window，不重复）
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
- 分辨率切换**计数中性**（只移动，不产生 / 销毁）：`materialize` 只从计数 ≥ 1.0 的桶析出整人（分数残量留在共演单元内）；`coarsen` 须并入共演单元内残留。**身份不守恒**（重采样新代表）。
- **质量账随生命周期折叠**：`coarsen` / `merge` / `dissolve` / `split` 除 `counts` 外必须折叠 `transfer_pool`、`yearly_inherited` 与 `conversion_residual`（逐段/逐项相加）；`merge` 的 resolved+resolved 快路径与 `split` 尤其不能漏（它们会删掉持有 mini 的簇）。否则财富（以及分数计数残留）蒸发。快照须往返这三项。财富口径见 `engineering-spec.md` §9。
- `rho ≥ 0`，coarsen 单调增，merge 可减；无悬空边（`other_ref` 必须可解析）。
- 显要者（notability）**不逐出**，其所在共演单元**不粗化**——关键个体不失去特殊性。

## 7. 扩展约定（防限死）

1. `level` 是 `int`（新增档位只改 `cost` + policy）。
2. `kind` 只经 `KINDS` 注册表查询。
3. `state` 是开放 `dict`（各 kind 自定变量）。
4. `merge` / `split` 是通用算子；切法 / 策略单独注入（MVP 不接自动策略，只留算子）。
5. 分辨率变化只经 `on_resolve` / `on_coarsen` 钩子，不改核心。

## 8. 阶段计划（现状）

- **Phase 0（已实现）**：resolved ↔ coarse 切换、单 kind、水位线调度、ρ 代理、快照守恒。
- **Phase 1（已实现）**：族级继承模型（族内池 + `overflow_fraction` 溢出口）。
- **Phase 2（已实现）**：合并 / 分裂自动策略（连通分量合并、断连切分；切法策略仍留白）。
- **Phase 3（部分）**：水位反馈已接；显要保护、宽限冻结、社会凝视已落地。**换档纪律**（驻留**缺省 30**、滞回 opt-in）与**通量遥测**（只读）已就位（见 §9）；mini 的**整数语义发放**已实现（"物化被卡"修复，见 §9）；"误差触发"未做。

## 9. 换档一致性账

**问法**：换档（`materialize` / `coarsen` / `merge` / `split` / `dissolve`，及窗口侧物化/退场）在**哪个量**上会偏离、被**什么**测、**成本**多少。性质分三类分开记（**严格守恒** / **统计近似** / **不可比**），另有观测账：

| 量 | 性质 | 仪器 | 已知边界 / 成本 |
| --- | --- | --- | --- |
| 计数（人头） | **严格守恒**（分辨率算子只移动，不产生/销毁） | `tests/test_cluster.py`、`tests/test_cluster_fidelity.py`、`bench.audit_ledger --clusters` / `--resolution` | — |
| 财富（分布质量 + 通道池 + 折算残差 + 继承段池） | **严格守恒**（折算差进残差；池只按实付扣） | `bench.audit_ledger --wealth`、`bench.audit_transfer` | 旧快照缺残差字段 ⇒ 恢复后 W 一次性断点（兼容边界） |
| 年龄分布 / 人口 / 已婚比例 / 人均财富 / 池占比 | **统计近似**（换档改变"分布视点"；"近似"指**跨臂/跨视点比较**口径——单次运行内人均财富由计数/财富的严格性钉死） | `bench.cluster_fidelity`（配对试验 + 跨 trial）；门槛口径 = 跨规模趋势（生产簇规模 ≤12 的单点读数不可判读） | 真实系统性偏差 ≲0.05（`age_l1` 尚未平台化）；`pop(R−C)` 有界（≈−0.7%@n=1600） |
| 身份 / 图结构（度、关系） | **不可比**（coarse 无图；重采样新代表 = 身份不守恒） | 无（`degree_l1 = n/a` 属类别错误） | 设计语义，不是缺陷 |
| 换档频率 / 驻留 / 被卡物化 / 身份重采样次数 | **观测账**（不构成守恒律） | `ResolutionManager.telemetry()`（字段 `switches` / `blocked` / `dwell` / `risk`）/ `resolution_summary()`；`bench.resolution_switch`（描述性） | 生产簇规模下事件计数小（个位/窗），判读需跨簇聚合；`blocked` 期望 ≈ 0，异常时按次计 |
| 身份质量 ρ | **观测账**（`coarsen` 单调增、`merge` 可减；不构成守恒律） | `resolution_summary()`（SSE `resolution` 字段） | — |
| 整数语义信用（`marriage_credit` / `death_credit`） | **发放器状态**（**非质量**、不进守恒恒等式；只影响发放时机） | `tests/test_cluster.py`（往返 / 折叠 / 发放） | `coarsen`/`merge` 求和、`dissolve`/`split` 折入全局时作废、快照往返（旧档缺字段按 0） |
| resolved 期间"实测事件 vs 粗模型期望"通量 | **只读遥测**（不进策略） | `ResolutionManager.telemetry()`；`tests/test_cluster.py` | 相关性研究已完成：**作触发不可用**（生产簇规模下是泊松噪声）；观测面保留 |

**换档纪律**：`WaterlinePolicy` 支持滞回（`theta_down`，缺省 = `theta_base` ⇒ 无滞回；**默认关闭、opt-in**——生产注意力轨迹未实测）；`ResolutionManager` 的最小驻留 `min_dwell_ticks` **缺省 30**（防抖闸：只延迟换档，不放行、不否决；构造参数传 0 关闭）。**只管 level 切换**（`materialize` / `coarsen`）；`merge` / `split` / `dissolve` 不受驻留/滞回约束。

**误差触发（候选，缺省关）**：`risk_alert=None`；启用时，**上次观测的相位离散度**（resolved 期逐 tick 由成员 `pedometer` 相对 `tick % 360` 的圆离散度更新）≥ 阈值的 coarse 簇被抬到**升级阈值** `theta_base` ⇒ 按常规路径**被物化（升级）**——即"证据支持它值得被看"；不阻止降档、不影响已 resolved 的簇。生产样态内该指示器近似随簇规模取常数（≈0.66–0.78）、簇间差异很小 ⇒ **缺省不启用**（仅对"同相异常"如整批同时出生有判别力）。

**成本注记**：换档成本 = resolved 侧按人数（`ClusterKind.cost`）、coarse 侧常数 1；每次换档的簿记 = 池/残差折叠 O(成员)；身份重采样 = 每个析出成员一次"新代表"生成（成年入窗互认 ≤3 个 acquaintance）。

**整数语义（已实现）**：mini（`family`）的 `marriage` / `death` 为**信用发放**版——**两个独立字段** `marriage_credit` / `death_credit`，按全局同源期望通量累积（单位 = **人份**）：婚配每 tick 对 **mini 自身**统计 `singles`（`marital=0 ∧ 18≤age<60` 的 count 和）与 `adults`（**全部** `18≤age<60` 的 count 和，**含已婚**），`credit += min(MARRIAGE_RATE × singles × q × 2, singles)`——**累积门槛只有 `singles > 1.0`（与全局公式同源），门槛之上累积与整人是否够发无关**；`q = 1 − (1 − p_elig)^MARRIAGE_MEAN_DEG`、`p_elig = singles / adults`（同一公式/常数；数值见 `engineering-spec.md` §2：`MARRIAGE_RATE = 0.1/360`、`DEATH_RATE = 0.05/360`、`MARRIAGE_MEAN_DEG = 2.5`；**360 tick = 1 年**）；死亡 `credit += Σ_{age≥60} count × DEATH_RATE`——**按 60+ 全部 count（含分数余量）累积**，分数贡献不可发放（既有边界）。**满值 = 婚配 2.0 / 死亡 1.0**，满即**整人发放**；信用**先行累积**（阻塞时保留、**可超过阈值跨 tick 累积**、不丢不清零）。抽样位置**不混入 mini id**——同构 mini 会在同一 tick 同步抽到相同位置（边际仍均匀；跨 mini 相关属已知性质）。

**婚配选人（2026-10-19 修订）** = **确定性加权均匀抽样**：候选 = `count ≥ 1.0 ∧ marital=0 ∧ 18 ≤ age < 60` 的桶；权重 = 桶内**整人数** `int(count)`（分数余量不计权、不参与抽取），总权重 = Σ 整人数（整数）；位置 = `_mix32(tick, 2·pair)` / `_mix32(tick, 2·pair+1)`（`pair` = 本 mini 本 tick 内已发放批数，从 0 起），对总权重取模后沿**索引升序**按整人数累计定位（命中 = 累计 > position，**整数边界**）。**`total < 2` 或 `second_total < 1` 时先 break（不对 0 取模）**；一桩婚事取两人：第一人桶的整人数减 1，仍 ≥1 才可再选；剩余整人 < 1 ⇒ **本批不发放、信用保留**。落桶：两人**各自**从原桶 `−1.0`、同 `(age, gender, wealth)` 的 `marital=1` 桶 `+1.0`（同一桶双取时即 `−2.0 / +2.0`；目标桶不存在则创建；`space.encode = ((age×2 + gender)×wealth_bins + wealth)×3 + marital`，**age 最高位**）。发放循环 `while credit ≥ 2.0`——**同一 tick 发到 credit < 2.0 或整人不足为止**。期望 ≡ 对**整人**单身总体均匀抽人（原"最大桶优先 + 平局索引序"已推翻——索引以 age 为最高位 ⇒ 会变成"最年轻优先"）。

**「整人桶不被削到 (0,1)」的准确含义**：整数计数的桶只按整 1.0 减、**永不被分数削**；**分数余量（`count < 1.0` 的桶）不参与抽取**；`count ≥ 1.0` 的桶可被抽走整 1.0（`count = 1.5` 的桶参与抽取、按整人数 1 计权），剩余 0.5 不参与后续发放（直到被 `birth`/`aging` 补成整人）。分数余量只可能来自 `birth` 注入或旧档。

死亡发放：候选 = `count ≥ 1.0 ∧ age ≥ 60` 的桶，按 `(-count, 索引升序)` 取 1.0——**平局时较年轻 60+ 优先移除**（与婚配旧规则同构；不触生育通道，登记为观察项）；**已婚 60+ 死亡不改变配偶 `marital`**（模型不建模寡居；第 3 档恒空）；发放循环 `while death_credit ≥ 1.0`——**同一 tick 发到 credit < 1.0 或整人不足为止**（不足时信用保留）。死亡记录写入 `recent_deaths`（每 tick **替换**语义；元素 `(age, wealth_bucket, amount = 1.0)`；由 `inject_inherited` 读取并清空）。

两者均不消耗 rng、确定性；单身/60+ 共演单元保持可物化（`blocked` **按簇累计**：`ResolutionManager` 每次升级物化尝试失败——mini 无可析出的整人桶——该簇 +1；期望 ≈ 0）。信用是发放器状态（**非质量**、不进守恒恒等式）：`coarsen`（**仅 mini→mini**；重建聚合时新 mini 的信用 = 旧 mini 信用之和——`fold_pools` 求和、新聚合从 0 起）与 `merge`（mini→mini）**求和**；`merge`（mini→全局测度）、`dissolve`、`split`（**MVP 只切 resolved 簇，mini 残留折回全局——不存在 mini→mini 的 split**）**作废清零**——不存在 `coarsen`→全局 的路径；快照往返（旧档缺字段按 0；旧档桶内容原样保留，其中的分数余量不可发放）。实现锚点：`app/core/measure/transitions.py`（`integer_marriage` / `integer_death` / `_mix32` / `_weighted_pick`）。**验收**：`python -m pytest tests/test_cluster.py -q`——7 条：婚配 5（`test_integer_marriage_fires_whole_pairs` / `test_integer_marriage_selection_is_age_uniform` / `test_integer_marriage_fractional_weights_are_uniform` / `test_integer_marriage_pair_can_share_bucket` / `test_integer_marriage_consumes_no_rng`）+ 死亡 2（`test_integer_death_loop_terminates_and_keeps_credit` / `test_integer_death_keeps_credit_without_whole_buckets`，既有 `test_integer_death_fires_whole_removals` 覆盖整人移除与 `recent_deaths`）。两个均匀性用例为**每 tick 重置**夹具（年龄均匀：42 个年龄桶各 1.0；分数均匀：3 个年龄桶各 1.2；均 2400 tick、每 tick 重建桶群并置 `marriage_credit = 2.0`；断言 min > 0.5×mean 且 max < 2×mean）；`python -m bench.cluster_fidelity --gate`。
