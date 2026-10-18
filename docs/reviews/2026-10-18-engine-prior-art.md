# 2026-10-18 · 引擎先例调研：分辨率交换 / 群体压缩 / 换档触发 / LLM 个体侧

> **性质**：调研 archive（检索 + 文献深读的结论与链接）。**吸收与否属未决**——候选清单见 §4，未决项见 §5；不要把本记录的"可偷"当承诺用。
> **方法**：12 组检索 + 3 份深读（EBT 用户手册 / WSC 2015《Multi Resolution Modeling》/ 若干主文献摘要页）；其余为摘要级，链接随文。细读前不要把摘要当结论用。

## 1. 逐组件先例

### 1.1 群体压缩（"一批人 = 一个带权重的单位"）

- **Super-individuals**（Scheffer et al. 1995, Ecological Modelling 80:161）——生态学里"超个体 = 同质个体群 + 数量权重"，与我们的"桶内 `count > 1`"同构。已知实操切法（2008 比较论文）：按空间格 / 初始年龄 / 形态切超个体。
  - 可偷：**分裂/合并判据的讨论**（判据细节未验证，需细读原文）；"lucky individual"平均掉稀有幸运者的偏差——与我们 p100 顶部噪声是同类问题。
- **EBT / 结构化种群**（de Roos，手册已深读）——cohort = **数量 + 平均 i-state**，逐 ODE 推进；**统计量"相同"的 cohort 合并**（取权重重心）、**"可忽略"的删除**（tolerance 参数化）；新生儿进入 **boundary cohort（"创建中"群体，统计量定义不同）**；事件可触发闭群（dynamic cohort closure）；cohort 按均值 i-state 排序但**明确告诫不可依赖顺序**。
  - 可偷：① 合并/删除的 tolerance 参数化；② "boundary cohort"独立档位（与我们"新簇 + 宽限期"有影子）；③ "顺序不可依赖"对我们 `occupied` 迭代纪律是外部佐证。
- **Covasim / Starsim（流行病，工业级工具）**——`pop_scale`：一个 agent 代表 k 人；支持**动态 rescaling**（阈值/因子触发自动缩放）；FAQ 的辩护："未暴露的 80 万人不必被代表"。
  - 可偷：自动粗化触发器的工程形态（阈值 + 平滑）；静态缩放 vs 动态缩放两档语义。

### 1.2 分辨率交换（materialize / dematerialize / coarsen 的邻居）

- **MRM / 军事仿真的 Aggregation-Disaggregation（AD）问题**（WSC 2015，深读）——触发 = **地理区域**（进 "disaggregation area" 展开、离开聚合）；两条路线：**A/D（单表示，切换有成本）** vs **MRE（双表示常驻）**；把 **consistency（一致性）与 cost-effectiveness** 列为核心难题（"一致性成本 = 维持一致要付多少参数/动作"）；另有 chain disaggregation、Yilmaz 等 10 条多分辨率设计要求。
  - 可偷：① "一致性账"视角（哪个量在换档处会偏、谁在测、成本多少）；② disaggregation area ≈ 我们的注意力/宽限触发；③ 10 条要求当对照清单。另：2025 有综述（MDPI Information 16(8):635），抓取失败，留作细读。
- **AdResS（分子动力学）**——原子级 / 粗粒级两区域实时互转（**grand-canonical**：可增减自由度）；关键结论：**两层各自正确，边界交换仍引入偏差，需一个校准过的 thermodynamic force 修正**。
  - 可偷：边界修正的"合法解法"先例；我们当前对应物 = 速率自个体引擎校准 + 收敛门槛。
- **PIC 宏粒子合并/分裂**（CPC 2023 / 2025）——合并要**守恒质量/动量/能量**，且"相位空间近邻才合并"以保住分布函数（PDF）。
  - 可偷：split 方向的矩守恒数学（未来大簇拆分用）；"近邻合并"与 EBT 的"相同合并"同族。
- **术语**：equation-free 方法把细↔粗互转叫 **lifting / restriction**（+ coarse projective integration）。
  - 可偷：查文献用的关键词。

### 1.3 换档触发（"何时细化/粗化"）

- 文献触发源盘点：AMR = 误差估计；军事 = 地理区域；流行病混合模型 = **感染数阈值 + 滞回**（JASSS 23/4/14）；Covasim = 阈值 + 平滑；图形学 = 相机距离 / 密度（LOD）。
- **tau-leaping 的 "leaping condition"**：用局部速率变化约束步长——成文的**步长-误差契约**语言。
- 观察：**"社会注意力驱动"没有成体系的先例**（游戏 LOD 最近似，但没有"观测者供养身份"的语义）——这是本项目的独有位。

### 1.4 前沿：个体侧（窗口）的"语义真值"升级

- **AgentSociety（2025, arXiv:2502.08691）**：LLM 驱动、10k+ agents、500 万次交互；有"大规模仿真引擎"，但**没有"无身份的大众"层**。
  - 可偷/定位：**LLM 放窗口、测度层承载其余**——窗口个体引擎做成可插拔（现事件机 ↔ LLM 认知），宏观账单不变；token 花在显要身上。
- **双表示的图形学先例**（Narain et al. 2009《Aggregate Dynamics》：离散个体 + 连续场、单边不可压约束）——佐证 dual representation 是各领域成熟招。

## 2. 对表（机制级）

