# -*- coding: utf-8 -*-
"""汉化状态全面核验：安装态（应为中文）/ 卸载态（应为英文）。

用法:
    python verify_state.py            # 自动判定当前状态
    python verify_state.py installed  # 断言处于安装态
    python verify_state.py uninstalled# 断言处于卸载态
"""
import hashlib
import json
import os
import re
import struct
import subprocess
import sys


def _running_watchers():
    """统计正在运行的 skills-watch 实例数（v3.0 安装态应为 0：非驻留架构）。
    wmic 在新版 Windows 已移除，失败时退化为 PowerShell CIM 查询，再失败返回 -1
    （核验器对 -1 不做通过判定）。"""
    for cmd in (
        ['wmic', 'process', 'where', "name like 'python%.exe'", 'get', 'commandline'],
        ['powershell', '-NoProfile', '-Command',
         ("[@(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | "
          "Where-Object { $_.Name -match '^python' -and "
          "$_.CommandLine -match 'skills-watch' })].Count")],
    ):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            out = (r.stdout or '').strip()
            if cmd[0] == 'wmic':
                if r.returncode != 0 or not out:
                    continue        # wmic 不可用（新版已移除）→ 退化 PowerShell
                return sum(1 for ln in out.splitlines() if 'skills-watch' in ln)
            try:
                return int(out)
            except ValueError:
                return 0
        except Exception:
            continue
    return -1


def _query_service(name):
    """查询 Windows 服务。返回 (Status, StartMode)，不存在/查询失败返回 None。

    不用 sc.exe：它在部分环境（含受限沙箱与企业安全策略）被禁用。改用 PowerShell
    的 Get-Service + Get-CimInstance，纯托管路径、无外部 exe 依赖。
    """
    try:
        import subprocess as _sp
        ps = ("$s = Get-Service -Name '%s' -ErrorAction SilentlyContinue; "
              "if ($s) { $c = Get-CimInstance Win32_Service -Filter \"Name='%s'\"; "
              "Write-Output ($s.Status.ToString() + '|' + $c.StartMode) } "
              "else { Write-Output 'NONE' }") % (name, name)
        r = _sp.run(['powershell', '-NoProfile', '-Command', ps],
                    capture_output=True, text=True, timeout=40)
        lines = [x.strip() for x in (r.stdout or '').splitlines() if x.strip()]
        if not lines or lines[-1] == 'NONE':
            return None
        parts = lines[-1].split('|')
        return (parts[0], parts[1] if len(parts) > 1 else '?')
    except Exception:
        return None


# ---- 安装目标自动定位（可移植：不写死版本/用户名） ----
# 优先级：install-context.json（安装时写入）> 自动探测 WindowsApps 最新 Claude_*
ZH_HOME = os.path.join(os.environ.get('USERPROFILE', ''), '.claude', 'zh')
_ctx = os.path.join(ZH_HOME, 'install-context.json')
PKG = None
VERSION = None
if os.path.isfile(_ctx):
    try:
        _c = json.load(open(_ctx, encoding='utf-8'))
        if _c.get('pkgPath') and os.path.isdir(_c['pkgPath']):
            PKG = _c['pkgPath']
            VERSION = _c.get('version')
    except Exception:
        pass
if not PKG:
    _wa = r'C:\Program Files\WindowsApps'
    if os.path.isdir(_wa):
        _best = None
        for _d in os.listdir(_wa):
            if not _d.startswith('Claude_'):
                continue
            _p = os.path.join(_wa, _d)
            _f = os.path.join(_p, 'app', 'resources', 'ion-dist', 'i18n', 'en-US.json')
            if os.path.isfile(_f):
                _m = os.path.getmtime(_f)
                if _best is None or _m > _best[0]:
                    _best = (_m, _p, _d)
        if _best:
            PKG = _best[1]
            m = re.match(r'Claude_(.+?)_x64__', _best[2])
            VERSION = m.group(1) if m else _best[2]

