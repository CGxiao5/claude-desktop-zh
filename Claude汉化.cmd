@echo off
REM ============================================================================
REM  Claude Desktop 简体中文汉化 —— 一体化管理工具
REM
REM  功能（输入数字选择）：
REM      1  安装 Claude 汉化
REM      2  卸载 Claude 汉化（保留 Claude 应用本身，界面恢复英文）
REM      3  彻底卸载 Claude（移除应用本体 + 全部残留，先扫描后确认）
REM      0  退出
REM
REM  设计原则：
REM    1) 启动即检测管理员权限；无权限时输出明确失败提示并退出，不做半途而废的操作
REM    2) 路径全部由环境变量动态拼接（%USERPROFILE% / %LOCALAPPDATA% / %APPDATA%）
REM       —— 无硬编码用户名、无硬编码用户路径，跨机器 / 跨用户名通用
REM    3) 彻底卸载：先扫描展示 → 再确认（回车或 Y 执行 / N 取消）；非法输入提示重输
REM    4) 删除前先检测存在性；不存在则跳过，不产生任何报错
REM    5) 用户数据直接删除，不做任何归档 / 备份
REM    6) 应用包走 MSIX 官方卸载机制，而非直接删 WindowsApps 目录
REM
REM  ★ 编码铁律（踩过坑，务必遵守）★
REM    cmd.exe 始终按系统 ANSI 代码页（中文 Windows 为 936/GBK）读取并解析批处理
REM    文件。若本文件存为 UTF-8，中文会被按 GBK 误解析——轻则乱码，重则某些字节
REM    被当成引号 / 管道符，直接破坏 for /f 与 echo 的语法结构。
REM    因此：本文件必须以 GBK 保存，且脚本内不要执行 chcp 65001。
REM ============================================================================

setlocal EnableDelayedExpansion
cd /d "%~dp0"
title Claude Desktop 简体中文汉化管理工具

REM ---------- 动态路径（全部取自环境变量，跨机器 / 跨用户名通用） ----------
set "UP=%USERPROFILE%"
set "LAD=%LOCALAPPDATA%"
set "RAD=%APPDATA%"
if not defined LAD set "LAD=%UP%\AppData\Local"
if not defined RAD set "RAD=%UP%\AppData\Roaming"
if not defined UP set "UP=%USERPROFILE%"
REM 彻底卸载流程全程依赖 %TEMP% 存放扫描脚本与日志；极少数环境（精简
REM 系统 / 服务上下文）该变量可能缺失，缺了会写到盘符根目录而失败。
if not defined TEMP set "TEMP=%LAD%\Temp"
set "ZH=%UP%\.claude\zh"
REM ★ 安全护栏基准：脚本自身所在目录（汉化包目录）。
REM   彻底卸载清除的是 Claude 的残留，汉化包本身（Claude汉化.cmd / README.md /
REM   Claude_zh服务说明.md / zh\ 等）不属于残留，任何删除动作都不得触及。
set "SELF=%~dp0"

REM ============================================================================
REM  [权限] 管理员权限检查——不足时输出明确提示并退出
REM ============================================================================
echo.
echo  ==========================================================
echo    Claude Desktop 简体中文汉化 —— 管理工具
echo  ==========================================================
echo.
echo  [检查] 正在验证管理员权限...

set "ISADMIN=0"
net session >nul 2>&1
if !errorlevel!==0 set "ISADMIN=1"
if "!ISADMIN!"=="0" (
  fltmc >nul 2>&1
  if !errorlevel!==0 set "ISADMIN=1"
)

if "!ISADMIN!"=="0" (
  echo.
  echo  [失败] 当前不是管理员权限，无法继续。
  echo.
  echo   原因：本工具需要
  echo          1^) 改写 Claude 安装目录（WindowsApps，归 TrustedInstaller 所有）
  echo          2^) 注册 / 删除 Windows 服务 Claude_zh
  echo         这两类操作都必须以管理员身份运行，普通权限会在中途静默失败。
  echo.
  echo   请这样重新运行：
  echo          1. 在本文件上点击鼠标右键
  echo          2. 选择"以管理员身份运行"
  echo          3. 若弹出 UAC 窗口，点击"是"
  echo.
  echo   为避免半途而废造成汉化状态不一致，这里直接退出。
  echo.
  pause
  exit /b 1
)
echo  [OK] 已具备管理员权限。
echo.
REM 注意：这里不要用 timeout /t —— 它会抢读 stdin 的第一个按键，
REM 导致后续 set /p 读不到用户的选择（实测吞字符）。
goto :MENU

REM ============================================================================
REM  主菜单
REM ============================================================================
:MENU
call :REFRESH_STATUS
cls
echo.
echo  ==========================================================
echo    Claude Desktop 简体中文汉化 —— 管理工具
echo  ==========================================================
echo.
echo    当前状态   汉化: !ZHSTAT!
echo              服务: !SVCSTAT!
echo.
echo  ----------------------------------------------------------
echo     1   安装 Claude 汉化
echo     2   卸载 Claude 汉化   （保留 Claude，界面恢复英文）
echo     3   彻底卸载 Claude    （移除应用本体及全部残留）
echo     0   退出
echo  ----------------------------------------------------------
echo.

