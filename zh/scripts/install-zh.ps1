# Claude Desktop 简体中文汉化 - 安装脚本 (Windows)
# 原理（实测验证）：
#   1. 前端词表部署到 ion-dist\i18n\zh-Hans.json（在 app.asar 之外，不受完整性校验约束）
#   2. dynamic\zh-Hans.json 必须存在，否则前端 JSON.parse 失败会丢弃整份词表
#   3. 前端语言白名单（在 bundle JS 中）加入 zh-Hans，否则渲染进程匹配不到中文会主动回写 en-US
#   4. config.json 的 locale 设为 zh-Hans
#   5. shell 层：resources\zh-Hans.json 合入 shell-overlay-zh.json（标题栏/管理配置窗口/菜单对话框）
$ErrorActionPreference = 'Stop'
$script:FailCount = 0
# ---------- 0a-2. 对齐 Python 输出编码（消除中文乱码） ----------
# 现象：内核汉化 / 源码汉化步骤的中文输出显示成「宸叉洿鏂?」之类乱码。
# 原因：内置运行时为 Python 3.15，自 3.15 起默认启用 UTF-8 模式（PEP 686），
#       经管道输出的是 UTF-8 字节；而 PowerShell 捕获外部程序输出时按
#       [Console]::OutputEncoding（中文 Windows 为 GBK/936）解码，两者不一致
#       即成乱码。（未捕获、直连控制台的调用走 WriteConsoleW，故不受影响。）
# 处理：显式把 Python 的 std 流对齐到当前控制台代码页，再供 PowerShell 解码。
try {
  $script:ConsoleCP = [Console]::OutputEncoding.CodePage
  if ($script:ConsoleCP -eq 65001) { $env:PYTHONIOENCODING = 'utf-8' }
  else                             { $env:PYTHONIOENCODING = 'cp' + $script:ConsoleCP }
} catch {
  $env:PYTHONIOENCODING = 'gbk'
}

# ---------- 0a-1. 环境变量大小写去重 ----------
# 实测（2026-10-15）：进程环境同时存在 HTTPS_PROXY 与 https_proxy（仅大小写不同）时，
# .NET Start-Process 构建环境块会抛「已添加项。字典中的关键字:HTTPS_PROXY」，导致
# 带输出重定向的守护进程启动静默失败、stderr 丢失。保留大写、删除小写副本（仅影响
# 本安装进程，不改动用户/注册表环境变量）。
foreach ($v in @('http_proxy','https_proxy','no_proxy','all_proxy','ftp_proxy')) {
  $lower = [Environment]::GetEnvironmentVariable($v, 'Process')
  $upper = [Environment]::GetEnvironmentVariable($v.ToUpperInvariant(), 'Process')
  if ($lower -and $upper) {
    try { Remove-Item ('Env:' + $v) -ErrorAction Stop } catch { }
  }
}

$script:lastT = Get-Date
function Write-Step($msg) {
  $d = (Get-Date) - $script:lastT
  $script:lastT = Get-Date
  Write-Host ("{0,4}s  {1}" -f ([int]$d.TotalSeconds), $msg) -ForegroundColor Cyan
}
function Write-Ok($msg)   { Write-Host ("  [OK] " + $msg) -ForegroundColor Green }
function Write-Warn2($msg){ Write-Host ("  [警告] " + $msg) -ForegroundColor Yellow }
function Write-Bad($msg)  { Write-Host ("  [失败] " + $msg) -ForegroundColor Red; $script:FailCount++ }

# ---------- 0a. 安装日志 ----------
# 控制台输出在部分环境下会被截断，日志同时落到
# %USERPROFILE%\.claude\zh\install.log，便于排障与回溯。
# 统一路径约定（v2.7）：所有运行时汉化文件（日志/备份/守护进程/payload/基线）
# 一律存放于用户目录 %USERPROFILE%\.claude\zh\，不再散落 %LOCALAPPDATA%。
$zhLogHome = Join-Path $env:USERPROFILE '.claude\zh'
if (-not (Test-Path $zhLogHome)) { New-Item -ItemType Directory -Path $zhLogHome -Force | Out-Null }
try {
  Start-Transcript -Path (Join-Path $zhLogHome 'install.log') -Force -ErrorAction Stop | Out-Null
} catch { }

# ---------- 0. 管理员检查 ----------
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$isAdmin = [Security.Principal.WindowsPrincipal]::new($id).IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)
if (-not $isAdmin) {
  Write-Host '需要管理员权限（修改 WindowsApps 下的应用资源）。请右键以管理员身份运行 安装.cmd。' -ForegroundColor Red
  Stop-Transcript -ErrorAction SilentlyContinue | Out-Null; exit 2
}

Write-Host ''
Write-Host '============================================' -ForegroundColor Cyan
Write-Host '  Claude Desktop 简体中文汉化 - 安装' -ForegroundColor Cyan
Write-Host '============================================' -ForegroundColor Cyan
Write-Host ''

# ---------- 1. 定位 Claude 安装包（优先 AppX 注册版本 = 实际运行版本） ----------
Write-Step '[1/8] 检测 Claude Desktop 安装...'
$regVersion = $null
try {
  $apx = Get-AppxPackage -Name Claude -ErrorAction Stop
  if ($apx -and $apx.Version) { $regVersion = [string]$apx.Version }
} catch { }
$allPkgs = Get-ChildItem "$env:ProgramFiles\WindowsApps" -Directory -Filter 'Claude_*' -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -match '^Claude_\d+\.\d+\.\d+\.\d+_' -and (Test-Path (Join-Path $_.FullName 'app\resources\ion-dist\i18n\en-US.json')) }
$pkg = $null
if ($regVersion) {
  $pkg = $allPkgs | Where-Object { ($_.Name -split '_')[1] -eq $regVersion } | Select-Object -First 1
  if ($pkg) { Write-Ok ("AppX 注册版本（实际运行版本）: $regVersion") }
}
if (-not $pkg) {
  $pkg = $allPkgs | Sort-Object { [version]($_.Name -split '_')[1] } -Descending | Select-Object -First 1
  if ($pkg) { Write-Warn2 ("未取到 AppX 注册版本，退化为最新目录版本: " + ($pkg.Name -split '_')[1]) }
}
if (-not $pkg) { Write-Bad '未在 WindowsApps 下找到可用的 Claude 安装（含 ion-dist\i18n）。'; Stop-Transcript -ErrorAction SilentlyContinue | Out-Null; exit 1 }
# 提示存在多版本共存（未激活版本不处理）
$stale = $allPkgs | Where-Object { $_.FullName -ne $pkg.FullName }
foreach ($s in $stale) { Write-Warn2 ("检测到未激活的旧版本目录（跳过，如需处理请先卸载汉化后重装）: " + $s.Name) }
$version = ($pkg.Name -split '_')[1]
$res  = Join-Path $pkg.FullName 'app\resources'
$i18n = Join-Path $res 'ion-dist\i18n'
$v1   = Join-Path $res 'ion-dist\assets\v1'
Write-Ok ("检测到 Claude $version")
Write-Host ("        " + $pkg.FullName)

