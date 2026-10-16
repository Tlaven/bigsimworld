# check-docs-sync.ps1 — 与 check-docs-sync.sh 等价(Windows)。
# 只查"有没有动过",不判对错。
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

# CODE_GLOB 默认按"代码文件扩展名"判定(适配"代码散落/在根目录"的项目);
# 若代码集中在某几个目录,改成目录式更准,如: '^(src|lib|app|packages)/'
$codeGlob = '^(app|bench|tests|web)/|^run\.py$'
$docGlob  = '^docs/'
$l1Files  = @('AGENTS.md','CLAUDE.md','.cursorrules','.cursor/rules/project.mdc','.windsurfrules','.github/copilot-instructions.md')

if (-not (git rev-parse --is-inside-work-tree 2>$null)) { exit 0 }

if ($Staged) {
  $changed = git diff --cached --name-only
} elseif ($Base) {
  $changed = git diff --name-only "$Base...HEAD"
} else {
  # 默认(工作区)模式:对比 HEAD 并纳入"未跟踪"文件(新项目常未 git add;unborn HEAD 时 git diff 还会报错)。
  $changed = @()
  $changed += @(git diff --name-only HEAD 2>$null)
  $changed += @(git ls-files --others --exclude-standard 2>$null)
}

if (-not $changed) { exit 0 }

$codeHit = $false; $docHit = $false
foreach ($f in $changed) {
  if ([string]::IsNullOrWhiteSpace($f)) { continue }
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
