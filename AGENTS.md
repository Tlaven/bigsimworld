# SimuWorld — AI 协作记忆文件（L1）

> 本文件由 `init-project-docs` 以**嫁接模式**生成：本仓库已有成体系文档，此处**不重述事实，只做定位 + 指针 + 约束**（遵循 E1 指针优先）。
> 标 **［推断,待确认］** 的条目是从代码 / 既有文档 / 与作者会话**推断的证据草稿**，待作者拍板（集中在「开放问题」）。**当前无未决项**（4 条已于 2026-10-17 拍板，见「开放问题」表）。
>
> 宿主：OpenCode → 本文件。若将来并存 Claude Code，请只加一行指针（`见 AGENTS.md`），**不要各写一份**。

## 项目概述

**一句话**：SimuWorld —— **可承载近乎无限人口的社会仿真**：把个体完整生命周期（结识→熟络→结友→婚配→生育→死亡→继承）在"**测度引擎 + 真个体窗口**"分层架构下推到千万级，**成本与人口 N 无关**。（源：`README.md`）

- **主路径**：`SIM_MODE=measure`（生产：均值场 + 真个体窗口）；`SIM_MODE=individual` 为高保真**参照**（O(N)，**非**生产路径）。（源：`docs/engineering-spec.md` §1/§8）
- **产品目标**：**宏观忠实 + 可审计** —— 宏观分布忠实于个体语义真值，且每一步守恒可对账。（**作者已拍板：定为正式目标**，2026-10-16；源：与作者会话；佐证：收敛门槛 + 全套守恒审计体系）
- **边界外（不做什么，同样重要）**：
  - 不以 `individual` 模式作生产路径（它是 O(N) 的参照本位）；
  - 不追 `p100`（最富个体）的采样噪声（跨种子 ±0.6% 有界噪声，**非**优化目标）；
  - **不做"家族物化"**（Stage 7 结论：不需要）；
  - 不设代码风格约束（`ruff` 只做运行时缺陷探测；风格不是本仓库质量基线，测量/实验优先）。
  - **不做跨共演单元的社会网络**（T3 已评估并搁置；**作者已确认"不做"**，2026-10-16）。
  - **不做关系漏斗 / 广场 / 两个 driver 的重构**（`SimulationEngine`、`EventEngine`）——它们是**已冻结的公共面**（本主题期间不动；通道从不接触 driver）。
  - **`transfer` 只做 R↔C**（C↔C 族间再分配、resolved 簇支付不做）；折算残差**只记账、不结算**（ADR-006）——不要给它发明"把钱还给谁"的规则。
  - **交互规则默认关**（`RULES` 空）：第一条 = 跨分辨率婚配（[`adr-007`](docs/decisions/adr-007-cross-resolution-marriage.md)；大众侧 [`adr-009`](docs/decisions/adr-009-mass-marriage.md)；`both` 并存见 [`adr-012`](docs/decisions/adr-012-both-marriage-guard.md)）——`SIM_CHANNEL_MARRIAGE` 缺省关：`1` = 簇侧 / `mass` = 大众侧 / `both` = 并存（通道「一人一意图」守卫保护）。
    **开启 = 新增一条婚配通量，属模型扩展、不是对个体引擎的近似** ⇒ 收敛/保真门槛一律只在默认关闭下跑；开启后要另行校准。
  - **不做广场的"亲属避让"**（原检查读死字段 `relatives`，从未生效；字段已删，只保留同 id 保护。真要实现属独立决策——会改变个体引擎行为与已拟合常数）。

## `[已定]`（人指定的东西）

> `[已定]` = 人明确指定、AI 不得改动的东西：接口签名、数据结构、失败码、命名。
> **它等同不变量**：要改先走 ADR。没标 `[已定]` 的"设计"才视为可由 AI 提议。
> （以下条目迁自既有拍板 / 冻结记录；新增指定物请随手往这里加。）