# AUMID（用于生成"Claude 中文版"启动器）：优先 Get-AppxPackage 包族名，
# 退化为包目录名推导（Claude_<ver>_<arch>__<pub> -> Claude_<pub>）。
# 应用 ID 优先 Get-StartApps 实测，默认 Claude。全程运行时探测，无硬编码。
$appFamily = $null
try { $appFamily = (Get-AppxPackage -Name Claude -ErrorAction Stop).PackageFamilyName } catch { }
if (-not $appFamily -and $pkg.Name -match '^([^_]+)_.*__([^_]+)$') { $appFamily = ($Matches[1] + '_' + $Matches[2]) }
$appId = 'Claude'
try {
  $sa = Get-StartApps -ErrorAction Stop | Where-Object { $_.AppID -like ($appFamily + '!*') } | Select-Object -First 1
  if ($sa) { $appId = ($sa.AppID -split '!')[-1] }
} catch { }
$aumid = "$(if ($appFamily) { $appFamily } else { '' })!$appId"

# ---------- 1b. 自动退出正在运行的 Claude ----------
# 实测：Claude 运行时会占用并自修复其资源文件，补丁/还原会被静默覆盖，
# 因此必须在改文件前完全退出 Claude（含后台进程）。
$claudeProcs = @(Get-Process -ErrorAction SilentlyContinue |
  Where-Object { $_.ProcessName -match '^claude' })
if ($claudeProcs.Count -gt 0) {
  Write-Step '[1b] 退出正在运行的 Claude（避免文件被占用或自修复）...'
  # 多轮强制退出直至清零：启动中途会有子进程陆续孵化，一次性 Stop 后
  # 仍可能残留并锁定目标文件（2026-10-15 实测：残留进程导致 asar integrity
  # 补丁/还原 PermissionError）。
  $stoppedTotal = 0
  foreach ($round in 1..5) {
    $alive = @(Get-Process -ErrorAction SilentlyContinue |
      Where-Object { $_.ProcessName -match '^claude' })
    if ($alive.Count -eq 0) { break }
    foreach ($p in $alive) {
      try { Stop-Process -Id $p.Id -Force -ErrorAction Stop; $stoppedTotal++ } catch { }
    }
    Start-Sleep -Seconds 2
  }
  Write-Ok ('已退出 ' + $stoppedTotal + ' 个 Claude 进程（已确认全部关闭）')
}

# ---------- 2. 兼容检测：白名单与语言名映射所在文件 ----------
Write-Step '[2/8] 检测前端资源结构...'
$wlOld  = '"en-US","de-DE","fr-FR","ko-KR","ja-JP","es-419","es-ES","it-IT","hi-IN","pt-BR","id-ID"'
$wlNew  = '"en-US","zh-Hans","de-DE","fr-FR","ko-KR","ja-JP","es-419","es-ES","it-IT","hi-IN","pt-BR","id-ID"'
$nmOld  = '{"en-US":{name:"English (United States)",localName:"English (United States)"},'
# 注意：JS 补丁按字节(Latin1)写回，中文字面量必须写作 JS 的 \uXXXX 转义（ASCII 安全）
$nmNew  = '{"en-US":{name:"English (United States)",localName:"English (United States)"},"zh-Hans":{name:"Chinese (Simplified)",localName:"\u7B80\u4F53\u4E2D\u6587"},'

$latin = [Text.Encoding]::GetEncoding(28591)  # Latin1：字节级无损读写
function Find-TextInJs($dir, $needle) {
  foreach ($f in (Get-ChildItem $dir -Filter '*.js' -ErrorAction SilentlyContinue)) {
    $s = $latin.GetString([IO.File]::ReadAllBytes($f.FullName))
    if ($s.Contains($needle)) { return $f.FullName }
  }
  return $null
}

# 幂等：若已打补丁则跳过
$alreadyPatched = $false
$wlFile = Find-TextInJs $v1 $wlNew
if ($wlFile) { $alreadyPatched = $true }
else {
  $wlFile = Find-TextInJs $v1 $wlOld
  if (-not $wlFile) { Write-Bad '未找到前端语言白名单，当前 Claude 版本结构不兼容，已中止（未修改任何文件）。'; Stop-Transcript -ErrorAction SilentlyContinue | Out-Null; exit 1 }
  $cnt = ([regex]::Matches($latin.GetString([IO.File]::ReadAllBytes($wlFile)), [regex]::Escape($wlOld))).Count
  if ($cnt -ne 2) { Write-Bad ("白名单文本命中 " + $cnt + " 次（预期 2 次），为避免写坏已中止。"); Stop-Transcript -ErrorAction SilentlyContinue | Out-Null; exit 1 }
  Write-Ok ("白名单文件: " + (Split-Path $wlFile -Leaf) + " (2 处)")
}
$nmFile = Find-TextInJs $v1 $nmOld
if (-not $nmFile -and -not (Find-TextInJs $v1 '"zh-Hans":{name:"Chinese (Simplified)"')) {
  Write-Warn2 '未找到语言名映射文本，设置页语言列表可能不显示中文条目（不影响汉化生效）。'
} elseif ($nmFile) {
  Write-Ok ("语言名映射文件: " + (Split-Path $nmFile -Leaf))
}

# 标题栏 tab 标签（uR 对象为硬编码英文，不走 i18n；用 \uXXXX 转义写入，ASCII 安全）
$tabsOld1 = 'chat:{mode:"chat",icon:"Chats",label:"Chat"}'
$tabsNew1 = 'chat:{mode:"chat",icon:"Chats",label:"\u804A\u5929"}'
$tabsOld2 = 'cowork:{mode:"cowork",icon:"Tasks",label:"Cowork"},code:{mode:"code",icon:"Code",label:"Code"}'
$tabsNew2 = 'cowork:{mode:"cowork",icon:"Tasks",label:"\u534F\u4F5C"},code:{mode:"code",icon:"Code",label:"\u4EE3\u7801"}'
$tabsFile = Find-TextInJs $v1 $tabsOld2
$tabsPatched = $false
if (-not $tabsFile) {
  if (Find-TextInJs $v1 'label:"\u534F\u4F5C"') { $tabsPatched = $true }
}
#  2) 标签条数组（key/label 形式，push 多处，是实际渲染的标签条）
$t2aOld = '{key:"chat",label:"Chat"}'
$t2aNew = '{key:"chat",label:"\u804A\u5929"}'
$t2bOld = '{key:"task",label:"Cowork"}'
$t2bNew = '{key:"task",label:"\u534F\u4F5C"}'
$t2cOld = '{key:"code",label:"Code"}'
$t2cNew = '{key:"code",label:"\u4EE3\u7801"}'
$tabs2File = Find-TextInJs $v1 $t2bOld
$tabs2Patched = $false
if (-not $tabs2File) {
  if (Find-TextInJs $v1 $t2bNew) { $tabs2Patched = $true }
}
if ($tabsFile) { Write-Ok ("标题栏标签文件(1): " + (Split-Path $tabsFile -Leaf)) }
if ($tabs2File) { Write-Ok ("标题栏标签文件(2): " + (Split-Path $tabs2File -Leaf)) }
if (-not $tabsFile -and -not $tabsPatched -and -not $tabs2File -and -not $tabs2Patched) {
  Write-Warn2 '未找到标题栏标签文本，顶部 Cowork/Code 标签将保持英文（不影响其他汉化）。'
}

