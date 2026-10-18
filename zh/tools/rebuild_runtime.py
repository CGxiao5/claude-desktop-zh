# -*- coding: utf-8 -*-
"""运行时资产重建：从补丁态反推并重建 %USERPROFILE%\\.claude\\zh\\backup\\ 下的
原始文件与三份补丁日志（用于迁移/意外丢失后的恢复）。

重建项（全部确定性可推导）：
  1. 4 个前端 JS 原始文件  —— 用 install-zh.ps1 的补丁定义做逆向替换
  2. shell-zh-Hans.json     —— 当前部署词表减去 overlay 键 = 官方原版
  3. kernel-patch-log.json   —— 扫描内核中文表项 + 由英文原文推导原始头/payload
  4. kernel-source-patch-log —— 扫描内核 UTF-8 中文源码字面量的偏移
  5. asar-source-patch-log   —— 扫描 app.asar 中文词条偏移 + 重算 integrity 双向哈希

用法: python rebuild_runtime.py          # 重建到 %USERPROFILE%\\.claude\\zh\\backup
      python rebuild_runtime.py --check  # 只检查不写盘
"""
import hashlib
import io
import json
import os
import re
import struct
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import zhstore  # noqa: E402

ZH = os.path.join(os.environ.get('USERPROFILE', ''), '.claude', 'zh')
BAK = os.path.join(ZH, 'backup')
VER = '2.37337.1.0'          # 由 install-context 决定，缺省用已知版本
WA = r'C:\Program Files\WindowsApps'
CHECK_ONLY = '--check' in sys.argv

# 自动定位包
ctx = os.path.join(ZH, 'install-context.json')
PKG = None
for d in os.listdir(WA):
    if d.startswith('Claude_') and os.path.isfile(os.path.join(WA, d, 'app', 'resources', 'app.asar')):
        PKG = os.path.join(WA, d)
        m = re.match(r'Claude_(.+?)_x64__', d)
        if m:
            VER = m.group(1)
        break
if os.path.isfile(ctx):
    try:
        c = json.load(open(ctx, encoding='utf-8'))
        if c.get('version'):
            VER = c['version']
    except Exception:
        pass
RES = os.path.join(PKG, 'app', 'resources')
BAKVER = os.path.join(BAK, VER)
V1 = os.path.join(RES, 'ion-dist', 'assets', 'v1')

# ---- install-zh.ps1 的补丁定义（必须与其保持一致）----
JS_REV = [
    # (补丁后文本, 原始文本)
    ('"en-US","zh-Hans","de-DE","fr-FR","ko-KR","ja-JP","es-419","es-ES","it-IT","hi-IN","pt-BR","id-ID"',
     '"en-US","de-DE","fr-FR","ko-KR","ja-JP","es-419","es-ES","it-IT","hi-IN","pt-BR","id-ID"'),
    ('"zh-Hans":{name:"Chinese (Simplified)",localName:"\\u7B80\\u4F53\\u4E2D\\u6587"},', ''),
    ('chat:{mode:"chat",icon:"Chats",label:"\\u804A\\u5929"}',
     'chat:{mode:"chat",icon:"Chats",label:"Chat"}'),
    ('cowork:{mode:"cowork",icon:"Tasks",label:"\\u534F\\u4F5C"},code:{mode:"code",icon:"Code",label:"\\u4EE3\\u7801"}',
     'cowork:{mode:"cowork",icon:"Tasks",label:"Cowork"},code:{mode:"code",icon:"Code",label:"Code"}'),
    ('{key:"chat",label:"\\u804A\\u5929"}', '{key:"chat",label:"Chat"}'),
    ('{key:"task",label:"\\u534F\\u4F5C"}', '{key:"task",label:"Cowork"}'),
    ('{key:"code",label:"\\u4EE3\\u7801"}', '{key:"code",label:"Code"}'),
]


def sha(b):
    return hashlib.sha256(b).hexdigest()


def align4(n):
    return (n + 3) & ~3


def w(path, data):
    if CHECK_ONLY:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if isinstance(data, bytes):
        with open(path, 'wb') as f:
            f.write(data)
    elif isinstance(data, dict):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
    else:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(data)
    print('    写出 %s' % os.path.relpath(path, ZH))


# 旧版写死的清单（前端资源名带内容哈希，Claude 升级即变，仅作最后兜底）
LEGACY_JS = ['c49da61a8-CCivQmSM.js', 'shared-21-DExJa6Im.js',
             'shared-20-78nc04b9.js', 'shared-52-DOMr1cuc.js']


