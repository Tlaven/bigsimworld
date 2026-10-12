# SimuWorld —— 可承载近乎无限人口的社会仿真

个体的完整生命周期（结识 → 熟络 → 结友 → 婚配 → 生育 → 死亡 → 继承），
通过"**测度引擎 + 真个体窗口**"的分层架构在**成本与人口 N 无关**的前提下推到千万级。

```
个体引擎（高保真参照，SIM_MODE=individual）
        ↑ 收敛验证（bench/：指纹 + 年龄L1/基尼/分位对比）
测度引擎（状态空间上的稀疏计数分布，每 tick 施加流算子，成本 = O(占用桶数)）
        ↕ 守恒同步（materialize / dematerialize，Σ测度 + len(窗口) 守恒）
物化窗口（≤ capacity 个带真实关系图的 Character）
        ↓
观测（SSE 实时推送）/ 持久化（快照）/ 控制（/api/v1/simulation start|stop|status）
```

## 快速开始

```bash
# 1) Redis（SSE 依赖）
redis-server

# 2) 后端（默认 measure 模式：均值场 + 真个体窗口）
python run.py            # http://localhost:5000

# 3) 前端
cd web && pnpm install && pnpm dev   # http://localhost:3000
```

环境变量：`SIM_MODE`（measure|individual）、`SIM_CAPACITY`（窗口大小，默认 1000）、
`SIM_POPULATION`（初始人口，默认 5000）、`SIM_RESUME=1`（从最新快照续跑世界；
`simulation/stop` 会自动落档，重启即续）。

## Web 接口

| 路由 | 说明 |
| --- | --- |
| `GET  /api/v1/simulation` | 运行状态（running/mode/simulation_time/population） |
| `POST /api/v1/simulation/start` | 启动仿真（引擎状态原地保留，可反复启停） |
| `POST /api/v1/simulation/stop` | 停止仿真（measure 模式自动落一份测度快照） |
| `GET  /api/v1/get-client-id` | 建 SSE 订阅 |
| `POST /api/v1/notify-connection` | connect 补发初始数据 / keepalive 保活 |
| `GET  /stream?channel=<id>` | SSE：`data` 每 tick 推送（time/population/simulation_load/people/age/wealth）、`initial_data` |

前端页面：`/world-overview`（默认，总览+负载曲线）、`/distribution-statistics`（年龄/财富分布）、
`/role-information`（窗口内真个体）。

## 基准与验证（bench/）

```bash
python -m bench.convergence --window --sizes 10000 1000000 --capacity 1000 --steps 3000
python -m bench.convergence --full-compare --sizes 2000 5000 10000 --steps 4000
python -m bench.run_scaling --engine legacy --sizes 1000 2000 5000 10000 20000 --steps 30 --warmup 5
```

详见 `bench/README.md`：逐阶段实测记录（DES 1.1–1.2×、局部化 5%、测度引擎人口 1000× 而单步恒定 ~2.5ms）。

## 文档地图

| 文档 | 内容 |
| --- | --- |
| `docs/engineering-spec.md` | **规范**：模型语义、速率表、守恒律、SSE/控制 API 契约 |
| `docs/history.md` | 工程日志：两阶段演进的全部数字、负结果与教训 |
| `bench/README.md` | 基准工具用法与当前权威数字 |
| `web/README.md` | 前端（页面/SSE 契约/环境变量） |

## 测试

```bash
python -m pytest -q      # 58 条：等价性/收敛门槛/守恒/契约
cd web && pnpm build     # 前端构建
```
