# -*- coding: utf-8 -*-
r"""
app.asar 内嵌技能描述汉化（等长源码字面量替换 + asar integrity 链修复）

背景：协作页「+ → 技能」菜单的 tooltip 读 app.asar 内嵌的技能注册表与
skillDescription 默认值，不走任何 i18n 词表，只能等长原地替换：
  新字节 = 中文 UTF-8 字节 + 尾部空格补齐到 原文 raw 字节数

难点：本版本 Electron 启用了 **asar integrity 校验**，链条两层：
  1. exe 内嵌资源 JSON 记录 header 的 SHA256：
       [{"file":"resources\\app.asar","alg":"SHA256","value":"<sha256(header JSON)>"}]
  2. header JSON 中每个文件条目记录内容哈希：
       "integrity":{"algorithm":"SHA256","hash":"<sha256(content)>",
                    "blocks":["<sha256(每 4MB 块)>",...],"blockSize":4194304}
任何一层不匹配，进程直接退出（ASAR Integrity Violation）。

修复策略（全程等长，不移动任何偏移）：
  a. 只改 *.js 内容（跳过 *.jsc 编译缓存——V8 源哈希不匹配会自然 cache miss，
     回退到从 .js 源码编译，功能不受影响）
  b. 重算受影响文件的 hash 与 blocks，等长（64 hex 字符）写回 header JSON
  c. 重算 sha256(header JSON)，等长写回 exe 资源中的 value
日志记录全部旧值（文件 offsets、各文件旧 hash/blocks、exe 旧 header 哈希），
--restore 精确逆向。幂等：每次运行先按日志还原，再重新应用。

词条来源：统一词条仓库（zhstore.py）的 asar-source 命名空间；
仓库不可用时使用内置 seed 表兜底。命中词条回写仓库（origin=kernel-scan）。

权限：app.asar 与 claude.exe 均位于 WindowsApps 下，需要管理员权限
（由 install-zh.ps1 保证；Claude 必须先退出）。
"""
import io
import json
import hashlib
import os
import struct
import sys

