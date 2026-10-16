# -*- coding: utf-8 -*-
r"""
Claude 汉化「统一词条仓库」（Translation Store）—— 单一持久真相源。

============================== 为什么要这个模块 ==============================
历史上词条散落在 5 处互不相通的地方，翻译产出没有回流通道，导致
「翻译成功但重启/重装后丢失、需要重新翻译」：

    tools/manual_extra.py        KEY_EXTRA / VAL_EXTRA   （人工 Edit）
    tools/shell_manual.py        SHELL_MANUAL            （人工 Edit）
    scripts/translate-kernel.py        TRANSLATIONS      （硬编码 139 条）
    scripts/translate-kernel-source.py SOURCE_TRANSLATIONS（硬编码 35 条）
    scripts/translate-skills.py        SKILL_ZH          （硬编码 11 条）

本模块把上述全部收敛到一个 JSON 仓库，并提供「读 → 翻译 → 回写」闭环：
任何一次成功翻译都必须 upsert 回仓库，安装时再从仓库重建产物。

============================== 命名空间与命名规则 ==============================
仓库按「命名空间（namespace）」分层，每层的**键的含义不同**，不可混用：

  fe-key        键 = formatjs 生成的短哈希 id（如 `OnsnuZtVJO`）
                来源 = app\resources\ion-dist\i18n\en-US.json 的 key
                约束 = 含 XML 富文本标签（<aupLink>/<learnMoreLink>…）时必须原样保留；
                       含 ICU 复数/选择格式（{n, plural, one {…} other {…}}）必须保留占位名

  fe-val        键 = 归一化后的英文原文全串（norm(): 弯引号→直引号 + strip）
                用途 = 同值多 key 批量覆盖（一个英文串常对应多个 id）

  shell-key     键 = shell 层 app\resources\en-US.json 的 key
                     （部分与 FE 同源，部分是原生 key 如 `keepAwakeEnabledTitle`）

  shell-val     键 = 归一化后的英文原文（同上 norm 规则）

  kernel-table  键 = 英文原文全串（内核字符串表条目，无 i18n id）

  kernel-source 键 = **ASCII 转义形态**的英文原文（如 `See where this session\\u2019s
                     tokens went`），必须与 claude.exe 中的字节完全一致
                     —— 非 ASCII 一律写成 \\uXXXX，否则搜不到

  skill         键 = 技能名（如 `pdf` / `setup-claude`），值 = 中文描述

============================== 合并去重规则 ==============================
每个条目带 origin（来源），优先级由高到低：

    manual  >  uia  >  kernel-scan  >  auto  >  seed

upsert 时：
  - 条目不存在                       -> 写入（added）
  - 已存在且值相同                   -> 不动（unchanged）
  - 已存在、新 origin 优先级更高     -> 更新（updated）
  - 已存在、新 origin 优先级**相同** -> 更新（updated），视为同一来源的
                                        人工演进；旧值保留在 prev 字段以便回滚
  - 已存在、新 origin 优先级更低     -> **保留旧值**（kept），并记 conflict
                                        （避免低可信来源覆盖人工修改过的内容）

force=True 可强制覆盖（仅限明确知道自己在做什么时使用）。

============================== 持久化与回滚 ==============================
  * 原子写：先写同目录 .tmp，再 os.replace() 原子替换 —— 不会出现半截文件
  * 写前备份：每次保存到 backup/zh-store-<UTC时间戳>.json，保留最近 MAX_BACKUPS 份
  * 损坏自愈：加载失败（JSON 损坏/编码错误）时自动回退到最新可用备份
  * 校验：写入后立即重新读一遍，条目数不符视为失败并回滚到备份

用法（作为库）：
    import zhstore
    tbl = zhstore.get('fe-key')              # -> {id: zh}
    n   = zhstore.upsert('fe-key', 'ABC', '中文')     # 单条
    st  = zhstore.upsert_many('fe-val', {'Hi':'你好'})  # 批量
    zhstore.save()                            # 落盘（原子写 + 备份）

用法（命令行）：
    python zhstore.py --stats
    python zhstore.py --get fe-key
    python zhstore.py --set fe-key 'ABC' '中文' [--origin manual]
    python zhstore.py --backups
    python zhstore.py --restore            # 从最新备份回滚
"""
import io
import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone

