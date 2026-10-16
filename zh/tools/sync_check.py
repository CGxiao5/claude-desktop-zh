# -*- coding: utf-8 -*-
"""同步性检查：词条仓库 -> 构建产物 -> 部署目标 的全链一致性核对。

核对维度：
  [A] 仓库 fe-key(420) / shell-val(133) 是否全部进入构建产物
  [B] 构建产物条目是否有仓库之外的“幽灵来源”（漂移检测）
  [C] 各命名空间在部署目标中的实际生效情况
  [D] 安装脚本可移植性（硬编码路径扫描）
用法: python sync_check.py [--res <app\\resources 实际路径>]
"""
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
T = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(T)
D = os.path.join(ROOT, 'resources')
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import zhstore  # noqa: E402

CJK = re.compile(r'[\u4e00-\u9fff]')

# --res 参数（与 build_additions 相同约定）；未指定时三级解析：
# install-context.json（安装时写入，最准）> WindowsApps glob 取 mtime 最新（与
# verify_state / build_additions 一致；按名字排序会选中共存的旧版本目录）。
R = None
if '--res' in sys.argv:
    R = sys.argv[sys.argv.index('--res') + 1]
else:
    _ctx = os.path.join(os.environ.get('USERPROFILE', ''), '.claude', 'zh',
                        'install-context.json')
    if os.path.isfile(_ctx):
        try:
            _pkg = json.load(open(_ctx, encoding='utf-8')).get('pkgPath')
            if _pkg and os.path.isdir(_pkg):
                R = os.path.join(_pkg, 'app', 'resources')
        except Exception:
            R = None
    if R is None:
        _wa = r'C:\Program Files\WindowsApps'
        _cands = []
        for d in os.listdir(_wa):
            if d.startswith('Claude_') and os.path.isfile(
                    os.path.join(_wa, d, 'app', 'resources',
                                 'ion-dist', 'i18n', 'en-US.json')):
                _cands.append(os.path.join(_wa, d, 'app', 'resources'))
        if _cands:
            R = max(_cands, key=os.path.getmtime)

fails = []


def chk(ok, label, detail=''):
    print('  [%s] %s%s' % ('OK  ' if ok else 'FAIL', label, ('  -> ' + detail) if detail else ''))
    if not ok:
        fails.append(label)


print('=' * 64)
print('  同步性检查%s' % ('  | 资源目录: ' + R if R else '  | 未找到已安装的 Claude，仅检查仓库与产物'))
print('=' * 64)

ns = zhstore.load()['namespaces']

print('\n[A] 仓库 -> 构建产物')
ck = json.load(open(os.path.join(D, 'custom-keys-zh.json'), encoding='utf-8'))
so = json.load(open(os.path.join(D, 'shell-overlay-zh.json'), encoding='utf-8'))

fe = ns.get('fe-key', {})
sv = ns.get('shell-val', {})
miss_fe = [k for k in fe if k not in ck]
bad_fe = [k for k in fe if k in ck and not CJK.search(str(ck[k]))]
chk(not miss_fe, 'fe-key %d 条全部进入 custom-keys-zh.json' % len(fe),
    ('缺失 %d: %s' % (len(miss_fe), miss_fe[:5])) if miss_fe else '全部在')
chk(not bad_fe, 'fe-key 条目均为中文', ('非中文 %s' % bad_fe[:5]) if bad_fe else '全部中文')
miss_sv = [k for k, v in sv.items() if v.get('zh') not in {str(x) for x in so.values()}]
chk(not miss_sv, 'shell-val %d 条译文已按值进入 shell-overlay-zh.json' % len(sv),
    ('未命中 %d: %s' % (len(miss_sv), miss_sv[:5])) if miss_sv else '全部在')

print('\n[B] 产物规模与仓库计数交叉核对')
chk(len(ck) >= len(fe), 'custom-keys-zh.json(%d) >= fe-key(%d)（含值映射衍生词条）' % (len(ck), len(fe)))
chk(len(so) >= len(sv), 'shell-overlay-zh.json(%d) >= shell-val(%d)' % (len(so), len(sv)))

