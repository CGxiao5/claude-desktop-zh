# -*- coding: utf-8 -*-
r"""
Claude 汉化守护进程

三项职责：
1. 技能描述：Claude 每次启动都会用 app.asar 内的原始文件覆盖
   %LOCALAPPDATA%\Claude-3p\local-agent-mode-sessions\skills-plugin 下的
   manifest.json / SKILL.md，导致技能描述汉化回退。斜杠菜单 tooltip 运行时
   实时读磁盘，因此轮询检测，发现回退立即重译。
2. 内核命令描述：Claude Code 内核（claude.exe）更新后字符串表/源码补丁丢失，
   监听内核文件的修改时间/尺寸变化，变化时重跑两个内核补丁模块。
3. 自愈基线：安装时写入 %USERPROFILE%\.claude\zh\state.json，记录
   FE 词表 / shell 词表 / JS 补丁 / locale 的期望状态。本进程每轮比对，
   发现被还原或覆盖（Claude 自动更新、文件校验还原）就地重部署。
   注：WindowsApps 下的文件需要管理员权限，非管理员运行时该项静默跳过。

进程启动时先做一次全量自检，因此开机后无需人工干预即可恢复汉化。
由 安装.cmd 部署到 %USERPROFILE%\.claude\zh\ 并加入开机启动项；
由 卸载.cmd 停止并移除。
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# 内置 Python 运行时的 pywin32 路径兜底（相对定位，不写死盘符）
try:
    import zhpy as _zhpy
    _zhpy.ensure_win32_path()
except Exception:
    pass

# pythonw 无控制台，屏蔽输出
_devnull = open(os.devnull, 'w')
sys.stdout = _devnull
sys.stderr = _devnull

INTERVAL = 10          # 秒：技能/内核轮询
HEAL_EVERY = 6         # 每 6 轮（约 60 秒）做一次基线自检
LOG_NAME = 'watch.log'

_si = None


def _startupinfo():
    global _si
    if _si is None and os.name == 'nt':
        _si = subprocess.STARTUPINFO()
        _si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        _si.wShowWindow = 0
    return _si


def _log(msg):
    """写日志到用户目录，便于排查；任何失败都不影响守护。"""
    try:
        p = os.path.join(HERE, LOG_NAME)
        with open(p, 'a', encoding='utf-8') as f:
            f.write('%s %s\n' % (time.strftime('%Y-%m-%d %H:%M:%S'), msg))
    except Exception:
        pass


def sha1_file(path):
    h = hashlib.sha1()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 16), b''):
            h.update(chunk)
    return h.hexdigest()


def grant_write(path):
    """WindowsApps 归 TrustedInstaller 所有；先取所有权再授权。失败静默。"""
    if os.name != 'nt':
        return
    si = _startupinfo()
    try:
        subprocess.run(['takeown', '/f', path, '/a'], startupinfo=si,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
    except Exception:
        pass
    flag = '(OI)(CI)(F)' if os.path.isdir(path) else '(F)'
    try:
        subprocess.run(['icacls', path, '/grant', 'Administrators:' + flag],
                       startupinfo=si, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=20)
    except Exception:
        pass


# --------------------------------------------------------------------------
# 基线自愈
# --------------------------------------------------------------------------
def heal_locale(cfg_path):
    if not cfg_path or not os.path.isfile(cfg_path):
        return False
    try:
        with open(cfg_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        return False
    if data.get('locale') == 'zh-Hans':
        return False
    try:
        data['locale'] = 'zh-Hans'
        with open(cfg_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        _log('heal: locale 已改回 zh-Hans')
        return True
    except Exception:
        return False


def heal_json_file(item, payload_name, payload_dir):
    """词表文件被还原/删除时，从 payload 副本恢复。"""
    if not item:
        return False
    path = item.get('path')
    want = item.get('sha1')
    if not path or not want:
        return False
    pay = os.path.join(payload_dir, payload_name)
    if not os.path.isfile(pay):
        return False
    want = (want or '').lower()
    try:
        if os.path.isfile(path) and sha1_file(path).lower() == want:
            return False
        d = os.path.dirname(path)
        if d and not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
        if d and os.path.isdir(d):
            grant_write(d)
        if os.path.isfile(path):
            grant_write(path)
        shutil.copyfile(pay, path)
        _log('heal: 已恢复词表 %s' % os.path.basename(path))
        return True
    except Exception:
        return False


def heal_js(pair):
    """JS 补丁被还原时，用基线里的 原文→补丁文 三元组重打（Latin1 字节级）。"""
    if not pair:
        return False
    path = pair.get('path')
    find = pair.get('find')
    repl = pair.get('replace')
    if not (path and find and repl) or not os.path.isfile(path):
        return False
    try:
        raw = open(path, 'rb').read()
    except Exception:
        return False
    fb = find.encode('latin-1', 'replace')
    rb = repl.encode('latin-1', 'replace')
    if rb in raw:          # 已补丁
        return False
    if fb not in raw:      # 结构变化，不敢动
        return False
    try:
        grant_write(path)
        with open(path, 'wb') as f:
            f.write(raw.replace(fb, rb))
        _log('heal: 已重打 JS 补丁 %s' % pair.get('name', os.path.basename(path)))
        return True
    except Exception:
        return False


def selfheal():
    st_path = os.path.join(HERE, 'state.json')
    if not os.path.isfile(st_path):
        return 0
    try:
        with open(st_path, 'r', encoding='utf-8') as f:
            st = json.load(f)
    except Exception:
        return 0
    payload_dir = st.get('payload', '')
    fixed = 0
    try:
        if heal_locale(st.get('configPath')):
            fixed += 1
    except Exception:
        pass
    for key, name in (('feZh', 'fe-zh-Hans.json'),
                      ('feDyn', 'fe-dynamic-zh-Hans.json'),
                      ('shellZh', 'shell-zh-Hans.json')):
        try:
            if heal_json_file(st.get(key), name, payload_dir):
                fixed += 1
        except Exception:
            pass
    for pair in (st.get('js') or []):
        try:
            if heal_js(pair):
                fixed += 1
        except Exception:
            pass
    return fixed


# --------------------------------------------------------------------------
# 内核
# --------------------------------------------------------------------------
def find_kernel():
    base = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Claude-3p', 'claude-code')
    best = None
    if os.path.isdir(base):
        for ver in os.listdir(base):
            vd = os.path.join(base, ver)
            if not os.path.isdir(vd):
                continue
            for h in os.listdir(vd):
                p = os.path.join(vd, h, 'claude.exe')
                if os.path.isfile(p):
                    try:
                        st = (os.path.getmtime(p), os.path.getsize(p))
                    except OSError:
                        continue
                    if best is None or st[0] > best[1][0]:
                        best = (p, st)
    return best


_MODULE_MTIME = {}


def _load(name):
    try:
        return __import__(name)
    except Exception:
        return None


def _reload_if_changed(mod):
    """模块副本被安装脚本更新后重新加载，避免继续用内存里的旧翻译表打补丁。

    典型故障：守护进程加载的是旧副本（翻译条目少），安装后新副本文件已更新但
    进程仍用旧表 —— 补丁会先按日志还原再按旧表重打，导致已翻译条目大规模回退。
    """
    if mod is None:
        return None
    f = getattr(mod, '__file__', None)
    if not f:
        return mod
    try:
        mt = os.path.getmtime(f)
    except OSError:
        return mod
    if _MODULE_MTIME.get(f) == mt:
        return mod
    _MODULE_MTIME[f] = mt
    if f in _MODULE_MTIME and _MODULE_MTIME.get('__seen__' + f):
        try:
            import importlib
            mod = importlib.reload(mod)
            _log('reload: 已重新加载模块 %s' % os.path.basename(f))
        except Exception:
            pass
    _MODULE_MTIME['__seen__' + f] = True
    return mod


def main(stop_check=None):
    # 运行模式（v4.0 起，常驻职责由 Windows 服务 Claude_zh 承担）：
    #   --once   一次性全量自愈：boot 内核补丁 + 基线自愈 + 技能重译，跑完即退出。
    #            服务不可用时的降级路径（Startup\claude-zh-heal.cmd）。
    #   --skills 启动器快速通道：仅技能重译（秒级），由"Claude 中文版"快捷方式在
    #            拉起 Claude 前后台执行。Claude 每次启动会用 app.asar 原件重新解压
    #            skills-plugin 覆盖译文，此通道保证启动后数秒内技能恢复中文。
    #   （无参数）常驻轮询模式：Windows 服务 Claude_zh 以本模式调用，stop_check 为
    #            可调用对象，返回 True 时退出循环（响应 SCM 停止控制）。
    mode = 'watch'
    if '--once' in sys.argv:
        mode = 'once'
    elif '--skills' in sys.argv:
        mode = 'skills'
    _log('watch: 启动 (pid=%d, 模式=%s)' % (os.getpid(), mode))
    # 词条仓库模块要先于内核模块加载：内核/技能脚本 import 它来读写译文。
    # 启动时登记项目仓库路径，保证运行时回写的词条落在项目仓库（持久资产），
    # 而不是随时可能被清理的运行时目录。
    try:
        import zhstore
        zhstore.register_project_store()
        _log('store: %s (%d 条)'
             % (zhstore.store_path(), sum(zhstore.count().values())))
    except Exception as e:
        _log('store: 词条仓库不可用 (%s)' % e)
    skills = _load('translate_skills_mod')
    kernel_mod = _load('translate_kernel_mod')
    ksrc_mod = _load('translate_kernel_source_mod')

    if mode == 'skills':
        if skills is not None:
            try:
                skills.main()
            except Exception:
                pass
        _log('skills: 快速通道完成，退出')
        return 0

    # 开机自检：启动时先跑一遍内核补丁与基线自愈，确保重启/更新后汉化仍在。
    # 两个内核模块内部都是幂等的（先按日志还原再重打）且有跨进程文件锁。
    # 例外：安装脚本 [7c/7d] 同步打过补丁后 3 分钟内启动的守护进程（典型：
    # [7g] 拉起的本进程）不再重跑——重跑既冗余，又会与被中途回收的上一个
    # 守护实例残留的锁互相阻塞（2026-10-15 实测：残留锁导致 boot 自检挂起
    # 5 分钟）；若补丁日志缺失或过旧，仍照常执行。
    _FRESH = 180                     # 秒：补丁日志视为「刚打过」的窗口

    def _log_fresh(path):
        try:
            return (time.time() - os.path.getmtime(path)) < _FRESH
        except OSError:
            return False

    for m, mlog in ((kernel_mod, 'kernel-patch-log.json'),
                   (ksrc_mod, 'kernel-source-patch-log.json')):
        if m is None:
            continue
        if _log_fresh(os.path.join(HERE, 'backup', mlog)):
            _log('boot: %s 日志 3 分钟内刚更新，跳过重打（安装已同步完成）'
                 % mlog)
            continue
        try:
            m.main()
        except Exception:
            pass
    try:
        n = selfheal()
        if n:
            _log('boot-heal: 修复 %d 项' % n)
    except Exception:
        pass

    if mode == 'once':
        # 一次性模式补完技能再退出（登录场景：Claude 可能已被拉起并覆盖过技能）
        if skills is not None:
            try:
                skills.main()
            except Exception:
                pass
        _log('once: 一次性自愈完成，退出（无驻留进程）')
        return 0

    return serve(skills, kernel_mod, ksrc_mod, stop_check=stop_check)


def serve(skills, kernel_mod, ksrc_mod, stop_check=None, interval=INTERVAL):
    r"""常驻主循环。

    命令行守护模式 stop_check=None，永久轮询；
    Windows 服务模式传入 stop_check（SCM 停止事件），每轮首尾各检查一次并分片
    等待。分片等待很关键：若用一整段 sleep(10)，SCM 下发停止后最长要 10 秒才
    响应，叠加多轮补丁耗时极易触发 30 秒服务停止超时（服务卡在"正在停止"）。
    """
    last_kernel = None
    rounds = 0
    while True:
        if stop_check is not None and stop_check():
            _log('serve: 收到停止信号，退出循环')
            return 0
        # 模块副本可能被安装脚本更新，跑补丁前先按需热重载
        try:
            # 词条仓库优先重载：内核/技能脚本 import 它读写译文，
            # 若仓库模块是旧版，回写会用旧逻辑覆盖新结构。
            try:
                import zhstore
                zhstore = _reload_if_changed(zhstore)
            except Exception:
                pass
            skills = _reload_if_changed(skills)
            kernel_mod = _reload_if_changed(kernel_mod)
            ksrc_mod = _reload_if_changed(ksrc_mod)
        except Exception:
            pass
        try:
            if skills is not None:
                skills.main()
        except Exception:
            pass

        if kernel_mod is not None:
            try:
                cur = find_kernel()
                if cur is not None:
                    sig = (cur[0], cur[1])
                    if last_kernel is None:
                        last_kernel = sig
                    elif sig != last_kernel:
                        # 内核文件变化（更新）→ 重跑补丁
                        try:
                            kernel_mod.main()
                        except Exception:
                            pass
                        if ksrc_mod is not None:
                            try:
                                ksrc_mod.main()
                            except Exception:
                                pass
                        _log('kernel: 检测到内核变化，已重打补丁')
                        last_kernel = sig
            except Exception:
                pass

        rounds += 1
        if rounds % HEAL_EVERY == 0:
            try:
                n = selfheal()
                if n:
                    _log('heal: 修复 %d 项' % n)
            except Exception:
                pass

        # 等待下一轮。服务模式分片等待（0.5s 粒度），保证 SCM 停止指令及时响应
        if stop_check is None:
            time.sleep(interval)
        else:
            _waited = 0.0
            while _waited < interval:
                if stop_check():
                    _log('serve: 收到停止信号，退出循环')
                    return 0
                time.sleep(0.5)
                _waited += 0.5


if __name__ == '__main__':
    main()
