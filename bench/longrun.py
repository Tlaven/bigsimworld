import argparse
import time

from app.core.measure.engine import MeanFieldEngine
from app.core.measure.transitions import FULL_FLOWS
from bench.world import make_characters


def main():
    parser = argparse.ArgumentParser(description="长地平线标定：占用桶 / 底表 / 耗时 / 池 轨迹")
    parser.add_argument("--population", type=int, default=20000)
    parser.add_argument("--ticks", type=int, default=36000)
    parser.add_argument("--window", type=int, default=3600, help="打印间隔（tick）")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    engine = MeanFieldEngine(characters=make_characters(args.population, seed=args.seed),
                             flows=FULL_FLOWS)
    print(f"population={args.population} ticks={args.ticks}（{args.ticks / 360:.0f} 年）seed={args.seed}")
    print(f"{'tick':>7} {'年':>5} {'occupied':>9} {'backing':>9} {'pop':>10} {'ms/tick':>9} {'pool':>10}")
    last = time.perf_counter()
    for i in range(1, args.ticks + 1):
        engine.step()
        if i % args.window == 0:
            now = time.perf_counter()
            ms = (now - last) / args.window * 1000
            last = now
            m = engine.measure
            print(f"{i:>7} {i // 360:>5} {len(m.occupied):>9} {len(m.counts):>9} "
                  f"{m.total():>10.0f} {ms:>9.3f} "
                  f"{float(sum(m.yearly_inherited.values())):>10.1f}")


if __name__ == "__main__":
    main()