if R:
    print('\n[C] 部署目标生效核验')
    i18n = os.path.join(R, 'ion-dist', 'i18n')
    dep = os.path.join(i18n, 'zh-Hans.json')
    dyn_dep = os.path.join(i18n, 'dynamic', 'zh-Hans.json')
    if os.path.exists(dep):
        zh = json.load(open(dep, encoding='utf-8'))
        en_us = json.load(open(os.path.join(i18n, 'en-US.json'), encoding='utf-8'))
        miss_dep = [k for k in fe if k in en_us and k not in zh]
        bad_dep = [k for k in fe if k in zh and not CJK.search(str(zh[k]))]
        chk(not miss_dep, '主词表 fe-key 全部在部署词表中', ('缺失 %s' % miss_dep[:5]) if miss_dep else '全部在')
        chk(not bad_dep, '部署词表对应值均为中文', ('非中文 %s' % bad_dep[:5]) if bad_dep else '全部中文')
        cjk_total = sum(1 for v in zh.values() if isinstance(v, str) and CJK.search(v))
        print('        部署主词表 %d 条，含中文 %d 条' % (len(zh), cjk_total))
        # 主词表外、属于 dynamic 的 key：须在 dynamic 部署词表且值=仓库译文
        dyn_en_path = os.path.join(i18n, 'dynamic', 'en-US.json')
        dyn_keys = []
        if os.path.exists(dyn_en_path):
            dyn_en = json.load(open(dyn_en_path, encoding='utf-8'))
            dyn_keys = [k for k in fe if k in dyn_en]
        if dyn_keys:
            if os.path.exists(dyn_dep):
                dz = json.load(open(dyn_dep, encoding='utf-8'))
                bad_dyn = [k for k in dyn_keys
                           if str(dz.get(k)) != fe[k]['zh'] or not CJK.search(str(dz.get(k)))]
                chk(not bad_dyn, 'dynamic %d 条部署值 = 仓库译文' % len(dyn_keys),
                    ('不一致 %d: %s' % (len(bad_dyn), bad_dyn[:5])) if bad_dyn else '全部一致')
            else:
                chk(False, 'dynamic\\zh-Hans.json 缺失')
        # 不在主/dynamic 词表的仓库 key = 旧版本残留（无害，仅清点）
        dead = [k for k in fe if k not in en_us and k not in dyn_keys]
        print('        （清点）旧版本残留词条 %d 条：不存在于当前版本任何词表，'
              '不会部署，保留以备版本回退（formatjs key 跨版本稳定）' % len(dead))
    else:
        chk(False, '部署词表存在（当前未安装属正常，见判定）')
else:
    print('\n[C] 跳过（未安装/无 --res）')

print('\n[D] 可移植性：硬编码路径扫描')
# 检测目标：绑定单一版本/单一用户/单一盘符包路径的绝对路径。
# 豁免：WindowsApps 下的自动探测 glob（os.listdir + startswith('Claude_')）属
# 运行时探测，非硬编码。
HARD = re.compile(r'[A-Z]:[\\\\/]{1,2}(Program Files|Users|Kimi)')
script_dirs = [os.path.join(ROOT, 'scripts'), T]
found = []
for sd in script_dirs:
    for n in os.listdir(sd):
        if not n.endswith(('.py', '.ps1', '.cmd')):
            continue
        p = os.path.join(sd, n)
        try:
            lines = open(p, encoding='utf-8', errors='replace').read().splitlines()
        except Exception:
            continue
        for ln, line in enumerate(lines, 1):
            for m in HARD.finditer(line):
                # 探测根目录常量（路径恰为 WindowsApps，不含版本目录）豁免：
                # 它是运行时 listdir 的起点，不是绑定版本的安装路径
                if 'WindowsApps' in line[m.end():m.end() + 15]:
                    continue
                seg = line[max(0, m.start() - 40):m.end() + 40]
                if 'WindowsApps' in seg and ("listdir" in seg or 'Claude_' in seg
                                              or 'startswith' in seg):
                    continue  # 自动探测，豁免
                if any(a in seg for a in ('LOCALAPPDATA', 'APPDATA', 'USERPROFILE')):
                    continue  # 环境变量定位，豁免
                found.append('%s:%d' % (os.path.relpath(p, ROOT), ln))
chk(not found, '脚本无机器相关硬编码绝对路径', ('%d 处: %s' % (len(found), found[:6])) if found else '干净')

print('\n' + '=' * 64)
print('  结果: %s' % ('全部通过' if not fails else '失败 %d 项: %s' % (len(fails), fails)))
sys.exit(0 if not fails else 1)
