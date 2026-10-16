#!/usr/bin/env bash
# check-docs-sync.sh — 最小检查器:代码变了,但 docs/ 和 L1 记忆文件都没动 → 提醒。
# Windows:本文件必须以 LF 检出(项目根 `.gitattributes` 加 `*.sh text eol=lf`)——CRLF 会让 bash 拒绝执行,pre-commit 反过来挡住每次提交。
# 它只查"有没有动过",不判对错(判对错交给 teach-back 验证者)。
#
# 用法:
#   bash check-docs-sync.sh              # 工作区 vs HEAD
#   bash check-docs-sync.sh --staged     # 只查暂存区(pre-commit 用)
#   bash check-docs-sync.sh --strict     # 触发时退出码 1(可当门禁);默认只提醒、退 0
#   bash check-docs-sync.sh <base-ref>   # 对比 <base-ref>...HEAD
#
# 按项目改下面三组(路径都从仓库根算,用正斜杠):
# CODE_GLOB 默认按"代码文件扩展名"判定(适配"代码散落/在根目录"的项目);
# 若你的代码集中在某几个目录,改成目录式更准,如: '^(src|lib|app|packages)/'
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

if [ "$STAGED" = 1 ]; then
  CHANGED=$(git diff --cached --name-only)
elif [ -n "$BASE" ]; then
  CHANGED=$(git diff --name-only "$BASE"...HEAD)
else
  # 默认(工作区)模式:对比 HEAD,并顺带纳入"未跟踪"文件——
  # 新项目里代码/文档常还没 git add,git diff 看不到它们;且 unborn HEAD(还没首次提交)时 git diff HEAD 会报错。
  CHANGED=$(
    { git diff --name-only HEAD 2>/dev/null || true
      git ls-files --others --exclude-standard 2>/dev/null || true
    }
  )
fi

[ -z "$CHANGED" ] && exit 0

code_hit=0; doc_hit=0
while IFS= read -r f; do
  [ -z "$f" ] && continue
  printf '%s' "$f" | grep -Eq "$DOC_GLOB" && doc_hit=1
  for l1 in $L1_FILES; do
    [ "$f" = "$l1" ] && doc_hit=1
  done
  printf '%s' "$f" | grep -Eq "$CODE_GLOB" && code_hit=1
done <<EOF
$CHANGED
EOF

if [ "$code_hit" = 0 ] && [ "$doc_hit" = 0 ]; then
  echo "[check-docs-sync] 本次改动未匹配到任何代码/文档文件——若属配置问题,请检查顶部 CODE_GLOB / DOC_GLOB。" >&2
fi

if [ "$code_hit" = 1 ] && [ "$doc_hit" = 0 ]; then
  echo "[check-docs-sync] 本次改了代码,但 docs/ 和 L1 记忆文件都没动。" >&2
  echo "                 确认对应层文档 / 不变量 / ADR 是否需同步?(见 L1「铁律 1」)" >&2
  [ "$STRICT" = 1 ] && exit 1
fi
exit 0
