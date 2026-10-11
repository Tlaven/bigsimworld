# 无头基准测试与性能测量（Phase 1）实施计划

> **给自动化执行者：** 必读子技能：superpowers:subagent-driven-development 或 superpowers:executing-plans。按任务逐条执行，用 `- [ ]` 勾选跟踪进度。每个任务结束都提交一次。

**Goal：** 让仿真引擎能在**不依赖数据库 / 多进程 / Web** 的前提下被构造和运行，并产出一份可复现的"人口规模 → 每步耗时 / 内存"扩展性基线报告。

**Architecture：** 给 `SimulationEngine` 增加显式的角色注入入口 `load_characters()`，把"从 DB 加载角色"和"运行引擎"解耦；新增独立 `bench/` 包，用空队列 `SinkQueue` 顶替 DB 写入队列，直接驱动 `engine.step()`，用 `time.perf_counter` 计时、`psutil` 采样 RSS。

**Tech Stack：** Python 3.12、pytest 9、psutil 6、SQLAlchemy 2。不引入新依赖（环境已具备）。

**动机与约束：** 项目的核心目标是"世界能容纳更多个体、更长期地演化"，而当前每 tick 全量遍历人口的模型，其成本正比于人口，长期必然越来越慢。要优化必须先测量。**本计划只做测量，不改动仿真语义**（唯一例外是修正空数据库启动时的崩溃）。

---

## 背景：已确认的事实

- DB 路径已能创建角色：`create_characters_from_db()`（`app/core/simulation/engine.py:29`）。
- 空库会崩溃：`query(...).order_by(id.desc()).first().id` 在无数据时对 `None` 取 `.id`（`app/core/simulation/engine.py:32`）。
- `engine.step()`（`app/core/simulation/engine.py:75`）是纯计算，不含 sleep；sleep 在 `runner.step` 的 `time_limit` 装饰器里。
- `engine.create_character()` / `remove_character()` 会向 `insert_queue` / `update_queue` 调用 `.put()`（`app/core/simulation/engine.py:53,59`），因此 bench 只需提供带 `put` 的假队列。
- 环境：Python 3.12.4；pytest、psutil、numpy、matplotlib 均已安装。

---

## 文件结构

- 修改：`app/core/simulation/engine.py` —— 增加 `load_characters()`，修正空库 `max_id`。
- 新建：`bench/__init__.py`、`bench/sinks.py`、`bench/world.py`、`bench/measure.py`、`bench/run_scaling.py`、`bench/profile_step.py`、`bench/README.md`。
- 新建：`tests/test_engine_seed.py`、`tests/test_bench_engine.py`、`pytest.ini`。
- 产出：`bench/results/scaling.csv`（提交，作为基线快照）。

---

## Task 1：让引擎可从显式角色列表构建（修正空库崩溃）

**Files:**
- Modify: `app/core/simulation/engine.py:1-43`
- Test: `tests/test_engine_seed.py`

- [ ] **Step 1：写失败测试**

创建 `tests/test_engine_seed.py`：

```python
from app.core.simulation.engine import SimulationEngine


class _Sink:
    def __init__(self):
        self.count = 0

    def put(self, item):
        self.count += 1


def _queues():
    return {"insert": _Sink(), "update": _Sink(), "delete": _Sink()}


def _char_dict(age=30, wealth=10000, gender="male", xing="张", name="张三"):
    return {
        "name": name, "age": age, "gender": gender, "xing": xing,
        "wealth": wealth, "DOB": None, "relationships": {},
        "status": "active", "pedometer": {"step": 0, "step_threshold": 10},
        "relation_record": {},
    }


def test_load_characters_builds_without_db():
    chars = [dict(_char_dict(), id=i) for i in range(1, 6)]
    engine = SimulationEngine(_queues(), characters=chars)
    assert len(engine.characters) == 5
    assert engine.max_id == 5


def test_load_characters_assigns_missing_ids():
    chars = [_char_dict(), _char_dict()]
    engine = SimulationEngine(_queues(), characters=chars)
    assert sorted(engine.characters.keys()) == [1, 2]
```