def js_targets(assets_dir, bak_dir):
    """解析本版本的 JS 补丁目标文件名（与 verify_state._js_patch_targets 同策略）。

    前端资源名带内容哈希，升级后必然变化，写死会导致本脚本在 [1] 步直接
    FileNotFoundError。优先级：state.json > 备份目录中的 .js > 目录内容扫描 > 旧版清单。
    """
    names = []
    st = os.path.join(ZH, 'state.json')
    if os.path.isfile(st):
        try:
            for it in json.load(open(st, encoding='utf-8')).get('js', []):
                n = os.path.basename(it.get('path') or '')
                if n.endswith('.js') and n not in names:
                    names.append(n)
        except Exception:
            names = []
    if not names and os.path.isdir(bak_dir):
        names = sorted(n for n in os.listdir(bak_dir) if n.endswith('.js'))
    if not names and os.path.isdir(assets_dir):
        marks = (b'"en-US","zh-Hans"', b'localName:"\\u7B80',
                 b'label:"\\u804A', b'label:"\\u534F')
        for n in sorted(os.listdir(assets_dir)):
            if not n.endswith('.js'):
                continue
            try:
                b = open(os.path.join(assets_dir, n), 'rb').read()
            except Exception:
                continue
            if any(m in b for m in marks):
                names.append(n)
    return names or list(LEGACY_JS)