# ---------------- seed 兜底表（raw 形态：非 ASCII 写作 \uXXXX） ----------------
SEED_TRANSLATIONS = {
 # 与词条仓库 asar-source 命名空间同步（键为文件内原始字节形态）
 "Create or update a scheduled task that runs automatically. Use when the user says things like \"every day\", \"each morning\", \"remind me in an hour\", \"run this at noon\", or wants to reschedule an existing task.":
   "创建或更新自动运行的计划任务。当用户说“每天”“每天早上”“一小时后提醒我”“中午运行这个”，或想重新安排现有任务时使用。",
 "Explain where this session's tokens went, with one simple chart in plain language. Use when the user says things like \"explain my usage\", \"where did my tokens go\", or asks for a usage breakdown.":
   "用一张简单图表，以通俗语言说明本次会话的 token 去向。当用户说“解释我的用量”“我的 token 去哪了”，或要求用量明细时使用。",
 "Guidance for distinctive, intentional visual design when building new UI or reshaping an existing one. Helps with aesthetic direction, typography, and making choices that don't read as templated defaults.":
   "构建新 UI 或改造现有 UI 时的视觉设计指导：美学方向、排版，避免模板化默认效果。",
 "Guided setup \\u2014 install a matching plugin, try a skill, connect tools.":
   "引导式设置——安装匹配插件、试用技能、连接工具。",
 "Reflective pass over your memory files \\u2014 merge duplicates, fix stale facts, prune the index.":
   "对记忆文件做反思性整理——合并重复、修正过时、精简索引。",
 "Show what's using your context window":
   "显示上下文窗口的占用情况",
 "Use this skill any time a .pptx or .potx file is involved in any way — as input, output, or both. This includes: creating slide decks, pitch decks, or presentations as PowerPoint (.pptx) files; reading, parsing, or extracting text from any .pptx or .potx file (even if the extracted content will be used elsewhere, like in an email, summary, or creating a different type of slide deck); editing, modifying, or updating existing presentations; combining or splitting slide files; working with templates (.potx), layouts, speaker notes, or comments. Trigger whenever the user asks for a PowerPoint or .pptx file, or references a .pptx or .potx filename, regardless of what they plan to do with the content afterward. However, when the user asks for a deck, slides, a slide deck, or a presentation without naming a file format, default to using a dedicated slide-deck artifact type or a separate slides skill if this session offers one; otherwise, use this skill.":
   "任何时候涉及 .pptx/.potx 文件都用本技能——作输入、输出或两者。包括：创建幻灯片、路演稿或 PowerPoint（.pptx）演示；读取、解析或提取任何 .pptx/.potx 文本（即使内容另作他用，如邮件、摘要或另一类幻灯片）；编辑更新现有演示文稿；合并或拆分幻灯片文件；处理模板（.potx）、版式、演讲者备注或批注。只要用户要 PowerPoint/.pptx 或提到 .pptx/.potx 文件名即触发。但若只要幻灯片/演示而未指定格式，且会话提供专用幻灯片工件或 slides 技能，默认用那个；否则用本技能。",
 "Use this skill any time a spreadsheet file is the primary input or output. This means any task where the user wants to: open, read, edit, or fix an existing .xlsx, .xlsm, .xltx, .csv, or .tsv file (e.g., adding columns, computing formulas, formatting, charting, cleaning messy data); create a new spreadsheet from scratch or from other data sources; or convert between tabular file formats. Trigger especially when the user references a spreadsheet file by name or path — even casually (like \\\"the xlsx in my downloads\\\") — and wants something done to it or produced from it. Also trigger for cleaning or restructuring messy tabular data files (malformed rows, misplaced headers, junk data) into proper spreadsheets. The deliverable must be a spreadsheet file. Do NOT trigger when the primary deliverable is a Word document, HTML report, standalone Python script, database pipeline, or Google Sheets API integration, even if tabular data is involved.":
   "任何时候电子表格文件是主要输入或输出时用本技能：打开、读取、编辑或修复现有 .xlsx/.xlsm/.xltx/.csv/.tsv（加列、算公式、格式化、制图、清洗脏数据）；从零或从其他数据源新建表格；表格格式间互转。用户按名称或路径提到表格文件——哪怕随口一说（如“我下载里的那个 xlsx”）——并要处理或从中生成内容时必触发。清洗重构脏乱表格数据（行错位、表头错位、垃圾数据）为规范电子表格也触发。交付物必须是电子表格文件。主要交付物是 Word 文档、HTML 报告、独立 Python 脚本、数据库管线或 Google Sheets API 集成时，即使涉及表格数据也不要触发。",
 "Use this skill when you need to read, inspect, or extract content from PDF files — especially when file content is NOT in your context and you need to read it from disk. Covers content inventory, text extraction, page rasterization for visual inspection, embedded image/attachment/table/form-field extraction, and choosing the right reading strategy for different document types (text-heavy, scanned, slide-decks, forms, data-heavy). Do NOT use this skill for PDF creation, form filling, merging, splitting, watermarking, or encryption — use the pdf skill instead.":
   "当需要读取、检查或提取 PDF 内容时用本技能——尤其内容不在上下文、需从磁盘读取时。涵盖内容清点、文本提取、页面栅格化视觉检查、嵌入图片/附件/表格/表单字段提取，并为不同文档类型（文本密集、扫描件、幻灯片、表单、数据密集）选择读取策略。不要用于创建 PDF、填表、合并、拆分、水印或加密——改用 pdf 技能。",
 "Use this skill whenever the user wants to create, read, edit, or manipulate Word documents (.docx) or Word templates (.dotx). Triggers include: any mention of Microsoft Word Documents, such as 'Word doc', 'word document', '.docx', '.dotx', 'microsoft doc'. Also use when extracting or reorganizing content from .docx or .dotx files, inserting or replacing images in documents, find-and-replace in Word files, working with tracked changes or comments, or converting content into a polished Word document. If the user asks for a deliverable as a Word or .docx file (to download, email or print), use this skill. However, if they ask for a document, page, report, memo, or notes WITHOUT naming a file format and the session offers Claude's own dedicated document or page skill or connector, use that instead, even if they will email or print it. Do NOT use for PDFs, spreadsheets, Google Docs, or coding unrelated to document generation.":
   "当用户要创建、读取、编辑或处理 Word 文档（.docx）或 Word 模板（.dotx）时用本技能。触发：任何提及 Microsoft Word 文档的说法，如“Word 文档”“word document”“.docx”“.dotx”“microsoft doc”。也用于：从 .docx/.dotx 提取或重组内容、在文档中插入或替换图片、Word 查找替换、处理修订或批注、生成精美 Word 文档。用户要求交付 Word/.docx 文件（下载、发邮件或打印）时用本技能。但若只要文档、页面、报告、备忘录或笔记而未指定格式，且会话提供 Claude 专属文档/页面技能或连接器，改用那个。不要用于 PDF、表格、Google 文档或无关编码。",
 "Use this skill whenever the user wants to do anything with PDF files. This includes reading or extracting text/tables from PDFs, combining or merging multiple PDFs into one, splitting PDFs apart, rotating pages, adding watermarks, creating new PDFs, filling PDF forms, encrypting/decrypting PDFs, extracting images, and OCR on scanned PDFs to make them searchable. If the user mentions a .pdf file or asks to produce one, use this skill.":
   "当用户要对 PDF 文件做任何操作时用本技能：读取/提取文本表格、合并多个 PDF、拆分、旋转页面、加水印、新建 PDF、填表单、加解密、提取图片、OCR 扫描件使其可搜索。提到 .pdf 文件或要生成 PDF 时使用。",
 "Work with Claude Design (claude.ai/design): create, import, export, sync, login":
   "Claude Design（claude.ai/design）创建、导入、导出、同步与登录",
}