# ---------------- 命名空间 ----------------
FE_KEY = 'fe-key'
FE_VAL = 'fe-val'
SHELL_KEY = 'shell-key'
SHELL_VAL = 'shell-val'
KERNEL_TABLE = 'kernel-table'
KERNEL_SOURCE = 'kernel-source'
ASAR_SOURCE = 'asar-source'   # app.asar 内嵌技能描述（等长源码字面量替换）
SKILL = 'skill'

NAMESPACES = (FE_KEY, FE_VAL, SHELL_KEY, SHELL_VAL,
              KERNEL_TABLE, KERNEL_SOURCE, ASAR_SOURCE, SKILL)

# origin 优先级：数值越大越权威，越不会被低优先级覆盖
ORIGIN_RANK = {
    'seed': 0,          # 由 seed-store.py 从旧硬编码表导入
    'auto': 1,          # 构建器/脚本自动生成
    'kernel-scan': 2,   # 扫描内核二进制得到的译文
    'uia': 3,           # UI 自动化实测界面发现的译文
    'manual': 4,        # 人工编写或修改
}

# 仓库约 4.3 MB，每份备份同体积。20 份会让项目目录无谓膨胀到 80 MB+，
# 而备份仅用于「仓库损坏时回滚」，保留最近 5 份已足够（覆盖最近一次会话的多次写入）。
MAX_BACKUPS = 5


# ---------------- 路径解析 ----------------
def zh_home():
    """统一运行时根（v2.7）：所有运行时汉化文件位于 %USERPROFILE%\\.claude\\zh\\。"""
    return os.path.join(os.environ.get('USERPROFILE', ''), '.claude', 'zh')


def project_store():
    """项目仓库的规范位置（词条资产必须落在这里，而不是运行时副本目录）。

    解析顺序：
      1) 本模块位于 <项目>/scripts/ 下 -> <项目>/resources/translations/zh-store.json
      2) 本模块是 %LOCALAPPDATA%\\claude-zh-hans\\ 下的运行时副本
         -> 读取同目录 store-path.txt 里登记的项目仓库路径
      3) 都拿不到 -> None
    """
    here = os.path.dirname(os.path.abspath(__file__))
    parent = os.path.dirname(here)          # scripts/ -> 项目根
    if os.path.isdir(os.path.join(parent, 'resources')):
        return os.path.join(parent, 'resources', 'translations', 'zh-store.json')
    # 运行时副本：查登记表
    reg = os.path.join(zh_home(), 'store-path.txt')
    if os.path.isfile(reg):
        try:
            p = io.open(reg, encoding='utf-8').read().strip()
            if p and os.path.isdir(os.path.dirname(p)):
                return p
        except Exception:
            pass
    return None


def register_project_store(path=None):
    """在运行时目录登记项目仓库路径（安装脚本调用一次即可）。"""
    p = path or project_store()
    if not p:
        return None
    try:
        os.makedirs(zh_home(), exist_ok=True)
        io.open(os.path.join(zh_home(), 'store-path.txt'),
                'w', encoding='utf-8').write(p)
        return p
    except OSError:
        return None


def _default_path():
    """仓库文件位置。优先项目仓库（持久化资产），否则退回运行时目录。

    环境变量 ZHHANS_STORE 最高优先，便于调试/隔离测试。
    """
    env = os.environ.get('ZHHANS_STORE')
    if env:
        return env
    p = project_store()
    if p:
        return p
    return os.path.join(zh_home(), 'zh-store.json')


def store_path():
    return os.environ.get('ZHHANS_STORE') or _default_path()


