# -*- coding: utf-8 -*-
"""从当前补丁态内核二进制确定性重建 kernel-patch-log.json。

背景：并发运行 translate-kernel 的两个实例时，后启动者会以空日志快照读到
已被前者补丁的二进制（全部 miss），并把日志覆盖为 {}，导致卸载无法还原。
本工具按 rebuild_runtime.py 第 3 段的推导方式，从「二进制中的中文表项 +
词条仓库的英文原文」重建完整还原日志。

推导规则（与打补丁互逆）：
  - 8 位 Latin-1 条目：orig_payload = en(latin-1)，orig_header = 0x80000000|len，
    零填充到 align4；补丁后 units = region/2
  - 16 位 UTF-16 条目：orig_payload = en(utf-16-le)，orig_header = len(en)（码元数），
    零填充到 align4；补丁后 units 不变
"""
import importlib.util
import json
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BAK = os.path.join(os.environ.get('USERPROFILE', ''), '.claude', 'zh', 'backup')
LOG_PATH = os.path.join(BAK, 'kernel-patch-log.json')


def align4(n):
    return (n + 3) & ~3


def main():
    spec = importlib.util.spec_from_file_location(
        'tk', os.path.join(ROOT, 'scripts', 'translate-kernel.py'))
    tk = importlib.util.module_from_spec(spec)
    sys.argv = [sys.argv[0]]
    spec.loader.exec_module(tk)
    table, n_store = tk.load_translations()
    kpath = tk.find_kernel()
    if not kpath:
        print('未找到内核')
        return 1
    kdata = open(kpath, 'rb').read()
    print('内核: %s (%.0f MB)' % (kpath, len(kdata) / 1048576))

    log = {}
    skipped_noncjk = 0
    for en, zh in table.items():
        # 译文不含中文字符（如 'Renamed to /usage-credits' -> '/usage-credits'）
        # 时，译文与合法英文表项无法区分（曾把内核中固有的 '/usage-credits'
        # 英文表项误判为补丁产物写入日志），一律跳过
        if not any('\u4e00' <= c <= '\u9fff' for c in zh):
            skipped_noncjk += 1
            continue
        try:
            en.encode('latin-1')
            is_latin1 = True
        except UnicodeEncodeError:
            is_latin1 = False
        if is_latin1:
            orig_payload = en.encode('latin-1')
            orig_header = 0x80000000 | len(orig_payload)
            region = align4(len(orig_payload))

            def unit_ok(u, txt, zh=zh, region=region):
                return u * 2 == region and u >= len(zh) and txt == zh
        else:
            orig_payload = en.encode('utf-16-le')
            orig_header = len(en)          # 码元数
            region = align4(len(orig_payload))

            def unit_ok(u, txt, zh=zh, en=en):
                return u == len(en) and u >= len(zh) and txt == zh

        needle = zh.encode('utf-16-le')
        offs = []
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
            log[en] = {
                'offset': offs[0],
                'orig_header': orig_header,
                'orig_payload_hex': (orig_payload + b'\x00' * (region - len(orig_payload))).hex(),
            }

    print('重建 %d 条（词条仓库 %d 条，跳过无中文译文 %d 条）'
          % (len(log), n_store, skipped_noncjk))

    # 交叉校验：未入日志的条目，内核中必须不存在对应中文（否则还原会残留）
    miss = [en for en in table if en not in log]
    leak = [en for en in miss
            if kdata.find(table[en].encode('utf-16-le')) >= 0]
    if leak:
        print('[警告] %d 条存在中文却未入日志（需人工核查）：%s'
              % (len(leak), [x[:40] for x in leak[:3]]))
        return 1
    print('[安全] 未命中 %d 条在内核中均无对应中文' % len(miss))

    if not os.path.isdir(BAK):
        os.makedirs(BAK)
    with open(LOG_PATH, 'w', encoding='utf-8') as f:
        json.dump(log, f, ensure_ascii=False, indent=1)
    print('已写入 %s' % LOG_PATH)
    return 0


if __name__ == '__main__':
    sys.exit(main())
