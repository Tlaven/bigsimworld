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
    parser.add_argument("--engine", choices=["legacy", "event"], default="legacy")
    parser.add_argument("--rare-stride", type=int, default=1,
                        help="event 引擎稀有事件降频倍数（1=逐位一致，建议 10）")
    parser.add_argument("--out", default="bench/results/scaling.csv")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    rows = []
    header = ["engine", "rare_stride", "n", "steps", "avg_ms", "p50_ms", "p95_ms", "max_ms", "rss_mb", "population_after"]
    print(f"engine={args.engine} rare_stride={args.rare_stride}")
    print(f"{'N':>8} {'avg_ms':>10} {'p50_ms':>10} {'p95_ms':>10} {'rss_MB':>10} {'pop':>8}")
    for n in args.sizes:
        engine = build_engine(n, seed=args.seed, engine=args.engine, rare_stride=args.rare_stride)
        if args.warmup:
            measure_steps(engine, args.warmup)
        result = measure_steps(engine, args.steps)
        summary = summarize(result)
        row = {"engine": args.engine, "rare_stride": args.rare_stride, "n": n, "steps": args.steps, **summary,
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
