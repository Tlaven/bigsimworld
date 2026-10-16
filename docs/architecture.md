# Architecture — L2 架构层（SimuWorld）

> **本层只放指针 + 决策 + 不变量**（遵循 E1 指针优先，避免与既有文档重复事实）。
> 事实细节的唯一定义处：**[`docs/engineering-spec.md`](engineering-spec.md)**（模型语义 / 速率 / 守恒律 / API 契约）。
> 三段式：[是什么] / [为什么] / [不变量]。

## [是什么] — 模块清单

| 模块 | 位置 | 定位 |
|---|---|---|
| 个体引擎（**语义真值**） | `app/core/simulation/{engine,event_engine}.py` | 逐个体高保真参照（`SIM_MODE=individual`，O(N)，非生产路径） |
| 测度引擎（生产） | `app/core/measure/{engine,measure,space,transitions}.py` | 状态空间稀疏计数 + 流算子，成本 = O(占用桶数) |
| 物化窗口 | `app/core/measure/window.py` | ≤ `capacity` 个真 `Character`（真实关系图），与测度守恒交换 |
| 分辨率层 | `app/core/measure/cluster.py` | 共演单元 / 注意力 / 水位线调度 / 显要保护 |
| 驱动 | `app/core/simulation/runner.py` | 1s/tick 推进、start/stop、SSE 推送 |
| 观测 / 控制 API | `app/api/v1/`、`app/models/` | simulation / resolution / attention / life / SSE / snapshot |
| 前端 | `web/`（Vue 3 + Vuetify 3） | 总览 / 分布统计 / 角色信息 / 分辨率页 |
| 基准与验证 | `bench/` | 收敛对比、守恒审计、N 无关性（无 Web/DB 依赖） |

（模块清单以 `docs/engineering-spec.md` §1 与 `bench/README.md` 为准。）

## [是什么] — 模块间关系（数据流）

```
individual(参照) ──► 个体引擎(O(N))            语义真值
                         ▲ 收敛验证(bench.convergence --full-compare)
measure(生产)    ──► 测度引擎(O(占用桶))  ◄────►  物化窗口(≤capacity)
                         ▲ 守恒交换(materialize / dematerialize)
                         └ 分辨率层(共演单元 resolved ↔ coarse)
                              │
                    观测(SSE) / 持久化(snapshot) / 控制(API)
```

## [是什么] — 主流程叙述（一 tick）

1. `SimulationRunner` 每 1s 触发一步（`time_limit(1)`），可反复 start/stop（状态原地保留）。
2. `WindowEngine.step`：先跑**测度层流算子**（衰老→收入→死亡→婚配→生育→继承），再让窗口内 `Character` 逐个演化个体事件。
3. 两层经 `materialize` / `dematerialize` 交换成员，维持 `Σ measure.counts + Σ_coarse size + len(window.characters) == 初始 + 出生 − 死亡`。
4. 分辨率层 `ResolutionManager.step`：周期 `_reconcile` 组建共演单元 → 注意力（外生 pin + 内生社会凝视 + 衰减）→ 水位线分配 → `resolved`/`coarse` 切换。
5. 结果经 SSE 推送（分布 + 具名个体 + `resolution`/`notables`）；`simulation/stop` 落快照，`SIM_RESUME=1` 恢复。

（逐步语义详见 `docs/engineering-spec.md`。）

## [为什么] — 架构决策

- **为什么"换层"**：在个体引擎上的一切优化（DES / 稀有事件降频 / 空间局部化）都**没突破 O(人口)** → 换层为"分布为主体 + 有限真个体窗口"。完整负结果见 `docs/history.md` 第一章；决策见 [`decisions/adr-001-resolution-layer.md`](decisions/adr-001-resolution-layer.md)。
- **为什么"机制通用、策略可插拔"**、为什么"默认态是匿名"、被拒方案清单见 L1 `AGENTS.md`「设计哲学」与 `docs/history.md`。
- 关键决策记录在 [`docs/decisions/`](decisions/README.md)（ADR）。

## [不变量] — 架构级约束

> 全量见 L1 [`AGENTS.md`](../AGENTS.md)「项目级约束」。架构级要点：

- **依赖方向**：`app/` 为核心；`bench/`、`tests/`、`web/` 依赖 `app/`，**反向禁止**（`bench/` 无 Web/DB 依赖）。
- **无环**：请求侧 `api → runner → engine → measure`，无回指。
- **量守恒**：`Σ measure.counts + Σ_coarse size + len(window.characters) == 初始 + 出生 − 死亡`；分辨率算子**计数中性**。验证：`tests/` + `bench.audit_ledger`（+ `--resolution`）。
- **成本与 N 无关**：测度层一切成本 = O(占用桶数)。验证：`bench.convergence --window`。
- **确定性可复现**：设 `SIM_SEED` 时同种子同发展。验证：`tests/`（可复现性）。