# ---------- 3. 备份 ----------
Write-Step '[3/8] 备份原始文件...'
$bakRoot = Join-Path $env:USERPROFILE '.claude\zh\backup'
$bak = Join-Path $bakRoot $version
New-Item -ItemType Directory -Force -Path $bak | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $bak 'acl') | Out-Null
$toBackup = @()
if (-not $alreadyPatched -and $wlFile) { $toBackup += $wlFile }
if ($nmFile) { $toBackup += $nmFile }
if ($tabsFile -and -not $tabsPatched) { $toBackup += $tabsFile }
if ($tabs2File -and -not $tabs2Patched) { $toBackup += $tabs2File }
foreach ($f in $toBackup) {
  $dst = Join-Path $bak (Split-Path $f -Leaf)
  if (-not (Test-Path $dst)) { Copy-Item $f $dst -Force }
  $aclFile = Join-Path (Join-Path $bak 'acl') ((Split-Path $f -Leaf) + '.acl')
  if (-not (Test-Path $aclFile)) {
    Push-Location (Split-Path $f -Parent)
    icacls (Split-Path $f -Leaf) /save $aclFile 2>$null | Out-Null
    Pop-Location
  }
}
Write-Ok ("备份目录: " + $bak)

# ---------- 3b. 词条仓库（唯一真相源）与词表重建 ----------
# v2.5：词条不再散落在多个硬编码表里，统一存于 resources/translations/zh-store.json。
# 安装时：登记仓库路径 -> 首次迁移历史词条 -> 由仓库重建词表产物。
# 这样任何一次成功翻译都会落盘，重装/重启后可原样复现，无需重新翻译。
Write-Step '[3b] 词条仓库准备与词表重建...'
$resDir0 = Join-Path (Split-Path $PSScriptRoot -Parent) 'resources'
$zhStore = Join-Path $PSScriptRoot 'zhstore.py'
$seedScript = Join-Path $PSScriptRoot 'seed-store.py'
$buildScript = Join-Path (Join-Path (Split-Path $PSScriptRoot -Parent) 'tools') 'build_additions.py'
# 解释器：优先汉化包内置的精简运行时，其次系统 Python。
# 注意：[3b] 位于 [7a-2]「部署内置运行时」之前，此时 .claude\zh\python 尚未落地，
# 因此直接用包内源 zh\python\python.exe（与部署后的副本同源同版本）。
# 这样即使系统没装 Python，词条仓库迁移与词表重建也能照常执行。
$pkgPy = Join-Path (Split-Path $PSScriptRoot -Parent) 'python\python.exe'
$py2 = $null
if (Test-Path $pkgPy) { $py2 = $pkgPy }
else { $py2 = (Get-Command python -ErrorAction SilentlyContinue).Source }
if ($py2 -and (Test-Path $zhStore)) {
  $prevEA = $ErrorActionPreference
  $ErrorActionPreference = 'Continue'
  try {
    # 登记项目仓库路径：使运行时副本（守护进程/内核脚本）也写回项目仓库，
    # 词条资产不会因卸载或运行时目录清理而丢失。
    & $py2 $zhStore '--register' 2>&1 | Out-Null
    $storeFile = Join-Path $resDir0 'translations\zh-store.json'
    if (-not (Test-Path $storeFile) -and (Test-Path $seedScript)) {
      & $py2 $seedScript 2>&1 | Out-Null
      if (Test-Path $storeFile) {
        Write-Ok ('已迁移历史词条到统一仓库: ' + $storeFile)
      } else {
        Write-Warn2 '词条仓库迁移未产出文件，沿用现有词表'
      }
    } elseif (Test-Path $storeFile) {
      Write-Ok ('词条仓库已存在: ' + $storeFile)
    }
    # 由仓库重建词表产物（仓库 -> resources/*.json），保证产物与仓库一致
    if (Test-Path $buildScript) {
      & $py2 $buildScript '--res' $res 2>&1 | Out-Null
      Write-Ok '已由词条仓库重建词表产物'
    }
  } catch {
    Write-Warn2 ('词条仓库步骤异常（沿用现有词表）: ' + $_.Exception.Message)
  }
  $ErrorActionPreference = $prevEA
  $global:LASTEXITCODE = 0
} else {
  Write-Warn2 '未找到可用的 Python 解释器或 zhstore.py，沿用现有词表'
}

# ---------- 4. 构建合并词表 ----------
Write-Step '[4/8] 构建 zh-Hans 词表（ldk-tokyo 词库 + 官方词条 + 手工补充）...'
$resDir = Join-Path (Split-Path $PSScriptRoot -Parent) 'resources'
$ldkPath  = Join-Path $resDir 'frontend-zh-CN.json'
$ldkDyn   = Join-Path $resDir 'dynamic-zh-CN.json'
$overlay  = Join-Path $resDir 'custom-overlay-zh.json'
foreach ($req in @($ldkPath, $ldkDyn, $overlay)) {
  if (-not (Test-Path $req)) { Write-Bad ("缺少词库文件: " + $req); Stop-Transcript -ErrorAction SilentlyContinue | Out-Null; exit 1 }
}

$pairRx = [regex]'"([^"\\]+)"\s*:\s*("(?:[^"\\]|\\.)*")'
function ConvertFrom-JsonPairs($text) {
  $h = @{}
  foreach ($m in $pairRx.Matches($text)) {
    if (-not $h.ContainsKey($m.Groups[1].Value)) { $h[$m.Groups[1].Value] = $m.Groups[2].Value }
  }
  return $h
}

$enText   = [IO.File]::ReadAllText((Join-Path $i18n 'en-US.json'), [Text.Encoding]::UTF8)
$ldkMap   = ConvertFrom-JsonPairs ([IO.File]::ReadAllText($ldkPath, [Text.Encoding]::UTF8))
$ovMap    = ConvertFrom-JsonPairs ([IO.File]::ReadAllText($overlay, [Text.Encoding]::UTF8))

# 手工 key 级增补（截图逐项核对产出），优先于 ldk 词库
$customKeysPath = Join-Path $resDir 'custom-keys-zh.json'
$ckCount = 0
if (Test-Path $customKeysPath) {
  $ckMap = ConvertFrom-JsonPairs ([IO.File]::ReadAllText($customKeysPath, [Text.Encoding]::UTF8))
  foreach ($k in $ckMap.Keys) { $ldkMap[$k] = $ckMap[$k]; $ckCount++ }
}

