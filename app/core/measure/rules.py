"""交互规则（第 9 缝 = `RULES` 注册表）的第一条实现。

**MarriageRule · 跨分辨率婚配（R→C）** —— 决策与被拒方案见
`docs/decisions/adr-007-cross-resolution-marriage.md`，步骤级规格见
`docs/modules/interaction-channel.md` N2-7。

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
    """窗口单身 → coarse 族单身的婚配意图（每 tick 每个合格单身掷一次 `rate`）。

    只发 `bind` 意图；由通道 `extract(amount=1)` + `link(..., "spouse")` 落地。
    """

    name = "cross_marriage"      # `RULES` 的键（规则名）
    kind = "spouse"              # `bind` 下的边名（见 N2-7 陷阱 7）
    emits_bind = True            # 会发 bind ⇒ `headroom_reserve` 照常预留窗口名额

    def __init__(self, rate=None):
        self.rate = MARRIAGE_RATE if rate is None else float(rate)

    def offers(self, context):
        window = context.window
        store = context.store
        rng = context.rng or getattr(window, "rng", None) or random
        space = window.space

        # ① 目标簇候选：每 tick 只扫一次 coarse 分布（避免"每个单身扫一遍簇"）
        pred = compile_match(ELIGIBLE, space)
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


def register_marriage_rule(rate=None) -> MarriageRule:
    """把跨分辨率婚配规则注册进 `RULES`（幂等：同名键覆盖）。"""
    rule = MarriageRule(rate=rate)
    register(rule)
    return rule
