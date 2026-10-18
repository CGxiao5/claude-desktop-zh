# -*- coding: utf-8 -*-
"""构建内置精简 Python 运行时（离线，不联网）。

从本机已安装的 Python（要求带 pywin32）复制「维持 Claude_zh 服务运行所必需的
最小文件集」到 zh\\python\\，随汉化包一起携带，之后不再依赖系统 Python。

用法：
    python zh/tools/build_embedded_python.py                 # 自动探测源解释器
    python zh/tools/build_embedded_python.py --src D:\\Python315
    python zh/tools/build_embedded_python.py --dest zh\\python

产物结构（zh\\python\\）：
    python.exe pythonw.exe python3XX.dll python3.dll vcruntime140*.dll
    pythonservice.exe pywintypes3XX.dll      <- pywin32 服务宿主与核心 DLL
    DLLs\\*.pyd                              <- 仅闭包需要的扩展模块
    Lib\\*.py + encodings/ importlib/ json/ ctypes/ re/ ...   <- 精简标准库
    Lib\\win32\\                             <- pywin32（放 Lib 下，不依赖 site 机制）
    RUNTIME.json                             <- 版本/构建信息

裁剪掉的成分：test、idlelib、tkinter、tcl、pip/ensurepip/setuptools、
site-packages 中的第三方包、Doc、include、libs、__pycache__、所有 .chm/.pdb。
"""
import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(os.path.dirname(HERE))          # ...\Claude汉化
PROBE = os.path.join(HERE, '_probe_closure.py')

# 根目录必带的宿主文件（python3XX 由版本号拼出）
ROOT_EXE = ['python.exe', 'pythonw.exe', 'python3.dll', 'python{VER}.dll',
            'vcruntime140.dll', 'vcruntime140_1.dll']
# pywin32 服务宿主与核心 DLL（放根目录，保证 .pyd 加载时能找到 pywintypes）
PYWIN32_ROOT = ['pythonservice.exe', 'pywintypes{VER}.dll']
# DLLs\\ 中闭包 .pyd 依赖的运行时 DLL。
# 不复制 libcrypto-3/libssl-3（合计 5.3 MB）：hashlib 会降级到解释器内置的
# md5/sha1/sha2/sha3/blake2 实现，实测结果一致，服务用不到 OpenSSL 算法。
DLL_DEPS = ['libffi-8.dll', 'libtommath.dll', 'zlib1.dll']
# 相应排除依赖 OpenSSL 的扩展模块
EXCLUDE_PYD = {'_hashlib', '_ssl'}

SKIP_DIRS = {'.git', '__pycache__', 'Demos', 'demos', 'test', 'tests',
             'idlelib', 'tkinter', 'tcl', 'Doc', 'include', 'libs', 'Tools'}
SKIP_EXT = {'.pyc', '.pyo', '.pdb', '.chm', '.lib', '.exp', '.h', '.hpp'}


def log(msg):
    sys.stdout.write(msg + '\n')
    sys.stdout.flush()


def find_source_python(explicit=None):
    """探测一个可用的源解释器：必须是 CPython 且装了 pywin32。"""
    cands = []
    if explicit:
        p = explicit if explicit.endswith('.exe') else os.path.join(explicit, 'python.exe')
        cands.append(p)
    else:
        cands.append(sys.executable)
        for cmd in ('python', 'python3', 'py'):
            try:
                out = subprocess.run([cmd, '-c', 'import sys;print(sys.executable)'],
                                     capture_output=True, text=True, timeout=15)
                if out.returncode == 0 and out.stdout.strip():
                    cands.append(out.stdout.strip().splitlines()[-1])
            except Exception:
                pass
        # 常见安装位置兜底
        for base in (os.environ.get('LOCALAPPDATA', ''), 'C:\\', 'D:\\'):
            if not base:
                continue
            for name in ('Program Files\\Python', 'Python'):
                d = os.path.join(base, name)
                if os.path.isdir(d):
                    if os.path.isfile(os.path.join(d, 'python.exe')):
                        cands.append(os.path.join(d, 'python.exe'))
                    for sub in sorted(os.listdir(d)):
                        f = os.path.join(d, sub, 'python.exe')
                        if os.path.isfile(f):
                            cands.append(f)
    seen = set()
    for c in cands:
        if not c or not os.path.isfile(c):
            continue
        c = os.path.abspath(c)
        if c in seen:
            continue
        seen.add(c)
        try:
            out = subprocess.run([c, '-c', 'import sys,win32serviceutil;print(sys.version_info[0],sys.version_info[1],sys.prefix)'],
                                 capture_output=True, text=True, timeout=30)
        except Exception:
            continue
        if out.returncode != 0:
            continue
        parts = out.stdout.strip().split()
        if len(parts) < 3:
            continue
        # 探针输出格式异常时 int() 会抛 ValueError 中断整个构建，按"此候选不可用"处理
        try:
            maj, minr = int(parts[0]), int(parts[1])
        except ValueError:
            continue
        prefix = ' '.join(parts[2:])
        return {'exe': c, 'prefix': prefix, 'ver': '%d%d' % (maj, minr),
                'version': '%d.%d' % (maj, minr)}
    return None