$sb = New-Object System.Text.StringBuilder
[void]$sb.Append('{')
$first = $true; $keyHit = 0; $valHit = 0; $total = 0
foreach ($m in $pairRx.Matches($enText)) {
  $k = $m.Groups[1].Value; $rawV = $m.Groups[2].Value; $total++
  $outV = $null
  if ($ldkMap.ContainsKey($k)) { $outV = $ldkMap[$k]; $keyHit++ }
  else {
    $inner = $rawV.Substring(1, $rawV.Length - 2)
    if (($inner.IndexOf('\') -lt 0) -and $ovMap.ContainsKey($inner)) { $outV = $ovMap[$inner]; $valHit++ }
  }
  if ($null -eq $outV) { $outV = $rawV }
  if (-not $first) { [void]$sb.Append(',') }
  $first = $false
  [void]$sb.Append('"').Append($k).Append('":').Append($outV)
}
[void]$sb.Append('}')
$zhDict = $sb.ToString()

# dynamic 词表（缺失会导致前端丢弃整份词表）
# ldk 词库打底 + 仓库 overlay 优先叠加：词条仓库是唯一真相源，
# 人工修订必须压过 ldk 旧译文（此前直接用 ldk，27 条人工修订被覆盖、3 条假照常部署）。
$dynEnText = [IO.File]::ReadAllText((Join-Path $i18n 'dynamic\en-US.json'), [Text.Encoding]::UTF8)
$dynMap = ConvertFrom-JsonPairs ([IO.File]::ReadAllText($ldkDyn, [Text.Encoding]::UTF8))
$dynOvPath = Join-Path $resDir 'dynamic-overlay-zh.json'
if (Test-Path $dynOvPath) {
  $dynOvMap = ConvertFrom-JsonPairs ([IO.File]::ReadAllText($dynOvPath, [Text.Encoding]::UTF8))
  foreach ($k in $dynOvMap.Keys) { $dynMap[$k] = $dynOvMap[$k] }
  Write-Ok ("dynamic overlay 叠加 " + $dynOvMap.Count + " 条（仓库优先）")
}
$sb2 = New-Object System.Text.StringBuilder
[void]$sb2.Append('{')
$first = $true
foreach ($m in $pairRx.Matches($dynEnText)) {
  $k = $m.Groups[1].Value; $rawV = $m.Groups[2].Value
  $outV = $rawV
  if ($dynMap.ContainsKey($k)) { $outV = $dynMap[$k] }
  if (-not $first) { [void]$sb2.Append(',') }
  $first = $false
  [void]$sb2.Append('"').Append($k).Append('":').Append($outV)
}
[void]$sb2.Append('}')
$dynDict = $sb2.ToString()
Write-Ok ("词表合并完成: 共 " + $total + " 条，key 命中 " + $keyHit + " 条（含手工增补 " + $ckCount + " 条），补充 " + $valHit + " 条")

# ---------- 4b. 停掉守护进程（防止安装期间自愈竞态） ----------
# 守护进程 skills-watch 会按"旧基线"把被改动的词表/JS 自愈回 payload 副本。
# 若它在安装期间运行，会把 [5/8] 刚部署的新词表覆盖回旧内容，随后 [7e] 又把
# 旧内容固化为新基线（此 bug 曾在重装时实发：新词条全部丢失）。
# 因此安装全程必须停掉守护进程，待 [7e] 基线写好后再由 [7g] 启动。
function Stop-SkillsWatch {
  $wps = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match '^pythonw?\.exe$' -and $_.CommandLine -match 'skills-watch\.py' })
  foreach ($wp in $wps) {
    try { Stop-Process -Id $wp.ProcessId -Force -ErrorAction Stop } catch { }
  }
  return $wps.Count
}
$stopped = Stop-SkillsWatch
if ($stopped -gt 0) { Write-Ok "已停止守护进程（$stopped 个），安装完成后再启动" }

# ---------- 5. 部署词表 ----------
Write-Step '[5/8] 部署词表文件...'
# WindowsApps 归 TrustedInstaller 所有：
#  - 目录需 (OI)(CI) 继承授权，新建文件才继承写权限
#  - 已存在的目标文件需单独取得所有权（幂等重装时可覆盖）
function Grant-Write($path) {
  try { takeown /f $path /a 2>&1 | Out-Null } catch { }
  if (Test-Path $path -PathType Container) {
    try { icacls $path /grant 'Administrators:(OI)(CI)(F)' 2>&1 | Out-Null } catch { }
  } else {
    # 文件不能带 (OI)(CI) 继承标志，否则 icacls 授权静默失败
    try { icacls $path /grant 'Administrators:(F)' 2>&1 | Out-Null } catch { }
  }
}
Grant-Write $i18n
Grant-Write (Join-Path $i18n 'dynamic')
foreach ($f in @((Join-Path $i18n 'zh-Hans.json'), (Join-Path $i18n 'dynamic\zh-Hans.json'))) {
  if (Test-Path $f) { Grant-Write $f }
}
$utf8NoBom = New-Object Text.UTF8Encoding($false)
[IO.File]::WriteAllText((Join-Path $i18n 'zh-Hans.json'), $zhDict, $utf8NoBom)
[IO.File]::WriteAllText((Join-Path $i18n 'dynamic\zh-Hans.json'), $dynDict, $utf8NoBom)
Write-Ok 'ion-dist\i18n\zh-Hans.json'
Write-Ok 'ion-dist\i18n\dynamic\zh-Hans.json'

# shell 层增补：resources\zh-Hans.json（官方 613 条 + 我们的 overlay，overlay 优先）
# shell 层负责：标题栏标签（Cowork/Code）、配置第三方推理窗口、菜单与权限对话框
$shellZhPath = Join-Path $res 'zh-Hans.json'
$shellOvPath = Join-Path $resDir 'shell-overlay-zh.json'
if ((Test-Path $shellZhPath) -and (Test-Path $shellOvPath)) {
  $shellBakFile = Join-Path $bak 'shell-zh-Hans.json'
  if (-not (Test-Path $shellBakFile)) {
    Copy-Item $shellZhPath $shellBakFile -Force
    $shellAcl = Join-Path (Join-Path $bak 'acl') 'shell-zh-Hans.json.acl'
    if (-not (Test-Path $shellAcl)) {
      Push-Location $res
      icacls 'zh-Hans.json' /save $shellAcl 2>$null | Out-Null
      Pop-Location
    }
  }
  Grant-Write $shellZhPath
  $shellBase = ConvertFrom-JsonPairs ([IO.File]::ReadAllText($shellZhPath, [Text.Encoding]::UTF8))
  $shellOv   = ConvertFrom-JsonPairs ([IO.File]::ReadAllText($shellOvPath, [Text.Encoding]::UTF8))
  foreach ($k in $shellOv.Keys) { $shellBase[$k] = $shellOv[$k] }
  $sbS = New-Object System.Text.StringBuilder
  [void]$sbS.Append('{')
  $firstS = $true
  foreach ($k in $shellBase.Keys) {
    if (-not $firstS) { [void]$sbS.Append(',') }
    $firstS = $false
    [void]$sbS.Append('"').Append($k).Append('":').Append($shellBase[$k])
  }
  [void]$sbS.Append('}')
  [IO.File]::WriteAllText($shellZhPath, $sbS.ToString(), $utf8NoBom)
  Write-Ok ("resources\zh-Hans.json 增补 " + $shellOv.Count + " 条（shell 层）")
} else {
  Write-Warn2 '未找到 shell 词表或 shell-overlay-zh.json，跳过 shell 层增补'
}

# ---------- 6. 补丁白名单与语言名映射 ----------
Write-Step '[6/8] 补丁前端语言白名单...'
function Patch-JsFile($path, $find, $replace) {
  # 修改 TrustedInstaller 文件：先取所有权再授权
  try { takeown /f $path /a 2>&1 | Out-Null } catch { }
  try { icacls $path /grant 'Administrators:(F)' 2>&1 | Out-Null } catch { }
  $s = $latin.GetString([IO.File]::ReadAllBytes($path))
  if (-not $s.Contains($find)) { return $false }
  $s2 = $s.Replace($find, $replace)
  [IO.File]::WriteAllBytes($path, $latin.GetBytes($s2))
  return $true
}

if (-not $alreadyPatched) {
  if (-not (Patch-JsFile $wlFile $wlOld $wlNew)) { Write-Bad '白名单补丁写入失败。'; Stop-Transcript -ErrorAction SilentlyContinue | Out-Null; exit 1 }
  Write-Ok '白名单已加入 zh-Hans（2 处）'
} else {
  Write-Ok '白名单已包含 zh-Hans，跳过（幂等）'
}
if ($nmFile) {
  if (Patch-JsFile $nmFile $nmOld $nmNew) { Write-Ok '语言名映射已加入 zh-Hans' }
}
if ($tabsFile -and -not $tabsPatched) {
  $null = Patch-JsFile $tabsFile $tabsOld1 $tabsNew1
  if (Patch-JsFile $tabsFile $tabsOld2 $tabsNew2) { Write-Ok '标题栏标签已汉化（KA 对象）' }
}
if ($tabs2File -and -not $tabs2Patched) {
  $null = Patch-JsFile $tabs2File $t2aOld $t2aNew
  $null = Patch-JsFile $tabs2File $t2bOld $t2bNew
  if (Patch-JsFile $tabs2File $t2cOld $t2cNew) { Write-Ok '标题栏标签已汉化（标签条数组）' }
}

# ---------- 7. 设置 locale ----------
Write-Step '[7/8] 写入 locale 配置...'
$configs = Get-ChildItem $env:LOCALAPPDATA -Directory -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -like 'Claude*' } |
  ForEach-Object { Join-Path $_.FullName 'config.json' } |
  Where-Object { Test-Path $_ }
