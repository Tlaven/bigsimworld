"""测度层的流算子（衰老 / 收入 / 死亡 / 继承 / 婚配 / 生育）。

速率严格来自个体模型的"每 tick 等效速率"（见计划 §0.1）。
所有算子的成本 = O(占用桶数)，与人口 N 无关。

**遍历序纪律（硬规则）**：凡迭代 `measure.occupied` 的循环一律 `sorted(...)`；
凡批量 `add` 的移动表（`moves`）按目标索引升序插入。理由：① 清算/支付按遍历序
消耗池（`distribute_pool` 的 `available` 递减），顺序决定每桶拿多少；② 浮点累加
序影响末位。二者叠加，"同一分布、换个构造顺序"就会得到不同的未来——这是
`SIM_SEED` 复现与快照接续的隐性前提。由 `tests/test_measure_transitions.py::
test_flows_are_construction_order_invariant` 守。
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
    for index in sorted(measure.occupied):
        age, gender, wealth, marital = space.decode(index)
        if age >= space.age_buckets - 1:
            continue
        target = space.encode(age + 1, gender, wealth, marital)
        moves[target] = moves.get(target, 0.0) + measure.counts[index]
        del measure.counts[index]  # 零条目不留：底表键集 ≡ occupied
        measure.occupied.discard(index)
    for target in sorted(moves):
        measure.add(target, moves[target])


def income(measure, tick):
    if tick % INCOME_PERIOD != 0:
        return
    space = measure.space
    moves = {}
    for index in sorted(measure.occupied):
        age, gender, wealth, marital = space.decode(index)
        if not (18 < age < 60):
            continue
        new_value = space.wealth_value(wealth) + INCOME_AMOUNT
        target = space.encode(age, gender, space.wealth_bucket(new_value), marital)
        moves[target] = moves.get(target, 0.0) + measure.counts[index]
        del measure.counts[index]  # 零条目不留：底表键集 ≡ occupied
        measure.occupied.discard(index)
    for target in sorted(moves):
        measure.add(target, moves[target])


def death(measure, tick):
    space = measure.space
    deaths = []
    for index in sorted(measure.occupied):
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

    实现用**差分数组**展平 gap 窗口（每记录 2 次写 + 一趟前缀和；原实现 = 每记录 ×
    窗口 ~33 槽 × 2 次字典操作）。贡献非负 ⇒ 前缀和不会抵消、池键集与逐槽版本一致；
    仅浮点累加序不同（末位）——即 2026-10-18 重基线的由来。
    """
    space = measure.space
    deaths = getattr(measure, "recent_deaths", None) or []
    if not deaths:
        measure.recent_deaths = []
        return
    use_leak = overflow > 0.0 and global_measure is not None
    span = space.age_buckets + 1  # 尾哨兵：child_high + 1 免边界分支
    keep_delta = [0.0] * span
    leak_delta = [0.0] * span if use_leak else None
    for age, wealth, amount in deaths:
        inherited = amount * space.wealth_value(wealth) * INHERITANCE_FRACTION
        child_low = max(0, age - 50)
        child_high = max(0, age - 18)
        window = child_high - child_low + 1
        if window <= 0:
            continue
        per_child = inherited / window
        leak = per_child * overflow if use_leak else 0.0
        keep = per_child - leak
        keep_delta[child_low] += keep
        keep_delta[child_high + 1] -= keep
        if use_leak and leak > 0.0:
            leak_delta[child_low] += leak
            leak_delta[child_high + 1] -= leak
    pool = measure.yearly_inherited
    acc = 0.0
    for child_age in range(space.age_buckets):
        acc += keep_delta[child_age]
        if acc != 0.0:
            pool[child_age] = pool.get(child_age, 0.0) + acc
    if use_leak:
        gp = global_measure.yearly_inherited
        acc = 0.0
        for child_age in range(space.age_buckets):
            acc += leak_delta[child_age]
            if acc != 0.0:
                gp[child_age] = gp.get(child_age, 0.0) + acc
    measure.recent_deaths = []  # 死者已完成映射，避免重复入账