def probe_closure(py):
    """用源解释器跑闭包探测，返回 (模块文件列表, 版本字符串, prefix)。"""
    out = subprocess.run([py, PROBE], capture_output=True, text=True, timeout=120)
    if out.returncode != 0:
        raise RuntimeError('闭包探测失败：%s' % (out.stderr[-500:],))
    d = json.loads(out.stdout)
    files = [f for f in d['modules'].values() if f and os.path.isfile(f)]
    return files, d['version'], d['prefix']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', default=None, help='源 Python 安装目录或 python.exe')
    ap.add_argument('--dest', default=os.path.join(PROJ, 'zh', 'python'),
                    help='输出目录（默认 zh\\python）')
    ap.add_argument('--force', action='store_true', help='强制清空重建')
    args = ap.parse_args()

    src = find_source_python(args.src)
    if not src:
        log('[错误] 未找到带 pywin32 的源 Python 解释器，无法构建内置运行时。')
        log('       请先在本机安装 Python 并执行 pip install pywin32，')
        log('       然后重新运行本脚本（本脚本不会联网下载任何东西）。')
        return 2
    log('[1/6] 源解释器：%s（%s）' % (src['exe'], src['version']))

    dest = os.path.abspath(args.dest)
    if os.path.isdir(dest):
        if args.force:
            shutil.rmtree(dest)
        else:
            old = os.path.join(dest, 'RUNTIME.json')
            if os.path.isfile(old):
                try:
                    info = json.load(io.open(old, encoding='utf-8'))
                    log('[提示] 目标已存在内置运行时 v%s（%s 构建）'
                        % (info.get('version'), info.get('build_time', '?')[:10]))
                except Exception:
                    pass
    os.makedirs(dest, exist_ok=True)

    files, version, prefix = probe_closure(src['exe'])
    log('[2/6] 依赖闭包：%d 个文件' % len(files))

    copied = 0
    total_bytes = 0

    def cp(rel_dst, abs_src):
        nonlocal copied, total_bytes
        d = os.path.join(dest, rel_dst)
        os.makedirs(os.path.dirname(d), exist_ok=True)
        shutil.copy2(abs_src, d)
        copied += 1
        total_bytes += os.path.getsize(abs_src)

    # --- 3. 根目录宿主文件 ---
    for name in ROOT_EXE:
        f = os.path.join(src['prefix'], name.format(VER=src['ver']))
        if os.path.isfile(f):
            cp(name.format(VER=src['ver']), f)
        else:
            log('       （跳过不存在的 %s）' % name.format(VER=src['ver']))
    for name in PYWIN32_ROOT:
        for cand in (os.path.join(src['prefix'], name.format(VER=src['ver'])),
                     os.path.join(src['prefix'], 'Lib', 'site-packages',
                                  'pywin32_system32', name.format(VER=src['ver']))):
            if os.path.isfile(cand):
                cp(name.format(VER=src['ver']), cand)
                break
        else:
            log('[警告] 缺少 %s —— 服务将无法注册！' % name.format(VER=src['ver']))
    log('[3/6] 已复制解释器宿主与 pywin32 服务宿主')

    # --- 4. 标准库闭包 ---
    lib = os.path.join(src['prefix'], 'Lib')
    for f in files:
        rel = os.path.relpath(f, src['prefix'])
        parts = rel.split(os.sep)
        top = parts[0]
        if top not in ('Lib', 'DLLs'):
            continue
        if top == 'Lib' and 'site-packages' in parts:
            continue                       # pywin32 在第 5 步统一放到 Lib\win32 下
        if top == 'DLLs' and os.path.splitext(os.path.basename(f))[0] in EXCLUDE_PYD:
            continue
        if os.path.splitext(f)[1] in SKIP_EXT:
            continue
        if any(p in SKIP_DIRS for p in parts):
            continue
        cp(rel, f)
    # encodings 全量（codec 查找表依赖 aliases，运行时按需 import，不能只留闭包那几个）
    enc_src = os.path.join(lib, 'encodings')
    n_enc = 0
    for root, dirs, fs in os.walk(enc_src):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in fs:
            if os.path.splitext(fn)[1] in SKIP_EXT:
                continue
            s = os.path.join(root, fn)
            cp(os.path.relpath(s, src['prefix']), s)
            n_enc += 1
    n_dll = 0
    for name in DLL_DEPS:
        f = os.path.join(src['prefix'], 'DLLs', name)
        if os.path.isfile(f):
            cp(os.path.join('DLLs', name), f)
            n_dll += 1
    # site.py：保留 site 机制（服务宿主用它初始化 sys.path）
    f = os.path.join(lib, 'site.py')
    if os.path.isfile(f):
        cp(os.path.join('Lib', 'site.py'), f)
    # 注意：不复制源安装的 sitecustomize.py（多为第三方注入，会拖入无关依赖）
    log('[4/6] 已复制精简标准库（encodings %d 个 / DLL 依赖 %d 个）' % (n_enc, n_dll))

    # --- 5. pywin32（放 Lib\\win32 下，使服务进程即使不导入 site 也能找到） ---
    sp = os.path.join(lib, 'site-packages')
    w32 = os.path.join(sp, 'win32')
    if not os.path.isdir(w32):
        log('[错误] 源环境缺少 pywin32（%s），无法构建服务所需的运行时。' % w32)
        return 3
    n_w32 = 0
    for fn in sorted(os.listdir(w32)):
        s = os.path.join(w32, fn)
        if os.path.isfile(s):
            if os.path.splitext(fn)[1] in SKIP_EXT or fn.lower().endswith('.txt'):
                continue
            if os.path.splitext(fn)[1] == '.pyd' and fn.split('.')[0] not in (
                    'win32api', 'win32event', 'win32service', 'servicemanager',
                    '_win32sysloader'):
                continue                       # 其余 GUI/打印类扩展与服务无关
            cp(os.path.join('Lib', 'win32', fn), s)
            n_w32 += 1
    w32lib = os.path.join(w32, 'lib')
    if os.path.isdir(w32lib):
        for fn in sorted(os.listdir(w32lib)):
            s = os.path.join(w32lib, fn)
            if os.path.isfile(s) and os.path.splitext(fn)[1] == '.py':
                cp(os.path.join('Lib', 'win32', 'lib', fn), s)
                n_w32 += 1
    log('[5/6] 已复制 pywin32（%d 个文件）' % n_w32)

    # pywin32 的 .pyd 在 win32\\、Python 模块在 win32\\lib\\，两条路径都必须在 sys.path 上。
    # 这里不用 site-packages 的 .pth 打补丁了事，而是自带 sitecustomize.py，
    # 服务宿主（pythonservice.exe）启动解释器时会自动执行它。
    sc = ('# -*- coding: utf-8 -*-\n'
          '"""内置运行时自带：把 pywin32 目录加入 sys.path。\n'
          '自动生成于 build_embedded_python.py，请勿手改。"""\n'
          'import os as _os, sys as _sys\n'
          '_lib = _os.path.dirname(_os.path.abspath(__file__))\n'
          'for _p in ("win32", _os.path.join("win32", "lib")):\n'
          '    _d = _os.path.join(_lib, _p)\n'
          '    if _d not in _sys.path:\n'
          '        _sys.path.append(_d)\n')
    io.open(os.path.join(dest, 'Lib', 'sitecustomize.py'), 'w', encoding='utf-8').write(sc)
    sp_dir = os.path.join(dest, 'Lib', 'site-packages')
    os.makedirs(sp_dir, exist_ok=True)
    io.open(os.path.join(sp_dir, 'pywin32.pth'), 'w', encoding='utf-8').write(
        '..\\win32\n..\\win32\\lib\n')

    # --- 6. 元信息 + 自检 ---
    info = {
        'name': 'Claude 汉化包内置 Python 运行时',
        'version': version,
        'tag': src['ver'],
        'build_time': time.strftime('%Y-%m-%d %H:%M:%S'),
        'source_python': src['exe'],
        'python_exe': 'python.exe',
        'pythonw_exe': 'pythonw.exe',
        'service_host': 'pythonservice.exe',
        'python_dll': 'python%s.dll' % src['ver'],
        'files': copied,
    }
    io.open(os.path.join(dest, 'RUNTIME.json'), 'w', encoding='utf-8').write(
        json.dumps(info, ensure_ascii=False, indent=2) + '\n')

    exe = os.path.join(dest, 'python.exe')
    ok = False
    if os.path.isfile(exe):
        # 必须校验 sys.prefix 落在内置目录内，否则说明 exe 通过 PATH 找到了系统解释器（假通过）
        chk = ('import sys,os,json,hashlib,subprocess,ctypes;'
               'import win32serviceutil,win32service,win32event,servicemanager;'
               'print("RUNTIME_OK", sys.version.split()[0], sys.prefix, sys.executable)')
        r = subprocess.run([exe, '-c', chk], capture_output=True, text=True,
                           timeout=60, cwd=os.path.dirname(dest))
        out = (r.stdout + r.stderr).strip()
        ok = (r.returncode == 0 and 'RUNTIME_OK' in r.stdout
              and os.path.normcase(os.path.abspath(dest)) in
              os.path.normcase(r.stdout))
        log('[6/6] 自检：%s' % ('通过 —— ' + r.stdout.strip() if ok
                                else '失败 —— ' + out[-400:]))
    else:
        log('[6/6] 自检：跳过（缺少 python.exe）')

    size = sum(os.path.getsize(os.path.join(r, f))
               for r, _, fs in os.walk(dest) for f in fs)
    log('')
    log('输出目录：%s' % dest)
    log('文件数：%d    体积：%.1f MB' % (copied, size / 1048576.0))
    log('状态：%s' % ('构建成功' if ok else '构建完成但自检未通过，请勿部署'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
