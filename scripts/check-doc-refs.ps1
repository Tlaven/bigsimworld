# check-doc-refs.ps1 — 结构性对账:docs/ 里的死链、未填占位符、标了 N2 却缺「验收」。
# 用法:
#   powershell -File check-doc-refs.ps1
#   powershell -File check-doc-refs.ps1 -Strict
param([switch]$Strict)
$ErrorActionPreference = 'SilentlyContinue'

# 按项目改:文档扩展名(含点)。默认同时认 .md 与 .markdown。
$DocExt = @('.md', '.markdown')

# 按项目改:对账要排除的路径(正则,匹配即跳过)。默认排除"非活契约":考古 / 存档层
# (如 docs/legacy/)与模板 stub 目录(docs/templates/——有些项目把模板放在 docs/ 内)。
# 置空字符串则不过滤。
$DocExclude = '^(docs/legacy/|docs/archive/|docs/templates/|docs-templates/)'

$root = (git rev-parse --show-toplevel 2>$null)
if (-not $root) { $root = (Get-Location).Path }
Set-Location $root
if (-not (Test-Path 'docs')) { Write-Host '[check-doc-refs] 无 docs/,跳过'; exit 0 }

$docsMd = Get-ChildItem -Path 'docs' -Recurse -File | Where-Object { $DocExt -contains $_.Extension }
if (($docsMd | Measure-Object).Count -eq 0) {
  Write-Host "[check-doc-refs] 警告:docs/ 下没有匹配 DocExt=$($DocExt -join ',') 的文件。"
  Write-Host '                 若你的文档用别的扩展名,改脚本顶部的 $DocExt。'
  exit 0
}

# 排除考古 / 存档层(非活契约;见顶部 $DocExclude)
if ($DocExclude) {
  $docsMd = @($docsMd | Where-Object {
    $rel = $_.FullName.Substring($root.Length).TrimStart('\','/').Replace('\','/')
    $rel -notmatch $DocExclude
  })
}

$found = $false

# 1) 死链
foreach ($f in $docsMd) {
  $text = Get-Content -Raw -LiteralPath $f.FullName -Encoding UTF8
  foreach ($m in [regex]::Matches($text, '\]\(([^)]+)\)')) {
    $t = $m.Groups[1].Value
    if ($t -match '^(https?:|#|mailto:)') { continue }
    $t = ($t -split '#')[0]
    if ([string]::IsNullOrWhiteSpace($t)) { continue }
    if ($t -notmatch '[/.]') { continue }   # 只看"像路径"的目标,跳过 `](被拒)` 这类标注
    $cand1 = Join-Path $f.DirectoryName $t
    $cand2 = Join-Path $root $t
    if (-not (Test-Path $cand1) -and -not (Test-Path $cand2)) {
      Write-Host "[dead-link] $($f.Name) -> $t"; $found = $true
    }
  }
}

# 2) 未填占位符 / TODO
$ph = $docsMd | Select-String -Pattern 'TODO|TBD|与用户对话后填|novelty=N[?]|未填写|待补充' -Encoding UTF8
if ($ph) {
  Write-Host '[placeholder] docs/ 仍有未填占位符 / TODO:'
  $ph | ForEach-Object { Write-Host "  $($_.Path):$($_.LineNumber)" }
  $found = $true
}

# 3) 标了 N2 却缺「验收」
#    先剥掉 HTML 注释——模板引导文字本身含这些词,不剥会把计数算花(假阴性)。
$targets = @()
foreach ($n in @('docs/core-code.md','docs/core-code.markdown')) { if (Test-Path $n) { $targets += $n } }
if (Test-Path 'docs/modules') {
  $targets += (Get-ChildItem 'docs/modules' -File | Where-Object { $DocExt -contains $_.Extension } | ForEach-Object { $_.FullName })
}
foreach ($f in $targets) {
  $raw = Get-Content -Raw -LiteralPath $f -Encoding UTF8
  if ($null -eq $raw) { continue }
  $body = [regex]::Replace($raw, '(?s)<!--.*?-->', '')
  $n2  = ([regex]::Matches($body, 'novelty=N2')).Count
  $acc = ([regex]::Matches($body, '\*\*验收\*\*')).Count
  if ($n2 -gt $acc) {
    Write-Host "[n2-missing-verification] $($f): N2 条目 $n2 个,「**验收**」仅 $acc 处"
    $found = $true
  }
}

if (-not $found) {
  Write-Host "[check-doc-refs] 无结构性发现(扫描 $($docsMd.Count) 个文档)。"
} else {
  Write-Host '[check-doc-refs] 以上为结构性提醒;语义一致性请跑 teach-back 验证者。'
  if ($Strict) { exit 1 }
}
exit 0