- [ ] **Step 2：运行测试，确认失败**

Run: `python -m pytest tests/test_engine_seed.py -v`
Expected: FAIL（`TypeError: __init__() got an unexpected keyword argument 'characters'`）

- [ ] **Step 3：实现 `load_characters` 并重构 `create_characters_from_db`**

把 `app/core/simulation/engine.py` 的 `__init__` 与 `create_characters_from_db` 改为：

```python
from sqlalchemy import func

from app.models import crud
from app.core.person.character import Character
...

class SimulationEngine:
    def __init__(self, db_queues, characters=None):
        self.simulation_time = 0
        self.characters = {}
        self.event_plaza = {
            "acquaintance": [],
        }
        self.publish_list = []
        self.later_queue = LaterDeque()

        # 数据库修改进程的共享队列
        self.insert_queue = db_queues["insert"]
        self.update_queue = db_queues["update"]
        self.delete_queue = db_queues["delete"]

        if characters is None:
            self.create_characters_from_db()
        else:
            self.load_characters(characters)

    def load_characters(self, character_dicts):
        """从 dict 列表构建 Character（不经过数据库）。id 缺失时自动分配。"""
        self.characters = {}
        self.max_id = 0
        for character_dict in character_dicts:
            character_dict = dict(character_dict)
            cid = character_dict.get("id")
            if cid is None:
                cid = self.max_id + 1
                character_dict["id"] = cid
            self.max_id = max(self.max_id, cid)
            self.characters[cid] = Character(self, **character_dict)
        print(f"Created {len(self.characters)} characters.")
        for character in self.characters.values():
            character.init_relationships()

    def create_characters_from_db(self):
        with crud.get_session() as session:
            self.max_id = session.query(func.max(crud.Table.id)).scalar() or 0
            query = crud.get_characters(session, filters={"status": "active"})
            columns = crud.Table.__table__.columns.keys()
            rows = [dict(zip(columns, row)) for row in query]
        self.load_characters(rows)
```

保留 `create_character` / `remove_character` / `step` 等其余方法不变。

- [ ] **Step 4：运行测试，确认通过**

Run: `python -m pytest tests/test_engine_seed.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5：提交**

```bash
git add app/core/simulation/engine.py tests/test_engine_seed.py
git commit -m "refactor: injectable character loading for SimulationEngine"
```

---

## Task 2：bench 包 —— 假队列与世界构建

**Files:**
- Create: `bench/__init__.py`、`bench/sinks.py`、`bench/world.py`
- Test: `tests/test_bench_engine.py`

- [ ] **Step 1：写失败测试**

创建 `tests/test_bench_engine.py`：

```python
from bench.world import build_engine


def test_build_engine_population():
    engine = build_engine(50, seed=1)
    assert len(engine.characters) == 50
    assert engine.max_id == 50


def test_step_advances_time_and_is_stable():
    engine = build_engine(50, seed=1)
    for _ in range(20):
        engine.step()
    assert engine.simulation_time == 20
```

- [ ] **Step 2：运行测试，确认失败**

Run: `python -m pytest tests/test_bench_engine.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'bench'`）

- [ ] **Step 3：实现**

创建 `bench/__init__.py`（空文件）。

创建 `bench/sinks.py`：

```python
class SinkQueue:
    """空队列：让引擎在没有真实 DB 写入进程时也能运行。"""

    def __init__(self):
        self.count = 0

    def put(self, item):
        self.count += 1

    def get(self):
        raise IndexError("SinkQueue is empty")

    def empty(self):
        return True

    def qsize(self):
        return 0
```

创建 `bench/world.py`：

```python
import random

from app.core.generation.human import generate_character
from app.core.simulation.engine import SimulationEngine
from bench.sinks import SinkQueue


def make_sink_queues():
    return {"insert": SinkQueue(), "update": SinkQueue(), "delete": SinkQueue()}


def make_characters(n, seed=None, age_range=(0, 80)):
    if seed is not None:
        random.seed(seed)
    characters = []
    for i in range(1, n + 1):
        character = generate_character(
            age=random.randint(*age_range),
            wealth=random.gauss(10000, 1000),
        )
        character["id"] = i
        characters.append(character)
    return characters