APP = os.path.join(PKG, 'app') if PKG else ''
RES = os.path.join(APP, 'resources') if PKG else ''
ION = os.path.join(RES, 'ion-dist') if PKG else ''
I18N = os.path.join(ION, 'i18n', 'zh-Hans.json') if PKG else ''
DYN = os.path.join(ION, 'i18n', 'dynamic', 'zh-Hans.json') if PKG else ''
SHELL = os.path.join(RES, 'zh-Hans.json') if PKG else ''
ASAR = os.path.join(RES, 'app.asar') if PKG else ''
EXE = os.path.join(APP, 'claude.exe') if PKG else ''
CONF = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Claude-3p', 'config.json')
BAK_DIR = os.path.join(ZH_HOME, 'backup', VERSION) if VERSION else os.path.join(ZH_HOME, 'backup')
if not PKG:
    print('[错误] 未定位到 Claude Desktop 安装目录，无法核验')
    sys.exit(2)

CJK = re.compile(r'[\u4e00-\u9fff]')
OK, BAD, WARN = '[OK]  ', '[FAIL]', '[WARN]'

# 第 8 轮新增 19 条 FE key（截图 6-12 反查得到）
NEW_KEYS = ['MpsZ34EpZH', 'zDckNDEUsW', 'aFwG8a56pF', 'P0gQiUc0+j', 'dnMG5c8GDx',
            'cxfXVHDjYE', 'zxDZnEbGiY', 'eMKehO2KIl', 'y2YuB93nEz', 'FtenArWTkI',
            'sFZOQNiiWa', 'InfCustomHeadersHint2', 'vVjD8kgAio', '5yaeKvpzWL',
            'B6i3SyZAU2', 'VsPAC2z1YR', 'v9YS8eHay0', 'TacDGqVkLa', 'Gqm6SFn9I2']

# 第 9 轮新增 35 条 FE key（连接页 + 能力页截图反查得到）
NEW_KEYS_R9 = ['YT+I9m2Ho0', 'SBjuzIVQAJ', 'dayANLBel0', 'O20EMso86S', 'dRsQ1NgKdo',
               '+ve5HIdJLG', 'N8nKVnjFDF', '/vs1W12TA0', 'z2x73mCBZ9', 'Y1xPjaGHSo',
               '5BMPzic821', 'vSpvldmS33', '94/7dcRsyP', 'eXwx/L4TgM', 'Cpqtiix6lD',
               'oqdOf+hjLS', '7AFPPgSJBu', 'scheduledTasksEnabledShort',
               'keepAwakeEnabledShort', 'developerModeEnabledTitle',
               'developerModeEnabledShort', '0I38l/TM7C', '3dSlpHs3f5',
               'XVYTn+sJ/a', 'H4Ea6XAuEf', 'kMVrXfFbvZ', 'GP16g9tMfY',
               'R0nTUNCSi6', 'OTJGMVqwLa', 'TnZHycC4Xk', 'CkU2BFhxiC',
               'SshTransportHint', '1h3TR2uKST', 'tevwj/1wDb', 'X2sJavpMCo']

# 本轮新增 6 条 asar 技能描述（英文原文 -> 中文译文）
ASAR_ITEMS = [
    ("Show what's using your context window", '显示上下文窗口的占用情况'),
    ('Work with Claude Design (claude.ai/design)', 'Claude Design（claude.ai/design）'),
    ('Reflective pass over your memory files', '对记忆文件做反思性整理'),
    ('Create or update a scheduled task', '创建或更新自动运行的计划任务'),
    ('Guided setup \\u2014 install a matching plugin', '引导式设置——安装匹配插件'),
    ("Explain where this session's tokens went", '用一张简单图表'),
]

results = []


def chk(ok, label, detail=''):
    results.append((ok, label, detail))
    print('  %s %s%s' % (OK if ok else BAD, label, ('  -> ' + detail) if detail else ''))


def load(p):
    try:
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def asar_blob():
    """读 app.asar 全文（仅用于文本检索，不解析结构）。"""
    try:
        with open(ASAR, 'rb') as f:
            return f.read()
    except Exception:
        return b''


