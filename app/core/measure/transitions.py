"""测度层的流算子（衰老 / 收入 / 死亡 / 继承 / 婚配 / 生育）。

速率严格来自个体模型的"每 tick 等效速率"（见计划 §0.1）。
所有算子的成本 = O(占用桶数)，与人口 N 无关。
"""

DEATH_RATE = 0.05 / 360        # age>=60，每 tick
BIRTH_RATE = 0.005 / 27        # 已婚且 18<=age<=50，每 tick
MARRIAGE_RATE = 0.1 / 360      # 单身且 18<=age<60，每 tick
MARRIAGE_MEAN_DEG = 2.5        # 单身者的平均可接触对象数（用于可用性闭合）
INHERITANCE_FRACTION = 0.1     # 个体模型：每个子女得 10%/nchild，合计 10%
INCOME_AMOUNT = 1000.0
INCOME_PERIOD = 30             # 每 30 tick 加一次收入
AGE_PERIOD = 360               # 每 360 tick 老一岁


def aging(measure, tick):
    if tick % AGE_PERIOD != 0:
        return
    space = measure.space
    moves = {}
    for index in list(measure.occupied):
        age, gender, wealth, marital = space.decode(index)
        if age >= space.age_buckets - 1:
            continue
        target = space.encode(age + 1, gender, wealth, marital)
        moves[target] = moves.get(target, 0.0) + measure.counts[index]
        measure.counts[index] = 0.0
        measure.occupied.discard(index)
    for target, amount in moves.items():
        measure.add(target, amount)


def income(measure, tick):
    if tick % INCOME_PERIOD != 0:
        return
    space = measure.space
    moves = {}
    for index in list(measure.occupied):
        age, gender, wealth, marital = space.decode(index)
        if not (18 < age < 60):
            continue
        new_value = space.wealth_value(wealth) + INCOME_AMOUNT
        target = space.encode(age, gender, space.wealth_bucket(new_value), marital)
        moves[target] = moves.get(target, 0.0) + measure.counts[index]
        measure.counts[index] = 0.0
        measure.occupied.discard(index)
    for target, amount in moves.items():
        measure.add(target, amount)


def death(measure, tick):
    space = measure.space
    deaths = []
    for index in list(measure.occupied):
        age, gender, wealth, marital = space.decode(index)
        if age >= 60:
            amount = measure.counts[index] * DEATH_RATE
            if amount > 0.0:
                measure.add(index, -amount)
                deaths.append((age, wealth, amount))
    measure.recent_deaths = deaths


def inject_inherited(measure, overflow=0.0, global_measure=None):
    """把 ``recent_deaths`` 的 10% 遗产按 gap 窗口注入 ``yearly_inherited`` 池。

    ``overflow`` 份额（[0,1]）改注入 ``global_measure`` 的池——用于"子女已离开共演单元"
    的溢出（C1c）；``overflow=0`` 且 ``global_measure=None`` 时与原行为一致。
    """
    space = measure.space
    deaths = getattr(measure, "recent_deaths", None) or []
    for age, wealth, amount in deaths:
        inherited = amount * space.wealth_value(wealth) * INHERITANCE_FRACTION
        child_low = max(0, age - 50)
        child_high = max(0, age - 18)
        window = child_high - child_low + 1
        if window <= 0:
            continue
        per_child = inherited / window
        leak = per_child * overflow if (overflow > 0.0 and global_measure is not None) else 0.0
        keep = per_child - leak
        pool = measure.yearly_inherited
        for child_age in range(child_low, child_high + 1):
            if keep > 0.0:
                pool[child_age] = pool.get(child_age, 0.0) + keep
            if leak > 0.0:
                gp = global_measure.yearly_inherited
                gp[child_age] = gp.get(child_age, 0.0) + leak
    measure.recent_deaths = []  # 死者已完成映射，避免重复入账


def distribute_pool(measure):
    """把 ``yearly_inherited`` 池按接收桶财富质量占比、整数桶位移分配出去。

    （整桶平移、不拆分桶计数；余量留池 —— 见 Stage 3/7 教训。）
    """
    space = measure.space
    cells_by_age = {}
    for index in measure.occupied:
        cells_by_age.setdefault(space.decode(index)[0], []).append(index)

    pool = measure.yearly_inherited
    for child_age, available in list(pool.items()):
        cells = cells_by_age.get(child_age)
        if not cells:
            continue  # 接收段无人：余量留池，下一年（有人的时候）再分
        total_mass = 0.0
        masses = []
        for index in cells:
            count = measure.counts[index]
            mass = count * space.wealth_value(space.decode(index)[2])
            masses.append((index, count, mass))
            total_mass += mass
        if total_mass <= 0.0:
            continue
        for index, count, mass in masses:
            if count <= 0.0 or available <= 0.0:
                continue
            ideal = available * (mass / total_mass)
            k = int(ideal / (count * space.wealth_width))  # 整数桶位移（floor，不超付）
            if k > 0:
                _shift_age_wealth(measure, space, [index], k)
                pool[child_age] = available - count * k * space.wealth_width
                available = pool[child_age]


