# -*- coding: utf-8 -*-
r"""
生成「汉化自愈基线」 state.json + payload 副本。

安装脚本把本次安装的路径信息写入 install-context.json，本模块据此：
  1. 把 FE 词表 / dynamic 词表 / shell 词表各复制一份到 payload/，并记录 SHA1（小写）
  2. 扫描前端 JS 目录，为「语言白名单 / 语言名映射 / 标题栏标签」定位所在文件，
     记录「原文 -> 补丁文」三元组
  3. 写出 state.json

守护进程 skills-watch.py 每轮读取 state.json 比对：
  - 词表 SHA1 不一致（被还原/覆盖/删除）-> 从 payload 复制回来
  - JS 补丁文缺失且原文仍在 -> 重打补丁（Latin1 字节级）
  - config.json 的 locale 不是 zh-Hans -> 改回

这样 Claude 自动更新或文件被还原后，无需人工干预即可自动恢复汉化。
"""
import hashlib
import json
import os
import shutil
import sys

# --- 前端 JS 补丁三元组（与 install-zh.ps1 中的常量严格一致） ---
WL_OLD = '"en-US","de-DE","fr-FR","ko-KR","ja-JP","es-419","es-ES","it-IT","hi-IN","pt-BR","id-ID"'
WL_NEW = '"en-US","zh-Hans","de-DE","fr-FR","ko-KR","ja-JP","es-419","es-ES","it-IT","hi-IN","pt-BR","id-ID"'

NM_OLD = '{"en-US":{name:"English (United States)",localName:"English (United States)"},'
NM_NEW = ('{"en-US":{name:"English (United States)",localName:"English (United States)"},'
          '"zh-Hans":{name:"Chinese (Simplified)",localName:"\\u7B80\\u4F53\\u4E2D\\u6587"},')

TABS_OBJ_OLD1 = 'chat:{mode:"chat",icon:"Chats",label:"Chat"}'
TABS_OBJ_NEW1 = 'chat:{mode:"chat",icon:"Chats",label:"\\u804A\\u5929"}'
TABS_OBJ_OLD2 = 'cowork:{mode:"cowork",icon:"Tasks",label:"Cowork"},code:{mode:"code",icon:"Code",label:"Code"}'
TABS_OBJ_NEW2 = ('cowork:{mode:"cowork",icon:"Tasks",label:"\\u534F\\u4F5C"},'
                 'code:{mode:"code",icon:"Code",label:"\\u4EE3\\u7801"}')

TAB_CHAT_OLD = '{key:"chat",label:"Chat"}'
TAB_CHAT_NEW = '{key:"chat",label:"\\u804A\\u5929"}'
TAB_COWORK_OLD = '{key:"task",label:"Cowork"}'
TAB_COWORK_NEW = '{key:"task",label:"\\u534F\\u4F5C"}'
TAB_CODE_OLD = '{key:"code",label:"Code"}'
TAB_CODE_NEW = '{key:"code",label:"\\u4EE3\\u7801"}'

JS_SPECS = [
    ('whitelist', WL_OLD, WL_NEW),
    ('lang-name', NM_OLD, NM_NEW),
    ('tabs-obj-chat', TABS_OBJ_OLD1, TABS_OBJ_NEW1),
    ('tabs-obj-cowork-code', TABS_OBJ_OLD2, TABS_OBJ_NEW2),
    ('tab-chat', TAB_CHAT_OLD, TAB_CHAT_NEW),
    ('tab-cowork', TAB_COWORK_OLD, TAB_COWORK_NEW),
    ('tab-code', TAB_CODE_OLD, TAB_CODE_NEW),
]

PAYLOADS = [
    ('feZh', 'zh-Hans.json', 'fe-zh-Hans.json'),
    ('feDyn', os.path.join('dynamic', 'zh-Hans.json'), 'fe-dynamic-zh-Hans.json'),
    ('shellZh', 'zh-Hans.json', 'shell-zh-Hans.json'),
]


def sha1_file(path):
    h = hashlib.sha1()
    with open(path, 'rb') as f:
        for c in iter(lambda: f.read(1 << 16), b''):
            h.update(c)
    return h.hexdigest().lower()


def scan_js(v1_dir):
    """在 v1 目录下定位每个补丁三元组所属文件。

    对每个 spec：优先匹配「已补丁」文本，其次匹配「原文」文本，
    两种情况都记录下来（守护进程按「补丁文是否存在」判断是否需要重打）。
    """
    try:
        files = [os.path.join(v1_dir, f) for f in os.listdir(v1_dir)
                 if f.lower().endswith('.js')]
    except OSError:
        return []
    cache = {}
    for p in files:
        try:
            with open(p, 'rb') as f:
                cache[p] = f.read()
        except OSError:
            continue

    pairs = []
    for name, old, new in JS_SPECS:
        ob = old.encode('latin-1', 'replace')
        nb = new.encode('latin-1', 'replace')
        hit = None
        for p, raw in cache.items():
            if nb in raw:            # 已补丁：以补丁后文本定位
                hit = p
                break
        if hit is None:
            for p, raw in cache.items():
                if ob in raw:        # 未补丁：以原文定位
                    hit = p
                    break
        if hit:
            pairs.append({'name': name, 'path': hit, 'find': old, 'replace': new})
    return pairs


def main():
    home = os.path.join(os.environ.get('USERPROFILE', ''), '.claude', 'zh')
    ctx_path = os.path.join(home, 'install-context.json')
    if not os.path.isfile(ctx_path):
        print('[state] 缺少 install-context.json，跳过')
        return 1
    with open(ctx_path, 'r', encoding='utf-8') as f:
        ctx = json.load(f)

    zh_home = ctx.get('zhHome') or home
    payload_dir = os.path.join(zh_home, 'payload')
    os.makedirs(payload_dir, exist_ok=True)

    i18n = ctx['i18n']
    res = ctx['res']
    st = {
        'schema': 'claude-zh-selfheal/1',
        'locale': 'zh-Hans',
        'pkgPath': ctx.get('pkgPath', ''),
        'version': ctx.get('version', ''),
        'payload': payload_dir,
        'configPath': os.path.join(os.environ.get('LOCALAPPDATA', ''),
                                   'Claude-3p', 'config.json'),
    }

    ok = 0
    for key, rel, pay_name in PAYLOADS:
        base = res if key == 'shellZh' else i18n
        src = os.path.join(base, rel)
        if not os.path.isfile(src):
            st[key] = {'path': src, 'sha1': None}
            continue
        dst = os.path.join(payload_dir, pay_name)
        shutil.copyfile(src, dst)
        st[key] = {'path': src, 'sha1': sha1_file(src)}
        ok += 1

    js_pairs = scan_js(ctx.get('v1', ''))
    st['js'] = js_pairs

    out = os.path.join(zh_home, 'state.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(st, f, ensure_ascii=False, indent=2)
    print('[state] 已写入 %s | 词表 %d 份, JS 补丁 %d 组' % (out, ok, len(js_pairs)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
