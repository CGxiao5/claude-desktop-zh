# -*- coding: utf-8 -*-
"""
Claude Desktop 内置技能描述汉化（用户目录 skills-plugin 运行副本）

斜杠菜单中各技能的悬停描述不是 i18n 词条，而是来自
%LOCALAPPDATA%\\Claude-3p\\local-agent-mode-sessions\\skills-plugin\\<id>\\<id>\\
下的 manifest.json 与各 skills\\<name>\\SKILL.md frontmatter。
本脚本将其中 description 翻译为中文（两处同步），幂等，可重复运行。

备份：首次运行时在同目录生成 <file>.zh-bak，卸载脚本据此还原。
注意：Claude 更新或技能更新后该目录可能被重新解压覆盖，重跑本脚本即可。

词条持久化（v2.5）：
  译文的唯一真相源是统一词条仓库（scripts/zhstore.py）的 skill 命名空间，
  本文件里的 SKILL_ZH 退化为首次 seed 的内置兜底。
  运行流程：仓库读取 -> 写入技能文件 -> 把实际生效的词条回写仓库。
"""
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zhstore

# 技能名 -> 中文描述（按 manifest.json 原文逐条翻译）
# 本表仅在仓库缺条目时兜底；正式译文以仓库为准（见 load_translations）。
SKILL_ZH = {
    'docx': '当用户需要创建、读取、编辑或处理 Word 文档（.docx）或 Word 模板（.dotx）时使用本技能。触发场景包括：任何提及 Microsoft Word 文档的说法，如“Word 文档”“word document”“.docx”“.dotx”“microsoft doc”。从 .docx 或 .dotx 文件中提取或重组内容、在文档中插入或替换图片、在 Word 文件中查找替换、处理修订或批注，或将内容整理成精美的 Word 文档时也使用本技能。如果用户要求交付 Word 或 .docx 文件（用于下载、发邮件或打印），使用本技能。但如果用户只说要文档、页面、报告、备忘录或笔记而未指定文件格式，且本会话提供 Claude 自己的专属文档或页面技能/连接器，则改用那个，即使最终要发邮件或打印。不要用于 PDF、电子表格、Google 文档或与文档生成无关的编码。',
    'pdf': '当用户需要对 PDF 文件做任何操作时使用本技能。包括：读取或提取 PDF 中的文本/表格、将多个 PDF 合并为一个、拆分 PDF、旋转页面、添加水印、创建新 PDF、填写 PDF 表单、加密/解密 PDF、提取图片，以及对扫描版 PDF 做 OCR 使其可搜索。如果用户提到 .pdf 文件或要求生成 PDF，使用本技能。',
    'pdf-reading': '当需要读取、检查或提取 PDF 文件内容时使用本技能——尤其是文件内容不在你的上下文中、需要从磁盘读取时。涵盖内容清点、文本提取、页面栅格化（用于视觉检查）、嵌入图片/附件/表格/表单字段提取，以及为不同文档类型（文本密集型、扫描件、幻灯片、表单、数据密集型）选择合适的读取策略。不要用本技能创建 PDF、填写表单、合并、拆分、加水印或加密——那些请改用 pdf 技能。',
    'pptx': '任何时候以任何方式涉及 .pptx 或 .potx 文件都使用本技能——无论作为输入、输出还是两者兼有。包括：创建幻灯片、路演稿或 PowerPoint（.pptx）演示文稿；读取、解析或提取任何 .pptx 或 .potx 文件的文本（即使提取的内容将用于别处，如邮件、摘要或创建另一种类型的幻灯片）；编辑、修改或更新现有演示文稿；合并或拆分幻灯片文件；处理模板（.potx）、版式、演讲者备注或批注。只要用户要求 PowerPoint 或 .pptx 文件、或提到 .pptx/.potx 文件名即触发，无论其后续打算如何处理这些内容。但如果用户只说要幻灯片或演示文稿而未指定文件格式，且本会话提供专用的幻灯片工件类型或独立的 slides 技能，则默认改用那个；否则使用本技能。',
    'xlsx': '任何时候电子表格文件是主要输入或输出时使用本技能。即用户想要：打开、读取、编辑或修复现有的 .xlsx、.xlsm、.xltx、.csv 或 .tsv 文件（如添加列、计算公式、格式化、制图、清洗脏乱数据）；从零或从其他数据源创建新电子表格；或在表格类文件格式之间转换。当用户按名称或路径提到电子表格文件时尤其要触发——哪怕是随口一说（比如“我下载文件夹里的那个 xlsx”）——并且要对其做处理或从中生成内容。另外，清洗或重构脏乱的表格数据文件（行格式错误、表头错位、垃圾数据）为规范电子表格时也触发。交付物必须是电子表格文件。当主要交付物是 Word 文档、HTML 报告、独立的 Python 脚本、数据库管线或 Google Sheets API 集成时，即使涉及表格数据也不要触发。',
    'frontend-design': '构建新 UI 或改造现有 UI 时，提供独特、有主见的视觉设计指导。帮助确定美学方向、排版，并做出不会沦为模板化默认效果的设计选择。',
    'schedule': '创建或更新自动运行的计划任务。当用户说“每天”“每天早上”“一小时后提醒我”“中午运行这个”，或想重新安排现有任务的时间时使用。',
    'setup-claude': '引导式设置——安装匹配的插件、试用技能、连接工具。',
    'setup-cowork': '引导式设置——安装匹配的插件、试用技能、连接工具。',
    'consolidate-memory': '对记忆文件进行反思性整理——合并重复条目、修正过时信息、精简索引。',
    'explain-usage': '用一张简明的图表，以通俗的语言解释本次会话的 token 都花在了哪里。当用户说“解释一下我的用量”“我的 token 都去哪了”，或要求用量明细时使用。',
}