def parse_asar(data):
    """解析 asar header，返回 (js_len, hdr_raw bytes, files list)。"""
    js_len = struct.unpack('<I', bytes(data[12:16]))[0]
    hdr_raw = bytes(data[16:16 + js_len])
    j = json.loads(hdr_raw.decode('utf-8'))
    base = 16 + js_len
    if base % 4:
        base += 4 - (base % 4)
    files = []

    def walk(node, path):
        for name, e in node.items():
            fp = path + '/' + name
            if 'files' in e:
                walk(e['files'], fp)
            else:
                files.append({
                    'path': fp,
                    'start': base + int(e.get('offset', 0)),
                    'size': e.get('size', 0),
                    'integrity': e.get('integrity'),
                })
    walk(j.get('files', {}), '')
    return js_len, hdr_raw, files, base


def asar_integrity_selfcheck():
    """校验 asar 两层 integrity 链是否自洽（exe 内嵌 header 哈希 + 各文件 hash）。"""
    try:
        with open(ASAR, 'rb') as f:
            data = f.read()
    except Exception as e:
        return None, 'app.asar 读取失败: %s' % e
    try:
        js_len, hdr_raw, files, base = parse_asar(data)
    except Exception as e:
        return None, 'header 解析失败: %s' % e

    # 层 1: exe 内嵌的 sha256(header JSON) 是否与实际一致
    try:
        with open(EXE, 'rb') as f:
            exeb = f.read()
    except Exception as e:
        return None, 'claude.exe 读取失败: %s' % e
    m = re.search(rb'\[\{"file":"resources\\\\app\.asar","alg":"SHA256","value":"([0-9a-f]{64})"\}\]', exeb)
    if not m:
        return None, 'exe 内未找到 asar integrity 记录'
    want = m.group(1).decode('ascii')
    got = hashlib.sha256(hdr_raw).hexdigest()
    l1 = (want == got)
    return (l1, got, want, files, data, base), None


# 旧版写死的清单（前端资源名带内容哈希，Claude 升级即变，仅作最后兜底）
LEGACY_JS_FILES = ('c49da61a8-CCivQmSM.js', 'shared-21-DExJa6Im.js',
                   'shared-20-78nc04b9.js', 'shared-52-DOMr1cuc.js')


def _shell_official_from_archive():
    """从卸载归档 zip 中取回安装前备份的官方 shell 词表。

    卸载会连 .claude\\zh（含 backup）一起删除，但卸载流程会先把整个目录归档到
    %TEMP%\\claude-zh-uninstall-<ts>.zip（供误卸载找回）。有它就能做精确比对，
    否则只能按"键是否存在"猜测——而官方原版本来就含部分 overlay 键，会误报。
    """
    import glob
    import zipfile
    tmp = os.environ.get('TEMP') or os.environ.get('TMP') or ''
    if not tmp:
        return None
    zs = sorted(glob.glob(os.path.join(tmp, 'claude-zh-uninstall-*.zip')),
                key=os.path.getmtime, reverse=True)
    for zp in zs:
        try:
            zf = zipfile.ZipFile(zp)
        except Exception:
            continue
        cands = [n for n in zf.namelist()
                 if n.replace('\\', '/').startswith('backup/')
                 and n.endswith('shell-zh-Hans.json')]
        if not cands:
            continue
        sel = None
        if VERSION:
            for n in cands:
                if '/' + VERSION + '/' in n.replace('\\', '/'):
                    sel = n
                    break
        try:
            return json.loads(zf.read(sel or cands[0]).decode('utf-8'))
        except Exception:
            continue
    return None