$cfgHit = 0
foreach ($cfg in $configs) {
  $txt = [IO.File]::ReadAllText($cfg, [Text.Encoding]::UTF8)
  if ($txt -match '"locale"\s*:') {
    $bakCfg = Join-Path $bak ('config.json')
    if (-not (Test-Path $bakCfg)) { Copy-Item $cfg $bakCfg -Force }
    $txt2 = $txt -replace '("locale"\s*:\s*")[^"]*(")', '${1}zh-Hans${2}'
    [IO.File]::WriteAllText($cfg, $txt2, $utf8NoBom)
    Write-Ok ("locale = zh-Hans  ->  " + $cfg)
    $cfgHit++
  }
}
if ($cfgHit -eq 0) { Write-Warn2 '未找到 config.json，将在首次启动后生效（可手动重跑安装脚本）。' }

# ---------- 7a-2. 部署内置 Python 运行时（离线，随汉化包携带） ----------
# 守护服务需要 Python + pywin32。v4.1 之前服务绑定的是"系统里碰巧装着的" Python：
# 用户一旦卸载 / 升级 / 更换发行版，服务就会静默失效（SCM 报 1053），而界面看起来
# 一切正常，极难排查。因此改为汉化包自带一份精简运行时（约 15 MB），从包内复制到
# %USERPROFILE%\.claude\zh\python\，路径相对解析、不写死盘符、全程不联网。
Write-Step '[7a-2] 部署内置 Python 运行时...'
if (-not $zhHome) { $zhHome = Join-Path $env:USERPROFILE '.claude\zh' }
$pyRuntimeSrc = Join-Path (Split-Path $PSScriptRoot -Parent) 'python'
$pyRuntimeDst = Join-Path $zhHome 'python'
$embeddedPy   = Join-Path $pyRuntimeDst 'python.exe'
if (Test-Path (Join-Path $pyRuntimeSrc 'python.exe')) {
  try {
    $needCopy = $true
    $rtSrcPath = Join-Path $pyRuntimeSrc 'RUNTIME.json'
    $rtDstPath = Join-Path $pyRuntimeDst 'RUNTIME.json'
    if ((Test-Path $embeddedPy) -and (Test-Path $rtSrcPath) -and (Test-Path $rtDstPath)) {
      $rtSrc = (Get-Content $rtSrcPath -Raw -Encoding UTF8 | ConvertFrom-Json)
      $rtDst = (Get-Content $rtDstPath -Raw -Encoding UTF8 | ConvertFrom-Json)
      if ($rtSrc.tag -eq $rtDst.tag -and $rtSrc.build_time -eq $rtDst.build_time) {
        $needCopy = $false                       # 版本一致：不重复拷贝 15 MB
      }
    }
    if ($needCopy) {
      if (-not (Test-Path $pyRuntimeDst)) { New-Item -ItemType Directory -Path $pyRuntimeDst -Force | Out-Null }
      Copy-Item (Join-Path $pyRuntimeSrc '*') $pyRuntimeDst -Recurse -Force
      Write-Ok ('内置 Python 运行时已部署: ' + $pyRuntimeDst)
    } else {
      Write-Ok ('内置 Python 运行时已是最新: ' + $embeddedPy)
    }
  } catch {
    Write-Bad ('内置 Python 运行时部署失败: ' + $_.Exception.Message)
  }
} else {
  Write-Bad ('汉化包缺少内置 Python 运行时: ' + $pyRuntimeSrc)
  Write-Warn2 '守护服务将不可用（汉化本体不受影响）。本程序不会联网下载 Python，请使用完整汉化包重装。'
}

# 统一解释器选择：内置运行时优先；内置缺失时才（带明确警告）临时使用系统 Python，
# 保证"用的是哪个解释器"始终可见，不会静默变化。
$pyExePath = $null
if (Test-Path $embeddedPy) {
  $pyExePath = $embeddedPy
} else {
  $pcmd = Get-Command python -ErrorAction SilentlyContinue
  if ($pcmd) {
    $pyExePath = $pcmd.Source
    Write-Warn2 ('未找到内置 Python 运行时，本次临时使用系统 Python: ' + $pyExePath)
  }
}

