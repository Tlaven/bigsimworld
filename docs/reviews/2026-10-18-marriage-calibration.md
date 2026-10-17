# 校准对账：跨分辨率婚配规则（ADR-007 跟进项）

- **对象**：`MarriageRule`（ADR-007 / L3 N2-7）的通量强度与"要不要开"
- **工具**：`python -m bench.calibrate_marriage`（本次新增）
- **配置**：N=1200、capacity=240、ticks=2000、seeds={1,2,3,4}；参照 = `EventEngine`（个体引擎）
- **口径**：**成年人**（`18 ≤ age < 60`）已婚比例；measure 臂 = 全局测度 + 各簇 mini + 窗口角色 **合并统计**
- **结论**：**效应小且有饱和；真正的瓶颈是"可达性"不是 rate；默认保持关**。另发现两个必须排掉的 A/B 混淆项。

## 1. 两个混淆项（先修测量，再谈数字）

### ① 共流扰动（已修：规则改用自有随机流）

第一版实验里，规则与窗口共用 `window.rng`。结果：**四档 rate 给出完全相同的**
`married_frac(adults) = 0.5623`（off 为 0.5432），而 crossings 全是 0
——那 +0.019 与 rate 无关，是"开关规则改变了窗口个体事件的随机流"。

修法：`MarriageRule(rate, rng=…)` 用**自有确定性流**（runner 由 `SIM_SEED` 派生
`random.Random(f"channel-marriage:{seed}")`）。修复后，`rate=0 + 自有流` 与
`同为 emits_bind 的 null 规则` 逐位一致（测试 `test_own_rng_does_not_perturb_window_stream`）。

### ② `headroom_reserve` 常驻（用 null 臂对齐）

只要 `RULES` 里存在会 `bind` 的规则，`_refill` 就永久少留 `cap_per_tick = 8` 个窗口名额
——**即使规则一个意图都不发**。实测"只注册、不发意图"的偏移（`null − off`）：
无合成族时 **+0.0100**、有合成族时 **+0.0031**（与窗口占用敏感度有关）。

修法（测量层）：校准必须带一个 **null 臂**（`emits_bind=True`、`offers → []`）。
"开启规则"的真实效应 = `on − null`；"占名额"的效应 = `null − off`。

> 这两条是**方法学**结论：只要"开一条规则"会同时改变**随机流**与**窗口名额**，
> 任何 off/on 对比都不是受控实验——先隔离，再读数。

## 2. 受控读数

### 生产样态（无合成族，`--family-pool 0`）

| arm | married_frac(adults) | crossings |
| --- | ---: | ---: |
| 参照（个体引擎） | 0.5616 | — |
| off（生产口径） | 0.5503 | 0 |
| null（占名额不发意图） | 0.5603 | 0 |
| 0.25×–2× `MARRIAGE_RATE` | 0.5603（= null） | **0** |

**规则一次都没触发**：生产世界里大多数单身在**全局测度**里，而 `scope` 只支持 coarse **簇**。
coarse 族多为"已婚+子女"结构，几乎没有 18–59 未婚桶 ⇒ 房源权重恒 0 ⇒ `offers → []`。

### 合成房态（`--family-pool 200`，给规则一个"族内单身池"）

| arm | married_frac(adults) | Δ vs null | crossings |
| --- | ---: | ---: | ---: |
| off | 0.6003 | −0.0031 | 0 |
| null | 0.6034 | 0 | 0 |
| 0.25× | 0.6061 | **+0.0027** | 5.5 |
| 0.50× | 0.6069 | **+0.0035** | 8.2 |
| 1.00× | 0.6197 | **+0.0163** | 9.0 |
| 2.00× | 0.6212 | **+0.0177** | 13.8 |

（crossings 为 4 seed 均值；合成 pool 会让 measure 臂整体高于参照，故只看 `Δ vs null` 列。）

- **效应小且有饱和**：0.5×→1× 跳一档（+0.0035 → +0.0163，可能受 crossings 9 vs 8 的噪声影响），
  1×→2× 只再 +0.001（crossings 9 → 14 也没带来更多已婚比例）。
- 所以"调 rate"的边际价值很低；**调不出量级**。

## 3. 结论与决定

1. **默认保持关**（`SIM_CHANNEL_MARRIAGE` 缺省 0）。关规则时 measure 合并已婚比例与个体参照
   差 **−0.011**（4 seed 均值；规模同 1200）——这不是本规则能修的，也不该由它修。
2. **开启 = 共演化演示**：在"族内单身池"存在时，1× 约 +1.6pp 成年已婚比例；
   生产样态下**几乎为零**（crossings=0）。
3. **下一步不是校准 rate，而是扩通道**：让 `bind` 能寻址**全局测度**（匿名大众）。
   那才是"窗口单身 ↔ 匿名大众"的正路；属**通道扩展**（新 `scope` 类型），需要独立 ADR。
4. **方案 C（挤占窗口概率保总风险）暂不做**：在一个几乎不发生的通量上做"总风险守恒"没有意义。

## 4. 复现

```bash
# 生产样态：规则无可达房源 ⇒ crossings = 0
python -m bench.calibrate_marriage --population 1200 --capacity 240 --ticks 2000 \
    --family-pool 0 --seeds 1 2 3 4

# 合成房态：测规则的真实通量（看 Δ vs null 列）
python -m bench.calibrate_marriage --population 1200 --capacity 240 --ticks 2000 \
    --family-pool 200 --seeds 1 2 3 4
```
