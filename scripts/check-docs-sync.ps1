# check-docs-sync.ps1 — 与 check-docs-sync.sh 等价(Windows)。
# 只查"有没有动过",不判对错(docs/reviews/ 对账留档=历史快照,不算"文档已同步")。
#
# 用法:
#   powershell -File check-docs-sync.ps1
#   powershell -File check-docs-sync.ps1 -Staged
#   powershell -File check-docs-sync.ps1 -Strict
#   powershell -File check-docs-sync.ps1 -Base <ref>
#
# 按项目改下面三组(路径都从仓库根算,用正斜杠):
param(
  [switch]$Staged,
  [switch]$Strict,
  [string]$Base = ""
)

# CODE_GLOB(项目定制):代码集中在 app / bench / tests / web + run.py——目录式判定比扩展名式更准
# (避免 scripts/ 等辅助文件被当成"代码改动"而误报)。
$codeGlob = '^(app|bench|tests|web)/|^run\.py$'
$docGlob  = '^docs/'
$l1Files  = @('AGENTS.md','CLAUDE.md','.cursorrules','.cursor/rules/project.mdc','.windsurfrules','.github/copilot-instructions.md')

if (-not (git rev-parse --is-inside-work-tree 2>$null)) { exit 0 }

# 所有 diff 显式带 -c core.autocrlf=true:不依赖运行方 git 的全局配置——
# "仓库在 Windows 检出为 CRLF、脚本在 WSL/未配 autocrlf 的 git 下运行"时,
# 工作区 CRLF vs index LF 会整仓误判为已改动(--strict 下挡住每次提交)。
# 代价:纯换行符改动(CRLF↔LF)不再出现在改动列表——这类改动本就不需要同步文档,接受。
if ($Staged) {
  $changed = git -c core.autocrlf=true diff --cached --name-only
} elseif ($Base) {
  $changed = git -c core.autocrlf=true diff --name-only "$Base...HEAD"
} else {
  # 默认(工作区)模式:对比 HEAD 并纳入"未跟踪"文件(新项目常未 git add;unborn HEAD 时 git diff 还会报错)。
  $changed = @()
  $changed += @(git -c core.autocrlf=true diff --name-only HEAD 2>$null)
  $changed += @(git ls-files --others --exclude-standard 2>$null)
}

if (-not $changed) { exit 0 }

$codeHit = $false; $docHit = $false
foreach ($f in $changed) {
  if ([string]::IsNullOrWhiteSpace($f)) { continue }
  # docs/reviews/ = 对账留档(历史快照)——改它不算"文档已同步"(与 check-doc-refs 的 DOC_EXCLUDE 同一拍板,2026-10-17)
  if ($f -like 'docs/reviews/*') { continue }
  if ($f -match $docGlob) { $docHit = $true }
  if ($l1Files -contains $f) { $docHit = $true }
  if ($f -match $codeGlob) { $codeHit = $true }
}

if ((-not $codeHit) -and (-not $docHit)) {
  Write-Host '[check-docs-sync] 本次改动未匹配到任何代码/文档文件——若属配置问题,请检查顶部 CODE_GLOB / DOC_GLOB。'
}

if ($codeHit -and -not $docHit) {
  Write-Host "[check-docs-sync] 本次改了代码,但 docs/ 和 L1 记忆文件都没动。" -ForegroundColor Yellow
  Write-Host "                 确认对应层文档 / 不变量 / ADR 是否需同步?(见 L1「铁律 1」)"
  if ($Strict) { exit 1 }
}
exit 0