# ---------- 7b. 内置技能描述汉化（用户目录 skills-plugin 运行副本） ----------
# Claude 每次启动会用 app.asar 原件覆盖 skills-plugin，因此除立即翻译外，
# 还部署一个轻量守护进程（skills-watch）轮询重译；tooltip 运行时实时读磁盘，重译即生效。
Write-Step '[7b] 技能描述汉化与守护进程部署...'
$skillScript = Join-Path $PSScriptRoot 'translate-skills.py'
$watchScript = Join-Path $PSScriptRoot 'skills-watch.py'
$svcScript   = Join-Path $PSScriptRoot 'zh_service.py'
$zhPyModule  = Join-Path $PSScriptRoot 'zhpy.py'
if (Test-Path $skillScript) {
  $pyExe = $pyExePath
  if ($pyExe) {
    # 技能汉化与守护进程部署属增强项：整段降级 ErrorAction 并做异常隔离，
    # 任何失败都不得中断后续的词表基线写入与最终校验。
    $oldEapW = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
      & $pyExe $skillScript
      $global:LASTEXITCODE = 0
    } catch {
      Write-Warn2 ('技能描述汉化执行失败: ' + $_.Exception.Message)
    }
    try {
      $zhHome = Join-Path $env:USERPROFILE '.claude\zh'
      if (-not (Test-Path $zhHome)) { New-Item -ItemType Directory -Path $zhHome -Force | Out-Null }
      Copy-Item $skillScript (Join-Path $zhHome 'translate_skills_mod.py') -Force
      # 词条仓库模块必须随行：内核/技能脚本运行时需 import 它才能回写译文
      if (Test-Path $zhStore) { Copy-Item $zhStore (Join-Path $zhHome 'zhstore.py') -Force }
      if (Test-Path $seedScript) { Copy-Item $seedScript (Join-Path $zhHome 'seed-store.py') -Force }
      # 运行时定位模块：服务与守护脚本均通过它相对定位内置 Python
      if (Test-Path $zhPyModule) { Copy-Item $zhPyModule (Join-Path $zhHome 'zhpy.py') -Force }
      if (Test-Path $watchScript) {
        Copy-Item $watchScript (Join-Path $zhHome 'skills-watch.py') -Force
        $pyw = Join-Path (Split-Path $pyExe) 'pythonw.exe'
        if (-not (Test-Path $pyw)) { $pyw = $pyExe }
        # ---- v4.0：常驻职责移交 Windows 服务 Claude_zh ----
        # 服务宿主脚本随模块一起部署到 .claude\zh；真正的注册与启动在 [7g]
        # （内核补丁、自愈基线全部就绪之后），与服务自身的 boot 自检不冲突。
        if (Test-Path $svcScript) {
          Copy-Item $svcScript (Join-Path $zhHome 'zh_service.py') -Force
        }
        # 清理 v3.0「非驻留自愈三件套」残留（升级路径）：登录自检自启项、
        # 中文版启动器、桌面快捷方式——服务模式下它们已无意义，留着只会让
        # 用户困惑（且旧启动器绕过了服务）。
        $startupDir = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup'
        Remove-Item (Join-Path $startupDir 'claude-zh-heal.cmd') -Force -ErrorAction SilentlyContinue
        Remove-Item (Join-Path $startupDir 'claude-zh-skills-watch.cmd') -Force -ErrorAction SilentlyContinue
        Remove-Item (Join-Path $zhHome 'start-claude-zh.cmd') -Force -ErrorAction SilentlyContinue
        Remove-Item (Join-Path ([Environment]::GetFolderPath('Desktop')) 'Claude 中文版.lnk') -Force -ErrorAction SilentlyContinue
        Write-Ok '常驻模块已部署（skills-watch + 服务宿主 zh_service.py）'
      }
    } catch {
      Write-Warn2 ('守护进程部署失败（不影响本次汉化）: ' + $_.Exception.Message)
    } finally {
      $ErrorActionPreference = $oldEapW
    }
  } else {
    Write-Warn2 '未找到 python，跳过技能描述汉化（可手动运行 scripts\translate-skills.py）'
  }
}

# ---------- 7c/7d. Claude Code 内核命令描述汉化（字符串表 + 源码字面量） ----------
# 内核 claude.exe 是 100MB+ 的 Bun 二进制，字符串表补丁与源码「等长原地替换」都要
# 全文件读写。历史上为省时改为「部署模块 + 由守护进程开机自检打补丁 + 直启兜底」，
# 但 2026-10-15 实测：直启的补丁实例与 [7g] 守护进程的 boot 自检并发运行同一
# 模块，后启动者以空日志快照读到前者已补丁的二进制（全部 miss、ok=0），
# save_log({}) 把还原日志覆盖为空 —— 卸载从此无法还原内核。两个模块已加跨进程
# 文件锁，且此处改为**同步执行**（NVMe 实测两模块合计约 10 秒），彻底消除竞态；
# 同步完成后 [7g] 才启动守护进程，其 boot 自检是唯一后续运行者。
Write-Step '[7c/7d] 内核汉化（字符串表 + 源码字面量，同步执行）...'
$kernelMods = [ordered]@{
  'translate-kernel.py'        = 'translate_kernel_mod.py'
  'translate-kernel-source.py' = 'translate_kernel_source_mod.py'
}
if (-not $zhHome) { $zhHome = Join-Path $env:USERPROFILE '.claude\zh' }
if (-not (Test-Path $zhHome)) { New-Item -ItemType Directory -Path $zhHome -Force | Out-Null }
$oldEapK = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
  $deployed = @()
  foreach ($k in $kernelMods.Keys) {
    $src = Join-Path $PSScriptRoot $k
    if (Test-Path $src) {
      Copy-Item $src (Join-Path $zhHome $kernelMods[$k]) -Force
      $deployed += $src
    }
  }
  if ($deployed.Count -gt 0) {
    foreach ($s in $deployed) {
      # 同步执行（模块内部有跨进程文件锁，与守护进程并发安全）
      $ko = & $pyExe $s 2>&1
      $ko | Where-Object { $_ } | ForEach-Object { Write-Host ('      ' + $_) }
    }
  } else {
    Write-Warn2 '未找到内核汉化模块，跳过（斜杠菜单部分描述将保持英文）'
  }
} catch {
  Write-Warn2 ('内核汉化失败（不影响本次汉化）: ' + $_.Exception.Message)
} finally {
  $ErrorActionPreference = $oldEapK
}

# ---------- 7f. app.asar 内嵌技能描述汉化（等长源码字面量替换） ----------
# 协作页「+ → 技能」菜单的 tooltip 读的是 app.asar 内嵌注册表，不走任何词表，
# 只能等长替换。app.asar 位于 WindowsApps 下，需要管理员权限——安装脚本恰好是
# 管理员上下文，故在此**同步执行**（读写 47MB 约数秒）；守护进程是用户态，
# 无权写 app.asar，因此 Claude 大版本更新替换 app.asar 后需重跑安装（同前端补丁）。
Write-Step '[7f] app.asar 技能描述汉化...'
$asarScript = Join-Path $PSScriptRoot 'translate-asar-source.py'
if (Test-Path $asarScript) {
  $oldEapA = $ErrorActionPreference
  $ErrorActionPreference = 'Continue'
  try {
    Copy-Item $asarScript (Join-Path $zhHome 'translate_asar_source_mod.py') -Force
    # app.asar 与 claude.exe（integrity 链修复要改 exe 内嵌的 header 哈希）
    # 均归 TrustedInstaller 所有，先取得写权限
    Grant-Write (Join-Path $res 'app.asar')
    Grant-Write (Join-Path (Split-Path $res -Parent) 'claude.exe')
    $ao = & $pyExe $asarScript 2>&1
    $ao | ForEach-Object { Write-Host '  ' $_ }
    $global:LASTEXITCODE = 0
    Write-Ok 'app.asar 技能描述补丁完成'
  } catch {
    Write-Warn2 ('app.asar 技能描述补丁失败（不影响其他汉化）: ' + $_.Exception.Message)
  } finally {
    $ErrorActionPreference = $oldEapA
  }
} else {
  Write-Warn2 '未找到 translate-asar-source.py，跳过（技能 tooltip 部分将保持英文）'
}