- **两个 driver（`SimulationEngine` / `EventEngine`）及其"关系漏斗 / 广场"**——**已冻结的公共面**，本主题期间不重构（源：「边界外」；通道从不接触 driver）。
- **通道配额常数**：`cap_per_cluster=2`、`cap_per_tick=8`；窗口 headroom 预留 = `cap_per_tick`（源：ADR-003 拍板 2）。
- **可重建维度 `RECONSTRUCTIBLE = {age, gender, wealth, marital}`** 与 `marital` 的**双人析出**语义（源：ADR-003 拍板 1）。
- **`scope` / `origin` 的 `("measure",)` 寻址形态**（只对 `bind`、双向）（源：ADR-008）。

## 开放问题（未决）

**当前无未决项。** 原先的 4 条已于 2026-10-17 全部拍板（决策型陈述只增不改，落档在 ADR）：

| # | 问题 | 结论 | 状态 | 落档 |
|---|---|---|---|---|
| 1 | 婚配维度 `marital` 是否可寻址 | **双人析出**（扩 `RECONSTRUCTIBLE` + `extract(amount=2)` 同桶取 2 人并 `link` 成配偶） | **已实现**（3 轮 teach-back + 6 条新测试） | [`adr-003`](docs/decisions/adr-003-interaction-channel.md) |
| 2 | 配额形态 | **常数**：`cap_per_cluster=2`、`cap_per_tick=8` + 窗口 headroom | 已实现 | 同上 |
| 3 | 宽限期归属 | **通道机制**：`_grace_ids(tick)` 在 `allocate()` 前给出分辨率冻结集（`grace_ticks=180`） | 已实现 | 同上 |
| 4 | 分辨率层保真门槛 | **分层门槛**：结构层不设阈值 + 跨规模趋势（`age_l1` 不随 n 升且 ≤0.06）+ `pop(R−C)` 相对偏差 ≤5% 硬门禁 | **已实现**（`bench.cluster_fidelity --gate` + CI 慢跑 job） | [`adr-004`](docs/decisions/adr-004-cluster-fidelity-gate.md) |

> **第 4 条的关键更正**：`pop(R−C)` **不是**"随 n 放大"——n≈400 见顶（−4.6%）后**回落**（800: −1.0%、1600: −0.66%）；
> `age_l1` 到 n=1600（0.0359）**仍未平台化**，且衰减远慢于 1/n。数据见 [`bench/README.md`](bench/README.md) 与 `history.md` Stage 16 修订。

（`scripts/` 已接入 CI：`.github/workflows/docs-guard.yml`——PR 时跑 `check-docs-sync --strict` + `check-doc-refs --strict`。）

> **文档侧跟进（非决策级）**：E1「提示与证据不占正文」的全库清扫（`Stage N` / 过程叙事等）本轮未做——登记于 `docs/reviews/2026-10-18-methodology-upgrade.md`。

## 常用命令

