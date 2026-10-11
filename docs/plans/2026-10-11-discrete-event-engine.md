# 离散事件引擎（Phase 2）实施计划

> **给自动化执行者：** 按任务逐条执行，用 `- [ ]` 勾选。每个任务结束提交一次。

**Goal：** 用一个**离散事件调度**引擎替换"每 tick 全量遍历所有角色"的驱动方式：只处理"到点的"事件，把每 tick 成本从 `O(人口)` 降到 `O(当 tick 到期事件数)`，同时**尽量逐位复现原引擎的行为**（同一随机种子下轨迹一致）。

**Architecture：** 复用现有 `Character` 与事件类（`IndividualEvents` / `PeopleEvents` / `Marry` / `Childbirth` / `Death`）——**只换驱动器**。新引擎 `EventEngine` 维护一个最小堆 `(time, seq, priority, counter, payload)`：
- 每个角色按自身相位调度三类周期事件：`AGE`（周期 360）、`WEALTH`（周期 30）、`LIFE`（周期 `step_threshold`）。
- 事件按 `(time, 角色插入序, 优先级)` 排序，从**角色优先**维度复现原引擎"逐角色先变更属性、再判定事件"的顺序，从而保持随机数调用顺序一致。
- `event_plaza` 配对（`PeopleEvents`）用"惰性广场事件"复现原引擎"每 tick 只要广场 >1 就配对"的行为。

**Tech Stack：** Python 3.12、`heapq`。无新依赖。

**关键依据（来自 Phase 1 基线）：** 原引擎每 tick 全量扫描（`Character.step` 每 tick 调用 N 次），每 10 tick 里 1 次是重事件步；DES 只保留"到期"处理。

---

## 复现依据（为什么能逐位复现）

- 三类周期（10 / 30 / 360）共用同一相位：原 `change_attribute` 每 tick `step += 1`，故角色在全局时间 `t` 的个人步数 = `base + (t - spawn)`，其中 `base` 为加载时的 `pedometer['step']`。事件发生在 `(base + elapsed) % period == 0` 的 tick。
- 30、360 均为 10 的倍数，因此属性边界 tick 一定落在"生命事件 tick"上，独立调度不会漏。
- `round_up_probability`、`move_temp_set`、`random.shuffle` 等随机调用只出现在 `possible_events` / 广场配对里；属性变更无随机。故只要 `possible_events` 的**集合与顺序**一致，随机流即一致。

---

## 文件结构

- 新建：`app/core/simulation/event_engine.py`（`EventEngine`）。
- 修改：`bench/world.py`（`build_engine(..., engine="legacy"|"event")`）。
- 修改：`bench/run_scaling.py`（`--engine` 参数）。
- 新建测试：`tests/test_event_engine.py`。
- 产出：更新 `bench/results/`、`bench/README.md`。

---

## Task 1：EventEngine 骨架与角色调度

**Files:** Create `app/core/simulation/event_engine.py`; Test `tests/test_event_engine.py`

- [ ] **Step 1：写失败测试**

```python
from app.core.simulation.event_engine import EventEngine
from bench.world import make_characters, make_sink_queues


def test_event_engine_builds_without_db():
    chars = make_characters(100, seed=1)
    engine = EventEngine(make_sink_queues(), characters=chars)
    assert len(engine.characters) == 100
    assert engine.max_id == 100


def test_event_engine_time_advances():
    chars = make_characters(50, seed=1)
    engine = EventEngine(make_sink_queues(), characters=chars)
    for _ in range(37):
        engine.step()
    assert engine.simulation_time == 37
```

- [ ] **Step 2：运行确认失败** `python -m pytest tests/test_event_engine.py -v` → FAIL(ModuleNotFoundError)

