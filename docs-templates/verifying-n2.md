# 给 N2 造验收（新领域没有 oracle，得亲手造）

> 适用：`docs/core-code.md` 与 `docs/modules/<name>.md` 里标记为 **N2（AI 未见）** 的单元。
> **N0 / N1 不用读本文件**——模型训练数据里有现成的惯用测试写法，自己能写。

## 为什么单独教

N0 / N1 的代码，模型见过大量同类测试；**N2 没有**——而且**你也没有 oracle**（连"正确答案"长什么样都还不知道）。
于是 N2 的风险不是"忘了写测试"，而是"**测试写了假**"：

- 拿实现自己的输出当期望（**循环自证**）；
- 断言同义反复（`result == result` 换个写法）；
- 只测 happy path，不测边界 / 失败分支。

这类假测试**没人能靠肉眼看出来**，所以必须用能识破它的手段。这也是 N2 与 N0/N1 在验证上的分水岭。

## 五种手段（按对"无 oracle"的替代力排序，选 1~2 种）

1. **不变量 → property test**（首选）
   - 把每条不变量写成"任意合法输入下恒成立"的断言。
   - 这是 N2 **唯一可靠的 oracle 替代品**。
   - 例：`∀ order, slots: 返回非 None ⇒ slot.used + order.weight <= slot.capacity`
   - 工具：hypothesis(py) / fast-check(js) / proptest(rs) / QuickCheck 类。

2. **mutation testing**（验"测试本身是否有效"）
   - 故意改坏实现，看测试会不会变红。红不了 = 这测试没用。
   - 专杀循环自证 / 同义测试。
   - 工具：mutmut / Stryker / cargo-mutants。

3. **approved scenario / golden fixture**（冻结期望）
   - 人工确认过的"输入 → 输出"冻结起来；之后被破坏就必须**重新批准**。
   - 可直接复用 `docs/glossary.md` 的 [例子] 栏正例——**同一事实一处定义**（术语表例子 = 验收 fixture）。

4. **盲测验证者**（独立找反例）
   - 一个**看不到实现**、只按文档用系统的人 / agent，专门找反例。
   - 复用同目录的 `teach-back-verifier-prompt.md`（同一套独立验证思路）。

5. **differential**（对照）
   - 有旧实现 / 参考实现时，做输出对照。

## 反模式（必读）

- ❌ 测试拿实现自己的输出当期望（循环自证）
- ❌ 断言同义反复
- ❌ 只测 happy path
- ❌ 把"有测试"当成"测试有效"

## 闸门

若某条 N2 逻辑**造不出可跑验收** → 不是"测试先欠着"，而是说明**逻辑还没讲到可实现**：
回去补 `[步骤级说明]`（core-code / L3），**别放行实现**。

## 写进文档

在 N2 单元的「验收」栏里写清：

- 命令 + 预期（`pytest tests/test_x.py` → 通过）；
- 或断言（property 形式的不变量）；
- 并注明用的是上面哪 1~2 种手段。

> `scripts/check-doc-refs.sh` 会**粗检**"标了 N2 却缺验收"——要求每条 N2 用 `novelty=N2` 标记、并配一个独立一行 `**验收**:…`（写法见 `docs-templates/module-doc.md`）。
> **它只数标记、判不了语义**：凑一个 `**验收**` 字样就能骗过它，验收是否真有意义仍归 teach-back 验证者。**"检查器过了"≠"验收对了"。**
