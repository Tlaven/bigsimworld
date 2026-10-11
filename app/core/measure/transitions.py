"""测度层的流算子（Stage 1：衰老 / 收入 / 死亡 / 出生）。

速率严格来自个体模型的"每 tick 等效速率"（见计划 §0.1）。
所有算子的成本 = O(占用桶数)，与人口 N 无关。
"""

DEATH_RATE = 0.05 / 360        # age>=60，每 tick
BIRTH_RATE = 0.005 / 27        # 已婚且 18<=age<=50，每 tick
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


DEFAULT_FLOWS = (aging, income, death, birth)
