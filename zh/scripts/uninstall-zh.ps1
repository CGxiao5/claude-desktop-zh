# Claude Desktop 简体中文汉化 - 卸载脚本 (Windows)
# 恢复内容：
#   1. 对系统中存在的所有 Claude 版本目录，从对应备份还原被补丁的 JS（字节级原样）与原 ACL
#   2. 还原 shell 层官方词表、删除部署的 zh-Hans 词表
#   3. config.json 的 locale 恢复为 en-US
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

function Write-Step($msg) { Write-Host $msg -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host ("  [OK] " + $msg) -ForegroundColor Green }
function Write-Warn2($msg){ Write-Host ("  [警告] " + $msg) -ForegroundColor Yellow }
function Write-Bad($msg)  { Write-Host ("  [失败] " + $msg) -ForegroundColor Red; $script:FailCount++ }

# ---------- 0. 管理员检查 ----------
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$isAdmin = [Security.Principal.WindowsPrincipal]::new($id).IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)
if (-not $isAdmin) {
  Write-Host '需要管理员权限。请右键以管理员身份运行 卸载.cmd。' -ForegroundColor Red
  exit 2
}

Write-Host ''
Write-Host '============================================' -ForegroundColor Cyan
Write-Host '  Claude Desktop 简体中文汉化 - 卸载' -ForegroundColor Cyan
Write-Host '============================================' -ForegroundColor Cyan
Write-Host ''

# ---------- 1. 枚举所有 Claude 版本目录 ----------
Write-Step '[1/4] 检测 Claude Desktop 安装...'
$pkgs = Get-ChildItem "$env:ProgramFiles\WindowsApps" -Directory -Filter 'Claude_*' -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -match '^Claude_\d+\.\d+\.\d+\.\d+_' -and (Test-Path (Join-Path $_.FullName 'app\resources\ion-dist\i18n\en-US.json')) } |
  Sort-Object { [version]($_.Name -split '_')[1] }
if (-not $pkgs) { Write-Bad '未找到 Claude 安装目录。'; exit 1 }
foreach ($p in $pkgs) { Write-Ok ("检测到 Claude " + ($p.Name -split '_')[1]) }

# ---------- 1b. 自动退出正在运行的 Claude ----------
# 实测：Claude 运行时会占用并自修复其资源文件，还原会被静默覆盖，
# 必须在还原前完全退出 Claude（含后台进程）。
$claudeProcs = @(Get-Process -ErrorAction SilentlyContinue |
  Where-Object { $_.ProcessName -match '^claude' })
if ($claudeProcs.Count -gt 0) {
  Write-Step '[1b] 退出正在运行的 Claude（避免还原被自修复覆盖）...'
  # 多轮强制退出直至清零：实测 Claude 启动中途会有子进程陆续孵化，一次性
  # Stop 后仍可能残留（残留进程锁定 claude.exe → asar integrity 还原
  # PermissionError，2026-10-15 实测事故）。
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
  $left = @(Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -match '^claude' }).Count
  if ($left -eq 0) { Write-Ok ('已退出 ' + $stoppedTotal + ' 个 Claude 进程（已确认全部关闭）') }
  else { Write-Warn2 ('仍有 ' + $left + ' 个 Claude 进程未能退出，还原可能失败') }
}

