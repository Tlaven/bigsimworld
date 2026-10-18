# 2026-10-18 · 攒批 teach-back（分辨率层契约增量）

> 铁律 9 的攒批复核：自锚点 `5441ca9` 以来的契约 delta（`scripts/review-backlog` 列出 5 个文件）。判的是"文档写没写清"，**不是**断言为真（事实类靠试跑 / 来源）。
> 输入边界（严格）：`docs/cluster-contract.md`（本体）+ `AGENTS.md`（上层约束）+ `docs/modules/interaction-channel.md` / `docs/engineering-spec.md` / `docs/glossary.md` / `docs/core-code.md`（显式指向的层）。未读 decisions / reviews / history / 源码 / tests / bench。

## 1. 范围与判定单元

- delta：`AGENTS.md`(2)、`docs/cluster-contract.md`(36)、`docs/engineering-spec.md`(9)、`docs/glossary.md`(3)、`docs/modules/interaction-channel.md`(24)。
- **大众婚配部分**（interaction-channel N2-7 增量 + spec / glossary / AGENTS 的配套句）已于同日**单独复核通过**（1 轮，4 条非阻断已采纳）——本单不重判。
- 本单判定单元 = **分辨率层增量**（`cluster-contract.md`：缝 2 注记 / §8 / §9 全节），判定范围 = **实现级**。

## 2. 判定：**通过**（0 条 [阻断]；10 条 [非阻断]）

验证者执行的关键动作：

- **独立推演 3 个场景**均**唯一可推**：a) 驻留下界的时序（`T0+20` 不动、`T0+30` 才可能动）；b) 整数语义下的桶演化与 `materialize` / `blocked` 判定（含"同桶 2.0 / 两桶各 1.0"的选人读法）；c) 信用在合并 / 快照 / 折入全局 × `coarsen` / `split` 的处置。
- **§9 六行逐行**核对"性质 × 仪器 × 边界"：自洽；与 L1 的守恒律 / 身份不守恒 / 分层门槛口径**无矛盾**（引用数字与 L1 更正版一致）。
- **未定义引用排查**：除"缺省关 / 未做 / 工具名"侧外，无空引用。

## 3. 非阻断清单与处置（全部收敛或登记）

| # | 发现 | 处置 |
| --- | --- | --- |
| G1 | `theta_up` / `theta_base` 两名一物；"反馈调阈值"与 spec "反馈调预算"冲突 | **已修**：缝 2 统一为 `theta_base`（固定 0.5）；点明 runner 反馈调 `budget_leaves`；补 MVP 预算竞争顺序（按注意力降序、超出降档） |
| G2 | 误差触发段写成规格语气；θ / 指示器 / 地板作用点未定义；"抬到 theta_base" 疑与宽限期教训冲突 | **已修（并纠一处误读）**：明确语义——抬到**升级阈值** ⇒ 按常规路径**被物化（升级）**（宽限期是"冻结"，此处物化正是目的）；写明相位离散度的更新口径；保留"候选、缺省关" |
| G3 | 整数语义的"满值 / 粒度 / 选人规则"未写死 | **已修**：单位 = 人份；满值婚配 2.0 / 死亡 1.0；婚配优先最大单身桶取 2.0（同态成对），否则两个整人单身桶各 1.0；死亡取最大整人 60+ 桶；确定性（count 降序 + 索引）；无整人挂起 |
| G4 | 信用无账行；`coarsen` / `split` 未写 | **已修**：§9 增"整数语义信用"行（发放器状态、非质量；coarsen/merge 求和、dissolve/split 作废、旧档按 0）；glossary 登记 |
| G5 | ρ 不在账表 | **已修**：§9 增"身份质量 ρ"行（观测账） |
| G6 | `bench.resolution_switch` / `telemetry()` 在允许层内证不到；`blocked` 归属不明 | **已修**：§9 行写字段名（`switches` / `blocked` / `dwell` / `risk`）；AGENTS 常用命令补 `bench.resolution_switch` |
| G7 | "换档"指称域含 merge/split/dissolve；驻留是否约束它们未写 | **已修**：明确"纪律只管 level 切换" |
| G8 | 新术语未登记；"回流体区"措辞 | **已修**：glossary 登记「整数语义（信用发放）」「换档纪律（驻留/滞回）」「误差触发（相位离散度）」；措辞改"折入全局测度"。「社会凝视 / 水位反馈」为锚点前遗留 → 记 backlog |
| G9 | row3"人均财富 = 统计近似"口径不明；`blocked` "≈0" vs "个位/窗" | **已修**：row3 注明"近似指跨臂/跨视点比较口径"；`blocked` 统一为"期望 ≈ 0，异常时按次计" |
| G10 | `allocate` 预算竞争顺序未定义（**既有空白**，早于锚点） | **已修（顺手）**：缝 2 补"按注意力降序分配、超出的簇降档"（MVP 顺序） |

## 4. 备注

- 验证者披露一处**工具卫生**问题：其 grep 曾越界看到 2–3 行允许层外内容（ADR 标题、bench README 行），**未用于判定**——不影响结论；记入下次派发的提醒（收紧 grep 模式）。
- 验证者未读 ADR（记录类不在输入边界）：默认值类决策的 ADR 落档不在本单判定范围。
- 事实类断言（工具存在性 / 读数）不在 teach-back 判定范围；本轮依赖的读数已在各自对账记录里。
- 遗留 backlog：glossary 补「社会凝视」「水位反馈」（锚点前术语，下次触碰 glossary 时一并登记）。

## 5. 锚点

复核完成于本轮修复提交；`.last-review` 已更新至该提交（同批）。