def _js_patch_targets(assets_dir):
    """解析本版本的 JS 补丁目标文件名。

    前端资源是带内容哈希的文件名（如 shared-52-<hash>.js），Claude 每次升级
    哈希都会变，写死必然失效（表现为 [6] 项全部"文件不存在"）。优先级：
      1) state.json 的 js[].path —— 安装时写入的真实文件名，最可靠
      2) 备份目录中的 .js 原始文件名 —— 卸载态据此做字节还原核验
      3) assets 目录内容扫描（命中补丁特征串）
      4) 旧版写死清单
    """
    names = []
    st = os.path.join(ZH_HOME, 'state.json')
    if os.path.isfile(st):
        try:
            for it in json.load(open(st, encoding='utf-8')).get('js', []):
                n = os.path.basename(it.get('path') or '')
                if n.endswith('.js') and n not in names:
                    names.append(n)
        except Exception:
            names = []
    if not names and os.path.isdir(BAK_DIR):
        names = sorted(n for n in os.listdir(BAK_DIR) if n.endswith('.js'))
    if not names and os.path.isdir(assets_dir):
        # 内容扫描：先按"已打补丁"特征找（安装态），再按"英文原版"特征找
        # （卸载态补丁已还原，中文特征不复存在，只认中文会一无所获）。
        # 候选限定为带内容哈希的前端文件名，避免扫全目录。
        patched = (b'"en-US","zh-Hans"', b'localName:"\\u7B80',
                   b'label:"\\u804A', b'label:"\\u534F')
        original = (b'"en-US","de-DE","fr-FR"',
                    b'localName:"English (United States)"',
                    b'label:"Chat"', b'label:"Cowork"', b'label:"Code"')
        cand = [n for n in sorted(os.listdir(assets_dir))
                if n.endswith('.js') and re.match(r'^(shared-\d+|c49da61a8)-', n)]
        for marks in (patched, original):
            for n in cand:
                try:
                    b = open(os.path.join(assets_dir, n), 'rb').read()
                except Exception:
                    continue
                if any(m in b for m in marks) and n not in names:
                    names.append(n)
            if names:
                break
    return names or list(LEGACY_JS_FILES)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'auto'
    fe = load(I18N)
    shell = load(SHELL)
    conf = load(CONF) or {}
    # 状态判定：locale 为主证据，但不能作为唯一证据——config.json 由 Claude
    # 首次启动后生成，全新安装时并不存在（安装脚本会打印"[警告] 未找到
    # config.json"），此时仅凭 locale 会误判为"已卸载"，进而跑错核验分支、
    # 产生整屏误报 FAIL。故并列采用 install-context.json / state.json 作为
    # 安装态证据：二者由安装写入，卸载时随 .claude\zh 一并删除。
    _evidences = [os.path.join(ZH_HOME, n)
                  for n in ('install-context.json', 'state.json')]
    installed = bool(fe) and (conf.get('locale') == 'zh-Hans'
                              or any(os.path.isfile(p) for p in _evidences))

    print('=' * 66)
    print('  汉化状态核验  |  判定: %s' % ('已安装(汉化态)' if installed else '已卸载(英文态)'))
    print('=' * 66)

    if installed:
        print('\n[1] 词表文件部署（期望：存在且为中文）')
        for p, name in ((I18N, 'ion-dist/i18n/zh-Hans.json'),
                        (DYN, 'ion-dist/i18n/dynamic/zh-Hans.json'),
                        (SHELL, 'resources/zh-Hans.json (shell)')):
            chk(os.path.exists(p), name)
        if fe:
            cjk = sum(1 for v in fe.values() if isinstance(v, str) and CJK.search(v))
            print('      前端词表 %d 条，其中含中文 %d 条' % (len(fe), cjk))
        if shell:
            cjk = sum(1 for v in shell.values() if isinstance(v, str) and CJK.search(v))
            print('      shell 词表 %d 条，其中含中文 %d 条' % (len(shell), cjk))

        print('\n[2] locale 配置')
        print('      config.json locale = %r' % conf.get('locale'))
        if not os.path.exists(CONF):
            # config.json 由 Claude 首次启动后生成；全新安装时尚不存在，安装脚本
            # 已就此打印"[警告] 未找到 config.json，将在首次启动后生效"。
            # 属预期过渡态，不计为失败（服务首次自愈时会补写 locale）。
            print('      [跳过] config.json 尚未生成（Claude 首次启动后写入，属预期）')
        else:
            chk(conf.get('locale') == 'zh-Hans', 'locale 为 zh-Hans')

        print('\n[3] 本轮新增 FE 词条落盘核验')
        if fe:
            for label, keys in (('第8轮 19 条', NEW_KEYS), ('第9轮 35 条', NEW_KEYS_R9)):
                miss = [k for k in keys if k not in fe]
                bad = [k for k in keys if k in fe and not CJK.search(str(fe[k]))]
                chk(not miss and not bad,
                    '%s新增 key 均已写入且为中文' % label,
                    ('缺失 %s' % miss) if miss else (('非中文 %s' % bad) if bad else '全部命中'))
        else:
            chk(False, '前端词表不存在')

        print('\n[3b] dynamic 词表（仓库优先 overlay）核验')
        if os.path.exists(DYN):
            dz = load(DYN) or {}
            store_path = os.path.join(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))), 'resources', 'translations', 'zh-store.json')
            if os.path.exists(store_path):
                _s = json.load(open(store_path, encoding='utf-8'))['namespaces']
                dyn_en = os.path.join(ION, 'i18n', 'dynamic', 'en-US.json')
                dyn_keys = [k for k in _s['fe-key'] if os.path.exists(dyn_en)
                            and k in json.load(open(dyn_en, encoding='utf-8'))]
                ok_n = bad = 0
                for k in dyn_keys:
                    v = dz.get(k)
                    if isinstance(v, str) and CJK.search(v):
                        ok_n += 1
                    else:
                        bad += 1
                chk(bad == 0, 'dynamic key（%d 条）部署值均为中文' % len(dyn_keys),
                    '中文 %d / 异常 %d' % (ok_n, bad))
        else:
            chk(False, r'dynamic\zh-Hans.json 不存在')

        print('\n[4] 本轮新增 app.asar 技能描述（6 条）落盘核验')
        blob = asar_blob()
        if blob:
            zh_hit = en_hit = 0
            for en, zh in ASAR_ITEMS:
                if zh.encode('utf-8') in blob:
                    zh_hit += 1
                elif en.encode('utf-8') in blob:
                    en_hit += 1
            print('      中文命中 %d 条 / 英文残留 %d 条' % (zh_hit, en_hit))
            chk(zh_hit >= 5, 'asar 技能描述已汉化（>=5 条中文命中）')
        else:
            chk(False, 'app.asar 读取失败')
    else:
        print('\n[1] 词表文件清除（期望：已删除/还原为英文）')
        for p, name in ((I18N, 'ion-dist/i18n/zh-Hans.json'),
                        (DYN, 'ion-dist/i18n/dynamic/zh-Hans.json')):
            chk(not os.path.exists(p), '已删除 %s' % name)
        # 注意：resources/zh-Hans.json 是 Claude 官方自带文件，本身含官方中文词条，
        # 因此不能按"是否含中文"判定，只能与官方原版比对，来源优先级：
        #   1) 安装前备份 .claude\zh\backup\<ver>\shell-zh-Hans.json（字节级）
        #   2) 卸载归档 zip（卸载会删除 .claude\zh，但先归档到 %TEMP%，可取回）
        # 两者都不可用时**不能**退回"overlay 键是否存在"判定：官方原版本来就含
        # 部分 overlay 键（实测 14 个，值亦与官方完全一致），那样会误报残留。
        bak_shell = os.path.join(BAK_DIR, 'shell-zh-Hans.json')
        if os.path.exists(bak_shell) and os.path.exists(SHELL):
            same = open(bak_shell, 'rb').read() == open(SHELL, 'rb').read()
            chk(same, 'resources/zh-Hans.json 与官方原版字节一致')
        elif not os.path.exists(SHELL):
            chk(True, 'resources/zh-Hans.json 已移除')
        elif os.path.exists(SHELL):
            _official = _shell_official_from_archive()
            if _official is None:
                print('      [跳过] 无官方原版可比对（备份已随 .claude\\zh 归档删除，'
                      '且未找到卸载归档 zip），不做残留判定')
            else:
                try:
                    _dep = json.load(open(SHELL, encoding='utf-8'))
                except Exception as e:
                    chk(False, 'shell 词表读取失败', str(e))
                    _dep = None
                if _dep is not None:
                    _diff = [k for k, v in _official.items()
                             if str(_dep.get(k)) != str(v)]
                    _extra = [k for k in _dep if k not in _official]
                    chk(not _diff and not _extra,
                        'resources/zh-Hans.json 与官方原版一致（归档比对 %d 条）'
                        % len(_official),
                        ('值不同 %s / 多出键 %s' % (_diff[:3], _extra[:3]))
                        if (_diff or _extra) else '逐键一致，无汉化残留')
        else:
            chk(False, 'resources/zh-Hans.json 状态异常')

        print('\n[2] locale 配置（期望：恢复 en-US）')
        print('      config.json locale = %r' % conf.get('locale'))
        chk(conf.get('locale') != 'zh-Hans', 'locale 已恢复非 zh-Hans')

        print('\n[3] app.asar 技能描述还原（期望：英文原文在位）')
        blob = asar_blob()
        en_hit = sum(1 for en, _ in ASAR_ITEMS if en.encode('utf-8') in blob)
        zh_hit = sum(1 for _, zh in ASAR_ITEMS if zh.encode('utf-8') in blob)
        print('      英文原文 %d 条 / 中文残留 %d 条' % (en_hit, zh_hit))
        chk(en_hit >= 5 and zh_hit == 0, 'asar 已还原英文且无中文残留')

    print('\n[5] app.asar integrity 链自洽校验')
    r, err = asar_integrity_selfcheck()
    if err:
        chk(False, 'integrity 链校验', err)
    else:
        l1, got, want, files, data, base = r
        chk(l1, '层1 exe 内嵌 header 哈希 MATCH', '%s...' % got[:16])
        checked = bad = 0
        bad_list = []
        for it in files:
            itg = it.get('integrity') or {}
            if itg.get('algorithm') != 'SHA256' or not it['size']:
                continue
            o, s = it['start'], it['size']
            h = hashlib.sha256(data[o:o + s]).hexdigest()
            checked += 1
            if h != itg.get('hash'):
                bad += 1
                bad_list.append(it['path'])
        # 原生模块（.node/.dll/.exe）Electron 不校验，安装时即不匹配，属预期
        native = [p for p in bad_list if p.endswith(('.node', '.dll', '.exe'))]
        real = [p for p in bad_list if p not in native]
        chk(not real, '层2 文件 hash 全量校验 (%d 个)' % checked,
            ('异常不匹配 %s' % real[:3]) if real else
            ('全部 MATCH（原生模块 %d 个不校验，属预期）' % len(native)))

    print('\n[6] 前端白名单 / 标题栏补丁')
    A1 = os.path.join(ION, 'assets', 'v1')
    # 标题栏补丁以 \uXXXX 大写/小写转义形态写入（Latin1 字节级），
    # 需检测码点落在 CJK 区间的转义序列
    esc = re.compile(rb'\\u([0-9a-fA-F]{4})')
    for n in _js_patch_targets(A1):
        p = os.path.join(A1, n)
        bp = os.path.join(BAK_DIR, n)
        if not os.path.exists(p):
            chk(False, '文件不存在 %s' % n)
            continue
        b = open(p, 'rb').read()
        if os.path.exists(bp):
            same = (b == open(bp, 'rb').read())
            if installed:
                chk(not same, '%s 已打补丁（与原始备份不同）' % n)
            else:
                chk(same, '%s 已字节级还原为原始版本' % n)
        chars = {chr(int(m.group(1), 16)) for m in esc.finditer(b)}
        cjk = {c for c in chars if '\u4e00' <= c <= '\u9fff'}
        if cjk:
            print('        CJK 转义字符: %s' % ''.join(sorted(cjk))[:24])

    print('\n[7] 词条仓库持久性')
    store = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         'resources', 'translations', 'zh-store.json')
    if os.path.exists(store):
        d = json.load(open(store, encoding='utf-8'))
        ns = d.get('namespaces', {})
        print('      ' + ' | '.join('%s=%d' % (k, len(v)) for k, v in ns.items()))
        chk(len(ns.get('asar-source', {})) >= 6, 'asar-source 词条 >= 6')
        chk(len(ns.get('fe-key', {})) >= 420, 'fe-key 词条 >= 420（第9轮 +35）')
    else:
        chk(False, '词条仓库存在')

    print('\n[8] 补丁日志')
    log = os.path.join(ZH_HOME, 'backup', 'asar-source-patch-log.json')
    if installed:
        chk(os.path.exists(log), 'asar 补丁日志存在（卸载时可精确还原）')
    else:
        chk(not os.path.exists(log), 'asar 补丁日志已随还原清除')

    # ---- [9] 内核 claude.exe（2026-10-15 新增：并发空日志覆盖事故后补盲区） ----
    # 安装态：字符串表中文在位 + kernel-patch-log 每条与二进制逐点一致（可还原）
    # 卸载态：kernel-table / kernel-source 译文零残留
    print('\n[9] 内核 claude.exe 补丁核验')
    kbase = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Claude-3p', 'claude-code')
    kpath = None
    if os.path.isdir(kbase):
        _bestmt = None
        for _ver in os.listdir(kbase):
            _vd = os.path.join(kbase, _ver)
            if not os.path.isdir(_vd):
                continue
            for _h in os.listdir(_vd):
                _p = os.path.join(_vd, _h, 'claude.exe')
                if os.path.isfile(_p):
                    _m = os.path.getmtime(_p)
                    if _bestmt is None or _m > _bestmt:
                        kpath, _bestmt = _p, _m
    if not kpath:
        print('      未找到 claude.exe 内核，跳过')
    else:
        kdata = open(kpath, 'rb').read()
        kstore = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              'resources', 'translations', 'zh-store.json')
        kt = {}
        ks = {}
        if os.path.exists(kstore):
            _ns = json.load(open(kstore, encoding='utf-8')).get('namespaces', {})
            kt = _ns.get('kernel-table', {})
            ks = _ns.get('kernel-source', {})

        def _zh(v):
            return v.get('zh') if isinstance(v, dict) else v

        def _cjk(s):
            # 译文不含中文字符（如 '/usage-credits' 与英文原样一致）时无法与
            # 合法英文表项区分，不参与命中/残留判定
            return bool(s) and any('\u4e00' <= c <= '\u9fff' for c in s)

        kt_hit = sum(1 for v in kt.values()
                     if _cjk(_zh(v)) and _zh(v).encode('utf-16-le') in kdata)
        ks_hit = sum(1 for v in ks.values()
                     if _cjk(_zh(v)) and _zh(v).encode('utf-8') in kdata)
        print('      内核: %s (%.0f MB)' % (os.path.basename(os.path.dirname(
            os.path.dirname(kpath))), len(kdata) / 1048576))
        if installed:
            chk(kt_hit >= 100, '内核字符串表已汉化（%d/%d 条译文在位）' % (kt_hit, len(kt)))
            chk(ks_hit >= 30, '内核源码字面量已汉化（%d/%d 条译文在位）' % (ks_hit, len(ks)))
            klog = os.path.join(ZH_HOME, 'backup', 'kernel-patch-log.json')
            ok_rec = bad_rec = 0
            if os.path.exists(klog):
                try:
                    kl = json.load(open(klog, encoding='utf-8'))
                except Exception:
                    kl = {}
                for en, rec in kl.items():
                    zh = _zh(kt.get(en))
                    if not zh:
                        continue
                    try:
                        off = rec['offset']
                        hdr = struct.unpack_from('<I', kdata, off - 8)[0]
                        if hdr >> 31:
                            bad_rec += 1
                            continue
                        units = hdr & 0x7FFFFFFF
                        txt = bytes(kdata[off:off + units * 2]).decode(
                            'utf-16-le').rstrip(' ')
                        if txt == zh:
                            ok_rec += 1
                        else:
                            bad_rec += 1
                    except Exception:
                        bad_rec += 1
            chk(ok_rec >= 100 and bad_rec == 0,
                'kernel-patch-log 与二进制逐点一致（%d 条可精确还原，%d 条异常）'
                % (ok_rec, bad_rec),
                '空/失配日志会导致卸载无法还原内核（2026-10-15 竞态事故）'
                if bad_rec or ok_rec < 100 else '')
        else:
            chk(kt_hit == 0, '内核无 kernel-table 中文残留（%d 条）' % kt_hit)
            chk(ks_hit == 0, '内核无 kernel-source 中文残留（%d 条）' % ks_hit)

    # ---- [10] Claude_zh 服务（v4.0：常驻职责由 Windows 服务承担） ----
    # 安装态：服务已注册且正在运行；旧版自愈资产（登录自检 / 启动器 / 快捷方式）
    #         必须已清理，避免两套机制并存互相打架。
    # 卸载态：服务已删除、降级用的登录自检也已移除、.claude\zh 目录已删除。
    print('\n[10] Claude_zh 服务')
    _svc = _query_service('Claude_zh')
    _su = os.path.join(os.environ.get('APPDATA', ''),
                       'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup')
    if installed:
        chk(os.path.exists(os.path.join(ZH_HOME, 'zh_service.py')),
            '服务宿主 zh_service.py 已部署到 .claude\\zh')
        if _svc is None:
            chk(False, '服务 Claude_zh 已注册（未找到）')
        else:
            _st, _start = _svc
            chk(True, '服务 Claude_zh 已注册（状态 %s / 启动类型 %s）' % (_st, _start))
            chk(_st == 'Running', '服务 Claude_zh 正在运行')
            # CIM Win32_Service.StartMode 取值为 'Auto'；Get-Service.StartType 才是
            # 'Automatic'。二者都要接受，否则该项会恒定失败。
            chk(_start in ('Auto', 'Automatic'),
                '服务 Claude_zh 为开机自动启动（当前 %s）' % _start)
        chk(not os.path.exists(os.path.join(_su, 'claude-zh-heal.cmd')),
            '旧版登录自检自启项已清理')
        chk(not os.path.exists(os.path.join(ZH_HOME, 'start-claude-zh.cmd')),
            '旧版中文版启动器已清理')
        _lnk = os.path.join(os.path.join(os.environ.get('USERPROFILE', ''),
                                         'Desktop'), 'Claude 中文版.lnk')
        chk(not os.path.exists(_lnk), '旧版桌面快捷方式「Claude 中文版」已清理')
    else:
        chk(_svc is None, '服务 Claude_zh 已删除')
        chk(not os.path.exists(os.path.join(_su, 'claude-zh-heal.cmd')),
            '登录自检自启项已移除')
        chk(not os.path.exists(os.path.join(_su, 'claude-zh-skills-watch.cmd')),
            '旧版驻留自启项已移除')

    # [10b] 免登录网关配置（官方 3P 模式，可选；仅安装态且配置过才有核验对象。
    # 卸载态下 .claude\zh 已删、无法得知曾经的配置 id，由卸载脚本负责还原。）
    if installed:
        print('\n[10b] 免登录网关配置（可选）')
        _gid = (load(_ctx) or {}).get('gatewayConfigId')
        if not _gid:
            print('      未配置免登录网关（gateway.json 未提供，跳过）')
        else:
            _lib = os.path.join(os.environ.get('LOCALAPPDATA', ''),
                                'Claude-3p', 'configLibrary')
            chk(os.path.exists(os.path.join(_lib, _gid + '.json')),
                '网关配置 <id>.json 已写入 configLibrary')
            _gmeta = load(os.path.join(_lib, '_meta.json')) or {}
            chk(_gmeta.get('appliedId') == _gid,
                'configLibrary 索引 appliedId 指向该配置')
        chk(not os.path.exists(ZH_HOME), '%USERPROFILE%\\.claude\\zh 已删除')

    print('\n' + '=' * 66)
    fails = [r for r in results if not r[0]]
    print('  结果: %d 项通过 / %d 项失败' % (len(results) - len(fails), len(fails)))
    if mode == 'installed':
        print('  期望: 安装态 -> %s' % ('符合' if (installed and not fails) else '不符合'))
        return 0 if (installed and not fails) else 1
    if mode == 'uninstalled':
        print('  期望: 卸载态 -> %s' % ('符合' if (not installed) else '不符合'))
        return 0 if (not installed) else 1
    return 0 if not fails else 1


if __name__ == '__main__':
    sys.exit(main())
