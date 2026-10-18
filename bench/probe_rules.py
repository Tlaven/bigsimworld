"""实验用探针规则（**非生产路径**）。

`MassMarriageRule` = 婚配规则的"大众候选"变体：窗口单身 × 全局测度匿名单身（R→M）。
用于 `bench.calibrate_marriage --scope measure` 的"语义双解"测量（2026-10-18 测量轮）：

- 通道侧**零改动**——`scope=("measure",)` 的 bind 路径由 N2-8 提供（ADR-008）；
- 本文件**不是**生产规则：采纳与否属独立决策；若采纳，正式化轮把它并入
  `app/core/measure/rules.py`（并走 N2-7 规格增补 + teach-back + runner 开关）。

与 `app/core/measure/rules.py::MarriageRule` 的差别**只有目标侧**：候选不扫 coarse 簇，
直接产 `scope=("measure",)` 意图；资格判定、掷骰顺序、**自有随机流**纪律逐行一致。
"""
from __future__ import annotations

import random

from app.core.measure.channel import Intent, compile_match
from app.core.measure.rules import ELIGIBLE
from app.core.measure.transitions import MARRIAGE_RATE


class MassMarriageRule:
    """窗口单身 → 全局测度匿名单身的婚配意图（每 tick 每个合格单身掷一次 `rate`）。

    只发 `bind` 意图；由通道 `extract(amount=1)` + `link(..., "spouse")` 落地，
    析出源 = `window.measure`（全局测度）；配额豁免 `cap_per_cluster`、仍受
    `cap_per_tick` 与窗口 headroom（N2-8）。
    """

    name = "mass_marriage"       # `RULES` 的键（与生产规则 `cross_marriage` 区分）
    kind = "spouse"              # `bind` 下的边名
    emits_bind = True            # 会发 bind ⇒ `headroom_reserve` 照常预留（与 null 臂口径一致）

    def __init__(self, rate=None, rng=None):
        self.rate = MARRIAGE_RATE if rate is None else float(rate)
        # 自有确定性流（推荐）：不与窗口个体事件争 rng（与生产规则同一纪律，2026-10-18 校准教训）。
        self.rng = rng

    def offers(self, context):
        window = context.window
        rng = self.rng or context.rng or getattr(window, "rng", None) or random
        space = window.space

        # ① 大众侧房源检查（每 tick 一次）：全局测度存在 count≥1.0 的合格整人桶才发意图，
        #    否则返回 [] —— 不产 `dropped:no_match` 噪声（与 N2-7 的"无房源不产意图"一致）。
        pred = compile_match(ELIGIBLE, space)
        measure = window.measure
        weight = 0.0
        for index in measure.occupied:
            if measure.counts[index] >= 1.0 and pred(index):
                weight += measure.counts[index]
        if weight <= 0.0:
            return []

        # ② 逐个窗口单身：合格 + 掷 rate（无候选抽样——大众侧只有一个"目标"）。
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
