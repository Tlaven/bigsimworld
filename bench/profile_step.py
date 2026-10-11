import argparse
import cProfile
import pstats

from bench.world import build_engine


def main():
    parser = argparse.ArgumentParser(description="Profile engine.step hotspots")
    parser.add_argument("--n", type=int, default=10000)
    parser.add_argument("--steps", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--engine", choices=["legacy", "event"], default="legacy")
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args()

    engine = build_engine(args.n, seed=args.seed, engine=args.engine)
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(args.steps):
        engine.step()
    profiler.disable()

    stats = pstats.Stats(profiler).sort_stats("cumulative")
    stats.print_stats(args.top)


if __name__ == "__main__":
    main()
