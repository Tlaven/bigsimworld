"""均值场（测度）引擎：以分布为主体，每 tick 施加流算子。

成本与人口 N 无关（只随占用桶数）。
"""

from app.core.measure import transitions
from app.core.measure.measure import Measure, measure_from_characters
from app.core.measure.space import StateSpace


class MeanFieldEngine:
    def __init__(self, space=None, measure=None, characters=None, flows=None):
        self.space = space or StateSpace()
        if measure is not None:
            self.measure = measure
        elif characters is not None:
            self.measure = measure_from_characters(characters, self.space)
        else:
            self.measure = Measure(self.space)
        self.flows = flows if flows is not None else transitions.DEFAULT_FLOWS
        self.simulation_time = 0

    def step(self):
        self.simulation_time += 1
        for flow in self.flows:
            flow(self.measure, self.simulation_time)

    def run_until(self, target):
        while self.simulation_time < target:
            self.step()