def build_engine(n, seed=None, age_range=(0, 80)):
    return SimulationEngine(
        make_sink_queues(),
        characters=make_characters(n, seed=seed, age_range=age_range),
    )
```

- [ ] **Step 4：运行测试，确认通过**

Run: `python -m pytest tests/test_bench_engine.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5：提交**

```bash
git add bench/__init__.py bench/sinks.py bench/world.py tests/test_bench_engine.py
git commit -m "feat(bench): sink queues and headless world builder"
```

---

## Task 3：单次运行测量函数

**Files:**
- Create: `bench/measure.py`
- Modify: `tests/test_bench_engine.py`（追加一个测试）

- [ ] **Step 1：追加失败测试**

在 `tests/test_bench_engine.py` 末尾追加：

```python
from bench.measure import measure_steps


def test_measure_returns_per_step_durations():
    engine = build_engine(30, seed=2)
    result = measure_steps(engine, 10)
    assert len(result["durations"]) == 10
    assert result["avg"] > 0
    assert result["population"] >= 30
```

- [ ] **Step 2：运行测试，确认失败**

Run: `python -m pytest tests/test_bench_engine.py::test_measure_returns_per_step_durations -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'bench.measure'`）

- [ ] **Step 3：实现**

创建 `bench/measure.py`：

```python
import statistics
import time

import psutil


def measure_steps(engine, steps):
    """逐步驱动 engine，返回每步耗时与内存统计（单位：毫秒 / MB）。"""
    process = psutil.Process()
    rss_before = process.memory_info().rss
    durations = []
    for _ in range(steps):
        start = time.perf_counter()
        engine.step()
        durations.append(time.perf_counter() - start)
    rss_after = process.memory_info().rss

    ms = [d * 1000 for d in durations]
    return {
        "steps": steps,
        "durations": durations,
        "avg": statistics.fmean(durations),
        "p50": statistics.median(durations),
        "p95": statistics.quantiles(durations, n=20)[18] if len(durations) >= 20 else max(durations),
        "max": max(durations),
        "rss_delta_mb": (rss_after - rss_before) / 1024 / 1024,
        "rss_mb": rss_after / 1024 / 1024,
        "population": len(engine.characters),
        "ms": ms,
    }


def summarize(result):
    return {
        "avg_ms": round(result["avg"] * 1000, 3),
        "p50_ms": round(result["p50"] * 1000, 3),
        "p95_ms": round(result["p95"] * 1000, 3),
        "max_ms": round(result["max"] * 1000, 3),
        "rss_mb": round(result["rss_mb"], 2),
        "population": result["population"],
    }
```

- [ ] **Step 4：运行测试，确认通过**

Run: `python -m pytest tests/test_bench_engine.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5：提交**

```bash
git add bench/measure.py tests/test_bench_engine.py
git commit -m "feat(bench): per-step timing and memory measurement"
```

---

## Task 4：扩展性扫描 CLI + CSV 输出

**Files:**
- Create: `bench/run_scaling.py`

- [ ] **Step 1：手动冒烟（先确认能跑）**

运行前先不写测试，直接实现后跑一次小规模确认输出。创建 `bench/run_scaling.py`：

```python
import argparse
import csv
import os

from bench.measure import measure_steps, summarize
from bench.world import build_engine