def distribute_pool(measure):
    """把 ``yearly_inherited`` 池按接收桶财富质量占比、整数桶位移分配出去。

    （整桶平移、不拆分桶计数；余量留池 —— 见 Stage 3/7 教训。）
    """
    space = measure.space
    cells_by_age = {}
    for index in sorted(measure.occupied):
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
                # 只按**实付量**扣池：触顶的桶不支付（返回 0）⇒ 份额留池，不得凭空销毁
                paid = _shift_age_wealth(measure, space, [index], k)
                if paid > 0.0:
                    pool[child_age] = available - paid
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
    """把若干桶的财富整体平移 steps 桶（整桶，无碎片；``steps`` 可正可负）。

    返回**实际移动的质量**（= 实际移出桶的 ``count × steps × 宽度``；``steps < 0`` 时为负）。
    触顶（``wealth + steps`` 越过 ``wealth_bins``）或触底（越过桶 0）的桶**不支付**、
    其份额留在池里——调用方**只能按本返回值扣池**，否则会凭空销毁质量（见 `docs/core-code.md` N2-3）；
    越界还会把索引串到别的 age/gender 桶，故下界守卫是**正确性前提**。
    """
    paid = 0.0
    moves = {}
    for index in sorted(cells):
        count = measure.counts[index]
        if count <= 0.0:
            continue
        age, gender, wealth, marital = space.decode(index)
        if wealth + steps >= space.wealth_bins:
            continue  # 触顶：本桶不支付，份额留池（不越界、不注水）
        if wealth + steps < 0:
            continue  # 触底：桶 0 不再可下移（负索引会串到别的 age/gender 桶）
        target = space.encode(age, gender, wealth + steps, marital)
        moves[target] = moves.get(target, 0.0) + count
        measure.add(index, -count)
        paid += count * steps * space.wealth_width
    for target in sorted(moves):
        measure.add(target, moves[target])
    return paid


