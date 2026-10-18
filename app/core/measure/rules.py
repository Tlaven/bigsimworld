"""交互规则（第 9 缝 = `RULES` 注册表）的第一条实现。

**MarriageRule · 跨分辨率婚配**（`target="cluster"` 簇侧 R→C / `"measure"` 大众侧 R→M）——
决策与被拒方案见 `docs/decisions/adr-007-cross-resolution-marriage.md` /
`adr-009-mass-marriage.md`，步骤级规格见 `docs/modules/interaction-channel.md` N2-7。

规则**只声明意图**：守恒、建边、配额、宽限期全部由通道执行。本文件不碰
`relationships`、不动 `Measure`、不做准入判断（配额不归规则管）。

**默认关**：`RULES` 空时不注册任何东西；runner 只在 `SIM_CHANNEL_MARRIAGE=1` 时调用
`register_marriage_rule()`。开启 = 新增一条婚配通量（窗口自己的婚配事件照常跑）⇒
**不**要求与纯个体引擎收敛（门槛只在默认关闭下跑）。
"""

from __future__ import annotations

import random

from app.core.measure.channel import Intent, Match, compile_match, register
from app.core.measure.transitions import MARRIAGE_RATE

# 目标桶的可匹配性：闭区间 ⇒ 个体引擎的 `18 ≤ age < 60`（age=60 已在死亡流里）写成 `(18, 59)`。
ELIGIBLE = Match(marital=0, age=(18, 59))


class MarriageRule:
    """窗口单身 → 粗侧单身的婚配意图（每 tick 每个合格单身掷一次 `rate`）。

    `target="cluster"`（缺省）→ coarse 族（计数加权抽样）；`target="measure"` → **全局测度**
    （大众婚配：无候选抽样，直接对匿名单身发起）。两者**单值互斥**（生产开关是单值开关）——
    通道不在 reserve 时复检发起者婚配态，两模式并存会让同一人被嫁两次。
    只发 `bind` 意图；由通道 `extract(amount=1)` + `link(..., "spouse")` 落地。
    """

    kind = "spouse"              # `bind` 下的边名（见 N2-7 陷阱 7）
    emits_bind = True            # 会发 bind ⇒ `headroom_reserve` 照常预留窗口名额
    # `RULES` 的键（规则名）**按目标侧区分**（adr-012）：同名注册会互相覆盖，`both` 需要两键并存。
    NAMES = {"cluster": "cross_marriage", "measure": "mass_marriage"}

    TARGETS = ("cluster", "measure")

    def __init__(self, rate=None, rng=None, target="cluster"):
        if target not in self.TARGETS:
            raise ValueError(f"unknown marriage target: {target!r}（只支持 {self.TARGETS}）")
        self.target = target
        self.name = self.NAMES[target]
        self.rate = MARRIAGE_RATE if rate is None else float(rate)
        # **规则自有的确定性随机流**（推荐）：与 `window.rng` 分开，否则"开关规则"会改变
        # 个体事件的随机流，A/B 与校准都不可控（2026-10-18 实测：共流时四档 rate 给出同一个
        # 被污染的数字）。`rng=None` 时退回 `context.rng`（惰性/兼容路径）。
        self.rng = rng

    def offers(self, context):
        window = context.window
        rng = self.rng or context.rng or getattr(window, "rng", None) or random
        space = window.space
        pred = compile_match(ELIGIBLE, space)

        # 大众目标侧（N2-7「候选侧」）：粗侧只有一个"目标"，无候选抽样。
        if self.target == "measure":
            return self._offers_measure(window, rng, pred)

        store = context.store
        # ① 目标簇候选：每 tick 只扫一次 coarse 分布（避免"每个单身扫一遍簇"）
        candidates = []
        for cid in sorted(store.clusters):
            cluster = store.clusters[cid]
            if cluster.level != 0:
                continue
            engine = cluster.state.get("engine")
            if engine is None:
                continue
            mini = engine.measure
            weight = 0.0
            for index in mini.occupied:
                if mini.counts[index] >= 1.0 and pred(index):
                    weight += mini.counts[index]
            if weight > 0.0:
                candidates.append((cid, weight))
        if not candidates:
            return []
        total = sum(weight for _, weight in candidates)

        # ② 逐个窗口单身：合格 + 掷 rate + 计数加权抽样选簇
        intents = []
        for rid in sorted(window.characters):
            character = window.characters[rid]
            if character.relationships.get("spouse"):
                continue
            if not (18 <= character.age < 60):
                continue
            if rng.random() >= self.rate:
                continue
            roll = rng.random() * total
            acc = 0.0
            chosen = candidates[-1][0]
            for cid, weight in candidates:
                acc += weight
                if acc >= roll:
                    chosen = cid
                    break
            intents.append(Intent(op="bind", kind=self.kind,
                                  origin=("character", rid),
                                  scope=("cluster", chosen),
                                  match=ELIGIBLE))
        return intents

    def _offers_measure(self, window, rng, pred):
        """大众目标侧：窗口单身 → 全局测度匿名单身（R→M，`scope=("measure",)`）。

        ① 房源检查（每 tick 一次）：全局测度里存在 `count ≥ 1.0` 且谓词命中的整人桶才发意图，
        否则返回 []（不产 `dropped:no_match` 噪声，也**不**消耗规则随机流）。
        ② 合格单身各掷一次 `rate`，命中即直接产出意图（无候选抽样 ⇒ 每次只消耗 1 个随机数）。
        配额/宽限语义由通道按 N2-8 执行（豁免 `cap_per_cluster`；`cap_per_tick`/headroom 仍是硬上界）。
        """
        measure = window.measure
        weight = 0.0
        for index in measure.occupied:
            if measure.counts[index] >= 1.0 and pred(index):
                weight += measure.counts[index]
        if weight <= 0.0:
            return []
        intents = []
        for rid in sorted(window.characters):
            character = window.characters[rid]
            if character.relationships.get("spouse"):
                continue
            if not (18 <= character.age < 60):
                continue
            if rng.random() >= self.rate:
                continue
            intents.append(Intent(op="bind", kind=self.kind,
                                  origin=("character", rid),
                                  scope=("measure",),
                                  match=ELIGIBLE))
        return intents


def register_marriage_rule(rate=None, rng=None, target="cluster") -> MarriageRule:
    """把跨分辨率婚配规则注册进 `RULES`（幂等：同名键覆盖）。"""
    rule = MarriageRule(rate=rate, rng=rng, target=target)
    register(rule)
    return rule
