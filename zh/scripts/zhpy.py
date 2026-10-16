# -*- coding: utf-8 -*-
r"""
内置 Python 运行时定位器（zhpy）
================================

汉化包自带一份精简 Python 运行时，随包携带在汉化目录的 python\\ 子目录下：

    %USERPROFILE%\\.claude\\zh\\
    ├── python\\                 <- 内置精简 Python（3.x + pywin32，仅本包使用）
    │   ├── python.exe / pythonw.exe
    │   ├── python3XX.dll  vcruntime140*.dll
    │   ├── pythonservice.exe    <- pywin32 服务宿主
    │   ├── pywintypes3XX.dll
    │   ├── DLLs\\                <- 仅服务所需的扩展模块
    │   ├── Lib\\                 <- 精简标准库 + win32\\
    │   └── RUNTIME.json          <- 版本 / 构建信息
    ├── zh_service.py
    ├── skills-watch.py
    └── ...

两条铁律
--------
1. **路径一律相对解析**：以本文件位置为起点逐级向上查找 ``python\\python.exe``，
   不写死任何盘符与绝对磁盘路径。整个 ``.claude\\zh`` 目录可以整体搬家、换盘、
   换用户，无需改任何配置。
2. **缺失即报错**：找不到内置运行时时 ``check()`` 输出明确的中文错误提示，
   **绝不联网下载**、也**绝不静默回退**到系统 Python（避免"看起来在跑，
   实际用的是别的解释器"这种难以排查的问题）。

命令行自检：
    python zhpy.py            # 打印运行时信息；缺失时打印错误并以 exit 2 退出
"""
import json
import os
import sys


def _here():
    return os.path.dirname(os.path.abspath(__file__))


def runtime_dir():
    """返回内置运行时目录（含 python.exe），找不到返回 None。

    从本文件所在目录起向上最多找 4 级，兼容 zhpy.py 位于 zh\\ 根或 zh\\scripts\\ 下。
    """
    d = _here()
    for _ in range(4):
        cand = os.path.join(d, 'python')
        if os.path.isfile(os.path.join(cand, 'python.exe')):
            return cand
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return None


def python_exe():
    d = runtime_dir()
    return os.path.join(d, 'python.exe') if d else None


def pythonw_exe():
    d = runtime_dir()
    if not d:
        return None
    p = os.path.join(d, 'pythonw.exe')
    return p if os.path.isfile(p) else os.path.join(d, 'python.exe')


def pythonservice_exe():
    d = runtime_dir()
    return os.path.join(d, 'pythonservice.exe') if d else None


def info():
    """读取 RUNTIME.json；不存在返回 None。"""
    d = runtime_dir()
    if not d:
        return None
    f = os.path.join(d, 'RUNTIME.json')
    if not os.path.isfile(f):
        return None
    try:
        return json.load(open(f, encoding='utf-8'))
    except Exception:
        return None


def ensure_win32_path():
    """把内置运行时的 pywin32 目录补进 sys.path。

    正常情况下 Lib\\sitecustomize.py 已经做过；但若服务宿主以 -S（不导入 site）
    启动，sitecustomize 不会执行，这里兜底，保证 win32serviceutil 等可导入。
    返回实际追加的路径列表。
    """
    d = runtime_dir()
    if not d:
        return []
    added = []
    for sub in (os.path.join('Lib', 'win32'), os.path.join('Lib', 'win32', 'lib')):
        p = os.path.join(d, sub)
        if os.path.isdir(p) and p not in sys.path:
            sys.path.append(p)
            added.append(p)
    return added


def check(exit_on_missing=True):
    """检测内置运行时是否可用。返回 True/False。

    缺失时输出明确的中文错误与处理建议（不下载、不静默回退）。
    """
    d = runtime_dir()
    if not d:
        sys.stderr.write(
            '\n[错误] 未找到汉化包内置的 Python 运行环境。\n'
            '       期望位置：%s\n'
            '       该环境随汉化包一同安装（离线，不会联网下载）。\n'
            '       处理办法：重新运行「Claude汉化.cmd → 安装/更新汉化」，\n'
            '       安装程序会把内置运行时从汉化包复制到上述目录。\n'
            '       （汉化本体已生效，仅自动修复/守护能力暂不可用。）\n\n'
            % os.path.join(_here(), 'python'))
        if exit_on_missing:
            sys.exit(2)
        return False
    exe = os.path.join(d, 'python.exe')
    meta = info() or {}
    sys.stdout.write('[OK] 内置 Python 运行时：%s\n' % d)
    sys.stdout.write('     版本 %s（%s 构建，%s 个文件）\n'
                     % (meta.get('version', '?'), meta.get('build_time', '?')[:10],
                        meta.get('files', '?')))
    sys.stdout.write('     解释器 %s\n' % exe)
    sys.stdout.write('     服务宿主 %s\n' % os.path.join(d, 'pythonservice.exe'))
    for sub, name in ((os.path.join('Lib', 'win32', 'win32service.pyd'), 'win32service'),
                      (os.path.join('Lib', 'win32', 'lib', 'win32serviceutil.py'), 'win32serviceutil')):
        if not os.path.isfile(os.path.join(d, sub)):
            sys.stderr.write('[错误] 内置运行时缺少 %s（%s），服务无法运行。\n'
                             % (name, os.path.join(d, sub)))
            if exit_on_missing:
                sys.exit(3)
            return False
    return True


if __name__ == '__main__':
    ok = check(exit_on_missing=False)
    sys.exit(0 if ok else 2)