set "MRETRY=0"

:MENU_INPUT
if !MRETRY! GEQ 10 (
  echo.
  echo  [提示] 连续 10 次未获得有效输入，已自动退出。
  echo.
  pause
  goto :EXIT_OK
)
REM 哨兵值技巧：set /p 读不到内容时会保持变量原值（实测：直接回车与输入流
REM 结束 EOF 都是如此，二者无法区分）。统一按"未读取到输入"计数重试，
REM 既避免误判成某个菜单项，也不会在输入流异常时陷入无限重输的死循环。
set "CH=__EOF__"
set /p "CH=请输入数字并选择： "
if "!CH!"=="__EOF__" (
  set /a MRETRY+=1
  echo.
  echo  [无效] 未读取到输入，请输入 0 ~ 3 的数字。
  echo.
  pause
  goto :MENU_INPUT
)
if "!CH!"=="1" goto :DO_INSTALL
if "!CH!"=="2" goto :DO_UNINSTALL
if "!CH!"=="3" goto :DO_FULL
if "!CH!"=="0" goto :EXIT_OK
set /a MRETRY+=1
echo.
echo  [无效] 只能输入 0 ~ 3 的数字（"!CH!" 不是有效选项），请重新选择。
echo.
pause
goto :MENU_INPUT

REM ============================================================================
REM  [1] 安装汉化
REM ============================================================================
:DO_INSTALL
cls
echo.
echo  ==========================================================
echo   [1] 安装 Claude 汉化
echo  ==========================================================
echo.
echo   将要执行：
echo     - 部署中文词表（渲染层 / shell 层 / dynamic 三份）
echo     - 补丁 4 个 JS 语言白名单与 app.asar 技能描述
echo     - 汉化 Claude Code 内核命令描述
echo     - 设置界面语言 locale = zh-Hans
echo     - 部署内置 Python 运行环境（随汉化包携带，离线，不依赖系统 Python）
echo     - 注册并启动 Windows 服务 Claude_zh（维持汉化，开机自启）
echo     - （可选）检测到包内 gateway.json 时，写入免登录网关配置（官方 3P 模式）
echo.
echo   注意：安装过程会自动退出正在运行的 Claude。
echo.
pause
echo.
echo  ----------------------------------------------------------
REM ---- 内置 Python 运行环境检测（离线随包携带；缺失只提示，不联网下载）----
set "ZH_PY_SRC=%~dp0zh\python\python.exe"
set "ZH_PY=%USERPROFILE%\.claude\zh\python\python.exe"
if exist "%ZH_PY_SRC%" (
  echo  [检测] 汉化包内置 Python 运行环境：存在，将随安装部署到 .claude\zh\python
) else (
  echo  [警告] 汉化包缺少内置 Python 运行环境：%ZH_PY_SRC%
  echo         汉化本体仍会正常安装，但守护服务无法注册（Claude 更新后不会自动恢复）。
  echo         请使用完整汉化包重新安装 —— 本程序不会联网下载 Python。
  echo.
  pause
)
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0zh\scripts\install-zh.ps1"
set "RC=!errorlevel!"
echo  ----------------------------------------------------------
echo.
if "!RC!"=="0" (
  echo  [完成] 汉化安装成功。
  echo.
  echo   请重新启动 Claude（正常从桌面图标或开始菜单启动即可，无需特殊方式）。
  echo   服务 Claude_zh 已随开机自启，Claude 更新后会自动恢复中文。
  if exist "%ZH_PY%" (
    echo  [检测] 内置 Python 运行环境已就位：%ZH_PY%
  ) else (
    echo  [警告] 内置 Python 运行环境未部署：%ZH_PY%
    echo         守护服务不可用，请重新运行安装（不会联网下载）。
  )
) else (
  echo  [失败] 安装未成功，退出码 !RC!。
  echo         请查看上方输出定位问题，或参考 README.md 的常见问题排查。
)
echo.
pause
goto :MENU

REM ============================================================================
REM  [2] 卸载汉化
REM ============================================================================
:DO_UNINSTALL
cls
echo.
echo  ==========================================================
echo   [2] 卸载 Claude 汉化
echo  ==========================================================
echo.
echo   将要执行：
echo     - 停止并移除 Windows 服务 Claude_zh
echo     - 还原 4 个 JS、app.asar、Claude Code 内核、shell 词表
echo     - 删除部署的词表，locale 恢复 en-US
echo     - 归档并删除 %UP%\.claude\zh（仅本选项，归档到 %TEMP% 供误卸载找回）
echo.
echo   注意：Claude 应用本体保留，界面恢复英文。
echo         词条仓库（zh-store.json）保留，重装汉化无需重新翻译。
echo.
pause
echo.
echo  ----------------------------------------------------------
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0zh\scripts\uninstall-zh.ps1"
set "RC=!errorlevel!"
echo  ----------------------------------------------------------
echo.
if "!RC!"=="0" (
  echo  [完成] 汉化已卸载。请重新启动 Claude，界面将恢复为英文。
) else (
  echo  [失败] 卸载未完全成功，退出码 !RC!。
  echo         请查看上方输出；若提示还原日志仍在，可重跑一次本选项。
)
echo.
pause
goto :MENU