# ---------- 7e. 写入自愈基线快照（守护进程据此在重启/更新后自动修复） ----------
# 基线内容与 JS 补丁三元组由 write-state.py 生成（纯 Python：便于校验与排错，
# 也避免 PowerShell 严格模式下原生命令退出码中断安装流程）。
Write-Step '[7e] 写入自愈基线快照...'
$wsScript = Join-Path $PSScriptRoot 'write-state.py'
if (-not $zhHome) { $zhHome = Join-Path $env:USERPROFILE '.claude\zh' }
if (-not (Test-Path $zhHome)) { New-Item -ItemType Directory -Path $zhHome -Force | Out-Null }
$ctx = @{
  pkgPath = $pkg.FullName
  version = $version
  res     = $res
  i18n    = $i18n
  v1      = $v1
  zhHome  = $zhHome
  # 内置 Python 运行时（随汉化包携带、离线）。服务据此定位解释器，
  # 路径由 zhHome 相对推导，不写死盘符，整体搬家后依然有效。
  pythonRuntime = (Join-Path $zhHome 'python')
  # 服务以 LocalSystem 运行，进程环境里的 USERPROFILE 指向 systemprofile。
  # 服务宿主据此反推真实用户目录（也可从 zhHome 上两级推导，这里是显式兜底）。
  userProfile = $env:USERPROFILE
}
$ctxJson = $ctx | ConvertTo-Json -Depth 4
[IO.File]::WriteAllText((Join-Path $zhHome 'install-context.json'), $ctxJson, $utf8NoBom)
if ((Test-Path $wsScript) -and $pyExe) {
  $oldEap2 = $ErrorActionPreference
  $ErrorActionPreference = 'Continue'
  try {
    & $pyExe $wsScript
    $global:LASTEXITCODE = 0
    if (Test-Path (Join-Path $zhHome 'state.json')) {
      Write-Ok ('自愈基线已写入: ' + (Join-Path $zhHome 'state.json'))
    } else {
      Write-Warn2 '自愈基线未生成（不影响本次汉化，仅失去自动修复能力）'
    }
  } catch {
    Write-Warn2 ('自愈基线写入失败（不影响本次汉化）: ' + $_.Exception.Message)
  } finally {
    $ErrorActionPreference = $oldEap2
  }
} else {
  Write-Warn2 '未找到 python 或 write-state.py，跳过自愈基线'
}

# ---------- 7h. 免登录网关配置（可选；Claude 官方第三方推理 3P 模式，非破解） ----------
# 凭据来源唯一且明确：包根目录 gateway.json（用户复制 gateway.example.json 填写）。
# 校验与写入逻辑全在 apply-gateway-config.py：exit 0=已写入 3=未提供/已有他人配置 1=校验失败。
Write-Step '[7h] 免登录网关配置（可选）...'
$gwScript = Join-Path $PSScriptRoot 'apply-gateway-config.py'
if ((Test-Path $gwScript) -and $pyExe) {
  $oldEap3 = $ErrorActionPreference
  $ErrorActionPreference = 'Continue'
  try {
    & $pyExe $gwScript
    if ($LASTEXITCODE -eq 1) { Write-Warn2 '网关凭据校验未通过，已跳过（不影响汉化本体）' }
    $global:LASTEXITCODE = 0
  } catch {
    Write-Warn2 ('网关配置写入失败（不影响汉化本体）: ' + $_.Exception.Message)
  } finally {
    $ErrorActionPreference = $oldEap3
  }
} else {
  Write-Ok '网关配置组件缺失，跳过（不影响汉化本体）'
}

# ---------- 7i. 跳过 Claude Code 初次安装确认（写入 ~/.claude.json 的 hasCompletedOnboarding=true） ----------
# 唯一实现：仅增量写该字段，其余字段保留；仅对 Claude Code CLI 生效（桌面版主界面登录不受影响）。
# 生命周期：安装/更新写入；仅卸载汉化不触碰；彻底卸载由 Claude汉化.cmd 随用户数据删除。
# exit 0=已写入/已存在  1=失败（仅警告，不中断安装）。
Write-Step '[7i] 跳过 Claude Code 初次安装确认...'
$obScript = Join-Path $PSScriptRoot 'apply-onboarding-skip.py'
if ((Test-Path $obScript) -and $pyExe) {
  $oldEap4 = $ErrorActionPreference
  $ErrorActionPreference = 'Continue'
  try {
    & $pyExe $obScript
    if ($LASTEXITCODE -ne 0) { Write-Warn2 '初次安装确认跳过写入失败（不影响汉化本体）' }
    $global:LASTEXITCODE = 0
  } catch {
    Write-Warn2 ('初次安装确认跳过写入失败（不影响汉化本体）: ' + $_.Exception.Message)
  } finally {
    $ErrorActionPreference = $oldEap4
  }
} else {
  Write-Ok '组件缺失，略过本步骤（不影响汉化本体）'
}

# ---------- 7g. 注册并启动 Windows 服务 Claude_zh ----------
# v4.0：常驻自愈由 Windows 服务承担（替代 v3.0 的登录自启项 + 启动器快捷方式）。
# 顺序铁律：此处已在 [7c/7d] 内核补丁、[7b] 技能翻译、[7e] 自愈基线全部就绪之后，
# 服务启动时的 boot 自检会因"补丁日志 3 分钟内刚更新"而跳过重打，不会与安装竞争。
Write-Step '[7g] 注册并启动 Windows 服务 Claude_zh...'
$SVC_NAME    = 'Claude_zh'
$SVC_DISPLAY = 'Claude Desktop 简体中文汉化服务'
$SVC_DESC    = '维持 Claude Desktop 汉化：技能描述重译、内核补丁重打、词表/JS/locale 基线自愈。'

# 服务宿主必须用带 pywin32 的解释器，否则进程起不来（SCM 报 1053 启动超时）
function Test-PyWin32 {
  param([string]$PyPath)
  if (-not $PyPath) { return $false }
  try {
    $o = & $PyPath -c "import win32serviceutil,win32service,win32event,servicemanager; print('PYWIN32_OK')" 2>$null
    return (($o -join '') -match 'PYWIN32_OK')
  } catch { return $false }
}

# 停止 + 删除服务。返回 none / removed / delete-failed
# 删除优先用 pywin32（python zh_service.py remove），它直接调 Windows SCM API，
# 不依赖 sc.exe（某些环境把 sc.exe 列入黑名单，或被安全策略禁用）；失败再依次
# 回退 sc.exe 与 WMI Win32_Service.Delete()。
function Remove-ClaudeZhService {
  param([string]$PyPath, [string]$SvcPyPath)
  $svc = Get-Service -Name $SVC_NAME -ErrorAction SilentlyContinue
  if (-not $svc) { return 'none' }
  if ($svc.Status -ne 'Stopped') {
    try { Stop-Service -Name $SVC_NAME -Force -ErrorAction SilentlyContinue } catch { }
    for ($i = 0; $i -lt 20; $i++) {          # 最多等 20 秒（服务停止超时是常见故障）
      Start-Sleep -Seconds 1
      $s2 = Get-Service -Name $SVC_NAME -ErrorAction SilentlyContinue
      if (-not $s2 -or $s2.Status -eq 'Stopped') { break }
    }
  }
  if ($PyPath -and $SvcPyPath -and (Test-Path $SvcPyPath)) {
    try {
      $null = & $PyPath $SvcPyPath remove 2>$null
      Start-Sleep -Seconds 1
      if (-not (Get-Service -Name $SVC_NAME -ErrorAction SilentlyContinue)) { return 'removed' }
    } catch { }
  }
  try {
    $null = & sc.exe delete $SVC_NAME 2>$null
    Start-Sleep -Seconds 1
    if (-not (Get-Service -Name $SVC_NAME -ErrorAction SilentlyContinue)) { return 'removed' }
  } catch { }
  try {
    $r = Invoke-CimMethod -ClassName Win32_Service -MethodName Delete `
           -Arguments @{ Name = $SVC_NAME } -ErrorAction Stop
    if ($r.ReturnValue -eq 0) { return 'removed' }
  } catch { }
  return 'delete-failed'
}

# 注册服务。同样优先 pywin32（--startup auto 保证开机自启），回退 sc.exe / New-Service
function New-ClaudeZhService {
  param([string]$PyPath, [string]$SvcPyPath)
  if ($PyPath -and $SvcPyPath -and (Test-Path $SvcPyPath)) {
    try {
      # pywin32 的 install 子命令不接受 "--startup auto" 这种写法（会打印 Usage 后
      # 退出且不注册），默认注册为 manual，随后用 Set-Service 改为自动启动。
      $null = & $PyPath $SvcPyPath install 2>$null
      Start-Sleep -Seconds 1
      if (Get-Service -Name $SVC_NAME -ErrorAction SilentlyContinue) {
        try { Set-Service -Name $SVC_NAME -StartupType Automatic -ErrorAction SilentlyContinue } catch { }
        return $true
      }
    } catch { }
  }
  try {
    $scBin = '\"' + $PyPath + '\" \"' + $SvcPyPath + '\"'   # sc：内层引号需转义为 \"
    $null = & sc.exe create $SVC_NAME binPath= $scBin start= auto DisplayName= $SVC_DISPLAY 2>$null
    Start-Sleep -Seconds 1
    if (Get-Service -Name $SVC_NAME -ErrorAction SilentlyContinue) { return $true }
  } catch { }
  try {
    New-Service -Name $SVC_NAME -BinaryPathName ('"' + $PyPath + '" "' + $SvcPyPath + '"') `
      -DisplayName $SVC_DISPLAY -StartupType Automatic -ErrorAction Stop | Out-Null
    return $true
  } catch { }
  return $false
}

