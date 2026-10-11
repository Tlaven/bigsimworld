

character -> individual_event -> event_plaza -> people_event -> simulation_engine

## 运行演示（均值场 + 真个体窗口）

三种模式：
- `individual`：逐个体引擎（原始高保真模型）。
- `measure`：均值场（分布为主体，成本与人口无关，可顶千万级）+ 真个体窗口。
- 默认 `measure`。

```bash
# 1) 启动 Redis（Flask-SSE 需要）
redis-server

# 2) 后端（默认 measure 模式；SIM_MODE=individual 可切换）
python run.py

# 3) 前端
cd web && npm run dev
```

前端右侧抽屉与"角色信息"页会实时展示窗口内的**真个体**（姓名/性别/年龄/财富/好友/婚配），
数据经 SSE（`data` 事件，`payload.people`）推送。

性能：`python -m bench.convergence --window --sizes 10000 1000000 --capacity 1000 --steps 3000`


event_plaza: dict[str, list[character]]
event_plaza = {
    "acquaintance": [obj1, obj2, obj3],

}

```
SimuWorld
├─ app
│  ├─ api
│  │  └─ v1
│  ├─ core
│  │  ├─ generation
│  │  │  ├─ human.py
│  │  │  ├─ name.py
│  │  │  └─ __init__.py
│  │  ├─ person
│  │  │  ├─ character.py
│  │  │  ├─ events.py
│  │  │  └─ __init.py
│  │  ├─ probability
│  │  │  ├─ func.py
│  │  │  └─ __init__.py
│  │  └─ simulation
│  │     ├─ engine.py
│  │     ├─ events.py
│  │     ├─ later.py
│  │     └─ __init__.py
│  ├─ models
│  │  ├─ crud.py
│  │  ├─ table.py
│  │  └─ __init__.py
│  ├─ schemas
│  ├─ services
│  ├─ utils
│  └─ __init__.py
├─ README.md
├─ run.py
└─ web