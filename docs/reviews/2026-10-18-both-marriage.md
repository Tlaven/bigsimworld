# 2026-10-18 · `both` 形态落地与「一人一意图」守卫（ADR-012）

> 背景：ADR-009 把 `both` 推迟到"一人一意图"守卫就绪之后；本记录 = 守卫与 `both` 的实现、测试与启用态读数。
> 纪律：**默认关**（`SIM_CHANNEL_MARRIAGE` 缺省 `0`）；单规则路径零行为变化（守卫不触发）。

## 1. 实现

- **守卫（通道层）**：`bind` 且 `origin="character"` 时，执行前复检发起者婚配态 ⇒ `dropped:initiator_married`（不耗配额、不 reserve）。位置在两侧解析之后、配额闸之前。
- **注册名按目标侧区分**：`MarriageRule` 的 `name` 改为实例属性——`cross_marriage`（簇）/ `mass_marriage`（大众）；`both` 下两键可在 `RULES` 并存（同名注册会互相覆盖）。
- **独立派生流**：`both` 下两条规则各用 `channel-marriage:{seed}:cluster` / `:measure`；**单值模式沿用原种子串**（不扰动既有读数）。
- **开关与工具**：`SIM_CHANNEL_MARRIAGE=both`；`calibrate_marriage` / `channel_marriage` 增加 `--scope both`，crossings 按 scope 拆分（校准汇总表加"族 / 众"列）。

## 2. 测试

- `test_bind_rejects_married_initiator`（`tests/test_channel.py`）：同一发起者被簇侧与全局测度两条意图命中 ⇒ 恰一条 `ok`（簇侧，先处理）+ 一条 `dropped:initiator_married`；人头守恒。
- `test_both_targets_register_side_by_side`（`tests/test_rule_marriage.py`）：两键并存、名字按目标侧。
- `test_rule_is_not_registered_by_default` 扩展为两键都不在。
- `pytest`：**238 passed**。

## 3. 验收读数（2026-10-18）

**channel_marriage**（1200 pop / 240 cap / 3000 ticks / `--seed-family 50` / seed 7）

| scope | crossings（族 / 众） | married_frac | Δ vs off | 逐次 identity（人头 / 财富） |
| --- | --- | --- | --- | --- |
| cluster | 16（16 / 0） | 0.475 | +0.100 | 0 / 0 |
| measure | 18（0 / 18） | 0.477 | +0.102 | 0 / 1.49e-08 |
| **both** | 16（5 / 11） | 0.425 | +0.050 | 0 / 7.45e-09 |

- **守卫在实测中未触发**（两规则独立流下"同一人同 tick 被两条意图命中"的概率低）——该路径由**单测强制覆盖**（构造同发起者双意图）；实测不触发不削弱守卫价值。
- both 的族/众拆分随种子波动（单 seed 读数，不做跨臂强判读）；总 crossings 与单臂同量级——**窗口 headroom / `cap_per_tick` 是共享瓶颈**（both 的 `dropped:window` = 86，单臂 24–33）。
- 默认关 ⇒ 生产 / 权威数字不变；`audit_ledger --clusters` identity **0.0000%**。

**calibrate_marriage --scope both**（1200 / 240 / 2000 tick / 4 seeds / 1× / `--family-pool 50`）

| arm | married_frac(adults) | Δ vs ref | Δ vs null | crossings 均值（族 / 众） |
| --- | --- | --- | --- | --- |
| off | 0.5927 | +0.0310 | −0.0020 | 0 |
| null | 0.5947 | +0.0330 | 0 | 0 |
| 1.00× | 0.6141 | +0.0524 | **+0.0194** | 14.0（6.0 / 8.0） |

- 参照（个体引擎）= 0.5616。1× 的规则语义效应 +1.94pp（vs null）；headroom 效应 +0.20pp。
- 与 ADR-009 的"默认关"结论一致：both 只会把已婚比例推得更高（扩展语义，不设门槛）。

## 4. 边界 / 备注

- 同 tick 竞争**确定性偏向簇侧**（`scope_type` 簇=0 < 全局测度=2）；不做随机平局（省 rng、保确定性）。
- `both` 两条通量与窗口 headroom / `cap_per_tick` 共享；高 rate 下先触 `dropped:window`。
- `mass_marriage` 是新注册键：`RULES["cross_marriage"]` 只对应簇侧。
- 守卫覆盖范围 = `origin="character"` 的 `bind`；C→R / M→R 的窗口侧对手方由谓词在**选取时**实时过滤（无同 tick 竞态）——范围声明。