def backup_dir():
    return os.path.join(os.path.dirname(store_path()), 'backup')


# ---------------- 归一化 ----------------
def norm(s):
    """值映射类命名空间的键归一化：弯引号 -> 直引号，去首尾空白。

    必须与 tools/build_additions.py 的 norm() 保持一致，否则按值匹配会失效。
    """
    if not isinstance(s, str):
        return s
    return (s.replace('\u2019', "'").replace('\u2018', "'")
             .replace('\u201c', '"').replace('\u201d', '"').strip())


def _now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


# ---------------- 内存状态 ----------------
_DB = None          # 整个仓库 dict
_LOADED_FROM = None  # 实际加载来源（用于损坏提示）


def _blank():
    return {
        'version': 2,
        'updated': _now(),
        'namespaces': {ns: {} for ns in NAMESPACES},
    }


def _normalize_inplace(db):
    """补全缺失的 schema 字段，容忍旧格式/半截数据。"""
    if not isinstance(db, dict):
        return _blank()
    db.setdefault('version', 2)
    db.setdefault('updated', _now())
    ns = db.setdefault('namespaces', {})
    if not isinstance(ns, dict):
        ns = {}
        db['namespaces'] = ns
    for n in NAMESPACES:
        v = ns.get(n)
        if not isinstance(v, dict):
            ns[n] = {}
            continue
        # 容忍「纯 {key: "中文"} 」的旧扁平格式：升级为带 meta 的条目
        for k, val in list(v.items()):
            if isinstance(val, str):
                v[k] = {'zh': val, 'origin': 'seed', 'updated': db['updated']}
            elif isinstance(val, dict):
                val.setdefault('origin', 'seed')
                val.setdefault('updated', db['updated'])
            else:
                v.pop(k, None)
    return db


def load(force=False):
    """加载仓库；损坏时自动回退到最新备份。"""
    global _DB, _LOADED_FROM
    if _DB is not None and not force:
        return _DB

    p = store_path()
    if os.path.isfile(p):
        try:
            db = json.load(io.open(p, encoding='utf-8'))
            _DB = _normalize_inplace(db)
            _LOADED_FROM = p
            return _DB
        except Exception as e:
            sys.stderr.write('[zhstore] 仓库损坏 (%s): %s\n' % (p, e))
            fallback = _restore_from_backup(p, verbose=True)
            if fallback is not None:
                _DB = _normalize_inplace(fallback)
                _LOADED_FROM = 'backup'
                sys.stderr.write('[zhstore] 已回退到最新可用备份\n')
                return _DB
    _DB = _blank()
    _LOADED_FROM = None
    return _DB


def _restore_from_backup(target, verbose=False):
    """把最新备份拷回 target；返回解析后的 dict（失败返回 None）。"""
    bd = backup_dir()
    if not os.path.isdir(bd):
        return None
    baks = sorted([f for f in os.listdir(bd)
                   if f.startswith('zh-store-') and f.endswith('.json')],
                  reverse=True)
    for name in baks:
        try:
            db = json.load(io.open(os.path.join(bd, name), encoding='utf-8'))
            shutil.copy2(os.path.join(bd, name), target)
            if verbose:
                sys.stderr.write('[zhstore] 使用备份: %s\n' % name)
            return db
        except Exception:
            continue
    return None


# ---------------- 读取 ----------------
def get(ns, default=None):
    """返回 {键: 中文} 的扁平映射（供翻译表直接消费）。"""
    db = load()
    bucket = db['namespaces'].get(ns) or {}
    return dict((k, v.get('zh', '')) for k, v in bucket.items() if v.get('zh'))


def get_meta(ns, key):
    db = load()
    return (db['namespaces'].get(ns) or {}).get(key)


def count(ns=None):
    db = load()
    if ns:
        return len(db['namespaces'].get(ns) or {})
    return dict((n, len(v)) for n, v in db['namespaces'].items())