REM ============================================================================
REM  [3] 彻底卸载 Claude —— 先扫描，再确认
REM ============================================================================
:DO_FULL
cls
set "TS=%DATE:~0,4%%DATE:~5,2%%DATE:~8,2%_%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%"
set "TS=%TS: =0%"
set "LOG=%TEMP%\claude-uninstall-%TS%.log"
set /a N_OK=0
set /a N_SKIP=0
set /a N_FAIL=0

echo.
echo  ==========================================================
echo   [3] 彻底卸载 Claude
echo  ==========================================================
echo.
echo  本操作会移除 Claude 应用本体及全部本地残留（含用户配置、会话、快捷方式、
echo  注册表项）。聊天记录保存在云端，不受影响。
echo  清理模式：直接删除，全程不创建备份、压缩包或还原点。
echo.
echo  [1/5] 扫描清理目标（仅检测，不做任何修改）...
echo.

set /a CNT_PKGDIR=0
set /a CNT_USER=0
set /a CNT_LNK=0
set /a CNT_REG=0

echo  --[A] 应用包 / 安装目录--
for /f "usebackq delims=" %%D in (`
  powershell -NoProfile -ExecutionPolicy Bypass -Command ^
   "$r=@(); $p=@(Get-AppxPackage -Name 'Claude' -AllUsers -ErrorAction SilentlyContinue); foreach($x in $p){ if($x.InstallLocation -and (Test-Path $x.InstallLocation)){$r+=$x.InstallLocation} }; if($r.Count -eq 0){ $g=Get-ChildItem 'C:\Program Files\WindowsApps' -Directory -Filter 'Claude_*' -Force -ErrorAction SilentlyContinue; foreach($y in @($g)){ $r+=$y.FullName } }; $r"
`) do (
  set "_C=%%D"
  if /i "!_C:~1,1!"==":" (
    set /a CNT_PKGDIR+=1
    set "PKGDIR!CNT_PKGDIR!=%%D"
    echo    [发现] !_C!
  )
)
if !CNT_PKGDIR!==0 echo    [无]   未发现 Claude 安装目录（可能已通过系统卸载）。
echo.

echo  --[A2] 其他盘符安装目录（只检查标准安装路径，不扫描盘内其他内容）--
set /a CNT_ODIR=0
for %%z in (D E F G H I J K L M N O P Q R S T U V W X Y Z) do (
  if exist "%%z:\" (
    for %%p in ("%%z:\Program Files\Claude" "%%z:\Program Files (x86)\Claude" "%%z:\Program Files\AnthropicClaude" "%%z:\Program Files\Anthropic" "%%z:\Claude-3p") do (
      if exist "%%~p" (
        set /a CNT_ODIR+=1
        set "ODIR!CNT_ODIR!=%%~p"
        set "_OP=%%~p"
        echo    [发现] !_OP!
      )
    )
  )
)
if !CNT_ODIR!==0 echo    [无]   其他盘符未发现 Claude 安装目录。
echo.

echo  --[B] 用户配置与数据目录--
set "UDIR1=%LAD%\Claude"
set "UDIR2=%LAD%\Claude-3p"
set "UDIR3=%LAD%\Claude-Data"
set "UDIR4=%RAD%\Claude"
set "UDIR5=%UP%\.claude"
set "UDIR6=C:\ProgramData\Claude"
set "UDIR7=%LAD%\Temp\claude"
set "UDIR8=%LAD%\AnthropicClaude"
set "UDIR9=%RAD%\Claude-Data"
set "UFILE=%UP%\.claude.json"

for %%i in (1 2 3 4 5 6 7 8 9) do (
  if exist "!UDIR%%i!" (
    echo    [发现] !UDIR%%i!
    set /a CNT_USER+=1
  ) else (
    echo    [无]   !UDIR%%i!
  )
)
if exist "%UFILE%" (
  echo    [发现] %UFILE%
  set /a CNT_USER+=1
) else (
  echo    [无]   %UFILE%
)
echo.

