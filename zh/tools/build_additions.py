# -*- coding: utf-8 -*-
# 构建增补词表：
#  out/custom-keys-zh.json   渲染层(FE) key->zh 增补（优先于 ldk）
#  out/shell-overlay-zh.json shell 层 key->zh 增补（合并进 resources/zh-Hans.json）
#
# 词条持久化（v2.5）：本构建器以**统一词条仓库**（scripts/zhstore.py）为第一来源，
# manual_extra.py / shell_manual.py 等人工词表作为「最新人工输入」覆盖之，
# 构建结束前再把人工词条回写仓库，使仓库始终是唯一真相源。
import json, io, sys, os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
# 包内相对定位：本脚本位于 <包根>/tools/，词表资源在 <包根>/resources/
D = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'resources')
# 资源目录解析优先级：--res 参数（安装脚本传入）> 自动探测 WindowsApps 最新版本。
# 不得写死版本号——跨机器/跨版本部署会装错目录。
def _detect_res():
    base = r'C:\Program Files\WindowsApps'
    if not os.path.isdir(base):
        return None
    best = None
    for d in os.listdir(base):
        if not d.startswith('Claude_'):
            continue
        p = os.path.join(base, d, 'app', 'resources')
        if os.path.isfile(os.path.join(p, 'ion-dist', 'i18n', 'en-US.json')):
            m = os.path.getmtime(os.path.join(p, 'ion-dist', 'i18n', 'en-US.json'))
            if best is None or m > best[0]:
                best = (m, p)
    return best[1] if best else None
R = None
if '--res' in sys.argv:
    _ri = sys.argv.index('--res')
    if _ri + 1 >= len(sys.argv):
        raise SystemExit('缺少参数：--res 需要指定 app\\resources 目录路径')
    R = sys.argv[_ri + 1]
else:
    R = _detect_res()
if not R:
    raise SystemExit('未定位到 Claude 资源目录：请以 --res <app\\resources 路径> 运行，或先安装 Claude')
# 官方 shell 词表备份优先（保真），否则读当前部署副本
_bak = None
if os.path.isdir(os.path.join(os.environ.get('USERPROFILE', ''), '.claude', 'zh', 'backup')):
    _bd = os.path.join(os.environ.get('USERPROFILE', ''), '.claude', 'zh', 'backup')
    for v in sorted(os.listdir(_bd), reverse=True):
        c = os.path.join(_bd, v, 'shell-zh-Hans.json')
        if os.path.isfile(c):
            _bak = c
            break
# 构建依赖（manual_extra / audit_matched / shell_fe_ids / shell_manual）一律从脚本
# 所在目录读取，不再依赖临时目录——临时目录会被系统清理，导致构建失败或误用旧词表。
T = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS = os.path.join(os.path.dirname(T), 'scripts')
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)
import zhstore

FE  = json.load(open(R + r'\ion-dist\i18n\en-US.json', encoding='utf-8'))
SE  = json.load(open(R + r'\en-US.json', encoding='utf-8'))
import os as _os
SZ  = json.load(open(_bak if (_bak and _os.path.exists(_bak)) else R + r'\zh-Hans.json', encoding='utf-8'))
LDK = json.load(open(D + r'\frontend-zh-CN.json', encoding='utf-8'))
LDE = json.load(open(D + r'\desktop-zh-CN.json', encoding='utf-8'))
OV  = json.load(open(D + r'\custom-overlay-zh.json', encoding='utf-8'))
matched = json.load(open(T + r'\audit_matched.json', encoding='utf-8'))
shell_fe_ids = json.load(open(T + r'\shell_fe_ids.json', encoding='utf-8'))

def norm(s):
    return s.replace('’', "'").replace('‘', "'").replace('“', '"').replace('”', '"').strip()

# ---------- 1. 手工 key->zh ----------
# 1a. 词条仓库优先（唯一真相源：含界面实测/内核扫描/人工改写的全部词条）
custom = zhstore.get(zhstore.FE_KEY)
n_store_key = len(custom)
# 1b. 截图逐项核对产物
for en, info in matched.items():
    if info['src'] == 'FE':
        for k in info['keys']:
            custom[k] = info['zh']