# ---------------- 写入 ----------------
def upsert(ns, key, zh, en=None, origin='auto', force=False):
    """写入/合并单条。返回 'added' | 'updated' | 'kept' | 'unchanged'。

    kept = 仓库里已有更高或同优先级的译文，保留旧值（防止覆盖人工修改）。
    """
    if ns not in NAMESPACES:
        raise ValueError('未知命名空间: %s' % ns)
    if not isinstance(key, str) or not key:
        return 'unchanged'
    zh = (zh or '').strip()
    if not zh:
        return 'unchanged'

    db = load()
    bucket = db['namespaces'].setdefault(ns, {})
    cur = bucket.get(key)

    if cur is None:
        bucket[key] = {'zh': zh, 'origin': origin, 'updated': _now()}
        if en and en != key:
            bucket[key]['en'] = en
        return 'added'

    if cur.get('zh') == zh:
        if en and en != key and not cur.get('en'):
            cur['en'] = en
            cur['updated'] = _now()
        return 'unchanged'

    old_rank = ORIGIN_RANK.get(cur.get('origin', 'seed'), 0)
    new_rank = ORIGIN_RANK.get(origin, 0)
    if not force and new_rank < old_rank:
        # 低可信来源不能覆盖高可信译文：保留旧值，记录冲突供人工审阅
        cur.setdefault('conflict', [])
        if isinstance(cur['conflict'], list) and len(cur['conflict']) < 5:
            cur['conflict'].append({'zh': zh, 'origin': origin, 'at': _now()})
        return 'kept'
    # 同优先级：视为同一来源的人工演进，取最新，旧值留档便于回滚

    bucket[key] = {'zh': zh, 'origin': origin, 'updated': _now()}
    if en and en != key:
        bucket[key]['en'] = en
    prev = cur.get('zh')
    if prev:
        bucket[key]['prev'] = prev
    return 'updated'


def upsert_many(ns, mapping, origin='auto', force=False, en_of=None):
    """批量写入。mapping = {键: 中文}；en_of(可选) = 键 -> 英文原文。

    返回 {'added': n, 'updated': n, 'kept': n, 'unchanged': n}
    """
    stat = {'added': 0, 'updated': 0, 'kept': 0, 'unchanged': 0}
    if not mapping:
        return stat
    for k, v in mapping.items():
        en = en_of.get(k) if en_of else None
        stat[upsert(ns, k, v, en=en, origin=origin, force=force)] += 1
    return stat


# ---------------- 落盘 ----------------
def _rotate_backups():
    bd = backup_dir()
    if not os.path.isdir(bd):
        return
    baks = sorted([f for f in os.listdir(bd)
                   if f.startswith('zh-store-') and f.endswith('.json')],
                  reverse=True)
    for name in baks[MAX_BACKUPS:]:
        try:
            os.remove(os.path.join(bd, name))
        except OSError:
            pass


def save(silent=False):
    """原子落盘。返回 (ok: bool, 备份路径 or None, 错误信息 or None)。"""
    db = load()
    db['updated'] = _now()
    p = store_path()
    tmp = p + '.tmp'
    bak_path = None
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
    except OSError as e:
        return False, None, '无法创建仓库目录: %s' % e

    # 1) 写前备份（仅在仓库已存在时）
    if os.path.isfile(p):
        try:
            os.makedirs(backup_dir(), exist_ok=True)
            bak_path = os.path.join(
                backup_dir(),
                'zh-store-%s.json' % datetime.now(timezone.utc)
                .strftime('%Y%m%dT%H%M%SZ'))
            shutil.copy2(p, bak_path)
            _rotate_backups()
        except OSError as e:
            sys.stderr.write('[zhstore] 备份失败(继续写入): %s\n' % e)

    # 2) 原子写
    try:
        text = json.dumps(db, ensure_ascii=False, indent=1, sort_keys=True)
        with io.open(tmp, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)
    except Exception as e:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass
        return False, bak_path, '写入失败: %s' % e

    # 3) 写后校验：重新读一遍，条目数必须一致
    try:
        again = json.load(io.open(p, encoding='utf-8'))
        before = dict((n, len(v)) for n, v in db['namespaces'].items())
        after = dict((n, len(v or {}))
                     for n, v in (again.get('namespaces') or {}).items())
        if any(before.get(n, 0) != after.get(n, 0) for n in NAMESPACES):
            raise IOError('写后校验不一致: %s != %s' % (before, after))
    except Exception as e:
        # 校验失败：回滚到备份
        if bak_path and os.path.isfile(bak_path):
            try:
                shutil.copy2(bak_path, p)
            except OSError:
                pass
        return False, bak_path, '校验失败已回滚: %s' % e

    if not silent:
        print('[zhstore] 已保存 %s | %s'
              % (p, ', '.join('%s=%d' % (n, count(n)) for n in NAMESPACES)))
    return True, bak_path, None