echo  --[B2] C 盘顶层兜底扫描（只在 C 盘，找名称含 claude / anthropic 的目录）--
set /a CNT_XDIR=0
set "PSX=%TEMP%\claude-scan-c-%TS%.ps1"
>  "%PSX%" echo $ErrorActionPreference='SilentlyContinue'
>> "%PSX%" echo $skip=@('%UDIR1%','%UDIR2%','%UDIR3%','%UDIR4%','%UDIR5%','%UDIR6%','%UDIR7%','%UDIR8%','%UDIR9%','%UFILE%')
>> "%PSX%" echo $roots=@($env:LOCALAPPDATA,$env:APPDATA,$env:USERPROFILE,'C:\ProgramData','C:\Program Files','C:\Program Files (x86)',$env:TEMP)
>> "%PSX%" echo $hit=@()
>> "%PSX%" echo foreach($r in $roots){ if(-not $r){continue}; if(-not (Test-Path -LiteralPath $r)){continue}; Get-ChildItem -LiteralPath $r -Force -Directory -ErrorAction SilentlyContinue ^| Where-Object { $_.Name -match 'claude^|anthropic' -and ($skip -notcontains $_.FullName) } ^| ForEach-Object { $hit+=$_.FullName } }
>> "%PSX%" echo $hit
powershell -NoProfile -ExecutionPolicy Bypass -File "%PSX%" > "%TEMP%\cu-scan-c.txt" 2>&1
REM 只收录形如 X:\... 的绝对路径行：PowerShell 报错/版权横幅等文本不得进删除清单
for /f "usebackq delims=" %%D in ("%TEMP%\cu-scan-c.txt") do (
  set "_C=%%D"
  if /i "!_C:~1,1!"==":" (
    set /a CNT_XDIR+=1
    set "XDIR!CNT_XDIR!=%%D"
    echo    [发现] !_C!
  )
)
if !CNT_XDIR!==0 echo    [无]   未发现其它命名残留。
if exist "%PSX%" del /f /q "%PSX%" >nul 2>&1
if exist "%TEMP%\cu-scan-c.txt" del /f /q "%TEMP%\cu-scan-c.txt" >nul 2>&1
echo.

echo  --[C] 快捷方式与启动项--
set "LNK1=%UP%\Desktop\Claude.lnk"
set "LNK2=%RAD%\Microsoft\Windows\Start Menu\Programs\Claude.lnk"
set "LNK3=C:\Users\Public\Desktop\Claude.lnk"
set "LNK4=%RAD%\Microsoft\Windows\Start Menu\Programs\Startup\Claude.lnk"
REM 汉化项目可能留下的开机自愈 / 守护启动项与中文版快捷方式（存在则一并清理）
set "LNK5=%RAD%\Microsoft\Windows\Start Menu\Programs\Startup\claude-zh-heal.cmd"
set "LNK6=%RAD%\Microsoft\Windows\Start Menu\Programs\Startup\claude-zh-skills-watch.cmd"
set "LNK7=%UP%\Desktop\Claude 中文版.lnk"

for %%i in (1 2 3 4 5 6 7) do (
  if exist "!LNK%%i!" (
    echo    [发现] !LNK%%i!
    set /a CNT_LNK+=1
  ) else (
    echo    [无]   !LNK%%i!
  )
)
echo.

echo  --[D] 注册表残留--
call :SCAN_REG
echo.

echo  --[E] C 盘临时文件与安装日志残留--
set /a CNT_TF=0
for /f "usebackq delims=" %%F in (`dir /b /a-d "%TEMP%\claude*" 2^>nul`) do (
  set /a CNT_TF+=1
  set "TFILE!CNT_TF!=%%F"
  echo    [发现] %TEMP%\%%F
)
if !CNT_TF!==0 echo    [无]   未发现临时文件残留。
echo.

echo  ==========================================================
echo   扫描结果：C 盘安装目录 !CNT_PKGDIR! 项 / 其他盘符安装目录 !CNT_ODIR! 项
echo             用户配置与数据 !CNT_USER! 项 / C 盘其它残留 !CNT_XDIR! 项
echo             快捷方式 !CNT_LNK! 项 / 注册表 !CNT_REG! 项 / 临时文件 !CNT_TF! 项
echo  ==========================================================
echo.

if !CNT_PKGDIR!==0 if !CNT_ODIR!==0 if !CNT_XDIR!==0 if !CNT_TF!==0 if !CNT_USER!==0 if !CNT_LNK!==0 if !CNT_REG!==0 (
  echo  没有发现任何 Claude 残留，无需清理。
  echo.
  pause
  goto :MENU
)

echo  本操作将永久删除上述项目，其中：
echo    - 用户配置与数据将被直接删除，不做任何备份、不经过回收站，无法恢复
echo    - 应用包通过系统官方机制卸载
echo    - Claude 聊天记录保存在云端，不受本地卸载影响
echo.
echo  [警告] 此操作不经过回收站，无法通过回收站撤销。
echo.

REM ---------------- 确认环节：回车或 Y 执行，N 取消，非法重输 ----------------
REM set /p 的关键陷阱（实测确认）：输入为空（直接回车）与输入流已结束(EOF)时，
REM 变量都保持原值、都不会被改写——单靠它无法区分"人按了回车"和"没的可读"。
REM 因此"回车=确认执行"必须先确认眼前是有人在键盘前操作的交互式控制台。
REM 判定方法：Windows 自带 timeout.exe 在输入被重定向时立即以 errorlevel 1 退出，
REM 在真实控制台返回 0。必须写全路径——否则可能命中 Git 自带的 GNU timeout
REM （它对 /t 参数一律报用法错误、返回 125，会让判定彻底失效）。
set "CRETRY=0"
set "IN_TTY=0"
"%SystemRoot%\System32\timeout.exe" /t 0 >nul 2>&1
if not errorlevel 1 set "IN_TTY=1"

