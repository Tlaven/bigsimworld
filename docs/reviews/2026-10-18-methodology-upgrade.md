# 2026-10-18 · 文档方法论升级（全量对齐 init-project-docs 当前版）

> 触发：用户指令「加载 init-project-docs 再调整项目文档」。按 skill 的 **Step 2D（delta 对账）** 判定：项目已在用该方法论（L1 有三段式 / 铁律 / E 规则指针），但 L1 方法论段、5 个旧模板与 2 个检查器停留在**早期版本**；`docs-templates/` 缺 4 件、`scripts/` 缺 `review-backlog`。用户拍板「**全量对齐**」。

## 1. 升级前的对账基线

新版检查器预演（含 `engineering-spec` / `cluster-contract` 扩入扫描面）：**37 条发现**——2 条 `[n2-missing-checklist]`（core-code / interaction-channel）+ 35 条 `[live-doc-refs]`（architecture 2 / glossary 1 / core-code 1 / engineering-spec 7 / cluster-contract 2 / interaction-channel 22）。

## 2. 本轮改动

### 2.1 L1（`AGENTS.md`，190 → 221 行）
新增 `[已定]` 段（4 条：冻结公共面 / 通道配额常数 / `RECONSTRUCTIBLE` 与双人析出 / `("measure",)` 寻址形态）；方法论段对齐当前版：铁律标签更名（`[脚本可查]` / `[需独立复核]` / `[只能靠自觉]`）、铁律 5 增「危险实现清单」、铁律 7 增「术语是分类信号」、铁律 9 改「按需工具、可攒批」、新增「文档完成判据」、novelty 段增「判 N0 两条条件 + 易错领域名单」、L4 判据改「加载闭包 ≥ 2」、加载表增「非功能需求」行、日常入口接 `review-backlog`、常用命令增检查器行。

### 2.2 `docs-templates/`（5 → 9 件，全部当前版）
新增 `verifying-nonfunctional.md` / `glossary.md` / `decisions-readme.md` / `core-code.md`；升级 `module-doc.md`（+危险实现清单 +失败语义表 +指针形）/ `verifying-n2.md`（+变异体用法 +契约断言通则 +"声称不是证据"）/ `teach-back-verifier-prompt.md`（+独立复算与遮挡核对两项必做动作）/ `evolution-rules.md`（E1 引用纪律 / E3 编号制 / E5 扩检 / E7 豁免）/ `adr-template.md`（指针修正）。

### 2.3 `scripts/`（2 → 3 个检查器）
`check-doc-refs` 升级（+大小写错链 / +危险实现清单 / +失败语义节 / +现状文档引记录 / +「挡住者」列非空）；`check-docs-sync` 升级（autocrlf 兼容 + `docs/reviews/` 豁免）；新增 `review-backlog` ×2。
**项目定制全部保留 / 补齐**：`CODE_GLOB`（目录式，避免 `scripts/` 误报）、`DocExclude`（+`docs-templates/` + `docs/reviews/`）、`LIVE_DOCS`（+`engineering-spec` / `cluster-contract`）、`CONTRACT`（同上两件）。`.last-review` 起点 = `499b44e 2026-10-18`。

### 2.4 现状文档引用自足化（35 处）
按新 E1（现状 / 规则陈述须自足；ADR / 对账件引用只作**入口文档**的导航），移除或改写：architecture 2、glossary 1、core-code 1、engineering-spec 7、cluster-contract 2、interaction-channel 22（含 4 处 `../reviews/` 相对链接——机器不查，一并清）。中央导航保留在 L1。

### 2.5 危险实现清单重构（10 张表）
`core-code.md`（N2-1..N2-5，5 张）+ `interaction-channel.md`（N2-5/6/7/8 + 模块级，5 张）：原「陷阱」列表 → 「最可能被写成的样子 / 为什么错 / 由谁挡住」三列表；「由谁挡住」只引**既有不变量**与**真实测试名**（与各单元验收 / mutation 一一对应）；interaction-channel 另补「失败语义」表（失败路径 / 对外表现 / 观测）。

