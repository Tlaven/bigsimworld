# bench —— 无头性能基准（Phase 1）

这一层**完全不依赖 Web / Redis / 多进程 DB**：用空队列 `SinkQueue` 顶替 DB 写入，直接驱动 `engine.step()`，用于测量"人口规模 → 每步耗时 / 内存"的扩展曲线，并定位热点。

## 脚本

| 脚本 | 用途 | 命令 |
| --- | --- | --- |
| `bench.run_scaling` | 扫描多个人口规模，输出扩展曲线到 CSV | `python -m bench.run_scaling --sizes 1000 2000 5000 10000 20000 --steps 30 --warmup 5` |
| `bench.profile_step` | 用 cProfile 找 `engine.step` 的热点函数 | `python -m bench.profile_step --n 10000 --steps 30 --top 20` |
| `bench.world` | 用固定随机种子构造 N 个角色的引擎（可复现） | `from bench.world import build_engine; build_engine(1000, seed=42)` |
| `bench.measure` | 逐步计时 + RSS 采样，返回 `avg/p50/p95/max` | `from bench.measure import measure_steps` |

结果默认写入 `bench/results/`。

## 基线结果（Python 3.12.4 / Windows / 单核，seed=42，1000–20000 人）

| N | avg_ms | p50_ms | p95_ms | rss_MB | 每千人 µs |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1,000 | 0.367 | 0.187 | 2.00 | 65.2 | 0.367 |
| 2,000 | 0.706 | 0.366 | 3.62 | 69.8 | 0.353 |
| 5,000 | 1.787 | 0.990 | 9.01 | 79.0 | 0.357 |
| 10,000 | 3.856 | 1.891 | 22.1 | 97.0 | 0.386 |
| 20,000 | 9.516 | 3.937 | 63.0 | 130.0 | 0.476 |

## 怎么解读

1. **耗时随人口近似线性，且略偏超线性。**
   每千人耗时从 0.353µs（2k）升到 0.476µs（20k），到 2 万人时人均成本比 1 千人时高约 **35%**。也就是说：人口越多，不是"每人成本恒定"，而是**越跑越慢**——因为 `event_plaza` 的全局洗牌和关系链表操作会随规模放大。
2. **耗时是尖峰式的（spiky）。**
   `p50` 远小于 `avg`、`p95` 却是 p50 的 10 倍以上（2 万人时 p50 3.9ms vs p95 63ms）。原因是 `possible_events()` 每 10 tick 才触发一次，**每 10 步里有 1 步是"重事件步"**，其余是便宜的属性步。
3. **内存线性增长，约 3.2 KB / 角色。**
   65MB → 130MB 对应 0 → 20000 人。外推：10 万人 ≈ 0.4GB、100 万人 ≈ 3GB，单进程必 OOM。
4. **热点排序**（`profile_n10000.txt`）：`Character.step`（全量遍历）> `possible_events` > `round_up_probability` > `random.shuffle`（`event_plaza` 全局洗牌）。

## 结论（这就是 Phase 2 的依据）

> **每步成本 ∝ 人口**，而这个世界的人口只会增长。因此当前模型**在数学上无法长期演化**：跑得越久人口越多，每步越慢，最终必然卡死或 OOM。

- 1 万人 ≈ 3.9ms/步；20 万人外推 ≈ 0.1s/步；千万级即秒级。
- 与 Web 层无关——瓶颈在仿真内核本身。

## 下一步（Phase 2 接口约定）

Phase 2 将把"全局同步 tick"改为"离散事件调度"：给每个体维护 `next_event_time`，用堆（heapq）只处理"下一次真正要发生的事"。目标是把成本从 **∝ 人口** 降到 **∝ 事件数**，让闲置个体零成本。

**Phase 2 完成后必须重跑本文件的基线命令做对比，验证人均耗时不再随人口增长而上升。**