```bash
# 后端（默认 measure 模式：均值场 + 真个体窗口）
python run.py                             # http://localhost:5000

# 前端
cd web && pnpm install && pnpm dev        # http://localhost:3000

# 测试 / 门禁（= CI 口径）
python -m pytest -q
python -m coverage run -m pytest -q && python -m coverage report   # 覆盖率门槛 fail_under=80
ruff check . --exclude web
cd web && pnpm build

# 基准 / 验证（改动算子前必跑，权威数字见 bench/README.md）
python -m bench.convergence --full-compare --sizes 2000 5000 10000 --steps 4000
python -m bench.audit_ledger --n 5000 --steps 8000
python -m bench.audit_ledger --clusters --n 3000 --steps 2000 --capacity 300     # 质量保持子集：整体恒等式
python -m bench.audit_ledger --resolution --n 3000 --steps 2000 --capacity 300   # 生产口径：逐算子守恒门禁
python -m bench.cluster_fidelity --members 8 --ticks 8000 --trials 40            # 共演单元保真度 A/B（配对 + 噪声带）
python -m bench.resolution_switch --ticks 600                                    # 换档动力学（四臂；含 blocked / 驻留 / 通量遥测）
python -m bench.audit_transfer                                                  # 质量侧 transfer 的财富恒等（池/清算/投递/折叠）
python -m bench.audit_ledger --wealth --n 1500 --steps 2500 --capacity 250       # 分辨率折算的财富恒等（含池 + 折算残差）
python -m bench.channel_marriage --ticks 3000                                   # 跨分辨率婚配规则 A/B（关 / 开）+ 守恒
python -m bench.calibrate_marriage --population 1200 --ticks 2000 --seeds 1 2 3 4  # 婚配规则校准（含 null 臂隔离混淆项）

# 文档检查器（手动；Windows 用 .ps1，bash 用 .sh）
powershell -File scripts/check-docs-sync.ps1
powershell -File scripts/check-doc-refs.ps1
powershell -File scripts/review-backlog.ps1      # 攒批复核：列出上次复核以来的契约变化（零 token，不判定）
```

## 架构

**一句话**：**测度层**（状态空间上的稀疏计数分布，成本 = O(占用桶数)，承载无限人口）与**真个体窗口**（≤ `capacity` 个带真实关系图的 `Character`）经 `materialize` / `dematerialize` **守恒交换**；**个体引擎是语义真值**，所有均值场近似必须收敛于它。

> L2 架构层 = [`docs/architecture.md`](docs/architecture.md)（其事实细节指 `docs/engineering-spec.md` §1）—— **此处不新造重复事实**（遵循 E1 指针优先）。
> 术语表 = [`docs/glossary.md`](docs/glossary.md)；决策 = [`docs/decisions/`](docs/decisions/README.md)；对账 = [`docs/reviews/`](docs/reviews/)。
> 分辨率/共演单元层契约 = [`docs/cluster-contract.md`](docs/cluster-contract.md)。
> 核心代码（L4，跨模块 / 骨架 / 高扇入的 N2）= [`docs/core-code.md`](docs/core-code.md)。
> 交互通道（L3，跨分辨率直接交互）= [`docs/modules/interaction-channel.md`](docs/modules/interaction-channel.md)。
> 演进史 / 实测数字 / 被拒方案 = [`docs/history.md`](docs/history.md)。
> 基准工具与当前权威数字 = [`bench/README.md`](bench/README.md)。
> Web 页面 / SSE 契约 = [`web/README.md`](web/README.md)。

## 设计哲学（[为什么]）与被拒方案

> 被拒方案是金矿（铁律 3）；完整记录见 `docs/history.md`。

- **为什么"换层"而非继续优化个体引擎**：第一章在单机上对个体引擎的所有优化（离散事件 DES、稀有事件降频 `rare_stride`、空间局部化 per-cell）**都没有突破 O(人口)**——这直接论证了换层到测度引擎的必要性。（负结果：DES 仅 1.1–1.2×，局部化 ~5%）
- **语义真值在个体引擎**：测度层是它的近似，必须收敛（`bench.convergence --full-compare`）。
- **机制通用、策略可插拔**：共演单元的 kind / 分辨率调度 / ρ 度量 / 合并分裂切法 / 显要判据，均经注册表或参数注入；MVP 只给每个策略一个实现，接口从第一天留好。（源：`docs/cluster-contract.md`）
- **守恒可审计优先于优雅**：账本禁止挂桶索引；禁止分数桶位移；财富转移只能"段池 + 整数桶支付 + 余量留池"。（源：`bench/README.md` 守恒纪律）
- **默认态是匿名**：身份是"被观察 / 被认识"供养的配额，注意力衰减即溶回统计。（源：`docs/history.md` 第三章）
- **被拒方案（为什么不）**：
  - 家族物化 —— Stage 7 证明不需要（`docs/history.md` Stage 7）；
  - per-cell pending 账本 —— 复用桶索引会凭空注水（+1.39e8）；
  - 分数桶位移 —— 计数碎片化（occupied 500→19.5k，77ms/step）；
  - 婚配 `r·min(M,F)` / `r·(M+F)` —— 严重欠婚 / 过婚；正解是**性别中立可用性闭合** `q ≈ 1-(1-p_elig)^deg`。

