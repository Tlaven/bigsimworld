# check-doc-refs.ps1 — 结构性对账:docs/ 里的死链(含大小写错链:目标存在但大小写不一致,大小写敏感系统上会断)、未填占位符、标了 N2 却缺 `**验收**` / 没有「危险实现清单」、模块文档缺「失败语义」、危险实现清单行未填(空/占位符)、现状文档引记录。
# 用法:
#   powershell -File check-doc-refs.ps1
#   powershell -File check-doc-refs.ps1 -Strict
param([switch]$Strict)
$ErrorActionPreference = 'SilentlyContinue'

# 按项目改:文档扩展名(含点)。默认同时认 .md 与 .markdown。
$DocExt = @('.md', '.markdown')

# 按项目改:对账要排除的路径(正则,匹配即跳过)。排除"不是本项目当前维护的文档"的那些:考古 / 存档层
# (如 docs/legacy/)、对账留档(docs/reviews/——历史快照,引用退役术语/旧链接是常态,
# 不是错误)与待填件目录(本项目 = docs-templates/)。
# 置空字符串则不过滤。
$DocExclude = '^(docs/legacy/|docs/archive/|docs/templates/|docs-templates/|docs/reviews/)'

$root = (git rev-parse --show-toplevel 2>$null)
if (-not $root) { $root = (Get-Location).Path }
Set-Location $root
if (-not (Test-Path 'docs')) { Write-Host '[check-doc-refs] 无 docs/,跳过'; exit 0 }

$docsMd = Get-ChildItem -Path 'docs' -Recurse -File | Where-Object { $DocExt -ccontains $_.Extension }
if (($docsMd | Measure-Object).Count -eq 0) {
  Write-Host "[check-doc-refs] 警告:docs/ 下没有匹配 DocExt=$($DocExt -join ',') 的文件。"
  Write-Host '                 若你的文档用别的扩展名,改脚本顶部的 DocExt / DOC_EXT。'
  exit 0
}

