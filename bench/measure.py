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