# 1c. 模糊定位修正（实际源串与截图略异）
from manual_fuzzy import FUZZY_FIX
custom.update(FUZZY_FIX)
# 遗漏词条补充（新版 2.37337 核对：含 XML 富文本标签的 key 级翻译）
sys.path.insert(0, T)
from manual_extra import KEY_EXTRA, VAL_EXTRA
custom.update(KEY_EXTRA)

# ---------- 2. 全局 英文值->中文 映射（用于同值多 key 复用与 shell 按值翻译） ----------
valmap = {}
def vput(en, zh):
    if en and zh and en != zh:
        valmap.setdefault(norm(en), zh)
# 我的候选（最高优先，先放）
for en, info in matched.items(): vput(en, info['zh'])
vput('Web searches', '网页搜索'); vput('Use 1M wherever it’s available', '可用时始终使用 1M')
vput('Skip WebFetch domain check', '跳过 WebFetch 域检查')
# 词条仓库的值映射（界面实测/内核扫描回写的长描述，次高优先）
for en, zh in zhstore.get(zhstore.FE_VAL).items(): vput(en, zh)
# 官方 shell 词条
for k, v in SE.items():
    z = SZ.get(k)
    if z and z != v: vput(v, z)
# ldk 前端词条（按 key 对齐 FE 英文值）
for k, z in LDK.items():
    en = FE.get(k)
    if en and z != en: vput(en, z)
# ldk desktop 词条（按 key 对齐 shell 英文值）
for k, z in LDE.items():
    en = SE.get(k)
    if en and z != en: vput(en, z)
# 现有 overlay
for en, zh in OV.items(): vput(en, zh)
# manual_extra 值映射、shell 权限对话框手工翻译 = **最新人工输入**，
# 用直接赋值覆盖同名条目（放在派生源之后），保证人工词表的修改一定生效，
# 并在构建末尾同步回词条仓库。
for en, zh in VAL_EXTRA.items():
    if en and zh: valmap[norm(en)] = zh
sys.path.insert(0, T)
from shell_manual import SHELL_MANUAL
for en, zh in SHELL_MANUAL.items():
    if en and zh: valmap[norm(en)] = zh
# 仓库里其余值映射（界面实测/内核扫描回写）补齐派生源之外的条目
for en, zh in zhstore.get(zhstore.SHELL_VAL).items(): vput(en, zh)
print('全局值映射:', len(valmap), '（仓库 fe-val %d 条）'
      % zhstore.count(zhstore.FE_VAL))

# ---------- 3. FE 增补：ldk 未覆盖的 key，用 custom 或值映射补齐 ----------
fe_add = dict(custom)
n_val = 0
for k, en in FE.items():
    if k in fe_add: continue
    z = LDK.get(k)
    if z and z != en: continue          # ldk 已覆盖
    zh = valmap.get(norm(en)) if isinstance(en, str) else None
    if zh:
        fe_add[k] = zh; n_val += 1
print('FE 增补: 手工 %d + 值映射 %d = %d' % (len(custom), n_val, len(fe_add)))

# ---------- 4. shell 增补 ----------
shell_add = {}
# 4a. asar 引用的 FE id（managed-config 窗口等）
sa = sb = sc = 0
for k, en in shell_fe_ids.items():
    zh = custom.get(k)
    if zh: shell_add[k] = zh; sa += 1; continue
    z = LDK.get(k)
    if z and z != en: shell_add[k] = z; sb += 1; continue
    zh = valmap.get(norm(en)) if isinstance(en, str) else None
    if zh: shell_add[k] = zh; sc += 1
