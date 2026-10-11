"""测度层的流算子（衰老 / 收入 / 死亡 / 继承 / 婚配 / 生育）。

速率严格来自个体模型的"每 tick 等效速率"（见计划 §0.1）。
所有算子的成本 = O(占用桶数)，与人口 N 无关。
"""

DEATH_RATE = 0.05 / 360        # age>=60，每 tick
BIRTH_RATE = 0.005 / 27        # 已婚且 18<=age<=50，每 tick
MARRIAGE_RATE = 0.1 / 360      # 单身且 18<=age<60，每 tick
MARRIAGE_MEAN_DEG = 2.5        # 单身者的平均可接触对象数（用于可用性闭合）
MEAN_PARENT_AGE_GAP = 25       # 父母与子女的年龄差（用于把遗产投向"子女"年龄段）
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


def inheritance(measure, tick):
    """把死者 10% 的财富转移给"子女"年龄段（年龄差 MEAN_PARENT_AGE_GAP）。

    均值场近似：无父子链，故把每个死者年龄 a 的遗产投向 a-gap 的整个年龄段，
    按人头均分（**均值正确**，丢失"富父母子女继承更多"的相关性）。

    为避免每次不足一桶的位移把计数碎片化到海量桶中，按年龄段累积位移，
    攒够整数桶时再做**整桶平移**。
    """
    space = measure.space
    deaths = getattr(measure, "recent_deaths", None)
    if not deaths:
        return

    inherited_by_child_age = {}
    for age, wealth, amount in deaths:
        child_age = age - MEAN_PARENT_AGE_GAP
        if child_age < 0:
            continue
        inherited = amount * space.wealth_value(wealth) * INHERITANCE_FRACTION
        inherited_by_child_age[child_age] = inherited_by_child_age.get(child_age, 0.0) + inherited
    if not inherited_by_child_age:
        return

    cells_by_age = {}
    for index in measure.occupied:
        age = space.decode(index)[0]
        cells_by_age.setdefault(age, []).append(index)

    pending = measure.pending_shift
    for child_age, total_inherited in inherited_by_child_age.items():
        cells = cells_by_age.get(child_age)
        if not cells:
            continue
        total_count = sum(measure.counts[i] for i in cells)
        if total_count <= 0.0:
            continue
        pending[child_age] = pending.get(child_age, 0.0) + (total_inherited / total_count) / space.wealth_width
        steps = int(pending[child_age])
        if steps <= 0:
            continue
        pending[child_age] -= steps
        _shift_age_wealth(measure, space, cells, steps)


def _shift_age_wealth(measure, space, cells, steps):
    """把某年龄段所有桶的财富整体上移 steps 桶（整桶，无碎片）。"""
    moves = {}
    for index in cells:
        count = measure.counts[index]
        if count <= 0.0:
            continue
        age, gender, wealth, marital = space.decode(index)
        target = space.encode(age, gender, min(wealth + steps, space.wealth_bins - 1), marital)
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