:CONFIRM_LOOP
if !CRETRY! GEQ 10 (
  echo.
  echo  [提示] 连续 10 次未获得有效输入，已取消操作（未做任何改动）。
  echo.
  pause
  goto :MENU
)
set "CONFIRM="
set /p "CONFIRM=确认执行？回车或输入 Y 执行，输入 N 取消： "
if not defined CONFIRM (
  REM 交互式控制台：按提示语义，回车即确认执行。
  if "!IN_TTY!"=="1" goto :DO_REMOVE
  echo.
  echo  [已取消] 未检测到键盘输入（脚本可能以重定向/自动方式运行）。
  echo           这种情况不按"回车"处理，请输入明确的 Y 后重试，以免误删。
  echo.
  pause
  goto :MENU
)
if /i "!CONFIRM!"=="Y" goto :DO_REMOVE
if /i "!CONFIRM!"=="YES" goto :DO_REMOVE
if /i "!CONFIRM!"=="N" goto :CONFIRM_CANCEL
if /i "!CONFIRM!"=="NO" goto :CONFIRM_CANCEL
set /a CRETRY+=1
echo.
echo  [无效] "!CONFIRM!" 不是有效输入：回车或 Y 执行，N 取消。
echo.
goto :CONFIRM_LOOP

:CONFIRM_CANCEL
echo.
echo  已取消，未做任何改动。
echo.
pause
goto :MENU

REM ============================================================================
REM  [3] 执行彻底卸载
REM ============================================================================
:DO_REMOVE
echo.
echo  [2/5] 停止汉化服务与 Claude 进程...
echo.

REM 先停掉汉化服务：服务进程持有 %UP%\.claude\zh 下文件的句柄与 python 解释器，
REM 不先停止会导致后续删除失败（表现为"文件被占用"）。
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
 "$s=Get-Service -Name 'Claude_zh' -ErrorAction SilentlyContinue; if($s){ if($s.Status -ne 'Stopped'){ Stop-Service -Name 'Claude_zh' -Force -ErrorAction SilentlyContinue; Start-Sleep -Seconds 3 }; & sc.exe delete Claude_zh 2>$null; Write-Output '   [OK] 已停止并移除服务 Claude_zh' } else { Write-Output '   [跳过] 服务 Claude_zh 不存在' }"

REM Claude 启动时会陆续孵化子进程，单轮 taskkill 杀不干净，
REM 残留进程占用文件句柄会导致后续删除失败，故采用多轮强退。
set "ROUND=0"
set "EVER=0"
:KILL_LOOP
set /a ROUND+=1
set "FOUND=0"
tasklist /FI "IMAGENAME eq Claude.exe" /NH 2>nul | find /I "Claude.exe" >nul
if !errorlevel!==0 (
  set "FOUND=1"
  set "EVER=1"
  taskkill /F /IM "Claude.exe" /T >nul 2>&1
)
if "!FOUND!"=="1" (
  if !ROUND! LSS 5 (
    ping -n 2 127.0.0.1 >nul
    goto :KILL_LOOP
  )
)
if "!EVER!"=="1" (
  echo   [OK] 已结束 Claude 进程（第 !ROUND! 轮后清零）。
  set /a N_OK+=1
) else (
  echo   [跳过] 未检测到运行中的 Claude 进程。
  set /a N_SKIP+=1
)
echo.

echo.

echo  [3/5] 卸载 Claude MSIX 应用包（官方机制）...
echo.
set "PS1=%TEMP%\claude-uninst-%TS%.ps1"
>  "%PS1%" echo $ErrorActionPreference = 'Continue'
>> "%PS1%" echo $pkgs = @(Get-AppxPackage -Name 'Claude' -AllUsers -ErrorAction SilentlyContinue)
>> "%PS1%" echo if ($pkgs.Count -eq 0) { Write-Output 'RESULT:NOTFOUND' } else { foreach ($p in $pkgs) { try { Remove-AppxPackage -Package $p.PackageFullName -AllUsers -ErrorAction Stop; Write-Output ('RESULT:REMOVED:' + $p.PackageFullName) } catch { Write-Output ('RESULT:FAIL:' + $_.Exception.Message) } } }
>> "%PS1%" echo $prov = @(Get-AppxProvisionedPackage -Online -ErrorAction SilentlyContinue ^| Where-Object { $_.DisplayName -match 'Claude' })
>> "%PS1%" echo foreach ($q in $prov) { try { Remove-AppxProvisionedPackage -Online -PackageName $q.PackageName -ErrorAction SilentlyContinue ^| Out-Null; Write-Output ('PROV:REMOVED:' + $q.DisplayName) } catch { Write-Output 'PROV:SKIP' } }

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%" > "%TEMP%\cu-out.txt" 2>&1
for /f "usebackq delims=" %%L in ("%TEMP%\cu-out.txt") do echo   %%L
type "%TEMP%\cu-out.txt" >> "%LOG%"
findstr /C:"RESULT:REMOVED" "%TEMP%\cu-out.txt" >nul
if !errorlevel!==0 (
  echo   [OK] 应用包已卸载（含预配包清理）。
  set /a N_OK+=1
) else (
  findstr /C:"RESULT:NOTFOUND" "%TEMP%\cu-out.txt" >nul
  if !errorlevel!==0 (
    echo   [跳过] 系统中没有已安装的 Claude 应用包。
    set /a N_SKIP+=1
  ) else (
    echo   [失败] 应用包卸载未成功（详见上方输出）。
    echo          建议：设置 → 应用 → Claude → 卸载，然后重跑本脚本清理残留。
    set /a N_FAIL+=1
  )
)
if exist "%PS1%" del /f /q "%PS1%" >nul 2>&1
if exist "%TEMP%\cu-out.txt" del /f /q "%TEMP%\cu-out.txt" >nul 2>&1
echo.