def deliver_transfer_pool(measure):
    """把通道池按整桶位移送回分布（**最穷整人桶优先**；余量留池）。返回实付质量。

    规格见 `docs/modules/interaction-channel.md` N2-6 第 6 步 / `adr-005`：

    - 目标是 ``count ≥ 1.0`` 的**整人桶**（分数残留不参与年度投递，否则"最穷优先"退化成"最稀优先"）；
    - 计划按目标桶财富**升序**（最穷优先）算，按财富**降序**应用——
      升序应用会把低桶刚收到的质量再搬一次（级联重复加）；
    - 只按 ``_shift_age_wealth`` 的**实付量**扣池（触顶分支不支付）。
    """
    space = measure.space
    pool = float(measure.transfer_pool)
    if pool <= 0.0:
        return 0.0
    width = space.wealth_width
    targets = sorted((index for index in measure.occupied if measure.counts[index] >= 1.0),
                     key=lambda index: (space.decode(index)[2], index))
    plan = []
    remaining = pool
    for index in targets:
        if remaining <= 0.0:
            break
        count = measure.counts[index]
        wealth = space.decode(index)[2]
        headroom = space.wealth_bins - 1 - wealth
        if headroom <= 0:
            continue
        k = int(remaining // (count * width))
        k = min(k, headroom)
        if k <= 0:
            continue
        plan.append((index, k))
        remaining -= count * k * width
    plan.sort(key=lambda item: space.decode(item[0])[2], reverse=True)  # 降序应用：防级联
    delivered = 0.0
    for index, k in plan:
        delivered += _shift_age_wealth(measure, space, [index], k)
    measure.transfer_pool = pool - delivered
    return delivered


def settle_transfer_pool(measure, tick):
    """年度投递（每 360 tick；与继承年清算同拍）。"""
    if tick % 360 == 0:
        return deliver_transfer_pool(measure)
    return 0.0


def birth(measure, tick):
    space = measure.space
    eligible = 0.0
    for index in sorted(measure.occupied):
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
    for index in sorted(measure.occupied):
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


# ------------------------------------------------ 整数语义发放（mini 专用，adr-010）

def integer_death(measure, tick):
    """小计数粗侧的死亡发放（整数语义；`FamilyKind` 专用；全局测度用流体版 `death`）。

    信用 += Σ_{age≥60} count×DEATH_RATE（与流体版**逐 tick 同源**的期望人-次）；
    积满 1.0 即发放：从 `count ≥ 1.0` 的 60+ 桶取 **1.0**（count 降序、平局索引序——
    确定性、不消耗随机数），记入 ``recent_deaths``（**替换**语义，与流体版一致）。
    整人桶不被削到 (0,1) ⇒ mini 保持可物化。见 `docs/decisions/adr-010-mini-integer-semantics.md`。
    """
    space = measure.space
    eligible_total = 0.0
    for index in sorted(measure.occupied):
        if space.decode(index)[0] >= 60:
            eligible_total += measure.counts[index]
    credit = measure.death_credit + eligible_total * DEATH_RATE
    fired = []
    while credit >= 1.0:
        candidates = [index for index in measure.occupied
                      if measure.counts[index] >= 1.0 and space.decode(index)[0] >= 60]
        if not candidates:
            break
        index = min(candidates, key=lambda i: (-measure.counts[i], i))
        age, _gender, wealth, _marital = space.decode(index)
        measure.add(index, -1.0)
        fired.append((age, wealth, 1.0))
        credit -= 1.0
    measure.death_credit = credit
    measure.recent_deaths = fired


def _mix32(tick, k):
    """确定性整数混合（无 rng）：(tick, k) → 32-bit。

    与 `random` 模块零接触 ⇒ `SIM_SEED` 语义不变；纯整数运算 ⇒ 跨平台逐位一致。
    """
    x = (tick * 0x9E3779B1 + k * 0x85EBCA6B) & 0xFFFFFFFF
    x ^= x >> 16
    x = (x * 0x7FEB352D) & 0xFFFFFFFF
    x ^= x >> 15
    x = (x * 0x846CA68B) & 0xFFFFFFFF
    x ^= x >> 16
    return x


def _weighted_pick(pairs, position):
    """按 ``(index, weight)`` 序列累计定位第 ``position`` 人（整型位置；权重为浮点）。

    调用方保证 ``0 ≤ position < Σ weight``；防御性返回 ``None``（定位失败时调用方留信用）。
    """
    acc = 0.0
    for index, weight in pairs:
        acc += weight
        if acc > position:
            return index
    return None


def integer_marriage(measure, tick):
    """小计数粗侧的婚配发放（整数语义；`FamilyKind` 专用；全局测度用流体版 `marriage`）。

    信用 += ``to_marry``（**与流体版同一公式 / 可用性闭合**——逐 tick 同源的期望人-次）；
    积满 2.0 即**整人成对发放**。选人 = **确定性加权均匀抽样**（对全体整人单身按 count
    加权；位置 = `_mix32(tick, k)` 对总权重取模，沿索引升序累计定位）——期望上与流体版
    "按桶占比摊派"（≡ 对单身总体均匀抽人）一致，且不消耗随机数。同一桶取两人仅当
    ``count ≥ 2.0``（与旧规则一致；否则会从分数余量桶取走两整人而销毁质量）。

    **修订（2026-10-19，收窄 adr-010）**：旧规则 = `(-count, index)` 排序取人；因
    `space.encode` 以 age 为最高位（索引升序 = 年龄升序），平局主导下等价于"最年轻优先"
    ⇒ 实测量到 coarse 臂系统性先嫁年轻单身（已婚 18–50 的 ≤30 岁份额 0.42 vs 流体 0.24），
    生育闭合放大 ⇒ 人口超产台阶（n=400 pop 相对 1.8% → 5.4%）。旧表述保留于 adr-010 原文
    （标注被修订）。
    """
    space = measure.space
    singles = adults = 0.0
    for index in sorted(measure.occupied):
        count = measure.counts[index]
        age, _gender, _wealth, marital = space.decode(index)
        if 18 <= age < 60:
            adults += count
            if marital == 0:
                singles += count
    credit = measure.marriage_credit
    if singles > 1.0 and adults > 0.0:
        p_elig = singles / adults
        availability = 1.0 - (1.0 - p_elig) ** MARRIAGE_MEAN_DEG
        credit += min(MARRIAGE_RATE * singles * availability * 2.0, singles)
    pair = 0
    while credit >= 2.0:
        whole = [index for index in sorted(measure.occupied)
                 if measure.counts[index] >= 1.0
                 and space.decode(index)[3] == 0
                 and 18 <= space.decode(index)[0] < 60]
        if not whole:
            break
        total = sum(measure.counts[index] for index in whole)
        if total < 2.0:
            break
        first = _weighted_pick([(index, measure.counts[index]) for index in whole],
                               _mix32(tick, 2 * pair) % int(total))
        second_pairs = []
        for index in whole:
            weight = measure.counts[index] - (1.0 if index == first else 0.0)
            if weight >= 1.0:                    # 该桶还够一整人（同桶双取仅 count ≥ 2.0）
                second_pairs.append((index, weight))
        second_total = sum(weight for _index, weight in second_pairs)
        second = None
        if second_total >= 1.0:
            second = _weighted_pick(second_pairs,
                                    _mix32(tick, 2 * pair + 1) % int(second_total))
        if first is None or second is None:      # 保底：定位失败时留信用不发放
            break
        for index in (first, second):
            age, gender, wealth, _marital = space.decode(index)
            measure.add(index, -1.0)
            measure.add(space.encode(age, gender, wealth, 1), 1.0)
        credit -= 2.0
        pair += 1
    measure.marriage_credit = credit


DEFAULT_FLOWS = (aging, income, death, birth)
FULL_FLOWS = (aging, income, death, marriage, birth, inheritance)