def has_cjk(s):
    return any('一' <= ch <= '鿿' for ch in s)


def backup_once(path):
    bak = path + '.zh-bak'
    if not os.path.exists(bak):
        with open(path, 'rb') as f:
            data = f.read()
        with open(bak, 'wb') as f:
            f.write(data)
        return True
    return False


def load_translations():
    """词条仓库优先，内置 SKILL_ZH 兜底。返回 (merged, 仓库条数)。"""
    try:
        store_tbl = zhstore.get(zhstore.SKILL)
    except Exception as e:
        sys.stderr.write('[技能汉化] 读取词条仓库失败(%s)，仅用内置表\n' % e)
        store_tbl = {}
    merged = dict(SKILL_ZH)
    merged.update(store_tbl)          # 仓库覆盖内置
    return merged, len(store_tbl)


def translate_manifest(path, table, applied=None):
    raw = io.open(path, encoding='utf-8').read()
    m = json.loads(raw)
    changed = 0
    for s in m.get('skills', []):
        name = s.get('name')
        zh = table.get(name)
        if zh and not has_cjk(s.get('description', '')):
            s['description'] = zh
            changed += 1
            if applied is not None:
                applied[name] = zh
    if changed:
        backup_once(path)
        io.open(path, 'w', encoding='utf-8', newline='').write(
            json.dumps(m, ensure_ascii=False, indent=1))
    return changed


# description 行为带引号或不带引号的 YAML 纯量（单行）
DESC_RE = re.compile(r'^(description:\s*)("(?:[^"\\]|\\.)*"|[^\n"][^\n]*)\s*$', re.M)


def translate_skill_md(path, zh):
    text = io.open(path, encoding='utf-8').read()
    m = DESC_RE.search(text)
    if not m:
        return False
    cur = m.group(0)
    if has_cjk(cur):
        return False
    esc = zh.replace('\\', '\\\\').replace('"', '\\"')
    new = '%s"%s"' % (m.group(1), esc)
    backup_once(path)
    io.open(path, 'w', encoding='utf-8', newline='').write(
        text[:m.start()] + new + text[m.end():])
    return True


def main():
    base = os.path.expandvars(
        r'%LOCALAPPDATA%\Claude-3p\local-agent-mode-sessions\skills-plugin')
    if not os.path.isdir(base):
        print('[技能汉化] 未找到 skills-plugin 目录，跳过')
        return 0
    table, n_store = load_translations()
    applied = {}          # 实际生效的 技能名->中文描述
    total_m = total_s = 0
    for dp, dn, fn in os.walk(base):
        if 'manifest.json' in fn:
            total_m += translate_manifest(os.path.join(dp, 'manifest.json'),
                                          table, applied)
        for name, zh in table.items():
            md = os.path.join(dp, 'skills', name, 'SKILL.md')
            if os.path.isfile(md):
                if translate_skill_md(md, zh):
                    total_s += 1
                    applied[name] = zh

    # 回写词条仓库：本次真正生效的译文落盘，下次直接复用（无需重翻）
    if applied:
        try:
            st = zhstore.upsert_many(zhstore.SKILL, applied, origin='auto')
            zhstore.save(silent=True)
            if st['added'] or st['updated']:
                print('[技能汉化] 词条仓库: 新增 %d，更新 %d（仓库 %d 条）'
                      % (st['added'], st['updated'], zhstore.count(zhstore.SKILL)))
        except Exception as e:
            sys.stderr.write('[技能汉化] 词条回写失败(不影响汉化): %s\n' % e)

    print('[技能汉化] manifest 更新 %d 处，SKILL.md 更新 %d 处 | 仓库词条 %d 条'
          % (total_m, total_s, n_store))
    return 0


if __name__ == '__main__':
    sys.exit(main())