---

## 文档方法论（AI 协作）

本项目采用**三段式 × 4 层**文档方法论。文档是人和 AI 的"共享内存"——写**决策需要的信息**，不写**实现需要的信息**（实现看代码）。

> **边界：** N2 的"步骤级说明"属于**决策 / 规则**，不算实现信息。判据：**删掉这句会让实现产生歧义吗？会 → 留；只是让实现更快 → 删。**

### 三段式（每层文档的内部结构）

```
[是什么]   事实：这一层的内容（模块清单 / 函数清单 / etc）
[为什么]   决策：考虑过的方案 + 选择 + 理由 + 被拒方案
[不变量]   约束：必须满足的条件（功能性 + 非功能性）
```

三者缺一都会让 AI 踩坑：只有事实不知道边界，只有决策不知道现状，只有不变量不知道为什么。

### 4 层（L = Layer；层按"加载图"切，不按抽象粒度切；L4 默认不写）

| 层 | 文件 | 何时写 |
|---|---|---|
| L1 整体定位 | 本文件 | 项目立项 |
| L2 架构层 | `docs/architecture.md` | 架构设计 |
| L3 模块详细 | `docs/modules/<name>.md`（从 `docs-templates/module-doc.md` 复制） | 每模块开发前 |
| L4 核心代码 | `docs/core-code.md` | 出现**被 ≥2 个工作场景共同加载**的核心单元（函数 / 表示 / 协议 / 公共后置条件）后（默认不写） |

> **层按"加载图"切，不按抽象粒度切：** 一层的存在理由，是"有一批工作场景必须同时加载同一批东西"。判"该不该有 L4"看**加载闭包**（该单元被 ≥2 个工作场景当前置读），不看"它抽象不抽象"。**入度只有 1 的 N2，留在它自己的 L3。**

### 跨层工件 + novelty 分档

- **术语表** `docs/glossary.md`：领域词的唯一定义处（受控词汇）。**术语先定义再使用**，文档别处只引用不重述。
- **决策记录** `docs/decisions/`：ADR，记"为什么"和被拒方案。
- **对账记录** `docs/reviews/`：teach-back 与"文档考古"的发现留档（E5 产出）。
- **novelty 分档：** N0 通用模式 / N1 项目特有 / **N2 AI 未见**。N2 必须给"步骤级说明 + 危险实现清单 + 精确例子 + 可跑验收"。
  - **N2 写在哪（路由）：** 属**模块内**逻辑 → 该模块 L3 的 N2 栏（**若该模块还没有 `docs/modules/<name>.md`，先照 `docs-templates/module-doc.md` 补一份**）；属**跨模块 / 架构骨架 / 高扇入**（判据：**加载闭包 ≥ 2**）→ 记到**公共处**：① `docs/core-code.md`（L4，本项目已建）；② **未建 L4 时**的合法家 = L2 的 `[不变量]` 架构级约束（模块边界规则 / 跨模块通信方式）。所谓"L4 默认不写" = 不主动建文件，但命中收录标准的 N2 **必须有家**——**未建层 ≠ 无处可写。**
    - **跨模块逻辑只许一处成文：** 记在公共处（L4，或 L2 的架构级约束），该模块 L3 只留一行指针（E1）；**不要两处各写一份**（必然漂移）。
  - **信号 · 该不该开一份 L3：** 某模块的细节一直往 L2 / 别的大文档里堆、而不是堆进它自己的 L3 → 这是"该给它开一份 L3"的信号（**不限于"新建模块"，存量模块同样适用**）。
  - **分档只回答"有没有先验"，不回答"先验对不对"——判 N0 要两条同时成立：** ① 训练见过 / 能检索到；② 存在**明显唯一**的公认写法。**看着眼熟、但存在多个语义相近实现**的领域——金额与舍入、时区与 DST、权限边界、ID 生成、重试与幂等、字符编码、并发读写——**一律不许判 N0**：按 N1 起评，核心单元按 N2。此最危险的一档，因为它的先验不是"没有"，而是"有很多个，随机挑一个，并且一样自信"。**这份名单（「易错领域名单」）是示例、不是封闭集合**——判据是"存在多个语义相近实现"；任何满足该判据的领域都算。**它怎么往里加条目：** 三类触发——① 调研发现新领域；② 真实事故 / 踩坑；③ 复核发现了名单之外的错法——**追加一行 + 来源**；在 E5 对账时顺手做。