def main():
    parser = argparse.ArgumentParser(description="Headless scaling benchmark")
    parser.add_argument("--sizes", type=int, nargs="+", default=[1000, 2000, 5000, 10000])
    parser.add_argument("--steps", type=int, default=30)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default="bench/results/scaling.csv")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    rows = []
    header = ["n", "steps", "avg_ms", "p50_ms", "p95_ms", "max_ms", "rss_mb", "population_after"]
    print(f"{'N':>8} {'avg_ms':>10} {'p50_ms':>10} {'p95_ms':>10} {'rss_MB':>10} {'pop':>8}")
    for n in args.sizes:
        engine = build_engine(n, seed=args.seed)
        if args.warmup:
            measure_steps(engine, args.warmup)
        result = measure_steps(engine, args.steps)
        summary = summarize(result)
        row = {"n": n, "steps": args.steps, **summary,
               "population_after": summary["population"]}
        rows.append(row)
        print(f"{n:>8} {summary['avg_ms']:>10.3f} {summary['p50_ms']:>10.3f} "
              f"{summary['p95_ms']:>10.3f} {summary['rss_mb']:>10.2f} {summary['population']:>8}")

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row[key] for key in header})
    print(f"\nSaved to {args.out}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2：运行小规模冒烟**

Run: `python -m bench.run_scaling --sizes 500 1000 --steps 10`
Expected: 打印两行表格，并在 `bench/results/scaling.csv` 写入 2 行数据。

- [ ] **Step 3：提交**

```bash
git add bench/run_scaling.py
git commit -m "feat(bench): scaling sweep CLI with CSV output"
```

---

## Task 5：热点分析脚本（cProfile）

**Files:**
- Create: `bench/profile_step.py`

- [ ] **Step 1：实现**

创建 `bench/profile_step.py`：

```python
import argparse
import cProfile
import pstats

from bench.world import build_engine


def main():
    parser = argparse.ArgumentParser(description="Profile engine.step hotspots")
    parser.add_argument("--n", type=int, default=10000)
    parser.add_argument("--steps", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args()

    engine = build_engine(args.n, seed=args.seed)
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(args.steps):
        engine.step()
    profiler.disable()

    stats = pstats.Stats(profiler).sort_stats("cumulative")
    stats.print_stats(args.top)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2：运行**

Run: `python -m bench.profile_step --n 10000 --steps 30 --top 15`
Expected: 打印按累计耗时排序的函数表（出现 `possible_events`、`change_attribute`、`random`、`move_temp_set` 等）。

- [ ] **Step 3：提交**

```bash
git add bench/profile_step.py
git commit -m "feat(bench): cProfile hotspot script"
```

---

## Task 6：跑基线并留存结果

- [ ] **Step 1：跑正式基线**

Run: `python -m bench.run_scaling --sizes 1000 2000 5000 10000 20000 --steps 30 --warmup 5 --seed 42`
Expected: 输出 5 行表格，`bench/results/scaling.csv` 更新。

- [ ] **Step 2：跑一次热点分析并保存**

Run: `python -m bench.profile_step --n 10000 --steps 30 --top 20 > bench/results/profile_n10000.txt`
Expected: 生成 `bench/results/profile_n10000.txt`。

- [ ] **Step 3：写 `bench/README.md`**

内容需包含：每个脚本的用途、运行命令、如何解读 `avg_ms` 随 `n` 的变化（是否线性）、以及 Phase 2 的接口约定。

- [ ] **Step 4：提交**

```bash
git add bench/README.md bench/results/
git commit -m "docs(bench): baseline scaling results and usage guide"
```

---

## 验收标准（Definition of Done）

- `python -m pytest -v` 全绿。
- `python -m bench.run_scaling` 一条命令即可产出扩展曲线，且**不需要** Redis / Web / DB 写入进程。
- `bench/results/scaling.csv` 已提交，包含 `1000..20000` 的基线数据。
- 能明确回答：**每步耗时随人口是线性、亚线性还是超线性增长？**（这是选择后续优化路线的唯一依据。）

---

## 后续阶段路线（本计划不实现，供下一份计划参考）

- **Phase 2 · 时间模型**：全局同步 tick → 离散事件调度（每个体的 `next_event_time` + heapq）；年龄/收入惰性求值。目标：成本 ∝ 事件数，而非人口。
- **Phase 3 · 交互局部化**：`event_plaza` 全局洗牌 → 局部邻域 / 空间索引抽样，去掉 O(n) shuffle。
- **Phase 4 · 数据布局**：对象图 → 数组（SoA）+ CSR 邻接；冷热分层、死者归档出内存。
- **Phase 5 · 并行/下沉**：在交互局部化之后做域分解多进程；仍然不够则把热循环下沉到 numpy / Cython / Rust。

> 原则：先用本计划的测量确定瓶颈，再决定投入哪个 Phase。不要跳过测量直接优化。