# ---------------- 诊断 ----------------
def stats():
    db = load()
    lines = []
    total = 0
    by_origin = {}
    conflicts = 0
    for ns in NAMESPACES:
        bucket = db['namespaces'].get(ns) or {}
        total += len(bucket)
        for v in bucket.values():
            by_origin[v.get('origin', 'seed')] = \
                by_origin.get(v.get('origin', 'seed'), 0) + 1
            if v.get('conflict'):
                conflicts += 1
        lines.append('  %-14s %5d 条' % (ns, len(bucket)))
    lines.append('  %-14s %5d 条' % ('合计', total))
    lines.append('  来源分布: ' + ', '.join(
        '%s=%d' % kv for kv in sorted(by_origin.items())))
    lines.append('  冲突待审: %d 条（仓库保留了高优先级旧值）' % conflicts)
    lines.append('  仓库文件: %s' % store_path())
    lines.append('  加载来源: %s' % (_LOADED_FROM or '(新建)'))
    return '\n'.join(lines)


# ---------------- CLI ----------------
def _cli():
    a = sys.argv[1:]
    if not a or '--stats' in a:
        print(stats())
        return 0
    if '--get' in a:
        ns = a[a.index('--get') + 1]
        d = get(ns)
        json.dump(d, io.open(store_path() + '.export-%s.json' % ns,
                             'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1, sort_keys=True)
        print('%s: %d 条 -> %s.export-%s.json' % (ns, len(d), store_path(), ns))
        return 0
    if '--set' in a:
        i = a.index('--set')
        ns, key, zh = a[i + 1], a[i + 2], a[i + 3]
        origin = 'manual'
        if '--origin' in a:
            origin = a[a.index('--origin') + 1]
        r = upsert(ns, key, zh, origin=origin, force=True)
        ok, bak, err = save()
        print('%s [%s] %s' % (ns, r, key))
        if not ok:
            sys.stderr.write('保存失败: %s\n' % err)
            return 1
        return 0
    if '--register' in a:
        # 在运行时目录登记项目仓库路径（安装脚本调用）
        p = register_project_store()
        if p:
            print('已登记项目仓库: %s' % p)
            print('运行时副本将写回该仓库（词条资产不随卸载丢失）')
            return 0
        sys.stderr.write('登记失败：未找到项目 resources 目录\n')
        return 1
    if '--backups' in a:
        bd = backup_dir()
        if not os.path.isdir(bd):
            print('(无备份)')
            return 0
        for f in sorted(os.listdir(bd), reverse=True):
            print('  %s  %d B' % (f, os.path.getsize(os.path.join(bd, f))))
        return 0
    if '--restore' in a:
        got = _restore_from_backup(store_path(), verbose=True)
        print('回滚: %s' % ('成功' if got else '无可用备份'))
        return 0 if got else 1
    print(__doc__[-1600:])
    return 0


if __name__ == '__main__':
    sys.exit(_cli())