def main():
    print('=' * 64)
    print('  运行时资产重建%s' % ('（仅检查）' if CHECK_ONLY else ''))
    print('  版本: %s' % VER)
    print('=' * 64)

    # ---------- 1. JS 原始文件 ----------
    print('\n[1] 前端 JS 原始文件（逆向替换）')
    js_files = js_targets(V1, BAKVER)
    print('  目标文件: %s' % ', '.join(js_files))
    for name in js_files:
        p = os.path.join(V1, name)
        if not os.path.isfile(p):
            print('  [跳过] 文件不存在（版本已变更）: %s' % name)
            continue
        raw = open(p, 'rb').read().decode('latin-1')
        n_rev = 0
        for new, old in JS_REV:
            cnt = raw.count(new)
            if cnt:
                raw = raw.replace(new, old)
                n_rev += cnt
        cjk = {chr(int(x, 16)) for x in re.findall(r'\\u([0-9A-Fa-f]{4})', raw)}
        cjk = {c for c in cjk if '\u4e00' <= c <= '\u9fff'}
        print('  %-26s 逆向 %d 处 | 残留 CJK 转义 %d 个（官方自带简繁体词条属正常）'
              % (name, n_rev, len(cjk)))
        w(os.path.join(BAKVER, name), raw.encode('latin-1'))

    # ---------- 2. shell-zh-Hans.json 官方原版 ----------
    print('\n[2] shell-zh-Hans.json（当前部署 - overlay 键）')
    cur = json.load(open(os.path.join(RES, 'zh-Hans.json'), encoding='utf-8'))
    ov = json.load(open(os.path.join(ROOT, 'resources', 'shell-overlay-zh.json'),
                       encoding='utf-8'))
    # 注意：overlay 键若与官方键重叠，减法会误删官方键；但无法得知官方原值，
    # 只能依赖 overlay 词表与官方词表键集不重叠这一前提（由 sync_check [B] 保证规模）。
    official = {k: v for k, v in cur.items() if k not in ov}
    print('  当前部署 %d 条 - overlay %d 条 = 官方 %d 条'
          % (len(cur), len(ov), len(official)))
    w(os.path.join(BAKVER, 'shell-zh-Hans.json'), official)

    # ---------- 3. kernel-patch-log.json ----------
    print('\n[3] kernel-patch-log.json（字符串表逆向推导）')
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'tk', os.path.join(ROOT, 'scripts', 'translate-kernel.py'))
    tk = importlib.util.module_from_spec(spec)
    sys.argv = [sys.argv[0]]
    spec.loader.exec_module(tk)
    table, n_store = tk.load_translations()
    kpath = tk.find_kernel()
    # 未安装 Claude Code 内核时 find_kernel() 返回 None（与安装脚本
    # "[kernel] 未找到 claude.exe 内核，跳过" 一致），此时不能 open(None)，
    # 否则整个重建流程在此崩溃——内核补丁日志本就无从产出，按跳过处理。
    if not kpath:
        print('  [跳过] 未找到 claude.exe 内核（未安装 Claude Code 内核，属正常）')
        kdata = b''
    else:
        kdata = open(kpath, 'rb').read()
    log_k = {}
    for en, zh in table.items():
        try:
            en.encode('latin-1')
            is_latin1 = True
        except UnicodeEncodeError:
            is_latin1 = False
        if is_latin1:
            orig_payload = en.encode('latin-1')
            orig_header = 0x80000000 | len(orig_payload)
            region = align4(len(orig_payload))
            # 补丁后：units = region/2（8->16 位整槽转换）
            # 默认参数绑定循环变量，避免闭包按引用捕获（B023）
            unit_ok = lambda u, txt, region=region, zh=zh: (  # noqa: B023
                u * 2 == region and u >= len(zh) and txt == zh)
        else:
            orig_payload = en.encode('utf-16-le')
            orig_header = len(en)           # 码元数
            region = align4(len(orig_payload))
            # 16 位条目：补丁不改槽位，units 仍为原码元数
            unit_ok = lambda u, txt, en=en, zh=zh: (  # noqa: B023
                u == len(en) and u >= len(zh) and txt == zh)
        # 扫描补丁态条目：中文 UTF-16LE 前缀命中 + 头部为 16 位
        offs = []
        needle = zh.encode('utf-16-le')
        i = 0
        while True:
            i = kdata.find(needle, i)
            if i < 0:
                break
            # 命中点前 8 字节才是表项头部；落在文件头 8 字节内的匹配不是表项，跳过
            if i < 8:
                i += 1
                continue
            hdr = struct.unpack_from('<I', kdata, i - 8)[0]
            if hdr >> 31 == 0:
                units = hdr & 0x7FFFFFFF
                try:
                    txt = bytes(kdata[i:i + units * 2]).decode('utf-16-le').rstrip(' ')
                except UnicodeDecodeError:
                    txt = None
                if txt is not None and unit_ok(units, txt):
                    offs.append(i)
            i += 1
        if offs:
            log_k[en] = {
                'offset': offs[0],
                'orig_header': orig_header,
                'orig_payload_hex': (orig_payload + b'\x00' * (region - len(orig_payload))).hex(),
            }
    if not kpath:
        print('  [跳过] 内核不存在，不产出 kernel-patch-log')
    else:
        print('  重建 %d 条（译文表 %d 条）' % (len(log_k), len(table)))
        miss_k = [en for en in table if en not in log_k]
        leak = []
        for en in miss_k:
            zh_m = table[en]
            if kdata.find(zh_m.encode('utf-16-le')) >= 0:
                leak.append(en)
        if miss_k:
            print('  未命中 %d 条（可能属其他内核版本或槽位溢出未打上）' % len(miss_k))
        if leak:
            print('  [警告] 其中 %d 条内核中存在中文却未入日志（需人工核查）：%s'
                  % (len(leak), [x[:40] for x in leak[:3]]))
        else:
            print('  [安全] 未命中条目在内核中均无对应中文（补丁时即未生效，还原后无残留）')
        w(os.path.join(BAK, 'kernel-patch-log.json'), log_k)

    # ---------- 4. kernel-source-patch-log.json ----------
    print('\n[4] kernel-source-patch-log.json（UTF-8 字面量偏移）')
    if not kpath:
        print('  [跳过] 内核不存在，不产出 kernel-source-patch-log')
    else:
        tbl_src = zhstore.get(zhstore.KERNEL_SOURCE)
        log_ks = {}
        for en, info in tbl_src.items():
            zh = info['zh'] if isinstance(info, dict) else info
            nb = en.encode('latin-1', 'replace')
            b = zh.encode('utf-8')
            if len(b) > len(nb):
                continue
            padded = b + b' ' * (len(nb) - len(b))
            offs = []
            i = 0
            while True:
                i = kdata.find(padded, i)
                if i < 0:
                    break
                offs.append(i)
                i += 1
            if offs:
                log_ks[en] = {'offsets': offs, 'zh': zh}
        print('  重建 %d 条（词表 %d 条）' % (len(log_ks), len(tbl_src)))
        w(os.path.join(BAK, 'kernel-source-patch-log.json'), log_ks)

    # ---------- 5. asar-source-patch-log.json ----------
    print('\n[5] asar-source-patch-log.json（含 integrity 双向哈希）')
    asar_path = os.path.join(RES, 'app.asar')
    exe_path = os.path.join(PKG, 'app', 'claude.exe')
    data = bytearray(open(asar_path, 'rb').read())
    if len(data) < 16:
        raise ValueError('app.asar 过小（%d 字节），不是合法的 asar 文件' % len(data))
    js_len = struct.unpack('<I', bytes(data[12:16]))[0]
    if js_len <= 0 or 16 + js_len > len(data):
        raise ValueError('app.asar header 长度异常（js_len=%d，文件 %d 字节）'
                         % (js_len, len(data)))
    hdr_raw = bytearray(data[16:16 + js_len])
    j = json.loads(bytes(hdr_raw).decode('utf-8'))
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
                files.append({'path': fp, 'start': base + int(e.get('offset', 0)),
                              'size': e.get('size', 0), 'integrity': e.get('integrity')})
    walk(j.get('files', {}), '')

    tbl_asar = zhstore.get(zhstore.ASAR_SOURCE)
    entries = {}
    touched = set()
    for en, info in tbl_asar.items():
        zh = info['zh'] if isinstance(info, dict) else info
        nb = en.encode('latin-1', 'replace')
        b = zh.encode('utf-8')
        if len(b) > len(nb):
            continue
        padded = b + b' ' * (len(nb) - len(b))
        offs = []
        i = 0
        while True:
            i = data.find(padded, i)
            if i < 0:
                break
            for f in files:
                if f['start'] <= i < f['start'] + f['size'] and f['path'].endswith('.js'):
                    offs.append(i)
                    touched.add(f['path'])
                    break
            i += 1
        if offs:
            entries[en] = {'offsets': offs, 'zh': zh}
    print('  重建词条 %d 条 / 涉及文件 %d 个' % (len(entries), len(touched)))

    # integrity：旧值 = 还原内容后重算；新值 = 当前内容
    spec2 = importlib.util.spec_from_file_location(
        'tas', os.path.join(ROOT, 'scripts', 'translate-asar-source.py'))
    tas = importlib.util.module_from_spec(spec2)
    sys.argv = [sys.argv[0]]
    spec2.loader.exec_module(tas)

    integ = {'files': {}, 'exe': None}
    hdr_cur = bytes(hdr_raw)
    hdr_old = hdr_cur
    for f in files:
        if f['path'] not in touched or not f.get('integrity'):
            continue
        itg = f['integrity']
        bs = itg.get('blockSize', 4194304)
        cur_c = bytes(data[f['start']:f['start'] + f['size']])
        new_hash, new_blocks = sha(cur_c), [sha(cur_c[i:i + bs]) for i in range(0, len(cur_c), bs)]
        # 还原内容（等长替换回英文 + 空格）
        old_c = bytearray(cur_c)
        for en, info in tbl_asar.items():
            zh = info['zh'] if isinstance(info, dict) else info
            nb = en.encode('latin-1', 'replace')
            b = zh.encode('utf-8')
            if len(b) > len(nb):
                continue
            padded = b + b' ' * (len(nb) - len(b))
            i = old_c.find(padded)
            while i >= 0:
                old_c[i:i + len(nb)] = nb
                i = old_c.find(padded, i + 1)
        old_c = bytes(old_c)
        old_hash, old_blocks = sha(old_c), [sha(old_c[i:i + bs]) for i in range(0, len(old_c), bs)]
        integ['files'][f['path']] = {'hash': [old_hash, new_hash],
                                     'blocks': [old_blocks, new_blocks]}
        # 原始 header = 当前 header 中把 hash/blocks 换回旧值（new -> old）
        hdr_old = tas._replace_file_integrity(hdr_old, new_hash, old_hash,
                                              new_blocks, old_blocks)
    # exe 记录：offset + [旧(原始 header 哈希), 新(当前 header 哈希)]
    exeb = open(exe_path, 'rb').read()
    m = re.search(rb'\[\{"file":"resources\\\\app\.asar","alg":"SHA256","value":"([0-9a-f]{64})"\}\]', exeb)
    assert m, 'exe 中未找到 asar integrity 记录'
    integ['exe'] = {'offset': m.start(1),
                    'old': sha(hdr_old),
                    'new': sha(hdr_cur)}
    print('  integrity：文件 %d 个 | exe header 哈希 旧=%s... 新=%s...'
          % (len(integ['files']), integ['exe']['old'][:16], integ['exe']['new'][:16]))
    log_asar = {'entries': entries, 'integrity': integ}
    w(os.path.join(BAK, 'asar-source-patch-log.json'), log_asar)

    print('\n' + '=' * 64)
    print('  重建完成：%s' % BAK)
    return 0


if __name__ == '__main__':
    sys.exit(main())