### 分层加载（AI 协作时按需读取）

| 场景 | 加载哪几层 |
|---|---|
| 平时对话 / 选方向 | 本文件（自动加载） |
| 遇到不认识的领域名词 | + `docs/glossary.md` |
| 做某模块工作 | + `docs/architecture.md` + 该模块 L3 |
| 改核心单元 / 新领域逻辑（N2） | **模块内**的 + 该模块 L3；**跨模块 / 骨架 / 高扇入**的 + `docs/core-code.md` **或** L2 的 `[不变量]` 架构级约束（含步骤级说明 / 危险实现清单 / 例子 / 验收） |
| 写非功能需求 / 审美要求 | + `docs-templates/verifying-nonfunctional.md`（确定性 / 性能 / 美观 / 合规怎么造验收） |
| 讨论架构变更 | + L2 的"为什么"和"不变量"段 |
| 讨论性能 / 质量 | + 各层"不变量"段 |
| 排查 bug | L2 主流程叙述 + 相关 L3 + 该 bug 所在的核心单元（core-code，或 L2 的架构级约束） |
| 文档演进 / 对账 / 大改动前 | + `docs-templates/evolution-rules.md`（E1–E7） |

### 日常入口（立项之后怎么用）

- **建新模块**：从 `docs-templates/module-doc.md` 生成 `docs/modules/<name>.md`，先填三段式（标 novelty 档），再写代码 `[脚本可查]`
- **改代码前（每次改动）**：载入相关 L2/L3。**不需要每次跑复核**；攒到你觉得"这批改动值得看一眼"时，跑 `scripts/review-backlog`（`.ps1` / `.sh`），再派独立 agent（见 `docs-templates/teach-back-verifier-prompt.md`）只复核 delta（喂整节：定义段 + 验收段必须同在——否则"没给"会被误判成缺口），复核完把起点写进 `docs/reviews/.last-review`——**推荐在对应实现之前完成** `[只能靠自觉]`
- **做决策**：按 E4 判要不要记 ADR；要记就当场写 `[需独立复核]`
- **收尾**：`scripts/` 已接入 CI（[`.github/workflows/docs-guard.yml`](.github/workflows/docs-guard.yml)，PR 跑 `check-docs-sync --strict` + `check-doc-refs --strict`）；本地可手动跑同名 `.ps1` / `.sh`。文档里"已验证 / 全绿"这类声称要标"未接 / 未复跑"——**声称不是证据** `[脚本可查]`

### 铁律

> 每条末尾的标签 = **这条靠什么生效**：`[脚本可查]` 检查器能判定 · `[需独立复核]` 要一个独立 agent 判断 · `[只能靠自觉]` 无法强制。
>
> **别与"验证方式"混：** 不变量还有一套"怎么验它"的标注——**强制 / 约定**（其中"约定" = 只写在文档里、没有自动检查）；两套轴含义不同，不要互推。