# ---------- 2. 逐版本还原 ----------
$latin = [Text.Encoding]::GetEncoding(28591)
foreach ($pkg in $pkgs) {
  $version = ($pkg.Name -split '_')[1]
  Write-Step ("[2] 清理 Claude $version ...")
  $res  = Join-Path $pkg.FullName 'app\resources'
  $i18n = Join-Path $res 'ion-dist\i18n'
  $v1   = Join-Path $res 'ion-dist\assets\v1'
  # 备份目录（v2.7 统一到 %USERPROFILE%\.claude\zh；兼容回退旧 %LOCALAPPDATA% 位置，
  # 以便还原旧版本安装留下的备份）
  $bak  = Join-Path $env:USERPROFILE ('.claude\zh\backup\' + $version)
  if (-not (Test-Path $bak)) {
    $bak = Join-Path $env:LOCALAPPDATA ('claude-zh-hans\backup\' + $version)
  }

  # 2a. 还原被补丁的 JS 文件
  if (Test-Path $bak) {
    foreach ($b in (Get-ChildItem $bak -Filter '*.js' -ErrorAction SilentlyContinue)) {
      $target = Join-Path $v1 $b.Name
      if (-not (Test-Path $target)) { Write-Warn2 ("目标文件已不存在（Claude 可能已更新）: " + $b.Name); continue }
      try { takeown /f $target /a 2>&1 | Out-Null } catch { }
      try { icacls $target /grant 'Administrators:(F)' 2>&1 | Out-Null } catch { }
      Copy-Item $b.FullName $target -Force
      Write-Ok ("已还原 " + $b.Name)
      $aclFile = Join-Path (Join-Path $bak 'acl') ($b.Name + '.acl')
      if (Test-Path $aclFile) {
        Push-Location $v1
        try { icacls $v1 /restore $aclFile 2>&1 | Out-Null } catch { }
        Pop-Location
      }
      # 尽量把所有权还给 TrustedInstaller（失败不影响功能）
      try { icacls $target /setowner 'NT SERVICE\TrustedInstaller' 2>&1 | Out-Null } catch { }
    }
  } else {
    Write-Warn2 ("未找到备份目录（该版本未被本工具补丁过或备份缺失）: " + $bak)
  }

  # 2b. 还原 shell 层官方词表
  $shellBakFile = Join-Path $bak 'shell-zh-Hans.json'
  $shellTarget  = Join-Path $res 'zh-Hans.json'
  if (Test-Path $shellBakFile) {
    try { takeown /f $shellTarget /a 2>&1 | Out-Null } catch { }
    try { icacls $shellTarget /grant 'Administrators:(F)' 2>&1 | Out-Null } catch { }
    Copy-Item $shellBakFile $shellTarget -Force
    $shellAcl = Join-Path (Join-Path $bak 'acl') 'shell-zh-Hans.json.acl'
    if (Test-Path $shellAcl) {
      Push-Location $res
      try { icacls $res /restore $shellAcl 2>&1 | Out-Null } catch { }
      Pop-Location
    }
    try { icacls $shellTarget /setowner 'NT SERVICE\TrustedInstaller' 2>&1 | Out-Null } catch { }
    Write-Ok '已还原 resources\zh-Hans.json（shell 层官方词表）'
  }

  # 2c. 删除渲染层词表
  foreach ($f in @((Join-Path $i18n 'zh-Hans.json'), (Join-Path $i18n 'dynamic\zh-Hans.json'))) {
    if (Test-Path $f) {
      try { takeown /f $f /a 2>&1 | Out-Null } catch { }
      try { icacls $f /grant 'Administrators:(F)' 2>&1 | Out-Null } catch { }
      # WindowsApps 内的文件归 TrustedInstaller 所有，回收站 API 不可用，直接删除
      [IO.File]::Delete($f)
      Write-Ok ("已删除 " + (Split-Path $f -Leaf))
    } else { Write-Ok ("本就无 " + (Split-Path $f -Leaf)) }
  }
}

# ---------- 3. 恢复 locale ----------
Write-Step '[3/4] 恢复 locale = en-US...'
$configs = Get-ChildItem $env:LOCALAPPDATA -Directory -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -like 'Claude*' } |
  ForEach-Object { Join-Path $_.FullName 'config.json' } |
  Where-Object { Test-Path $_ }
$cfgHit = 0
foreach ($cfg in $configs) {
  $txt = [IO.File]::ReadAllText($cfg, [Text.Encoding]::UTF8)
  if ($txt -match '"locale"\s*:\s*"zh-Hans"') {
    $txt2 = $txt -replace '("locale"\s*:\s*")[^"]*(")', '${1}en-US${2}'
    [IO.File]::WriteAllText($cfg, $txt2, (New-Object Text.UTF8Encoding($false)))
    Write-Ok ("locale = en-US  ->  " + $cfg)
    $cfgHit++
  }
}
if ($cfgHit -eq 0) { Write-Ok 'config.json 无需调整' }

# ---------- 3b. 停止并移除 Claude_zh 服务（v4.0）+ 清理旧版自愈资产 ----------
$SVC_NAME = 'Claude_zh'

# 兼容旧版本：v3.0 及更早的常驻 pythonw 进程
$watchProcs = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -match '^pythonw?\.exe$' -and $_.CommandLine -match 'skills-watch\.py' }
foreach ($p in $watchProcs) {
  try { Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop } catch { }
}
$hadWatch = (@($watchProcs)).Count -gt 0

