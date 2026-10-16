# -*- coding: utf-8 -*-
r"""
词条仓库迁移器（seed）—— 把历史上散落在 5 处硬编码表里的词条灌入统一仓库。

迁移来源与命名空间的对应关系：

  tools/manual_extra.py  KEY_EXTRA        -> fe-key        (origin=manual)
  tools/manual_extra.py  VAL_EXTRA        -> fe-val        (origin=manual)
  tools/manual_fuzzy.py  FUZZY_FIX        -> fe-key        (origin=manual)
  tools/audit_matched.json (src=FE)       -> fe-key        (origin=manual)
  tools/shell_manual.py  SHELL_MANUAL     -> shell-val     (origin=manual)
  scripts/translate-kernel.py TRANSLATIONS       -> kernel-table  (origin=seed)
  scripts/translate-kernel-source.py SOURCE_TRANSLATIONS
                                                 -> kernel-source (origin=seed)
  scripts/translate-skills.py SKILL_ZH           -> skill         (origin=seed)

幂等 & 安全：
  * 重复运行安全。已存在且值相同 -> unchanged；
    已存在但仓库里是更高优先级来源（manual/uia/kernel-scan）-> 保留旧值（kept），
    绝不覆盖人工修改过的内容。
  * 只有仓库为空或来源同为 seed 时才会写入/更新。

用法：
    python seed-store.py              # 迁移并落盘
    python seed-store.py --dry-run    # 只统计，不写盘
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zhstore

# tools/ 目录（人工维护的词条源）
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, 'tools')
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

TOTAL = {'added': 0, 'updated': 0, 'kept': 0, 'unchanged': 0}


def bump(stat):
    for k, v in stat.items():
        TOTAL[k] += v


def feed(ns, mapping, origin, label, en_of=None):
    if not mapping:
        print('  %-34s (空)' % label)
        return
    st = zhstore.upsert_many(ns, mapping, origin=origin, en_of=en_of)
    bump(st)
    print('  %-34s %5d 条 -> %-14s 新增%d 更新%d 保留%d 无变化%d'
          % (label, len(mapping), ns,
             st['added'], st['updated'], st['kept'], st['unchanged']))


def main():
    dry = '--dry-run' in sys.argv
    print('[seed] 仓库: %s' % zhstore.store_path())
    print('[seed] 迁移来源:')

    # ---------- 1. 人工维护的 FE key 级词条 ----------
    from manual_extra import KEY_EXTRA, VAL_EXTRA
    feed(zhstore.FE_KEY, KEY_EXTRA, 'manual', 'manual_extra.KEY_EXTRA')

    import manual_fuzzy
    feed(zhstore.FE_KEY, manual_fuzzy.FUZZY_FIX, 'manual',
         'manual_fuzzy.FUZZY_FIX')

    # audit_matched：截图逐项核对产物，按 FE key 展开
    am_path = os.path.join(TOOLS, 'audit_matched.json')
    if os.path.isfile(am_path):
        am = json.load(io.open(am_path, encoding='utf-8'))
        am_keys, am_en = {}, {}
        for en, info in am.items():
            if info.get('src') != 'FE':
                continue
            for k in info.get('keys', []):
                am_keys[k] = info['zh']
                am_en[k] = en
        feed(zhstore.FE_KEY, am_keys, 'manual', 'audit_matched(src=FE)',
             en_of=am_en)

    # ---------- 2. 人工维护的值映射（长描述，按值复用到所有同值 key） ----------
    feed(zhstore.FE_VAL, VAL_EXTRA, 'manual', 'manual_extra.VAL_EXTRA')

    from shell_manual import SHELL_MANUAL
    feed(zhstore.SHELL_VAL, SHELL_MANUAL, 'manual', 'shell_manual.SHELL_MANUAL')

    # ---------- 3. 内核/技能翻译表（脚本内硬编码，origin=seed 可被后续扫描覆盖） ----------
    # 文件名带连字符，无法直接 import，用 importlib 按路径加载
    import importlib.util

    def load_mod(fname, modname):
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), fname)
        spec = importlib.util.spec_from_file_location(modname, p)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    tk = load_mod('translate-kernel.py', 'tk_mod')
    feed(zhstore.KERNEL_TABLE, tk.TRANSLATIONS, 'seed',
         'translate-kernel.TRANSLATIONS')

    tks = load_mod('translate-kernel-source.py', 'tks_mod')
    feed(zhstore.KERNEL_SOURCE, tks.SOURCE_TRANSLATIONS, 'seed',
         'translate-kernel-source.SOURCE_TRANSLATIONS')

    tsk = load_mod('translate-skills.py', 'tsk_mod')
    feed(zhstore.SKILL, tsk.SKILL_ZH, 'seed', 'translate-skills.SKILL_ZH')

    print('[seed] 合计: 新增 %d，更新 %d，保留(不覆盖人工) %d，无变化 %d'
          % (TOTAL['added'], TOTAL['updated'], TOTAL['kept'], TOTAL['unchanged']))

    if dry:
        print('[seed] --dry-run：未落盘')
        return 0

    ok, bak, err = zhstore.save()
    if not ok:
        sys.stderr.write('[seed] 保存失败: %s\n' % err)
        sys.stderr.write('[seed] 仓库未变更；备份: %s\n' % (bak or '(无)'))
        return 1
    print('[seed] 备份: %s' % (bak or '(首次创建，无备份)'))
    print()
    print(zhstore.stats())
    return 0


if __name__ == '__main__':
    sys.exit(main())