1. **先文档，再代码**——大改动前先更新对应层文档，文档是设计的契约 `[脚本可查]`
2. **ADR 即时记录**——决策当下就写，事后补 90% 会丢（触发粒度见 E4） `[需独立复核]`
3. **被拒方案要记"为什么不"**——拒绝的方案要记下原因，一年后 AI 提同样方案时，这是唯一能挡住它的记录 `[只能靠自觉]`
4. **写决策需要的信息，不写实现需要的信息**——细节让 AI 现场读代码 `[只能靠自觉]`
5. **不变量优先级最高**——三段里"不变量"最不能省，它是 AI 改代码时必须遵守的约束。**先写危险实现清单**（3 种最可能被写出来的"看起来对"的错法）——**互为遮挡：每条不变量至少挡掉一种，每项至少被一条不变量或验收挡住**；清单空 = 不变量还没想清。**人指定的接口 / 数据结构 / 失败码 / 命名标 `[已定]`**，等同不变量——AI 不得"顺手优化" `[需独立复核]`
6. **推翻陈述必须先修文档**——[是什么] 不保留已经过时的旧陈述、[为什么] 被推翻要标状态（`> ⚠️ 已被 … 推翻`，一行，保留原文）、不变量被违反时从三条出路里选一条（修订原文 / 加例外 / 放弃改动）。共享内存失真比没有内存更危险 `[需独立复核]`
7. **术语先定义再使用**——出现新领域名词先登记 `docs/glossary.md`；文档里出现未登记名词 = 漂移信号。**术语是分类信号，不是闸门信号**：新词所在的**最小逻辑单元**按 N1 起评、核心单元按 N2（若该词描述的正是领域特有的新行为，直接按 N2——登记时评估）。**只有该词还没有可判定的定义**（词条空白 / 有 ≥2 种互相竞争的含义 / 含义刚被修改）**才值得做复核**——"新增了一个已定义清楚的词"不算信号，否则冷启动时每个单元都触发，复核立刻退化成仪式 `[需独立复核]`
8. **N2 逻辑必须写到可实现**——AI 未见的领域 / 创新核心，必须给"步骤级说明 + 危险实现清单 + 精确例子 + 可跑验收"（怎么造验收见 `docs-templates/verifying-n2.md`），否则 AI 只能猜 `[需独立复核]`
9. **teach-back 是按需工具，不是必经关卡**——命中 **N2 / 不变量 / 术语歧义 / 跨层大改** 时**值得**做，由你主动发起（派发靠自觉）；默认**攒批**做——先跑 `scripts/review-backlog`，只把 delta 喂给独立 agent——**推荐在对应实现前完成**。逐次跑太贵。结论记 `docs/reviews/`；另：**它判的是"文档写没写清"，不是"断言为真"**——事实类断言靠外部核实（试跑 / 来源）：能试跑先试跑，不能则写出来源或谁拍的板 `[只能靠自觉]`
10. **长期事实只留在 `docs/` 一处**——本次调研 / 试错 / 草稿写进任务笔记（如 `task_plan.md`）；一旦确认要长期保留，就登记进 `docs/` 对应文件并从任务笔记里删掉 `[只能靠自觉]`
11. **压缩时保护关键上下文**——压缩 / 清理上下文时务必保留：术语表路径、当前不变量、验收命令、未决问题（open questions） `[只能靠自觉]`

### 文档完成判据（什么时候停）

三条**同时**满足即停，不再往文档里加内容：

1. **如果你做过复核** → 它判「通过」（「通过」只说明文档内部一致——事实断言另靠外部核实（试跑 / 来源），见铁律 9；判「需人拍板」也停笔——把判定为「需人拍板」的那几条未决问题交给用户）；**没做就跳过这条**（复核不强制，别为了凑这一条去跑）；
2. **危险实现清单**每一项都被某条不变量或某条 `**验收**` 挡住；
3. 每条 N2 都有可跑验收（命令 或 property 断言）。