echo  [4/5] 执行删除（每一项均先检测存在性）...
echo.
echo  --[A] C 盘安装目录残留--
if !CNT_PKGDIR! GTR 0 (
  for /l %%i in (1,1,!CNT_PKGDIR!) do call :RMDIR_SAFE "!PKGDIR%%i!" "C 盘安装目录"
) else (
  echo    [跳过] 没有 C 盘安装目录残留。
)
echo.

echo  --[A2] 其他盘符安装目录--
if !CNT_ODIR! GTR 0 (
  for /l %%i in (1,1,!CNT_ODIR!) do call :RMDIR_SAFE "!ODIR%%i!" "其他盘符安装目录"
) else (
  echo    [跳过] 其他盘符没有 Claude 安装目录。
)
echo.

echo  --[B] 用户配置与数据目录--
for %%i in (1 2 3 4 5 6 7 8 9) do call :RMDIR_SAFE "!UDIR%%i!" "用户数据目录"
call :DELFILE_SAFE "%UFILE%" "用户数据文件"
echo.

echo  --[B2] C 盘兜底扫描发现的残留目录--
if !CNT_XDIR! GTR 0 (
  for /l %%i in (1,1,!CNT_XDIR!) do call :RMDIR_SAFE "!XDIR%%i!" "C 盘残留目录"
) else (
  echo    [跳过] 没有其它命名残留。
)
echo.

echo  --[C] 快捷方式与启动项--
for %%i in (1 2 3 4 5 6 7) do call :DELFILE_SAFE "!LNK%%i!" "快捷方式/启动项"
echo.

echo  --[D] 注册表残留--
call :CLEAN_REG
echo.

echo  --[E] C 盘临时文件与安装日志残留--
if !CNT_TF! GTR 0 (
  for /l %%i in (1,1,!CNT_TF!) do call :DELFILE_SAFE "%TEMP%\!TFILE%%i!" "临时文件"
) else (
  echo    [跳过] 没有临时文件残留。
)
echo.

echo  [5/5] 卸载结果摘要
echo.
echo  ==========================================================
echo   卸载结果摘要
echo  ==========================================================
echo.
echo   删除成功     : !N_OK! 项
echo   跳过(不存在) : !N_SKIP! 项
echo   失败         : !N_FAIL! 项
echo.
echo   清理模式     : 直接删除，未创建任何备份 / 压缩包 / 还原点
echo.
echo   残留复检     :
set "LEFT=0"
call :RECHECK UDIR 9 ""
call :RECHECK PKGDIR !CNT_PKGDIR! ""
call :RECHECK ODIR !CNT_ODIR! ""
call :RECHECK XDIR !CNT_XDIR! ""
call :RECHECK TFILE !CNT_TF! "%TEMP%"
if exist "%UFILE%" (
  echo     [残留] %UFILE%
  set /a LEFT+=1
)
if !LEFT!==0 echo     无残留，清理彻底。
echo.
(
echo ===== Claude 卸载摘要 %TS% =====
echo 删除成功: !N_OK!  跳过: !N_SKIP!  失败: !N_FAIL!
echo 清理模式: 直接删除，无备份
)>>"%LOG%"
echo   完整日志: %LOG%
echo.
echo  提示：建议重启一次电脑，确保 MSIX 包信息与文件句柄完全释放。
echo.
pause
goto :MENU

REM ============================================================================
REM  子程序：刷新状态显示
REM ============================================================================
:REFRESH_STATUS
set "ZHSTAT=未安装"
if exist "%ZH%\skills-watch.py" set "ZHSTAT=已安装"
set "SVCSTAT=未注册"
for /f "usebackq delims=" %%S in (`
  powershell -NoProfile -ExecutionPolicy Bypass -Command ^
   "$s=Get-Service -Name 'Claude_zh' -ErrorAction SilentlyContinue; if($s){ Write-Output ('已注册(' + $s.Status + ')') } else { Write-Output 'NONE' }"
`) do set "SVCSTAT=%%S"
if "!SVCSTAT!"=="NONE" set "SVCSTAT=未注册"
goto :eof

