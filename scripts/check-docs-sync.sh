#!/usr/bin/env bash
# check-docs-sync.sh — 最小检查器:代码变了,但本项目当前维护的文档(docs/ 除 reviews/——对账留档是历史快照,不算同步)和 L1 记忆文件都没动 → 提醒。
# Windows:本文件必须以 LF 检出(项目根 `.gitattributes` 加 `*.sh text eol=lf`)——CRLF 在 Linux / WSL / CI 上会直接语法错,pre-commit 反过来挡住每次提交(Git Bash 多数版本能容忍,但别赌)。
# 它只查"有没有动过",不判对错(判对错交给 teach-back 验证者)。
#
# 用法:
#   bash check-docs-sync.sh              # 工作区 vs HEAD
#   bash check-docs-sync.sh --staged     # 只查暂存区(pre-commit 用)
#   bash check-docs-sync.sh --strict     # 触发时退出码 1(可当门禁);默认只提醒、退 0
#   bash check-docs-sync.sh <base-ref>   # 对比 <base-ref>...HEAD
#
# 按项目改下面三组(路径都从仓库根算,用正斜杠):
# CODE_GLOB(项目定制):代码集中在 app / bench / tests / web + run.py——目录式判定比扩展名式更准
# (避免 scripts/ 等辅助文件被当成"代码改动"而误报)。
CODE_GLOB='^(app|bench|tests|web)/|^run\.py$'
DOC_GLOB='^docs/'
L1_FILES='AGENTS.md CLAUDE.md .cursorrules .cursor/rules/project.mdc .windsurfrules .github/copilot-instructions.md'

set -u
STRICT=0; STAGED=0; BASE=""
for a in "$@"; do
  case "$a" in
    --strict) STRICT=1 ;;
    --staged) STAGED=1 ;;
    *)        BASE="$a" ;;
  esac
done

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0

# 所有 diff 显式带 -c core.autocrlf=true:不依赖运行方 git 的全局配置——
# "仓库在 Windows 检出为 CRLF、脚本在 WSL/未配 autocrlf 的 git 下运行"时,
# 工作区 CRLF vs index LF 会整仓误判为已改动(--strict 下挡住每次提交)。
# 代价:纯换行符改动(CRLF↔LF)不再出现在改动列表——这类改动本就不需要同步文档,接受。

if [ "$STAGED" = 1 ]; then
  CHANGED=$(git -c core.autocrlf=true diff --cached --name-only)
elif [ -n "$BASE" ]; then
  CHANGED=$(git -c core.autocrlf=true diff --name-only "$BASE"...HEAD)
else
  # 默认(工作区)模式:对比 HEAD,并顺带纳入"未跟踪"文件——
  # 新项目里代码/文档常还没 git add,git diff 看不到它们;且 unborn HEAD(还没首次提交)时 git diff HEAD 会报错。
  CHANGED=$(
    { git -c core.autocrlf=true diff --name-only HEAD 2>/dev/null || true
      git ls-files --others --exclude-standard 2>/dev/null || true
    }
  )
fi

[ -z "$CHANGED" ] && exit 0

code_hit=0; doc_hit=0
while IFS= read -r f; do
  [ -z "$f" ] && continue
  # docs/reviews/ = 对账留档(历史快照)——改它不算"文档已同步"(与 check-doc-refs 的 DOC_EXCLUDE 同一拍板,2026-10-17)
  case "$f" in docs/reviews/*) continue ;; esac
  printf '%s' "$f" | grep -Eq "$DOC_GLOB" && doc_hit=1
  for l1 in $L1_FILES; do
    [ "$f" = "$l1" ] && doc_hit=1
  done
  printf '%s' "$f" | grep -Eq "$CODE_GLOB" && code_hit=1
done <<EOF
$CHANGED
EOF

if [ "$code_hit" = 0 ] && [ "$doc_hit" = 0 ]; then
  echo "[check-docs-sync] 本次改动未匹配到任何代码/文档文件——若属配置问题,请检查顶部 CODE_GLOB / DOC_GLOB。"
fi

if [ "$code_hit" = 1 ] && [ "$doc_hit" = 0 ]; then
  echo "[check-docs-sync] 本次改了代码,但 docs/ 和 L1 记忆文件都没动。"
  echo "                 确认对应层文档 / 不变量 / ADR 是否需同步?(见 L1「铁律 1」)"
  [ "$STRICT" = 1 ] && exit 1
fi
exit 0
