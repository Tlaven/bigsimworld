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
另有：`REDIS_URL`（SSE 依赖，默认 `redis://localhost:6379/0`）、`SIM_DB_PATH`（SQLite 路径，
默认 `db.sqlite3`）、`CORS_ORIGINS`（允许来源，默认 `*`）、`SIM_SEED`（整数；设了即进入
**确定性模式**——固定整局随机并关闭墙钟负载反馈，同种子必然同发展）、`SIM_NOTABLE_FRACTION`
（显要分位，默认 `0.01` = 财富 top 1% 的个体被自动保护——不逐出、不粗化；`off` 关闭）。

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
| `docs/engineering-spec.md` | **规范**：模型语义、速率表、守恒律、SSE/控制 API 契约、分辨率与共演单元层 |
| `docs/cluster-contract.md` | 分辨率/共演单元层契约：数据模型、扩展缝、通用算子、不变量 |
| `docs/history.md` | 工程日志：个体→测度→分辨率三阶段演进的全部数字、负结果与教训 |
| `bench/README.md` | 基准工具用法与当前权威数字 |
| `web/README.md` | 前端（页面/SSE 契约/环境变量） |

## 测试与 CI

```bash
python -m pytest -q                   # 等价性/收敛门槛/守恒/契约
python -m coverage run -m pytest -q && python -m coverage report   # 含 80% 覆盖率门槛（fail_under）
ruff check . --exclude web            # 运行时缺陷级别检查（风格约束刻意不设）
cd web && pnpm build                  # 前端构建
```

GitHub Actions（`.github/workflows/ci.yml`）在 push/PR 时自动跑同样的事：后端（依赖安装 + ruff + pytest，
含 `bench.audit_ledger` 的小规模守恒门禁）与前端（`pnpm install --frozen-lockfile` + 构建）。
守恒审计的全尺寸版与收敛对比保持为本地测量工具（`bench/README.md`），不进 CI 时间预算。