# 排除考古 / 存档层(不是本项目当前维护的文档;见顶部 $DocExclude)
if ($DocExclude) {
  $docsMd = @($docsMd | Where-Object {
    $rel = $_.FullName.Substring($root.Length).TrimStart('\','/').Replace('\','/')
    $rel -notmatch $DocExclude
  })
}

$found = $false

# HTML 注释剥离(行数保真;模板引导注释不算正文)——#3 计数与 #4 引用扫描共用
function Strip-Comments([string[]]$lines) {
  $out = New-Object System.Collections.Generic.List[string]
  $inC = $false
  foreach ($line in $lines) {
    $buf = $line; $outLine = ''
    while ($buf -ne '') {
      if ($inC) {
        $i = $buf.IndexOf('-->')
        if ($i -lt 0) { $buf = ''; break }
        $buf = $buf.Substring($i + 3); $inC = $false
      } else {
        $i = $buf.IndexOf('<!--')
        if ($i -lt 0) { $outLine += $buf; $buf = ''; break }
        $outLine += $buf.Substring(0, $i)
        $buf = $buf.Substring($i + 4); $inC = $true
      }
    }
    $out.Add($outLine)
  }
  return ,$out
}

# 1) 死链
foreach ($f in $docsMd) {
  $rel = $f.FullName.Substring($root.Length).TrimStart('\','/').Replace('\','/')
  $text = Get-Content -Raw -LiteralPath $f.FullName -Encoding UTF8
  foreach ($m in [regex]::Matches($text, '\]\(([^)]+)\)')) {
    $t = $m.Groups[1].Value
    if ($t -match '^(https?:|#|mailto:)') { continue }
    $t = ($t -split '#')[0]
    if ([string]::IsNullOrWhiteSpace($t)) { continue }
    if ($t -notmatch '[/.]') { continue }   # 只看"像路径"的目标,跳过 `](被拒)` 这类标注
    $cand1 = Join-Path $f.DirectoryName $t
    $cand2 = Join-Path $root $t
    # 存在性之后再做字面大小写比对:大小写不敏感文件系统(Windows/默认 macOS)会放过
    # 错大小写链接,在大小写敏感系统(Linux CI)上会断。-ceq = 大小写敏感比较。
    $exact = $false; $caseHit = $false
    foreach ($p in @($cand1, $cand2)) {
      if (Test-Path -LiteralPath $p) {
        $base = [IO.Path]::GetFileName($p)
        if ([string]::IsNullOrEmpty($base)) { $exact = $true; continue }   # 尾斜杠目录链接:不比大小写
        $dir  = [IO.Path]::GetDirectoryName($p)
        if (Get-ChildItem -LiteralPath $dir -Force -ErrorAction SilentlyContinue |
              Where-Object { $_.Name -ceq $base }) { $exact = $true }
        else { $caseHit = $true }
      }
    }
    if (-not $exact) {
      if ($caseHit) {
        Write-Host "[case-mismatch] ${rel} -> $t(目标存在但大小写不一致,大小写敏感系统上会断)"
      } else {
        Write-Host "[dead-link] ${rel} -> $t"
      }
      $found = $true
    }
  }
}

# 2) 未填占位符 / TODO
$ph = $docsMd | Select-String -Pattern 'TODO|TBD|与用户对话后填|novelty=N[?]|未填写|待补充' -Encoding UTF8
if ($ph) {
  Write-Host '[placeholder] docs/ 仍有未填占位符 / TODO:'
  $ph | ForEach-Object { $relp = $_.Path.Substring($root.Length).TrimStart('\','/').Replace('\','/'); Write-Host "  ${relp}:$($_.LineNumber):$($_.Line)" }
  $found = $true
}

# 3) 标了 N2 却缺 `**验收**`
#    先剥掉 HTML 注释——模板引导文字本身含这些词,不剥会把计数算花(假阴性)。
$targets = @()
# 按项目改:下面是"可能含 N2 条目"的文档(L4 / L2 公共节 / L3)。
# L2 文件名若不是 docs/architecture.md(项目自定义 L2 名),把实际名字加进这张表。
foreach ($n in @('docs/core-code.md','docs/core-code.markdown','docs/architecture.md','docs/architecture.markdown')) { if (Test-Path $n) { $targets += $n } }
if (Test-Path 'docs/modules') {
  $targets += (Get-ChildItem 'docs/modules' -File | Where-Object { $DocExt -ccontains $_.Extension } | ForEach-Object { $_.FullName.Substring($root.Length).TrimStart('\','/').Replace('\','/') })
}
foreach ($f in $targets) {
  $raw = Get-Content -Raw -LiteralPath $f -Encoding UTF8
  if ($null -eq $raw) { continue }
  $body = (Strip-Comments ($raw -split "`n")) -join "`n"
  $n2  = ([regex]::Matches($body, 'novelty=N2')).Count
  $acc = ([regex]::Matches($body, '\*\*验收\*\*')).Count
  if ($n2 -gt $acc) {
    Write-Host "[n2-missing-verification] $($f): N2 条目 $n2 个,「**验收**」仅 $acc 处"
    $found = $true
  }
  # 指针形(模块按 N2 路由把正文记在公共处、只留一行指针)
  $pointer = ($body -match '\*\*验收\*\*[^\r]*见 *`?docs/')
  # 标了 N2 却没有「危险实现清单」(指针形除外)
  $dan = ([regex]::Matches($body, '危险实现清单')).Count
  if (($n2 -gt 0) -and ($dan -eq 0) -and (-not $pointer)) {
    Write-Host "[n2-missing-checklist] $($f): 标了 N2 却没有「危险实现清单」"
    $found = $true
  }
  # 模块文档必须有「失败语义」一节(覆盖 N1;指针形除外)
  if (($f -like 'docs/modules/*') -and (-not $pointer) -and ($body -notmatch '失败语义')) {
    Write-Host "[module-missing-failure-semantics] $($f): 模块文档没有「失败语义」一节"
    $found = $true
  }
}

# 4) 现状文档里出现指向"记录类文档"的引用
#    规则(E1):现状 / 规则陈述必须**自足**,不许挂到记录类文档上当依据;
#    "要理由 / 被拒方案 / 来由时去哪读"的引用只许写在**入口类文档的导航位**(那类不扫)。
#    按项目改:LIVE_DOCS = 现状 / 规则类文档(默认 L2 是 docs/architecture.md;L2 改名或另有现状类文档时加进来)。
$liveDocs = @('docs/architecture.md','docs/architecture.markdown','docs/glossary.md','docs/glossary.markdown','docs/engineering-spec.md','docs/cluster-contract.md')
foreach ($n in @('docs/core-code.md','docs/core-code.markdown')) { if (Test-Path $n) { $liveDocs += $n } }
if (Test-Path 'docs/modules') {
  $liveDocs += (Get-ChildItem 'docs/modules' -File | Where-Object { $DocExt -ccontains $_.Extension } | ForEach-Object { $_.FullName.Substring($root.Length).TrimStart('\','/').Replace('\','/') })
}
$refPat = 'docs/decisions/|docs/reviews/|ADR-\d{3}|adr-\d{3}-'
foreach ($f in $liveDocs) {
  if (-not (Test-Path -LiteralPath $f)) { continue }
  $raw = Get-Content -Raw -LiteralPath $f -Encoding UTF8
  if ($null -eq $raw) { continue }
  $ln = 0
  foreach ($line in (Strip-Comments ($raw -split "`n"))) {   # 剥注释:引导注释里的示例引用不算正文
    $ln++
    if ($line -match '⚠') { continue }   # E1 的状态标记(带不带变体选择符都算),不是依据
    if ($line -match $refPat) {
      Write-Host "[live-doc-refs] ${f}:${ln}:${line}: 现状类文档引了记录类文档(现状陈述须自足;理由类引用请挪到入口类文档的导航位)"
      $found = $true
    }
  }
}

# 5) 危险实现清单的行级粗检:数据行的「挡住者」列要有内容、不能是占位符
#    列位置由表头定位(找含"挡住"的那一列;表头没有这一列 → 不猜、不报),因此**不看列数与写法**。
#    起始形态:标题(`### 危险实现清单…`)或粗体(`**危险实现清单**——`,含 `- ` 前缀);
#    表结束(表开始后的第一个非表行)即停止——避免把同节后续的普通表格算进来。
#    机器只查"填没填";写法是否真挡得住仍是 teach-back 验证者的事
foreach ($f in $targets) {
  $raw = Get-Content -Raw -LiteralPath $f -Encoding UTF8
  if ($null -eq $raw) { continue }
  $ln2 = 0; $inSec = $false; $inTab = $false; $bcol = -1
  foreach ($line in (Strip-Comments ($raw -split "`n"))) {
    $ln2++
    if ($line -match '^#+\s*\**危险实现清单' -or $line -match '^(\s*-\s+)?\*\*危险实现清单') { $inSec = $true; $inTab = $false; $bcol = -1; continue }
    if (-not $inSec) { continue }
    if ($line -match '^#') { $inSec = $false; $inTab = $false; $bcol = -1; continue }
    if ($line -match '^\|') {
      $cells = $line -split '\|'
      if (-not $inTab) {   # 表头行:定位"挡住者"列
        $inTab = $true; $bcol = -1
        for ($j = 1; $j -lt $cells.Count; $j++) { if ($cells[$j] -match '挡住') { $bcol = $j; break } }
        continue
      }
      if ($bcol -lt 0) { continue }   # 表头没有"挡住"列 → 不猜
      if ($line -match '^\|[\s:|-]+\|\s*$') { continue }   # 分隔行
      $cell = ''
      if ($cells.Count -gt $bcol) { $cell = $cells[$bcol] }
      $lc = $cell.Trim().ToLower()
      if ($lc -eq '' -or $lc -match '^(-|—|待补|tbd|todo|\?|n/a)$') {
        Write-Host "[danger-blocker] ${f}:${ln2}:${line}: 危险实现清单行未填(""挡住者""列为空 / 占位符)"
        $found = $true
      }
      continue
    }
    if ($inTab) { $inSec = $false; $inTab = $false; $bcol = -1 }   # 表后首个非表行 → 结束
  }
}

if (-not $found) {
  Write-Host "[check-doc-refs] 无结构性发现(扫描 $($docsMd.Count) 个文档)。"
} else {
  Write-Host '[check-doc-refs] 以上为结构性提醒;语义一致性请跑 teach-back 验证者。'
  if ($Strict) { exit 1 }
}
exit 0
