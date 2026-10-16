# -*- coding: utf-8 -*-
r"""
Claude_zh —— Windows 服务宿主（Claude Desktop 简体中文汉化常驻服务）

为什么需要常驻进程
------------------
汉化本体（词表 / JS 补丁 / asar 补丁 / locale）都是落盘即持久的，本身不需要
任何进程。真正需要"有人盯着"的是三件会反复发生的事：

1. 技能描述：Claude **每次启动**都会用 app.asar 内的原始文件覆盖
   %LOCALAPPDATA%\Claude-3p\local-agent-mode-sessions\skills-plugin 下的
   manifest.json / SKILL.md，把译文打回英文。
2. 内核命令描述：Claude Code 内核（claude.exe）自动更新后，字符串表补丁与
   源码字面量补丁随新二进制一起丢失。
3. 自愈基线：Claude 自动更新 / MSIX 自修复 / 文件校验还原，可能把
   ion-dist\i18n\zh-Hans.json、resources\zh-Hans.json、4 个 JS 补丁、locale
   回滚成英文态。

v4.0 起这些职责由本服务承担（此前是开机启动项里的常驻 pythonw 进程）。
服务名固定 **Claude_zh**，随开机自动启动，不依赖任何用户登录会话。

LocalSystem 上下文的关键坑
--------------------------
服务默认以 LocalSystem 运行，此时环境里的 USERPROFILE / APPDATA / LOCALAPPDATA
全部指向 C:\Windows\System32\config\systemprofile，**不是**真正装了 Claude 的
那个用户。若直接使用，所有"用户目录"计算都会落到 systemprofile，汉化会静默
失效（看起来服务在跑，实际上什么都没修）。

因此 SvcDoRun 第一件事就是 adopt_user_env()：从同目录 install-context.json 的
zhHome（形如 C:\Users\<名>\.claude\zh）反推用户根目录，并覆盖进程环境变量，
之后加载的所有模块都按真实用户目录工作。

手动管理（管理员 PowerShell）：
    python zh_service.py install     # 注册服务（需 pywin32）
    python zh_service.py start       # 启动
    python zh_service.py stop        # 停止
    python zh_service.py remove      # 删除
    sc query Claude_zh               # 查看状态
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
LOG_NAME = 'service.log'

# 服务由 pywin32 宿主（pythonservice.exe）启动，解释器取自汉化包内置运行时
# （.claude\zh\python\）。正常情况下 Lib\sitecustomize.py 已把 pywin32 目录
# 加进 sys.path；但若宿主以 -S 启动（不导入 site），这里兜底补一次路径，
# 保证 win32serviceutil / win32event 一定能导入。
if HERE not in sys.path:
    sys.path.insert(0, HERE)
try:
    import zhpy as _zhpy                      # 内置运行时定位器（相对路径解析）
    _zhpy.ensure_win32_path()
except Exception as _e:                       # 定位器缺失不致命：仅少一层兜底
    pass

SERVICE_NAME = 'Claude_zh'
SERVICE_DISPLAY = 'Claude Desktop 简体中文汉化服务'
SERVICE_DESC = ('维持 Claude Desktop 汉化：技能描述重译、内核补丁重打、'
                '词表/JS/locale 基线自愈。停止本服务不会卸载汉化，'
                '但 Claude 更新后不会自动恢复中文。')


def _log(msg):
    """写日志文件。服务无控制台，日志是唯一可观测手段；失败绝不影响服务。"""
    try:
        with open(os.path.join(HERE, LOG_NAME), 'a', encoding='utf-8') as f:
            f.write('%s %s\n' % (time.strftime('%Y-%m-%d %H:%M:%S'), msg))
    except Exception:
        pass


def _user_profile_from_context():
    """从 install-context.json 反推目标用户根目录。

    zhHome 形如 C:\\Users\\<名>\\.claude\\zh —— 上两级即用户根。
    安装脚本在 [7e] 写入该文件，含 zhHome / pkgPath / version 等。
    """
    import json
    ctx_path = os.path.join(HERE, 'install-context.json')
    try:
        with open(ctx_path, encoding='utf-8') as f:
            ctx = json.load(f)
    except Exception as e:
        _log('ctx: 读取失败 (%r) %s' % (e, ctx_path))
        return None
    prof = ctx.get('userProfile')
    zh_home = ctx.get('zhHome') or ''
    if not prof and zh_home:
        # ...\.claude\zh -> ...\.claude -> 用户根
        prof = os.path.dirname(os.path.dirname(zh_home.rstrip('\\/')))
    if prof and os.path.isdir(prof):
        return prof
    _log('ctx: 无法定位用户目录 (zhHome=%r userProfile=%r)' % (zh_home, prof))
    return None


def adopt_user_env():
    """把服务的 LocalSystem 环境变量改写为目标用户。返回用户根目录或 None。"""
    prof = _user_profile_from_context()
    if not prof:
        return None
    os.environ['USERPROFILE'] = prof
    os.environ['HOME'] = prof
    os.environ['APPDATA'] = os.path.join(prof, 'AppData', 'Roaming')
    os.environ['LOCALAPPDATA'] = os.path.join(prof, 'AppData', 'Local')
    # 服务会话里 USERNAME / USERDOMAIN 常为 SYSTEM，一并纠正，避免日志与
    # 依赖它们的子进程行为异常
    os.environ['USERNAME'] = os.path.basename(prof)
    return prof


try:
    import win32serviceutil
    import win32service
    import win32event
    import servicemanager
except ImportError as _e:                                   # pragma: no cover
    _log('FATAL: 缺少 pywin32 (%r)。服务无法运行，请 pip install pywin32' % (_e,))
    raise


class ClaudeZhService(win32serviceutil.ServiceFramework):
    _svc_name_ = SERVICE_NAME
    _svc_display_name_ = SERVICE_DISPLAY
    _svc_description_ = SERVICE_DESC

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        # 手动复位事件：SvcStop 置位，主循环轮询检测
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self._stopped = False

    # ---- SCM 控制回调 ----
    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        _log('SvcStop: 收到停止控制，通知主循环退出')
        self._stopped = True
        win32event.SetEvent(self.hWaitStop)

    def SvcShutdown(self):
        # 系统关机：与 SvcStop 同样处理（主循环短轮询，退出足够快）
        self.SvcStop()

    def _is_stopping(self):
        """供 skills_watch.serve() 每轮调用；不阻塞。"""
        if self._stopped:
            return True
        try:
            if win32event.WaitForSingleObject(self.hWaitStop, 0) == win32event.WAIT_OBJECT_0:
                self._stopped = True
        except Exception:
            pass
        return self._stopped

    # ---- 服务主体 ----
    def SvcDoRun(self):
        # 必须尽早报告 RUNNING，否则超过 30 秒 SCM 判定启动超时
        try:
            self.ReportServiceStatus(win32service.SERVICE_RUNNING)
        except Exception:
            pass
        try:
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED, (self._svc_name_, ''))
        except Exception:
            pass

        _log('=' * 56)
        _log('service: %s 启动 (pid=%d)' % (SERVICE_NAME, os.getpid()))
        # 记录实际使用的解释器：内置运行时缺失或被系统 Python 顶替时能一眼看出
        try:
            import zhpy as _z
            _rt = _z.runtime_dir()
            _log('python: %s' % (getattr(sys, 'executable', '?')))
            _log('runtime: %s (内置=%s)' % (_rt, bool(_rt)))
            if not _rt:
                _log('WARN: 未找到内置 Python 运行时，当前解释器可能来自系统环境')
        except Exception as _e:
            _log('python: %s (zhpy 不可用: %r)' % (getattr(sys, 'executable', '?'), _e))

        prof = adopt_user_env()
        if not prof:
            _log('FATAL: 无法确定目标用户目录，服务退出（请重新运行安装）')
            return
        _log('env: USERPROFILE=%s' % prof)
        _log('env: LOCALAPPDATA=%s' % os.environ.get('LOCALAPPDATA'))
        _log('env: APPDATA=%s' % os.environ.get('APPDATA'))

        try:
            if HERE not in sys.path:
                sys.path.insert(0, HERE)
            # 注意：部署文件名是 skills-watch.py（连字符），不是合法的 Python 模块名，
            # 不能 import skills_watch —— 必须按文件路径加载（实测踩坑）。
            import importlib.util
            _sw = os.path.join(HERE, 'skills-watch.py')
            _spec = importlib.util.spec_from_file_location('skills_watch', _sw)
            if _spec is None or _spec.loader is None:
                _log('FATAL: 无法加载 %s（文件缺失或损坏）' % _sw)
                return
            skills_watch = importlib.util.module_from_spec(_spec)
            sys.modules['skills_watch'] = skills_watch
            _spec.loader.exec_module(skills_watch)
            _log('boot: 已加载 skills-watch.py，进入常驻循环')
            rc = skills_watch.main(stop_check=self._is_stopping)
            _log('loop: 主循环返回 rc=%s' % rc)
        except Exception as e:
            import traceback
            _log('FATAL: 主循环异常 %r' % (e,))
            try:
                _log(traceback.format_exc())
            except Exception:
                pass

        _log('service: 已停止')


if __name__ == '__main__':
    if len(sys.argv) > 1:
        # install / start / stop / restart / remove / update 等管理命令
        win32serviceutil.HandleCommandLine(ClaudeZhService)
    else:
        # 无参数 = 由 SCM 启动
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(ClaudeZhService)
        servicemanager.StartServiceCtrlDispatcher()