REM ============================================================================
REM  子程序：残留复检  %1=变量名前缀  %2=数量  %3=可选父目录
REM  命中即打印 [残留] 并累加 LEFT
REM ============================================================================
:RECHECK
set "_RP=%~1"
set "_RN=%~2"
set "_RB=%~3"
if not defined _RN goto :eof
if "!_RN!"=="" goto :eof
if !_RN! LEQ 0 goto :eof
for /l %%i in (1,1,!_RN!) do (
  call set "_RT=%%!_RP!%%i%%"
  if defined _RB set "_RT=!_RB!\!_RT!"
  if exist "!_RT!" (
    echo     [残留] !_RT!
    set /a LEFT+=1
  )
)
goto :eof

REM ============================================================================
REM  子程序：安全删除目录（先检测存在性，再删除；失败不中断脚本）
REM  %~1 = 目录路径    %~2 = 描述文字
REM ============================================================================
:RMDIR_SAFE
set "_P=%~1"
set "_D=%~2"
if not defined _P goto :eof
call :GUARD_PATH "!_P!" _OK
if "!_OK!"=="0" (
  echo    [保护] 拒绝删除受保护/非法路径: !_P!
  set /a N_SKIP+=1
  goto :eof
)
if not exist "!_P!" (
  echo    [跳过] !_D! 不存在: !_P!
  set /a N_SKIP+=1
  goto :eof
)
echo    - 删除 !_D!: !_P! ...
rd /s /q "!_P!" >nul 2>&1
if exist "!_P!" (
  echo      [失败] 目录仍存在（可能被进程占用或权限不足）。
  set /a N_FAIL+=1
) else (
  echo      [完成] 已删除。
  set /a N_OK+=1
)
goto :eof

REM ============================================================================
REM  子程序：路径安全护栏（彻底卸载的唯一删除闸门）
REM  %~1 = 待删路径；%~2 = 返回变量名（1=允许删除，0=拒绝）
REM  拒绝规则：
REM    1) 空路径 / 未定义
REM    2) 非绝对路径（第 2 个字符不是冒号）——防止相对路径命中当前目录
REM    3) 盘符根目录（如 D:\）
REM    4) ★ 脚本自身所在目录（汉化包目录）及其内部任何内容 ★
REM    5) 系统/用户关键目录本身（Windows、Program Files、Users、用户主目录等）
REM ============================================================================
:GUARD_PATH
set "_G=%~1"
set "%~2=0"
if not defined _G goto :eof
if /i not "!_G:~1,1!"==":" goto :eof
if "!_G:~3!"=="" goto :eof
echo "!_G!" | findstr /I /C:"!SELF!" >nul
if !errorlevel!==0 goto :eof
for %%G in ("C:\Windows" "C:\Windows\System32" "C:\Program Files" "C:\Program Files (x86)" "C:\Users" "C:\ProgramData" "!UP!" "!LAD!" "!RAD!" "!SELF:~0,-1!") do (
  if /i "!_G!"=="%%~G" goto :eof
)
set "%~2=1"
goto :eof

REM ============================================================================
REM  子程序：安全删除文件（先护栏，再检测存在性；不存在则静默返回）
REM  %~1 = 文件路径    %~2 = 描述文字
REM ============================================================================
:DELFILE_SAFE
set "_F=%~1"
set "_T=%~2"
if not defined _F goto :eof
if not exist "!_F!" goto :eof
call :GUARD_PATH "!_F!" _OK
if "!_OK!"=="0" (
  echo    [保护] 拒绝删除受保护/非法文件: !_F!
  set /a N_SKIP+=1
  goto :eof
)
echo    - 删除 !_T!: !_F! ...
del /f /q "!_F!" >nul 2>&1
if exist "!_F!" (
  echo      [失败] 文件仍存在（可能被占用）。
  set /a N_FAIL+=1
) else (
  echo      [完成] 已删除。
  set /a N_OK+=1
)
goto :eof

REM ============================================================================
REM  子程序：扫描注册表残留（只列出，不删除）
REM ============================================================================
:SCAN_REG
set "_REPO=HKCU\Software\Classes\Local Settings\Software\Microsoft\Windows\CurrentVersion\AppModel\Repository\Packages"

REM [D1] MSIX 包注册信息（正常卸载后系统会清理，此处检测残留）
for /f "delims=" %%K in ('reg query "!_REPO!" 2^>nul ^| findstr /I /R "Claude_"') do (
  echo    [发现] %%K
  set /a CNT_REG+=1
)