print('shell(FE id): 手工 %d + ldk %d + 值映射 %d' % (sa, sb, sc))
# 4b. shell 原生缺失 key
da = db = 0
for k, en in SE.items():
    z = SZ.get(k)
    if z is not None and z != en: continue   # 官方已翻译
    zh = LDE.get(k)
    if zh and zh != en: shell_add[k] = zh; da += 1; continue
    zh = valmap.get(norm(en)) if isinstance(en, str) else None
    if zh: shell_add[k] = zh; db += 1
print('shell(原生): ldk-desktop %d + 值映射 %d' % (da, db))
# 4c. 标题栏等 shell 引用的 FE id 必含项
for k in ['+MH0VdRCHz', 'h2vipunVVd', 'WTrOy36sdu']:
    if k not in shell_add and k in custom: shell_add[k] = custom[k]

# ---------- 4d. dynamic 词表 overlay（仓库优先于 ldk） ----------
# dynamic\en-US.json 里的 key 不在主词表中，主 custom-keys-zh.json 对它们无效；
# 历史上安装直接用 ldk 的 dynamic-zh-CN.json，导致仓库里 27 条人工修订被旧值
# 覆盖、3 条 ldk 假覆盖（值仍是英文）照常部署。此处从仓库筛出 dynamic key
# 生成 overlay，安装时叠加在 ldk 之上（overlay 优先），仓库恢复唯一真相源。
DYN_EN = json.load(open(R + r'\ion-dist\i18n\dynamic\en-US.json', encoding='utf-8'))
dyn_add = {}
for k, en in DYN_EN.items():
    zh = custom.get(k)
    if zh and (not isinstance(en, str) or zh != en):
        dyn_add[k] = zh
print('dynamic overlay: 仓库命中 %d / %d（叠加于 ldk 之上）' % (len(dyn_add), len(DYN_EN)))

# ---------- 5. 输出 ----------
os.makedirs(T + r'\out', exist_ok=True)
json.dump(fe_add, open(D + r'\custom-keys-zh.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1, sort_keys=True)
json.dump(shell_add, open(D + r'\shell-overlay-zh.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1, sort_keys=True)
json.dump(dyn_add, open(D + r'\dynamic-overlay-zh.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1, sort_keys=True)
print()
print('写出 custom-keys-zh.json :', len(fe_add))
print('写出 shell-overlay-zh.json:', len(shell_add))
print('写出 dynamic-overlay-zh.json:', len(dyn_add))

# ---------- 5b. 回写词条仓库（使仓库成为唯一真相源） ----------
# 只回写「非派生的原始人工词条」：派生的值映射结果不入仓库，
# 否则会把确定性可重算的内容固化进仓库，造成膨胀与来源失真。
try:
    st1 = zhstore.upsert_many(zhstore.FE_KEY, custom, origin='manual')
    st2 = zhstore.upsert_many(zhstore.FE_VAL, VAL_EXTRA, origin='manual')
    st3 = zhstore.upsert_many(zhstore.SHELL_VAL, SHELL_MANUAL, origin='manual')
    ok, bak, err = zhstore.save(silent=True)
    if ok:
        print('词条仓库回写: fe-key +%d/~%d, fe-val +%d/~%d, shell-val +%d/~%d'
              % (st1['added'], st1['updated'], st2['added'], st2['updated'],
                 st3['added'], st3['updated']))
    else:
        sys.stderr.write('[警告] 词条仓库保存失败: %s\n' % err)
        sys.stderr.write('       仓库未更新，但词表已正常产出（不影响本次安装）\n')
except Exception as e:
    sys.stderr.write('[警告] 词条仓库回写异常: %s\n' % e)

# ---------- 6. 统计 shell 剩余未覆盖（供清单） ----------
remain = []
for k, en in SE.items():
    z = SZ.get(k)
    if (z is None or z == en) and k not in shell_add:
        if isinstance(en, str) and len(en) > 1 and any(c.isalpha() for c in en) and not en.startswith('{'):
            remain.append(en)
print('shell 仍未覆盖（去占位/单字符后）:', len(remain))
json.dump(sorted(set(remain)), open(T + r'\shell_remaining.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
for s in sorted(set(remain))[:25]: print('   -', s[:90])
