"""测度层的状态空间：维度分桶 + 混合基数编码。

Stage 1 维度：年龄段、性别、财富段、婚配状态。
财富用**线性分桶**（宽度 = 收入步长），使"收入 +1000"是一次精确的桶位移；
对数分桶无法表示小额加法漂移。
"""


class StateSpace:
    def __init__(self, age_buckets=121, genders=2, maritals=3,
                 wealth_width=1000.0, wealth_bins=3000):
        self.age_buckets = age_buckets
        self.genders = genders
        self.maritals = maritals
        self.wealth_width = float(wealth_width)
        self.wealth_bins = wealth_bins
        self.dims = (age_buckets, genders, wealth_bins, maritals)
        self.size = age_buckets * genders * wealth_bins * maritals

    # ---------------------------------------------------------------- 编码

    def encode(self, age, gender, wealth, marital):
        g, w, m = self.genders, self.wealth_bins, self.maritals
        return ((age * g + gender) * w + wealth) * m + marital

    def decode(self, index):
        g, w, m = self.genders, self.wealth_bins, self.maritals
        marital = index % m
        index //= m
        wealth = index % w
        index //= w
        gender = index % g
        age = index // g
        return age, gender, wealth, marital

    # ------------------------------------------------------------ 财富分桶

    def wealth_bucket(self, value):
        bucket = int(value / self.wealth_width)
        if bucket < 0:
            return 0
        return min(bucket, self.wealth_bins - 1)

    def wealth_value(self, bucket):
        """该桶的代表值（桶中心）。"""
        return (bucket + 0.5) * self.wealth_width
