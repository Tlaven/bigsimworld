# ADR-012: `both` 形态（簇 + 大众婚配并存）与通道级「一人一意图」守卫

## 状态
accepted（2026-10-18）

## 背景

ADR-009 采纳大众婚配时把「`cluster` + `measure` 并存」列为**方案 C 推迟**，条件 = 「一人一意图」守卫：通道执行 `bind` 时不复检发起者婚配态、去重键含 `scope` ⇒ 同一 tick 两条不同 `scope` 的意图会让**同一人被嫁两次**。本 ADR 解除该条件。

## 考虑过的方案

- **方案 A（采纳）通道级守卫 + 三值开关**：`bind` 且 `origin="character"` 时，执行前复检发起者婚配态（`relationships["spouse"]` 非空 ⇒ `dropped:initiator_married`，不耗配额、不 reserve）；`SIM_CHANNEL_MARRIAGE` 增加 `both`（同时注册 `target="cluster"` 与 `target="measure"` 两条规则）。
- **方案 B（拒）无守卫直接双规则**：同一人被嫁两次（ADR-009 已记录），破坏"一个窗口个体每 tick 至多成婚一次"。
- **方案 C（拒）随机平局**（两条意图竞争同一发起者时掷骰）：需额外消耗 rng、且"谁先"不可预测——与确定性纪律相悖；采用**确定性处理序**（通道排序键 `scope_type`：cluster=0 < measure=2 ⇒ 同 tick 内簇侧先于全局测度）。
- **方案 D（拒）通道级 tick 锁**（每 tick 每个 initiator 只允许一条意图入场）：会错误拒绝同一人两条不同 `kind`/`op` 的合法意图（如未来规则同一 tick 既 `bind` 又 `transfer`）；守卫只约束"婚配态"这个具体前提。

## 选择

方案 A。要点：

1. 守卫只覆盖 `origin="character"` 的 `bind`；C→R / M→R 的窗口侧对手方在**选取时**由谓词实时过滤（无同 tick 竞态）——登记为范围声明。
2. 规则注册名按目标侧区分（`cross_marriage` / `mass_marriage`）：同名注册会互相覆盖，`both` 需要两键并存。
3. `both` 下两条规则各用**独立派生随机流**（`channel-marriage:{seed}:cluster` / `:measure`）；单值模式沿用原种子串（不扰动既有读数）。
4. 默认关（缺省 `0`，`RULES` 空）；启用语义照旧 = **新增婚配通量、非近似**（ADR-007 / ADR-009）。

## 后果

- **正面**：共演形态"真实共演化"（窗口个体既可嫁入族、也可嫁入匿名大众）；通道获得一条通用安全不变量（未来任何多规则组合都受保护）。
- **负面 / 边界**：`both` 下两条通量叠加，已婚比例进一步抬高（预期，属扩展语义，不设门槛）；同 tick 竞争**偏向簇侧**（确定性使然）；`cap_per_tick` 由两类意图共享；`mass_marriage` 是新注册键（按 `RULES["cross_marriage"]` 找大众规则会落空——文档/术语表已同步）。
- **验收**：通道守卫单测（同发起者两条意图 ⇒ 一 `ok` + 一 `dropped:initiator_married`）；`channel_marriage --scope both` 逐次人头/财富守恒（浮点级）；启用态读数进对账记录。