# 服务停止 + 删除。三种情形都要正确收尾：
#   存在且运行 -> 先停止（等其真正停下，避免文件占用导致后续还原失败）再删除
#   存在已停止 -> 直接删除
#   不存在     -> 静默跳过（重复卸载 / 服务从未注册成功）
$svcState = 'none'
$svc = Get-Service -Name $SVC_NAME -ErrorAction SilentlyContinue
if ($svc) {
  $svcState = 'found'
  if ($svc.Status -ne 'Stopped') {
    try { Stop-Service -Name $SVC_NAME -Force -ErrorAction SilentlyContinue } catch { }
    for ($i = 0; $i -lt 20; $i++) {
      Start-Sleep -Seconds 1
      $s2 = Get-Service -Name $SVC_NAME -ErrorAction SilentlyContinue
      if (-not $s2 -or $s2.Status -eq 'Stopped') { break }
    }
  }
  # 删除：优先 pywin32（python zh_service.py remove，直接调 SCM API，不依赖
  # sc.exe）；失败再依次回退 sc.exe 与 WMI Win32_Service.Delete()
  $deleted = $false
  $svcPyPath = Join-Path (Join-Path $env:USERPROFILE '.claude\zh') 'zh_service.py'
  # 内置 Python 运行时优先（随汉化包携带、离线）；系统 Python 仅作兜底，
  # 因为用户机器上完全可能没有装 Python（此时卸载也必须能删掉服务）。
  $_zhTmp = Join-Path $env:USERPROFILE '.claude\zh'
  $_embPy = Join-Path $_zhTmp 'python\python.exe'
  if (Test-Path $_embPy) { $pySvc = $_embPy } else { $pySvc = (Get-Command python -ErrorAction SilentlyContinue).Source }
  if ($pySvc -and (Test-Path $svcPyPath)) {
    try {
      $null = & $pySvc $svcPyPath remove 2>$null
      Start-Sleep -Seconds 1
      $deleted = -not (Get-Service -Name $SVC_NAME -ErrorAction SilentlyContinue)
    } catch { }
  }
  if (-not $deleted) {
    try {
      $null = & sc.exe delete $SVC_NAME 2>$null
      Start-Sleep -Seconds 1
      $deleted = -not (Get-Service -Name $SVC_NAME -ErrorAction SilentlyContinue)
    } catch { }
  }
  if (-not $deleted) {
    try {
      $r = Invoke-CimMethod -ClassName Win32_Service -MethodName Delete `
             -Arguments @{ Name = $SVC_NAME } -ErrorAction Stop
      $deleted = ($r.ReturnValue -eq 0)
    } catch { }
  }
  if ($deleted) {
    Write-Ok ('已停止并移除 Windows 服务 ' + $SVC_NAME)
    $svcState = 'removed'
  } else {
    Write-Warn2 ('服务 ' + $SVC_NAME + ' 已停止但删除失败（可在管理员 PowerShell 执行 sc delete Claude_zh）')
    $svcState = 'delete-failed'
  }
} else {
  Write-Ok ('服务 ' + $SVC_NAME + ' 不存在，无需移除')
}

# 移除自启项（v4.0 降级路径 + 旧版驻留方案，兼容全部历史命名）
$startupDir = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup'
$hadStartup = $false
foreach ($sc in @('claude-zh-heal.cmd', 'claude-zh-skills-watch.cmd')) {
  $fp = Join-Path $startupDir $sc
  if (Test-Path $fp) { [IO.File]::Delete($fp); $hadStartup = $true }
}
# 移除 v3.0 桌面快捷方式「Claude 中文版」
$lnkPath = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Claude 中文版.lnk'
$hadLnk = Test-Path $lnkPath
if ($hadLnk) { Remove-Item $lnkPath -Force -ErrorAction SilentlyContinue }
if ($hadWatch -or $hadStartup -or $hadLnk) {
  Write-Ok '已停止旧版自愈进程，移除登录自检与「Claude 中文版」快捷方式'
}
$zhHome = Join-Path $env:USERPROFILE '.claude\zh'
# 还原补丁用的解释器：内置运行时优先，其次系统 Python
$pyExe = $null
if (Test-Path (Join-Path $zhHome 'python\python.exe')) {
  $pyExe = Join-Path $zhHome 'python\python.exe'
} else {
  $pyExe = (Get-Command python -ErrorAction SilentlyContinue).Source
}

# ---------- 3c. 还原 Claude Code 内核命令描述（translate-kernel.py --restore） ----------
$kernelLog = Join-Path $zhHome 'backup\kernel-patch-log.json'
if (Test-Path $kernelLog) {
  $kernelScript = Join-Path $PSScriptRoot 'translate-kernel.py'
  if ((Test-Path $kernelScript) -and $pyExe) {
    try { & $pyExe $kernelScript --restore } catch { Write-Warn2 ('内核补丁还原失败: ' + $_.Exception.Message) }
  } else {
    Write-Warn2 '未找到 python 或 translate-kernel.py，内核补丁未还原（不影响使用，内核更新后自动消失）'
  }
}

# ---------- 3d. 还原内核「源码字面量 / 内嵌 SKILL.md」补丁 ----------
$kernelSrcLog = Join-Path $zhHome 'backup\kernel-source-patch-log.json'
if (Test-Path $kernelSrcLog) {
  $kernelSrc = Join-Path $PSScriptRoot 'translate-kernel-source.py'
  if ((Test-Path $kernelSrc) -and $pyExe) {
    try { & $pyExe $kernelSrc --restore } catch { Write-Warn2 ('内核源码补丁还原失败: ' + $_.Exception.Message) }
  } else {
    Write-Warn2 '未找到 python 或 translate-kernel-source.py，内核源码补丁未还原'
  }
}

# ---------- 3e. 还原 app.asar 技能描述补丁（translate-asar-source.py --restore） ----------
$asarLog = Join-Path $zhHome 'backup\asar-source-patch-log.json'
if (Test-Path $asarLog) {
  $asarSrc = Join-Path $PSScriptRoot 'translate-asar-source.py'
  if ((Test-Path $asarSrc) -and $pyExe) {
    try {
      & $pyExe $asarSrc --restore
      Write-Ok '已还原 app.asar 技能描述补丁'
    } catch { Write-Warn2 ('app.asar 技能描述补丁还原失败: ' + $_.Exception.Message) }
  } else {
    Write-Warn2 '未找到 python 或 translate-asar-source.py，app.asar 补丁未还原'
  }
}

$skillsBase = Join-Path $env:LOCALAPPDATA 'Claude-3p\local-agent-mode-sessions\skills-plugin'
if (Test-Path $skillsBase) {
  $restoredSkills = 0
  foreach ($bakFile in (Get-ChildItem $skillsBase -Recurse -Filter '*.zh-bak' -ErrorAction SilentlyContinue)) {
    $orig = $bakFile.FullName -replace '\.zh-bak$',''
    try {
      Copy-Item $bakFile.FullName $orig -Force
      [IO.File]::Delete($bakFile.FullName)
      $restoredSkills++
    } catch { Write-Warn2 ('技能文件还原失败: ' + $orig) }
  }
  if ($restoredSkills -gt 0) { Write-Ok ("已还原技能描述英文原文（" + $restoredSkills + " 个文件）") }
  else { Write-Ok '技能描述无需还原' }
}

# ---------- 3f. 清理用户目录 .claude\zh（先归档后删除） ----------
# 上面各还原步骤已按 .claude\zh\backup 中的日志/备份完成还原，本目录使命结束。
# 删除前整目录 zip 归档到 %TEMP%（含原始备份与还原日志，误卸载可完整找回），
# 删除后 Claude-3p 官方用户数据不受影响（上面仅回写了 locale 字段）。
if (Test-Path $zhHome) {
  $restorePending = $false
  foreach ($lg in @('backup\kernel-patch-log.json', 'backup\kernel-source-patch-log.json',
                    'backup\asar-source-patch-log.json')) {
    if (Test-Path (Join-Path $zhHome $lg)) { $restorePending = $true }
  }
  if ($restorePending) {
    Write-Warn2 '检测到还原日志仍存在（内核/asar 还原未执行成功），.claude\zh 暂不删除以防不可恢复'
  } else {
    try {
      $ts = Get-Date -Format 'yyyyMMddTHHmmss'
      $zipPath = Join-Path $env:TEMP ("claude-zh-uninstall-" + $ts + ".zip")
      if (Get-Command Compress-Archive -ErrorAction SilentlyContinue) {
        Compress-Archive -Path (Join-Path $zhHome '*') -DestinationPath $zipPath -Force
        Write-Ok ('已归档到: ' + $zipPath)
      }
    } catch {
      Write-Warn2 ('归档失败（仍继续删除）: ' + $_.Exception.Message)
    }
    try {
      Remove-Item $zhHome -Recurse -Force -ErrorAction Stop
      Write-Ok ('已删除汉化运行目录: ' + $zhHome)
    } catch {
      Write-Warn2 ('目录删除失败（部分文件被占用）: ' + $_.Exception.Message)
    }
  }
}
# ---------- 3g. 旧版备份目录提示（v2.7 之前写在 %LOCALAPPDATA%\claude-zh-hans） ----------
# 安装脚本自 v2.7 起统一到 %USERPROFILE%\.claude\zh，但更早的安装可能在旧位置留下
# 备份。这里只提示不删除：目录里可能有旧版本的原始文件，删除与否交由用户确认。
$legacyDir = Join-Path $env:LOCALAPPDATA 'claude-zh-hans'
if (Test-Path $legacyDir) {
  Write-Warn2 ('发现旧版汉化备份目录（v2.7 之前的位置）: ' + $legacyDir)
  Write-Warn2 '本脚本不会自动删除它；确认无需保留后可手动删除。汉化本体已完全清除，不影响使用。'
}

$projStore = Join-Path (Split-Path $PSScriptRoot -Parent) 'resources\translations\zh-store.json'
if (Test-Path $projStore) {
  Write-Ok ('词条仓库已保留（卸载不丢词条，重装免重译）: ' + $projStore)
}
Write-Ok 'Claude-3p 为 Claude 官方用户数据目录，已按官方数据处理：仅回写 locale 字段，目录保留'

# ---------- 4. 校验 ----------
Write-Step '[4/4] 卸载后校验...'
$dirty = $false
foreach ($pkg in $pkgs) {
  $ver  = ($pkg.Name -split '_')[1]
  $i18n = Join-Path (Join-Path $pkg.FullName 'app\resources') 'ion-dist\i18n'
  $v1   = Join-Path (Join-Path $pkg.FullName 'app\resources') 'ion-dist\assets\v1'
  if (Test-Path (Join-Path $i18n 'zh-Hans.json')) { Write-Bad ("[$ver] zh-Hans.json 仍存在"); $dirty = $true }
  $hasZh = $false
  foreach ($f in (Get-ChildItem $v1 -Filter '*.js' -ErrorAction SilentlyContinue)) {
    $s = $latin.GetString([IO.File]::ReadAllBytes($f.FullName))
    if ($s.Contains('"en-US","zh-Hans","de-DE"')) { $hasZh = $true; break }
  }
  if ($hasZh) { Write-Bad ("[$ver] 白名单补丁仍存在（可能被 Claude 更新覆盖过备份，请重新安装后再卸载）"); $dirty = $true }
}
if (-not $dirty) { Write-Ok '所有汉化内容已清除' }

Write-Host ''
if ($script:FailCount -eq 0) {
  Write-Host '卸载完成！已还原全部程序文件，删除 %USERPROFILE%\.claude\zh 与自启项，' -ForegroundColor Green
  Write-Host '停止并移除全部汉化自愈组件（无任何驻留进程）。' -ForegroundColor Green
  Write-Host 'Claude-3p 为官方用户数据目录，已保留（仅 locale 回写为 en-US）。' -ForegroundColor Green
  Write-Host '请重新启动 Claude，界面将恢复为英文。' -ForegroundColor Green
  exit 0
} else {
  Write-Host '卸载存在未解决项，请检查上方输出。' -ForegroundColor Red
  exit 1
}