### 2.6 对账顺带修正的存量漂移（E5 产出）
1. **通道 L3 的财富折叠口径滞后 Stage 18**：不变量 9 / 12、N2-6 第 7 步只说"两个池"，未含 `conversion_residual`——按代码与 `bench.audit_ledger --wealth` 的现状回写（含快照"往返三项"）。
2. **状态空间桶数 stale**：`2.18e6 / ≈17MB`（3000 财富桶时代）→ `43.56M = 121×2×60000×3 ≈ 348MB`；core-code ×2、interaction-channel ×2（`space.py` 当前默认 `maritals=3`、`wealth_bins=60000` 为地面真值）。
3. **`engineering-spec` §9 的 `w − c` 符号重载**：Stage 18 复盘已定"统一为 `wealth − c`"，spec 漏改——已改。
4. **清算级联反例算术错误**（teach-back 第 1 轮**独立复算**命中）：`20000 / 2.5×` → `23000 / 2.875×`，并把"触发条件"改成与例一致的表述（高桶位移落进被计划的低桶）。
5. **小幅口径收敛**：`ChannelRecord` 的 `delta_mass` / `pool_after` / `cell` 注释、`Intent.op` 补入字段契约与子组件表、`stale` / `no_match` 划分（4 处统一为"解析失败 ⇒ stale；候选桶为空 ⇒ no_match"）、N2-4 折算 `marital` 口径、N2-5 配偶缺失分支的 `delta_mass`、N2-7 开关调用形态（`register_marriage_rule(rng=…)`，按 runner 现状）、不变量 5 的"规则自有流"例外、spec §9 折叠句补 `split`、core-code N2-1 的 `marital` 3 档声明。

## 3. teach-back（3 单元 × 独立 subagent；文件白名单制）

| 单元 | 判定范围 | 第 1 轮 | 第 2 轮 |
|---|---|---|---|
| L1（整份） | 决策级 | **通过**（16 条非阻断；「宽限期」缺词条已补） | —（无需） |
| 通道 L3（整份） | 实现级 | **不通过**：1 条 [阻断]（清算级联反例算术）+ 15 条非阻断 | **通过**（阻断项经其独立复算确认修复；已处理非阻断逐条到位；收口 3 条另采纳） |
| core-code L4（整份） | 实现级 | **不通过**：1 条 [阻断]（桶数 vs fixture 自相矛盾）+ 9 条非阻断 | **通过**（同法确认；收口 2 条另采纳） |

> **方法论实证**：两条 [阻断] 都不是"复述 / 缺口清单"命中的，而是新版验证者的**必做动作·独立复算**命中的（级联反例的算术；桶数与 `encode(30,0,10,0)` 的自洽）。这与 `verifying-n2` 新增的「契约断言通则：先跑一次，再写进契约」同向。
>
> **输入白名单**：skill 要求"只喂文档、不让验证者自己去仓库读"；因文档体量（200–900 行）×3 单元，本轮改为**文件白名单**（验证者只读显式列出的文件；禁读 `reviews/` `decisions/` `history` git 源码 tests）。两轮验证者均如实披露了检索越界（目录级 grep 带出边界外文件的行），均声明未用于判定。

## 4. 验收与门禁

| 项 | 结果 |
|---|---|
| `scripts/check-doc-refs.ps1`（新版，16 文档全扫） | **无结构性发现** |
| `scripts/check-docs-sync.ps1` | 静默（docs / L1 均有改动，符合预期） |
| `scripts/review-backlog.ps1` | 正常（自 `499b44e` 起；工作区未提交 ⇒ "无变化"） |
| `bash -n`（Git Bash，3 个 `.sh`） | 通过 |
| `python -m pytest` | **未跑**——本轮无代码改动（仅 docs / templates / scripts）；`docs-guard.yml` 在 PR 上会跑两个检查器 |

## 5. 判定与留档

- **结论**：三个单元均「通过」；无「需人拍板」的**文档缺陷**。
- **待拍板（作者已知、文档已显式声明；非本次缺陷）**：① 规则侧是否把大众（全局测度）纳入 `MarriageRule` 候选（N2-7 尾注）；② 是否做异性配对（跨 `gender` 桶取对，N2-5）。
- **后续（非决策级，已登记 L1「开放问题」段）**：E1「提示与证据不占正文」的全库清扫（`Stage N` / 过程叙事等）本轮未做。
- **`.last-review`**：已更新为本轮升级的提交 **`5441ca9`**（2026-10-18）——它是下一次 `review-backlog` 的起点。（建立时的初始基线为 `499b44e`。）
- **留档的 [非阻断]**（未逐一采纳，见 r2 报告的"作者留档"清单）：通道 `#11/#12/#14/#15/#16` 与 r2 的 `N1–N8` 未采纳项；core-code `#2/#3/#4/#5/#9` 与 r2 的 `新-2/3/5/6`；L1 的 16 条建议未采纳项。按「文档完成判据」第 1 条（复核判「通过」即停），不再继续堆改。
