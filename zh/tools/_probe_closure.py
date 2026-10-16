# -*- coding: utf-8 -*-
"""探测守护服务所需的最小依赖闭包（在源 Python 下运行）。

思路：
1. 静态扫描 AST —— 汉化脚本（zh/scripts/*.py）+ pywin32 的 win32/lib/*.py
   里 import 了什么，得到候选顶层模块名；
2. 逐个 import 这些模块，取 sys.modules 的闭包（含传递依赖）；
3. 输出每个模块对应的文件（builtin/frozen 记为 null）。

输出 JSON：{"version":, "prefix":, "modules": {模块名: 绝对路径或 null}}
"""
import ast
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(os.path.dirname(HERE))          # ...\Claude汉化
SCRIPTS = os.path.join(PROJ, 'zh', 'scripts')

# 兜底清单：解释器/服务宿主启动必需，静态扫描扫不到的（动态 import、C 层触发）
BASE = [
    'encodings', 'codecs', 'site', 'abc', 'collections', 'enum', 'types',
    'warnings', 'contextlib', 'copy', 'operator', 'keyword', 'reprlib',
    'linecache', 'inspect', 'tempfile', 'glob', 'fnmatch', 'random', 'zlib',
    'pathlib', 'threading', 'msvcrt', 'winreg', 'locale', 'gettext',
    'platform', 'bisect', 'heapq', 'pickle', 'copyreg', 'textwrap',
    'base64', 'binascii', 'string', 'numbers', 'decimal', 'calendar',
    'weakref', 'atexit', 'signal', 'errno', 'stat', 'filecmp', 'datetime',
    'logging', 'traceback', 'subprocess', 'shutil', 'hashlib', 'struct',
    'json', 're', 'io', 'ctypes', 'importlib', 'os', 'sys', 'time',
    'win32event', 'win32service', 'win32serviceutil', 'servicemanager',
]


def scan_dir(d, exts=('.py',)):
    """扫描目录下所有 .py 的 import 顶层模块名。"""
    found = set()
    if not os.path.isdir(d):
        return found
    for fn in os.listdir(d):
        if not fn.endswith(exts):
            continue
        try:
            src = io.open(os.path.join(d, fn), encoding='utf-8', errors='replace').read()
            tree = ast.parse(src)
        except Exception:
            continue
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                for a in n.names:
                    found.add(a.name.split('.')[0])
            elif isinstance(n, ast.ImportFrom):
                if n.level == 0 and n.module:
                    found.add(n.module.split('.')[0])
    return found


def main():
    # pywin32 的 Python 模块目录（服务注册路径会间接 import 到 win32timezone 等）
    sp = os.path.join(sys.prefix, 'Lib', 'site-packages')
    win32_lib = os.path.join(sp, 'win32', 'lib')

    tops = set(BASE)
    tops |= scan_dir(SCRIPTS)                 # 汉化脚本自身的依赖
    tops |= scan_dir(win32_lib)               # pywin32 各模块的依赖

    for name in sorted(tops):
        try:
            __import__(name)
        except Exception as e:
            sys.stderr.write('skip %s: %s\n' % (name, e))

    mods = {}
    for name, m in list(sys.modules.items()):
        f = getattr(m, '__file__', None)
        if f is None:
            mods[name] = None                  # builtin（无需复制）
        elif f.startswith('<'):
            mods[name] = None                  # frozen（已编译进解释器）
        else:
            mods[name] = os.path.abspath(f)

    out = {'version': sys.version.split()[0], 'prefix': sys.prefix, 'modules': mods}
    sys.stdout.write(json.dumps(out, ensure_ascii=False))


if __name__ == '__main__':
    main()