ZH_HOME = os.path.join(os.environ.get('USERPROFILE', ''), '.claude', 'zh')
BAK_DIR = os.path.join(ZH_HOME, 'backup')
LOG = os.path.join(BAK_DIR, 'asar-source-patch-log.json')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import zhstore
except Exception:
    zhstore = None


# ---------------- 词条表读写 ----------------

def _load_table():
    if zhstore is not None:
        try:
            t = zhstore.get(zhstore.ASAR_SOURCE)
            if t:
                return dict(t)
        except Exception:
            pass
    return dict(SEED_TRANSLATIONS)


def _writeback(applied):
    if zhstore is None or not applied:
        return
    try:
        zhstore.upsert_many(zhstore.ASAR_SOURCE, applied, origin='kernel-scan')
        ok, bak, err = zhstore.save(silent=True)
        if ok:
            print('[asar-src] 仓库已回写 %d 条' % len(applied))
        else:
            print('[asar-src][警告] 仓库回写失败: %s' % err, file=sys.stderr)
    except Exception as e:
        print('[asar-src][警告] 仓库回写异常: %s' % e, file=sys.stderr)


# ---------------- 路径定位 ----------------

def find_targets():
    """返回 (app.asar 路径, claude.exe 路径)，AppX 注册版本优先。"""
    base = r'C:\Program Files\WindowsApps'
    if not os.path.isdir(base):
        return None, None
    cands = []
    for d in os.listdir(base):
        if not d.startswith('Claude_'):
            continue
        a = os.path.join(base, d, 'app', 'resources', 'app.asar')
        e = os.path.join(base, d, 'app', 'claude.exe')
        if os.path.isfile(a) and os.path.isfile(e):
            cands.append((os.path.getmtime(a), a, e))
    if not cands:
        return None, None
    _, a, e = max(cands)
    return a, e


# ---------------- asar 结构 ----------------

