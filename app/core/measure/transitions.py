"""测度层的流算子（Stage 1：衰老 / 收入 / 死亡 / 出生）。

速率严格来自个体模型的"每 tick 等效速率"（见计划 §0.1）。
所有算子的成本 = O(占用桶数)，与人口 N 无关。
"""

DEATH_RATE = 0.05 / 360        # age>=60，每 tick
BIRTH_RATE = 0.005 / 27        # 已婚且 18<=age<=50，每 tick
MARRIAGE_RATE = 0.1 / 360      # 单身且 18<=age<60，每 tick
MARRIAGE_MEAN_DEG = 2.5        # 单身者的平均可接触对象数（用于可用性闭合）
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
    measure.outflow(lambda index: space.decode(index)[0] >= 60, DEATH_RATE)


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
FULL_FLOWS = (aging, income, death, marriage, birth)
