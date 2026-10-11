"""测度层的状态空间：维度分桶 + 混合基数编码。

Stage 1 维度：年龄段、性别、财富段、婚配状态。
（`degree` / `cell` 维度预留给 Stage 2/空间局部化。）
"""

import math


class StateSpace:
    def __init__(self, age_buckets=121, genders=2, wealth_buckets=48, maritals=3,
                 wealth_min=1.0, wealth_max=1e7):
        self.age_buckets = age_buckets
        self.genders = genders
        self.wealth_buckets = wealth_buckets
        self.maritals = maritals
        self.dims = (age_buckets, genders, wealth_buckets, maritals)
        self.size = age_buckets * genders * wealth_buckets * maritals

        self._log_min = math.log10(wealth_min)
        self._log_max = math.log10(wealth_max)
        self._log_span = self._log_max - self._log_min

    # ---------------------------------------------------------------- 编码

    def encode(self, age, gender, wealth, marital):
        g, w, m = self.genders, self.wealth_buckets, self.maritals
        return ((age * g + gender) * w + wealth) * m + marital

    def decode(self, index):
        g, w, m = self.genders, self.wealth_buckets, self.maritals
        marital = index % m
        index //= m
        wealth = index % w
        index //= w
        gender = index % g
        age = index // g
        return age, gender, wealth, marital

    # ------------------------------------------------------------ 财富分桶

    def wealth_bucket(self, value):
        if value <= 10 ** self._log_min:
            return 0
        frac = (math.log10(value) - self._log_min) / self._log_span
        bucket = int(frac * self.wealth_buckets)
        return min(bucket, self.wealth_buckets - 1)

    def wealth_value(self, bucket):
        """该桶的代表值（几何中心）。"""
        frac = (bucket + 0.5) / self.wealth_buckets
        return 10 ** (self._log_min + frac * self._log_span)