def parse_asar(data):
    """解析 header，返回 (js_len, hdr_raw(bytearray), files)。

    files: [{'path','start','end','integrity','size'}]，start/end 为绝对偏移。
    """
    # 文件被截断/损坏时，下面的切片解包会抛 struct.error 堆栈。这里先做长度
    # 校验，给出可读的失败原因，便于定位（安装中断时尤其重要）。
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
                off = int(e.get('offset', 0))
                size = e.get('size', 0)
                files.append({
                    'path': fp,
                    'start': base + off,
                    'end': base + off + size,
                    'size': size,
                    'integrity': e.get('integrity'),
                })
    walk(j.get('files', {}), '')
    return js_len, hdr_raw, files


# 除 .js 外允许补丁的成员：bundled-skills 注册表（斜杠菜单 anthropic-skills:*
# tooltip 的真实来源，2026-10-16 定位）。它是 UTF-8 JSON，键含原始非 ASCII
# 字符（— 等），与 .js 的 \uXXXX 转义形态不同。
EXTRA_PATCHABLE = ('/resources/bundled-skills/manifest.json',)


def file_at(files, off, suffix='.js'):
    """返回包含绝对偏移 off 且可补丁的文件条目（.js 或 EXTRA_PATCHABLE）。"""
    for f in files:
        if f['start'] <= off < f['end'] and (
                f['path'].endswith(suffix) or f['path'] in EXTRA_PATCHABLE):
            return f
    return None


def key_bytes(en):
    """键的字节形态：.js 源码是 ASCII（非 ASCII 为 \\uXXXX 转义）；
    manifest.json 是 UTF-8（非 ASCII 为原始多字节）。latin-1 可编码说明是
    纯 ASCII 键；否则按 UTF-8。"""
    try:
        return en.encode('latin-1')
    except UnicodeEncodeError:
        return en.encode('utf-8')


def _sha(b):
    return hashlib.sha256(bytes(b)).hexdigest()


# ---------------- 日志 ----------------

def load_log():
    try:
        return json.load(io.open(LOG, encoding='utf-8'))
    except Exception:
        return None


def save_log(d):
    os.makedirs(BAK_DIR, exist_ok=True)
    io.open(LOG, 'w', encoding='utf-8').write(
        json.dumps(d, ensure_ascii=False, indent=1))


# ---------------- 完整性链修复 ----------------

def _replace_file_integrity(hdr, old_hash, new_hash, old_blocks, new_blocks):
    """在 header JSON 字节流中精确替换单个文件的 integrity（等长）。

    hash 用带 key 的模式 `"hash":"<old>"` 全局唯一替换；
    blocks 在该文件条目窗口（hash 位置 ±600 字节）内的 `"blocks":[...]` 数组
    区间中替换——小文件 hash == blocks[0] 时不会误伤。
    """
    if old_hash != new_hash:
        pat = b'"hash":"' + old_hash.encode('ascii') + b'"'
        assert hdr.count(pat) == 1, 'hash 记录不唯一: %s' % old_hash[:16]
        hdr = hdr.replace(pat, b'"hash":"' + new_hash.encode('ascii') + b'"', 1)
    if old_blocks != new_blocks:
        h_idx = hdr.find(b'"hash":"' + new_hash.encode('ascii') + b'"')
        lo = max(0, h_idx - 700)
        hi = min(len(hdr), h_idx + 700 + 70 * (len(new_blocks) + 1))
        seg = hdr[lo:hi]
        rel = h_idx - lo
        # 窗口可能覆盖相邻条目的 blocks 数组：取离 hash 最近的一处
        # （字段顺序不保证，前后都候选）
        cands = []
        j = seg.find(b'"blocks":[')
        while j >= 0:
            cands.append(j)
            j = seg.find(b'"blocks":[', j + 1)
        assert cands, '未找到 blocks 数组'
        b_start = min(cands, key=lambda x: abs(x - rel))
        b_end = seg.find(b']', b_start)
        assert b_end > b_start
        arr = seg[b_start:b_end]
        for old, new in zip(old_blocks, new_blocks):
            if old == new:
                continue
            pat = b'"' + old.encode('ascii') + b'"'
            assert arr.count(pat) == 1, 'block 值在数组区间不唯一: %s' % old[:16]
            arr = arr.replace(pat, b'"' + new.encode('ascii') + b'"', 1)
        hdr = hdr[:lo] + seg[:b_start] + arr + seg[b_end:] + hdr[hi:]
    return hdr