$svcPy    = Join-Path $zhHome 'zh_service.py'
$pyForSvc = $null
# 铁律：服务必须绑定汉化包内置运行时（路径由 zhHome 相对推导，不写死盘符）。
# 绑定系统 Python 的历史教训：用户卸载/升级 Python 后服务静默失效（SCM 1053），
# 而界面无任何提示。内置运行时随汉化包走，生命周期与汉化一致。
if (Test-Path $embeddedPy) {
  if (Test-PyWin32 $embeddedPy) {
    $pyForSvc = $embeddedPy
    Write-Ok ('服务将使用内置运行时: ' + $embeddedPy)
  } else {
    Write-Bad ('内置运行时不可用（缺少 pywin32 或文件损坏）: ' + $embeddedPy)
  }
} else {
  Write-Bad ('未找到内置 Python 运行时: ' + $embeddedPy)
  Write-Warn2 '本程序不会联网下载 Python。请重新运行完整安装以部署内置运行时。'
}
if (-not $pyForSvc) {
  # 仅在内置环境确实缺失时兜底用系统 Python，并明确告知风险
  foreach ($cand in @((Get-Command python -ErrorAction SilentlyContinue).Source,
                      (Get-Command python3 -ErrorAction SilentlyContinue).Source)) {
    if ($cand -and (Test-PyWin32 $cand)) {
      $pyForSvc = $cand
      Write-Warn2 ('临时回退到系统 Python: ' + $cand + ' —— 卸载或升级该 Python 会导致服务失效')
      break
    }
  }
}

if ($pyForSvc -and (Test-Path $svcPy)) {
  $rmState = Remove-ClaudeZhService $pyForSvc $svcPy   # 重装：先清旧注册，保证 binPath 最新
  if ($rmState -eq 'removed')      { Write-Ok '已移除已存在的 Claude_zh 服务（重装场景）' }
  elseif ($rmState -eq 'delete-failed') { Write-Warn2 '已存在的 Claude_zh 服务无法删除，改为原地重启' }
  if (New-ClaudeZhService $pyForSvc $svcPy) {
    try { $null = & sc.exe description $SVC_NAME $SVC_DESC 2>$null } catch { }
    try {
      Start-Service -Name $SVC_NAME -ErrorAction Stop
      Start-Sleep -Seconds 4
      $s = Get-Service -Name $SVC_NAME -ErrorAction SilentlyContinue
      if ($s -and $s.Status -eq 'Running') {
        Write-Ok ('服务 Claude_zh 已注册并运行（' + $pyForSvc + '）')
      } else {
        Write-Warn2 ('服务 Claude_zh 已注册但未运行（状态: ' + $(if ($s) { $s.Status } else { '未知' }) + '），下次开机自动生效')
      }
    } catch {
      Write-Warn2 ('服务 Claude_zh 启动失败（不影响本次汉化）: ' + $_.Exception.Message)
    }
  } else {
    Write-Warn2 '服务 Claude_zh 注册失败，回退为登录自检模式'
    $pyForSvc = $null
  }
}

if (-not $pyForSvc) {
  # 降级路径：无 pywin32 时退回登录时一次性自愈（--once），保证功能不缺失，
  # 只是恢复时机从"实时"退化为"下次登录"。
  $pyw = $null
  if (Test-Path $embeddedPy) {
    $pyw = Join-Path (Split-Path $embeddedPy) 'pythonw.exe'
    if (-not (Test-Path $pyw)) { $pyw = $embeddedPy }
  } else {
    $pc0 = Get-Command python -ErrorAction SilentlyContinue
    if ($pc0) {
      $pyw = Join-Path (Split-Path $pc0.Source) 'pythonw.exe'
      if (-not (Test-Path $pyw)) { $pyw = $pc0.Source }
    }
  }
  if ($pyw) {
    $startupDir = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup'
    $healCmd = Join-Path $startupDir 'claude-zh-heal.cmd'
    $healLine = '@echo off' + "`r`n" +
      'if not exist "%USERPROFILE%\.claude\zh\skills-watch.py" exit /b' + "`r`n" +
      'start "" /min "' + $pyw + '" "%USERPROFILE%\.claude\zh\skills-watch.py" --once' + "`r`n"
    [IO.File]::WriteAllText($healCmd, $healLine, [Text.Encoding]::ASCII)
    Write-Warn2 '未找到带 pywin32 的 Python，已降级为登录自检（安装 pip install pywin32 后重装可启用服务）'
  } else {
    Write-Warn2 '未找到 Python，自愈能力不可用（汉化本体已生效，但 Claude 更新后不会自动恢复）'
  }
}

# ---------- 8. 校验 ----------
$ErrorActionPreference = 'Stop'   # 恢复严格模式
Write-Step '[8/8] 安装后校验...'
$s = $latin.GetString([IO.File]::ReadAllBytes($wlFile))
if ($s.Contains('"zh-Hans"')) { Write-Ok '白名单补丁已生效' } else { Write-Bad '白名单补丁未生效' }
if (Test-Path (Join-Path $i18n 'zh-Hans.json')) { Write-Ok 'zh-Hans.json 已部署' } else { Write-Bad '词表缺失' }
if (Test-Path (Join-Path $i18n 'dynamic\zh-Hans.json')) { Write-Ok 'dynamic\zh-Hans.json 已部署' } else { Write-Bad 'dynamic 词表缺失' }

Write-Host ''
if ($script:FailCount -eq 0) {
  Write-Host '汉化安装完成！请完全退出 Claude（含托盘）后重新启动。' -ForegroundColor Green
  Write-Host '如需恢复英文：以管理员身份运行 卸载.cmd。' -ForegroundColor Green
  Write-Host '注意：Claude 自动更新到新版本后需重新运行本安装脚本。' -ForegroundColor Yellow
  Stop-Transcript -ErrorAction SilentlyContinue | Out-Null; exit 0
} else {
  Write-Host '安装过程中出现错误，请检查上方输出。' -ForegroundColor Red
  Stop-Transcript -ErrorAction SilentlyContinue | Out-Null; exit 1
}