- [ ] **Step 3：实现**（见对话中完整代码：`EventEngine`，含 `load_characters`、`_schedule_character`、`_push`、`step`、`_run_until`、`_ensure_plaza`、`create_character`、`remove_character`、`create_characters_from_db`、`_update_utc`；常量 `AGE=0, WEALTH=1, LIFE=2, PLZ=3`）

- [ ] **Step 4：运行确认通过** `python -m pytest tests/test_event_engine.py -v` → PASS

- [ ] **Step 5：提交** `git commit -m "feat(sim): discrete-event engine skeleton"`

---

## Task 2：与原引擎逐位一致性测试

**Files:** Modify `tests/test_event_engine.py`

- [ ] **Step 1：写一致性测试**

```python
import copy
import random

from app.core.simulation.engine import SimulationEngine
from app.core.simulation.event_engine import EventEngine
from bench.world import make_characters, make_sink_queues


def _run(engine, steps, seed):
    random.seed(seed)
    for _ in range(steps):
        engine.step()
    return (
        engine.simulation_time,
        len(engine.characters),
        sum(c.age for c in engine.characters.values()),
        sum(c.wealth for c in engine.characters.values()),
        sum(len(c.relationships["friend"]) for c in engine.characters.values()),
    )


def test_event_engine_matches_legacy():
    chars = make_characters(200, seed=7)
    legacy = SimulationEngine(make_sink_queues(), characters=copy.deepcopy(chars))
    event = EventEngine(make_sink_queues(), characters=copy.deepcopy(chars))
    assert _run(legacy, 300, 999) == _run(event, 300, 999)
```

- [ ] **Step 2：运行** `python -m pytest tests/test_event_engine.py::test_event_engine_matches_legacy -v`
  - 若 PASS → 逐位一致，完成。
  - 若 FAIL → 记录差异字段，调 `EventEngine` 的事件顺序/相位；**最多允许分歧为"统计等价"**，此时把断言改成容差比较并在 README 说明偏差原因（不得默默放宽）。

- [ ] **Step 3：提交** `git commit -m "test(sim): event engine matches legacy trajectory"`

---

## Task 3：基准接入与对照测量

**Files:** Modify `bench/world.py`、`bench/run_scaling.py`

- [ ] **Step 1：`build_engine` 增加 `engine` 参数**（默认 `"legacy"`，`"event"` 用 `EventEngine`）。

- [ ] **Step 2：`run_scaling` 增加 `--engine` 并透传。**

- [ ] **Step 3：跑对照**

```
python -m bench.run_scaling --engine legacy --sizes 1000 5000 10000 20000 --steps 30 --out bench/results/scaling_legacy.csv
python -m bench.run_scaling --engine event  --sizes 1000 5000 10000 20000 --steps 30 --out bench/results/scaling_event.csv
```

- [ ] **Step 4：提交** `git commit -m "feat(bench): head-to-head legacy vs event engine"`

---

## Task 4：更新结论

- [ ] **Step 1：更新 `bench/README.md`**：加对照表与解读（p50 是否被抹平、avg 提速倍数、人均耗时是否下降、仍为 O(人口) 的原因与 Phase 3 方向）。
- [ ] **Step 2：`python -m pytest -q` 全绿。**
- [ ] **Step 3：提交** `git commit -m "docs(bench): phase 2 event-engine comparison"`

---

## 验收标准

- 事件引擎无头可跑，且与原引擎**同种子轨迹一致**（或偏差有明确书面说明）。
- 对照基准显示：重事件步的 p50/p95 尖峰被抹平，avg 有可测量提升。
- 明确写出：**为什么 DES 仍未改变 O(人口) 的渐近性**（每个活跃角色仍每 10 tick 必须掷骰），以及 Phase 3（局部化/去全量洗牌）与 Phase 4（数组化）才是渐近性的下一步。

## 后续（不在本计划内）

Phase 3 交互局部化（去全局 `event_plaza` 洗牌）→ Phase 4 数据布局（SoA + CSR、冷热分层）→ Phase 5 并行/下沉。