def fix_integrity(asar_data, hdr_raw, files, touched_paths, exe_path, dry=False):
    """重算 touched 文件 integrity 并等长写回 header；重算 header 哈希写回 exe。

    返回 {'files': {path: {'hash': [old,new], 'blocks': [[old...],[new...]]}},
          'exe': {'offset': n, 'old': h, 'new': h}} 供日志与还原。
    """
    hdr = bytes(hdr_raw)
    report = {'files': {}, 'exe': None}
    for f in files:
        if f['path'] not in touched_paths or not f.get('integrity'):
            continue
        integ = f['integrity']
        old_hash = integ.get('hash')
        old_blocks = list(integ.get('blocks', []))
        bs = integ.get('blockSize', 4194304)
        content = bytes(asar_data[f['start']:f['end']])
        new_hash = _sha(content)
        new_blocks = [_sha(content[i:i + bs]) for i in range(0, len(content), bs)]
        hdr = _replace_file_integrity(hdr, old_hash, new_hash, old_blocks, new_blocks)
        report['files'][f['path']] = {'hash': [old_hash, new_hash],
                                      'blocks': [old_blocks, new_blocks]}
    # 写回 header（长度不变）
    assert len(hdr) == len(hdr_raw), 'header 长度变化，中止'
    if not dry:
        hdr_raw[:] = hdr

    # exe 资源中的 header 哈希
    new_header_hash = _sha(hdr)
    exe_data = bytearray(open(exe_path, 'rb').read())
    old_exe_hash = None
    exe_off = -1
    # 从 exe 资源 JSON 中解析当前记录值
    import re as _re
    m = _re.search(rb'\[\{"file":"resources\\\\app\.asar","alg":"SHA256","value":"([0-9a-f]{64})"\}\]',
                   bytes(exe_data))
    assert m, '未在 exe 中找到 asar integrity 资源记录'
    old_exe_hash = m.group(1).decode('ascii')
    exe_off = m.start(1)
    exe_data[exe_off:exe_off + 64] = new_header_hash.encode('ascii')
    report['exe'] = {'offset': exe_off, 'old': old_exe_hash, 'new': new_header_hash}
    if not dry:
        open(exe_path, 'wb').write(bytes(exe_data))
    return report


def restore_integrity(exe_path, integ_log):
    """按日志还原 exe header 哈希（文件 hash/blocks 随内容还原后自然回到旧值，
    但 header JSON 中的记录已被改动，必须显式写回）。"""
    if not integ_log:
        return
    exe_data = bytearray(open(exe_path, 'rb').read())
    ex = integ_log.get('exe')
    if ex:
        exe_data[ex['offset']:ex['offset'] + 64] = ex['old'].encode('ascii')
        open(exe_path, 'wb').write(bytes(exe_data))


def restore_header_hashes(hdr_raw, integ_log):
    """把 header JSON 中各文件的 hash/blocks 写回旧值（等长，精确替换）。"""
    if not integ_log:
        return
    hdr = bytes(hdr_raw)
    for path, rec in (integ_log.get('files') or {}).items():
        # 反向：日志中 [old, new]，还原即 old<-new
        hdr = _replace_file_integrity(hdr, rec['hash'][1], rec['hash'][0],
                                      rec['blocks'][1], rec['blocks'][0])
    hdr_raw[:] = hdr


# ---------------- 主流程 ----------------