def inheritance(measure, tick):
    """遗产流算子（年批 + 段池 + 秩保持整数分配）。

    个体模型里：死者把 10%/子女 的财富交给**自己的**子女——
    ① 子女年龄分布在孩子出生年龄（父母 18–50）的整个窗口，不必恰差 25；
    ② 富父母的子女继承更多（"富→富"相关沿代际传导）。

    均值场闭合（Stage 3 教训的推论：分红桶的任何"分数拆分"会碎片化，
    任何"跨主人复用桶索引"的账本会凭空注水——故全部用**整数桶分配、
    支付即瞬发、无 per-cell 账本**）：
    - 段池：死者 10% 财富按 gap 窗口 u∈[a-50, a-18] 进入
      measure.yearly_inherited[u]（生育率对 18..50 岁父母近均匀 → 密度均匀）；
    - 年度清算（每 360 tick 一次）：对每个非空段池，按接收桶的
      **财富质量占比**分配各自的理想份额；每个桶只支付 floor() 得到的
      **整数桶位移**（整桶平移，不拆分桶内计数）；余量留池下年再分。
    - 守恒：池只进（遗产注入）出（支付 count×k×宽度 ≤ 理想份额），无注水。
    """
    inject_inherited(measure)
    if tick % 360 == 0:
        distribute_pool(measure)


def _shift_age_wealth(measure, space, cells, steps):
    """把若干桶的财富整体上移 steps 桶（整桶，无碎片）。"""
    moves = {}
    for index in cells:
        count = measure.counts[index]
        if count <= 0.0:
            continue
        age, gender, wealth, marital = space.decode(index)
        if wealth + steps >= space.wealth_bins:
            return  # 触顶：本桶余下的支付留池，不越界
        target = space.encode(age, gender, wealth + steps, marital)
        moves[target] = moves.get(target, 0.0) + count
        measure.add(index, -count)
    for target, amount in moves.items():
        measure.add(target, amount)


def birth(measure, tick):
    space = measure.space
    eligible = 0.0
    for index in measure.occupied:
        age, gender, wealth, marital = space.decode(index)
        if marital == 1 and 18 <= age <= 50:
            eligible += measure.counts[index]
    amount = eligible * BIRTH_RATE
    if amount <= 0.0:
        return
    half = amount / 2.0
    measure.inflow(space.encode(0, 0, 0, 0), half)
    measure.inflow(space.encode(0, 1, 0, 0), amount - half)


def marriage(measure, tick):
    """均值场婚配（个体模型里婚配是**性别中立**的：从 friend/familiarity 里
    挑任意 18<=age<60 的单身者）。

    每个单身者以 MARRIAGE_RATE 发起；成功率由"可接触对象中至少一个单身"的
    可用性 q 决定，q ≈ 1-(1-p_elig)^deg。
    """
    space = measure.space
    cells = []
    singles = 0.0
    adults = 0.0
    for index in list(measure.occupied):
        count = measure.counts[index]
        age, gender, wealth, marital = space.decode(index)
        if 18 <= age < 60:
            adults += count
            if marital == 0:
                cells.append((index, count))
                singles += count
    if singles <= 1.0 or adults <= 0.0:
        return
    p_elig = singles / adults
    availability = 1.0 - (1.0 - p_elig) ** MARRIAGE_MEAN_DEG
    to_marry = min(MARRIAGE_RATE * singles * availability * 2.0, singles)
    if to_marry <= 0.0:
        return
    # 每桩婚事消耗 2 个单身者；按性别/年龄占比摊到各桶
    for index, count in cells:
        move = to_marry * (count / singles)
        if move <= 0.0:
            continue
        age, gender, wealth, marital = space.decode(index)
        measure.add(space.encode(age, gender, wealth, 1), move)
        measure.add(index, -move)


DEFAULT_FLOWS = (aging, income, death, birth)
FULL_FLOWS = (aging, income, death, marriage, birth, inheritance)