| 我们的机制 | 最近先例 | 先例有 / 我们没有 |
| --- | --- | --- |
| 桶内 `count > 1`（超个体语义） | super-individual / EBT cohort / Covasim 缩放 | 分裂/合并判据（超个体方差判据；EBT tolerance） |
| materialize / dematerialize | MRM 的 AD 展开/聚合；AdResS 交换 | "一致性成本"语言；边界修正纪律；滞回切换控制 |
| coarsen / merge / split | PIC 守恒合并；EBT 合并/删除 | 矩守恒 split；"近邻/相同"合并判据 |
| 换档调度（注意力 + 水线） | AMR / 军事区域 / 流行病阈值 | 误差触发通道、滞回带（要不要借：未决） |
| 窗口 = 唯一有图/身份处 | MRE 双表示；Narain 双表示 | （结构性同族，无需借） |
| 个体侧事件机 | 各 ABM 引擎 | LLM 可插拔（前沿方向） |

## 3. 判词（评估）

- **组件级都有近亲，组合级没有**：最接近的 MRM 不在意守恒对账；超个体 / EBT 没有"身份重采样"这个动作（其成员始终是真实个体）。
- 本项目独有词三条：**双向身份↔分布的重采样桥**（身份不守恒、计数/财富守恒）；**注意力驱动的分辨率调度**；**浮点级对账的守恒文化**——前两条文献里有邻居（不慌），第三条是别人没有的。
- 欠挖方向：经济学 OLG 的 "blocks" 技术；GAMA / Repast 生态的聚合机制；（细读）Scheffer 1995/2008 的分裂判据。

## 4. 候选吸收项（供计划/拍板）

1. **一致性账**：借 MRM 的"一致性成本"视角，给分辨率层列"哪个量在换档处可能偏 / 谁在测 / 成本"——纯审计，不改行为。
2. **触发纪律**：滞回带 + 误差/通量残差通道（试点）——把"注意力决定看哪里、误差决定哪里看不准"分开。
3. **merge/split 判据细读**：Scheffer 1995/2008 → 评估能否替换或补充现有的"连通分量 + size cap"。
4. **窗口个体引擎可插拔**（方向性，未立项）：为 LLM 语义真值留接口。

## 5. 未决（待拍板）

- 吸收哪些项、以什么形态落地（本记录不构成承诺）。
- ④ 是否立项（涉及成本 / API，属另一决策）。

> **跟进（2026-10-18）**：第一批已落地——① 一致性账（`cluster-contract.md` §9）；② 换档纪律 + 通量遥测（缺省 No-Op）；③ Scheffer 细读（**无分裂判据**；结论与"为什么不"见 [`2026-10-18-resolution-consistency-audit.md`](2026-10-18-resolution-consistency-audit.md)）；④ 仍未立项。

## 附：来源

- [Super-individuals（Scheffer et al. 1995）](https://www.sciencedirect.com/science/article/pii/030438009400055M) · [2008 比较论文（Elsevier）](https://www.sciencedirect.com/science/article/pii/S0304380008000574)
- [EBT User's Manual（de Roos）](https://staff.fnwi.uva.nl/a.m.deroos/downloads/EBT/EBTmanual.pdf) · [EBT 主页](https://staff.fnwi.uva.nl/a.m.deroos/EBT/index.html)
- [Multi Resolution Modeling（WSC 2015）](https://informs-sim.org/wsc15papers/253.pdf) · [MRM 综述（MDPI 2025）](https://www.mdpi.com/2078-2489/16/8/635)
- [AdResS（JCTC 2012）](https://pubs.acs.org/doi/10.1021/ct3003354) · [ESPResSo AdResS 教程](https://espressopp.github.io/tutorial.AdResS.html)
- [PIC 动态合并/分裂（CPC 2023）](https://www.sciencedirect.com/science/article/pii/S0010465523002588) · [守恒式聚类-合并（CPC 2025）](https://www.sciencedirect.com/science/article/pii/S0010465525001237)
- [Equation-free modeling（Wikipedia）](https://en.wikipedia.org/wiki/Equation-free_modeling)
- [混合流行病 ABM-方程切换（JASSS 23/4/14）](https://www.jasss.org/23/4/14.html) · [混合 metapopulation 框架（PMC）](https://pmc.ncbi.nlm.nih.gov/articles/PMC11815675/)
- [Tau-leaping（Wikipedia）](https://en.wikipedia.org/wiki/Tau-leaping) · [Exact tau-leaping（arXiv 2025）](https://arxiv.org/pdf/2509.12631)
- [Covasim 参数（pop_scale / rescale）](https://docs.covasim.org/parameters.html) · [Covasim FAQ（动态缩放）](https://docs.covasim.org/faq.html) · [Starsim rescaling](http://docs.starsim.org/user_guide/advanced_rescaling.html)
- [TRS integerisation（Lovelace & Ballas 2013）](https://arxiv.org/abs/1303.5228) · [Spatial Microsimulation with R](https://spatial-microsim-book.robinlovelace.net/smsimr)
- [AgentSociety（arXiv 2502.08691）](https://arxiv.org/abs/2502.08691) · [AgentSociety GitHub](https://github.com/tsinghua-fib-lab/agentsociety)
- [Continuum Crowds（SIGGRAPH 2006）](https://grail.cs.washington.edu/projects/continuum-crowds/continuum-crowds.pdf) · [Aggregate Dynamics（Narain et al. 2009）](https://dl.acm.org/doi/10.1145/1618452.1618468)