缺任一条 = 还没写完；三条齐了还想再加，多半是在把实现细节抄进决策层。

### 演化期规则（立项之后，文档怎么不死）

> **E1–E7 的唯一归属是 `docs-templates/evolution-rules.md`**（随项目落地）。本 L1 只留指针——**做文档演进 / 对账 / 大改动前加载它**。
> （一句话：三段式是容器；每段里的陈述按**性质**——描述型 / 决策型 / 约束型 / 方向型——分四类，腐烂方式各异，维护动作见那七条。）

---

## 项目级约束（L1 [不变量] 段）

- **守恒律**：`Σ measure.counts + Σ_coarse size + len(window.characters) == 初始 + 出生 − 死亡`；所有分辨率算子（`create/materialize/coarsen/merge/split/dissolve`，以及窗口侧 `materialize`/`dematerialize`）**计数中性**（只移动，不产生/销毁）。（源：`docs/engineering-spec.md` §9、`docs/cluster-contract.md` §6）
- **身份不守恒**：`coarsen → materialize` 是**重采样新代表**（人数守恒、身份不保）。不要把身份当守恒量。
- **财富守恒（含池与折算残差）**：`W = Σ_测度 [count×桶中心 + transfer_pool + conversion_residual + Σ yearly_inherited] + Σ 窗口 wealth`；`transfer`（R→C / C→R / 清算 / 投递）与**所有分辨率折算**（materialize/coarsen/merge/split/dissolve/dematerialize/unbind/回填）严格中性。池**非负且按粗侧归属**，残差是**不可花费**的符号账；`coarsen/merge/dissolve/split` 必须折叠三样（两个池 + 残差）。门禁 `bench.audit_transfer` + `bench.audit_ledger --wealth`。（源：`docs/decisions/adr-005-transfer-quality-side.md`、`adr-006-conversion-residual.md`、`docs/engineering-spec.md` §9）
- **收敛门槛**（测度 vs 个体）：`gini_diff < 0.02`、`wealth_ks < 0.06`、`age_l1 < 0.06`、`married_diff < 0.10`。判定由 `tests/`（`pytest`）断言；人肉核对口径 = `bench.convergence --full-compare --sizes 2000 5000 10000 --steps 4000`。（源：`docs/history.md` 验收门槛）
- **分辨率层保真门槛（分层）**：**禁止**在生产簇规模（`members ≤ 12`）上设单点阈值；门槛只在可判读口径上定义——跨规模（n≥400）+ 配对试验 + 多 trial：`age_l1` 随 n **不升**且最大 n 处 ≤ 0.06、`pop(R−C)` 相对偏差 ≤ 5% 且**不随 n 增长**。验证：`python -m bench.cluster_fidelity --gate`（CI 慢跑）；结构层仍由 `tests/test_cluster_fidelity.py` 守。（源：`docs/decisions/adr-004-cluster-fidelity-gate.md`）
- **质量底线**：`coverage fail_under=80`；`ruff` 仅运行时缺陷（`E9/F63/F7/F82`），**风格刻意不设**。（源：`pyproject.toml`）
- **确定性**：设 `SIM_SEED` 即固定随机种子 + 跳过墙钟负载反馈（同种子必然同发展）；`SIM_RESUME=1` 以快照为准、**不参与**种子重演。（源：`docs/engineering-spec.md` §9）
- **算子改动纪律**：改财富/账本类算子必跑 `bench.audit_ledger` (+ `--resolution`)；账本禁止挂桶索引、禁止分数桶位移、转移只走"段池 + 整数桶 + 余量留池"。（源：`bench/README.md`）
- **技术栈**：后端 Python 3.12（Flask）；前端 Vue 3 + Vuetify 3；SSE 依赖 Redis；持久化 SQLite。