def apply():
    asar, exe = find_targets()
    if not asar:
        print('[asar-src] 未找到 app.asar，跳过')
        return 0
    log = load_log()

    data = bytearray(open(asar, 'rb').read())
    js_len, hdr_raw, files = parse_asar(data)

    # 1) 幂等还原（内容 + header 记录 + exe 记录）
    restored = 0
    if log:
        for en, info in (log.get('entries') or {}).items():
            nb = key_bytes(en)
            for off in info['offsets']:
                data[off:off + len(nb)] = nb
                restored += 1
        restore_header_hashes(hdr_raw, log.get('integrity'))
        restore_integrity(exe, log.get('integrity'))
        # 内容已还原，把 header 写回 asar
        data[16:16 + js_len] = bytes(hdr_raw)
        # 关键：还原后必须重新解析 header。
        # fix_integrity 以 files 里的 integrity 记录为"旧值"基准做等长替换；
        # 若沿用还原前解析的 files（其记录是上一轮的"新值"），当本轮译文与上轮
        # 完全一致时 old_hash == new_hash 会被跳过，导致 header 停留在还原后的
        # 原始哈希而内容已是补丁态——层 2 校验必挂（本 bug 曾在重装时实发）。
        js_len, hdr_raw, files = parse_asar(data)

    # 2) 应用新补丁（.js + EXTRA_PATCHABLE 成员，跳过 .jsc 等其他文件）
    table = _load_table()
    new_entries = {}
    touched = set()
    ok = miss = overflow = skipped_jsc = 0
    for en, zh in table.items():
        nb = key_bytes(en)
        b = zh.encode('utf-8')
        if len(b) > len(nb):
            print('[asar-src][超长] %r 译文 %d 字节 > 原文 %d 字节'
                  % (en[:40], len(b), len(nb)))
            overflow += 1
            continue
        new = b + b' ' * (len(nb) - len(b))
        offs = []
        i = 0
        while True:
            i = data.find(nb, i)
            if i < 0:
                break
            f = file_at(files, i, '.js')
            if f is not None:
                offs.append(i)
                touched.add(f['path'])
            else:
                skipped_jsc += 1
            i += 1
        if not offs:
            miss += 1
            continue
        for o in offs:
            data[o:o + len(nb)] = new
        new_entries[en] = {'offsets': offs, 'zh': zh}
        ok += 1

    # 3) 完整性链修复 + 写盘
    integ_report = None
    if ok or restored:
        integ_report = fix_integrity(data, hdr_raw, files, touched, exe)
        data[16:16 + js_len] = bytes(hdr_raw)
        open(asar, 'wb').write(bytes(data))
    save_log({'entries': new_entries, 'integrity': integ_report})
    print('[asar-src] %s | 替换 %d 条（共 %d 处），未命中 %d，超长 %d，跳过 .jsc %d 处'
          % ('已更新' if ok else '无需更改', ok,
             sum(len(v['offsets']) for v in new_entries.values()),
             miss, overflow, skipped_jsc))
    if integ_report:
        print('[asar-src] integrity 链已修复: %d 个文件 + exe header 哈希'
              % len(integ_report['files']))

    _writeback({en: v['zh'] for en, v in new_entries.items()})
    return 0


def restore():
    asar, exe = find_targets()
    log = load_log()
    if not asar or not log:
        print('[asar-src] 无补丁日志或 app.asar 不存在，跳过还原')
        return 0
    data = bytearray(open(asar, 'rb').read())
    js_len, hdr_raw, files = parse_asar(data)
    n = 0
    for en, info in (log.get('entries') or {}).items():
        nb = key_bytes(en)
        for off in info['offsets']:
            data[off:off + len(nb)] = nb
            n += 1
    restore_header_hashes(hdr_raw, log.get('integrity'))
    restore_integrity(exe, log.get('integrity'))
    data[16:16 + js_len] = bytes(hdr_raw)
    open(asar, 'wb').write(bytes(data))
    try:
        os.remove(LOG)
    except OSError:
        pass
    print('[asar-src] 已还原 %d 处 + integrity 链（%s）' % (n, asar))
    return 0


def main():
    if '--restore' in sys.argv:
        return restore()
    return apply()


if __name__ == '__main__':
    sys.exit(main())
