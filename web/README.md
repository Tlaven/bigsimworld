# SimuWorld Web

Vue 3 + Vuetify 3 观测前端：世界总览 / 分布统计 / 角色信息三个页面，数据全部经 SSE（`/stream`）实时推送。

## 开发

```bash
pnpm install
pnpm dev      # 端口 3000；后端默认为 http://localhost:5000（见 .env.development）
```

## 构建

```bash
pnpm build    # 产物在 dist/
```

## 环境变量

- `.env.development`：`VITE_API_BASE_URL=http://localhost:5000`
- `.env.production`：部署地址

## 页面

| 路由 | 内容 |
| --- | --- |
| `/world-overview` | 世界时间、总人口、连接状态、单步耗时曲线（默认跳转） |
| `/distribution-statistics` | 年龄 / 财富分布（来自测度层 survey） |
| `/role-information` | 物化窗口内的真个体（姓名/性别/年龄/财富/好友/婚配） |
| `/resolution` | 显名者 / 团 / 注意度（θ/预算/ρ）+ 个体生命轨迹；pin/放掉 |

## SSE 契约

- 事件类型：`data`（每 tick 推送）、`initial_data`（连接建立后补发分布）。
- `data` payload：`time`（世界时间）、`population`、`simulation_load`（每步引擎耗时，秒）、
  `people`（具名个体：`{id,name,gender,age,wealth,relationships{friend,spouse,parent,child}}`）、
  `age` / `wealth`（分布 `[labels, counts]`）、`resolution`（`theta_base`/`budget_leaves`/`rho`/`cluster_count`/`resolved_count`/`clusters[]`）、
  `notables`（显名者：`{id,name,age,wealth,cluster_id,attention,notable}`；`notable=true` 为
  财富高位分位、被系统保护的显要个体，`cluster_id` 为 null 表示未入团）。
- 断线自动重连（指数退避，上限 10s）；页面关闭时 `sendBeacon` 退订。

## 分辨率/注意度接口

- `GET /api/v1/resolution`：分辨率摘要。
- `GET/POST /api/v1/attention`：`POST {person_id|cluster_id, value}` 置注意度（pin=1 / 放掉=0）。
- `GET /api/v1/life/<person_id>`：个体生命轨迹 `[{tick,age,wealth,friends,spouses}]`。