REM [D2] 软件自建注册表键
for %%R in ("HKCU\Software\Claude" "HKLM\SOFTWARE\Claude" "HKCU\Software\Anthropic" "HKLM\SOFTWARE\Anthropic" "HKCU\Software\Anthropic\Claude" "HKLM\SOFTWARE\WOW6432Node\Claude" "HKLM\SOFTWARE\WOW6432Node\Anthropic" "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\Claude.exe" "HKLM\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\Claude.exe" "HKLM\SYSTEM\CurrentControlSet\Services\Claude_zh" "HKLM\SYSTEM\CurrentControlSet\Services\Claude") do (
  reg query "%%~R" >nul 2>&1
  if !errorlevel!==0 (
    echo    [发现] %%~R
    set /a CNT_REG+=1
  )
)

REM [D3] 卸载信息项（DisplayName 含 Claude）
for %%H in ("HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall" "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall" "HKLM\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall") do (
  for /f "delims=" %%S in ('reg query %%~H 2^>nul') do (
    reg query "%%S" /v DisplayName 2>nul | findstr /I "Claude" >nul
    if !errorlevel!==0 (
      echo    [发现] %%S
      set /a CNT_REG+=1
    )
  )
)
REM [D4] 用户环境变量中 Claude / Anthropic 相关的值（PATH 不计入，避免误判系统路径）
for /f "tokens=1" %%A in ('reg query "HKCU\Environment" 2^>nul ^| findstr /I "Claude Anthropic"') do (
  if /i not "%%A"=="Path" (
    echo    [发现] 用户环境变量 %%A
    set /a CNT_REG+=1
  )
)
if !CNT_REG!==0 echo    [无]   未发现注册表残留（MSIX 应用通常无传统卸载项，若此处空白且上方无报错属正常）。
goto :eof

REM ============================================================================
REM  子程序：清理注册表（先检测再删，逐项记录结果）
REM ============================================================================
:CLEAN_REG
set "_REPO=HKCU\Software\Classes\Local Settings\Software\Microsoft\Windows\CurrentVersion\AppModel\Repository\Packages"

REM [D1] MSIX 包注册信息残留
set "_N=0"
for /f "delims=" %%K in ('reg query "!_REPO!" 2^>nul ^| findstr /I /R "Claude_"') do (
  echo    - 删除注册表项: %%K
  reg delete "%%K" /f >nul 2>&1
  reg query "%%K" >nul 2>&1
  if !errorlevel!==0 (
    echo      [失败] 项仍存在（可能权限不足）。
    set /a N_FAIL+=1
  ) else (
    echo      [完成] 已删除。
    set /a N_OK+=1
  )
  set /a _N+=1
)
if !_N!==0 echo    [跳过] 无 MSIX 包注册信息残留。

REM [D2] 软件自建注册表键
for %%R in ("HKCU\Software\Claude" "HKLM\SOFTWARE\Claude" "HKCU\Software\Anthropic" "HKLM\SOFTWARE\Anthropic" "HKCU\Software\Anthropic\Claude" "HKLM\SOFTWARE\WOW6432Node\Claude" "HKLM\SOFTWARE\WOW6432Node\Anthropic" "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\Claude.exe" "HKLM\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\Claude.exe" "HKLM\SYSTEM\CurrentControlSet\Services\Claude_zh" "HKLM\SYSTEM\CurrentControlSet\Services\Claude") do (
  reg query "%%~R" >nul 2>&1
  if !errorlevel!==0 (
    echo    - 删除注册表项: %%~R
    reg delete "%%~R" /f >nul 2>&1
    reg query "%%~R" >nul 2>&1
    if !errorlevel!==0 (
      echo      [失败] 项仍存在。
      set /a N_FAIL+=1
    ) else (
      echo      [完成] 已删除。
      set /a N_OK+=1
    )
  )
)

REM [D3] 卸载信息项
for %%H in ("HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall" "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall" "HKLM\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall") do (
  for /f "delims=" %%S in ('reg query %%~H 2^>nul') do (
    reg query "%%S" /v DisplayName 2>nul | findstr /I "Claude" >nul
    if !errorlevel!==0 (
      echo    - 删除卸载信息项: %%S
      reg delete "%%S" /f >nul 2>&1
      reg query "%%S" >nul 2>&1
    )
  )
)

REM [D4] 用户环境变量中 Claude / Anthropic 相关的值（跳过 PATH，避免破坏系统路径）
set "_M=0"
for /f "tokens=1" %%A in ('reg query "HKCU\Environment" 2^>nul ^| findstr /I "Claude Anthropic"') do (
  if /i not "%%A"=="Path" (
    echo    - 删除用户环境变量: %%A
    reg delete "HKCU\Environment" /v "%%A" /f >nul 2>&1
    reg query "HKCU\Environment" /v "%%A" >nul 2>&1
    if !errorlevel!==0 (
      echo      [失败] 仍存在。
      set /a N_FAIL+=1
    ) else (
      echo      [完成] 已删除。
      set /a N_OK+=1
    )
    set /a _M+=1
  )
)
if !_M!==0 echo    [跳过] 无 Claude 相关的用户环境变量。
goto :eof

REM ============================================================================
REM  退出
REM ============================================================================
:EXIT_OK
echo.
echo  已退出。若刚安装或卸载汉化，请重新启动 Claude 使改动生效。
echo.
endlocal
exit /b 0
