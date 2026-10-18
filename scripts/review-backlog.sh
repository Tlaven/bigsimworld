#!/usr/bin/env bash
# review-backlog.sh — 列出"自上次复核以来"契约文档的变化（零 token，只列清单，不判定）
#
# teach-back 是按需 + 攒批做的。攒批的代价是"复核时要重读多少"；
# 本脚本把它变成"只看 delta"：哪些契约文件变了、哪些不变量/单元编号增删改。
#
# 用法: bash scripts/review-backlog.sh
# 复核完成后: mkdir -p docs/reviews && echo "<sha> <yyyy-mm-dd>" > docs/reviews/.last-review
# （打印的"现成命令"按各平台给出——.ps1 版用 Set-Content,这是有意的平台差异）
# 退出码恒为 0。

set -u

# 契约面:L1(全部宿主文件名,与 check-docs-sync 的 L1_FILES 对齐)/L2/L4 + 术语表 + 模块文档(模块级不变量住 L3)
# + 项目补充:engineering-spec / cluster-contract 也是契约面
CONTRACT="AGENTS.md CLAUDE.md .cursorrules .cursor/rules/project.mdc .windsurfrules .github/copilot-instructions.md docs/architecture.md docs/architecture.markdown docs/core-code.md docs/core-code.markdown docs/glossary.md docs/glossary.markdown docs/modules/ docs/engineering-spec.md docs/cluster-contract.md"
MARKER="docs/reviews/.last-review"

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo "[review-backlog] 不是 git 仓库，跳过。"; exit 0; }

head_sha=$(git rev-parse --short HEAD 2>/dev/null)
existing=""
for f in $CONTRACT; do [ -e "$f" ] && existing="$existing $f"; done
[ -z "$existing" ] && { echo "[review-backlog] 未找到契约文件（$(printf '%s' "$CONTRACT" | sed 's/ /, /g')）。"; exit 0; }

since=""
[ -f "$MARKER" ] && since=$(head -n1 "$MARKER" 2>/dev/null | awk '{print $1}')

if [ -z "$since" ]; then
  echo "[review-backlog] 还没有复核起点（$MARKER 不存在）——首次按全量列。"
  echo "契约文件:"
  for f in $existing; do echo "  - $f"; done
  echo ""
  if [ -n "$head_sha" ]; then
    echo "复核完成后写入起点:  mkdir -p docs/reviews && echo \"$head_sha $(date +%F)\" > $MARKER"
  else
    echo "（尚无提交——先提交一次,再把 HEAD 写入 $MARKER 作为起点）"
  fi
  exit 0
fi

echo "[review-backlog] 自 $since 以来的契约变化（当前 HEAD=$head_sha）："
stat=$(git diff --stat "$since..HEAD" -- $existing 2>/dev/null)
if [ -z "$stat" ]; then echo "  （无变化）"; exit 0; fi
printf '%s\n' "$stat" | sed 's/^/  /'

echo ""
echo "被增删改的编号（复核时只看这些 + 它们引用的上下文）："
# 编号族是启发式(示例来自试点项目约定):按项目增删
# 行过滤用 awk(--/++ 元数据行排除,且不吞首字符——行首紧跟 +/- 的编号也要能匹配)
hits=$(git diff -U0 "$since..HEAD" -- $existing 2>/dev/null \
  | awk '/^[+-]/ && !/^(\+\+\+|---)/' \
  | grep -E '\b(I-[0-9]+|Q-[0-9]+|A-[0-9]+|M[0-9]+-[0-9]+|U-[0-9]+|P-A[0-9]+-[0-9]+)\b')
nhits=0
[ -n "$hits" ] && nhits=$(printf '%s\n' "$hits" | wc -l | tr -d ' ')
if [ "$nhits" -gt 0 ]; then
  printf '%s\n' "$hits" | head -n 80 | sed 's/^/  /'
  [ "$nhits" -gt 80 ] && echo "  …（还有 $((nhits - 80)) 行，直接看 git diff）"
else
  echo "  （未识别到编号变化——可能改的是叙述/白话，仍需人工扫一眼 diff）"
fi

echo ""
if [ -n "$head_sha" ]; then
  echo "复核完成后写入新起点:  mkdir -p docs/reviews && echo \"$head_sha $(date +%F)\" > $MARKER"
else
  echo "（尚无提交——先提交一次,再把 HEAD 写入 $MARKER 作为起点）"
fi
exit 0
