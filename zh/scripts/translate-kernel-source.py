# -*- coding: utf-8 -*-
"""
Claude Code 内核「源码字面量 / 内嵌 markdown」原地汉化补丁。

与 translate-kernel.py（字符串表 8→16 位转换）互补：

  内核里有一部分命令描述**没有字符串表条目**——它们只以两种形态存在：
    1) Bun 打包的 JS 源码字面量，例如
         menuDescription:"Launch this project\\u2019s app to see your change working"
    2) 内嵌的 SKILL.md frontmatter，例如
         description: Complete a security review of the pending changes...
  这类文本在二进制中是**纯 ASCII**（非 ASCII 一律写成 \\uXXXX 转义），
  因此无法走字符串表通道，改用「等长原地替换」：

      新字节 = 中文 UTF-8 字节 + 空格补齐到 原字节数

  字节数完全不变 → 不移动任何偏移、不破坏 JS/markdown 结构与 Bun 内部索引。
  JS 源码按 UTF-8 解析，中文正常；尾部空格在 tooltip 中不可见。

还原：日志文件记录「原文 -> 所有偏移」，--restore 依据日志写回英文原文。
幂等：每次运行先按日志还原，再重新应用，因此可安全重复执行。

词条持久化（v2.5）：
  译文的**唯一真相源**是统一词条仓库（scripts/zhstore.py）的 kernel-source
  命名空间，本文件里的 SOURCE_TRANSLATIONS 退化为「首次 seed 的内置兜底」。
  运行流程：仓库读取 -> 应用补丁 -> 把实际生效的词条回写仓库。
  因此任何一次成功翻译都不会丢失，重装/重启后可原样复现，无需重新翻译。
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zhstore

# ---------------- 内置兜底：内核中的 ASCII 原文 -> 中文译文 ----------------
# 注意：原文里的非 ASCII 一律写成 \uXXXX 转义（与内核中的字节完全一致）。
# 本表只在仓库为空/缺条目时兜底；正式译文以仓库为准（见 load_translations）。
SOURCE_TRANSLATIONS = {
 # 与词条仓库 kernel-source 命名空间同步（键为 ASCII 转义形态）
 "Answer questions about Claude Code features and settings":
   "解答关于 Claude Code 功能与设置的问题",
 "Author or improve the run-<unit> skill - a per-project skill that tells agents how to build, launch, and drive this project's app. Use when the user asks to set up the project, get it running, write run instructions, or verify build/run steps work from a clean environment.":
   "编写或改进 run-<unit> 技能——告诉智能体如何构建、启动并运行本项目应用的每项目技能。用户要求搭建项目、跑起来、写运行说明，或验证干净环境下构建/运行步骤可用时使用。",
 "Build a design together, one decision at a time":
   "协同构建设计，逐步确定决策",
 "Build and debug apps that use the Claude API":
   "构建并调试使用 Claude API 的应用",
 "Change settings: hooks, permissions, environment variables":
   "修改设置：钩子、权限、环境变量",
 "Chart and dashboard design guidance":
   "图表与仪表盘设计指南",
 "Clean up the changed code without changing behavior":
   "保持行为不变，清理已改动的代码",
 "Complete a security review of the pending changes on the current branch":
   "完成对当前分支待提交更改的安全审查",
 "Create a git commit":
   "创建 git 提交",
 "Create a pull request":
   "创建拉取请求",
 "Create a skill that knows how to run this project\\u2019s app":
   "创建一个懂得如何运行本项目应用的技能",
 "Create and manage routines: cloud agents on a schedule":
   "创建并管理例程：定时运行的云端智能体",
 "Diagramming guidance for Artifacts":
   "工件的绘图指南",
 "Embed reusable components in an Artifact":
   "在工件中嵌入可复用组件",
 "Guided setup \\u2014 pick a role, install a plugin, try a skill, connect tools":
   "引导式设置——选角色、装插件、试技能、连接工具",
 "Health-check the user's Claude Code setup and fix issues: diagnose installation health \\u2014 what the `claude doctor` terminal diagnostics cover \\u2014 from local data (duplicate or leftover installs, PATH, unparseable settings files, broken or colliding agent definitions, skills whose frontmatter fails to parse); find unused skills, MCP servers, and plugins versus their context cost and disable dead weight; deduplicate local CLAUDE.md files against checked-in ones; trim checked-in CLAUDE.md files by cutting content a session could derive from the codebase (directory layouts, tech-stack lists, architecture overviews) while keeping gotchas, rationale, and non-standard conventions; migrate always-loaded CLAUDE.md guidance into lazy skills and nested CLAUDE.md files; flag slow hooks and context-heavy extensions; check the installed version is current; make auto mode the default permission mode; and pre-approve frequently denied read-only commands. Use when the user asks for a doctor run, checkup, audit, tune-up, or cleanup of their Claude Code setup or configuration.":
   "体检用户的 Claude Code 配置并修复问题：从本地数据诊断安装健康——即 `claude doctor` 终端诊断覆盖的内容（重复或残留安装、PATH、无法解析的设置文件、损坏或冲突的智能体定义、frontmatter 解析失败的技能）；找出未使用的技能、MCP 服务器和插件，对照上下文开销禁用累赘；对照已入库 CLAUDE.md 去重；精简已入库 CLAUDE.md，删掉会话可从代码库推导的内容（目录结构、技术栈、架构概述），保留坑点、缘由和非标准约定；把常驻加载的 CLAUDE.md 指导迁移为惰性技能与嵌套 CLAUDE.md；标记缓慢钩子和吃上下文的扩展；检查版本是否最新；把 auto 设为默认权限模式；预先批准频繁被拒的只读命令。用户要求 doctor 体检、审计、调优或清理配置时使用。",
 "Health-check your setup and fix issues: installation, unused extensions, duplicated or bloated memory files, slow hooks, updates, permissions":
   "体检当前配置并修复问题：安装项、未使用的扩展、重复或臃肿的记忆文件、缓慢的钩子、更新与权限",
 "Initialize a new CLAUDE.md file with codebase documentation":
   "初始化 CLAUDE.md 文件，写入代码库文档",
 "Launch and drive this project's app to see a change working. Use when asked to run, start, or screenshot the app, or to confirm a change works in the real app (not just tests). First looks for a project skill that already covers launching the app; otherwise falls back to built-in patterns per project type (CLI, server, TUI, Electron, browser-driven, library).":
   "启动并运行本项目的应用，实际查看改动效果。被要求运行、启动或截图应用，或确认改动在真实应用（非仅测试）中生效时使用。先找已覆盖启动的项目技能；否则按项目类型（CLI、服务器、TUI、Electron、浏览器驱动、库）回退到内置模式。",
 "Launch this project\\u2019s app to see your change working":
   "启动本项目的应用，实际查看改动效果",
 "Let Claude browse and interact with pages in your Chrome":
   "让 Claude 浏览并操作你 Chrome 里的页面",
 "Load the reference for writing Workflow tool scripts":
   "加载编写 Workflow 工具脚本的参考资料",
 "Make a mod: a change to Claude's own interface or behaviour, such as a live pane or panel, a band above the prompt, a status line, a toast, a slash command, or a hook on tool calls or prompts. Use to make, change or debug a mod or its hooks module.":
   "制作 mod：修改 Claude 自身界面或行为，如实时窗格/面板、输入框横幅、状态栏、toast、斜杠命令，或工具调用与提示词的钩子。用于创建、修改或调试 mod 及其 hooks 模块。",
 "Pair on a whiteboard artifact \\u2014 you draw, Claude answers on it":
   "在白板工件上协作——你画，Claude 在白板上作答",
 "Plan a large change; background agents each open a PR":
   "规划大型改动；后台智能体各自开出 PR",
 "Pre-approve safe read-only commands based on your usage":
   "按使用习惯预先批准安全的只读命令",
 "Prototype an idea as a working Artifact":
   "把想法原型化为可运行工件",
 "Publish a PR review briefing Artifact from a template":
   "基于模板发布 PR 评审简报工件",
 "Publish a data-table Artifact from a template":
   "基于模板发布数据表工件",
 "Publish a report Artifact from a template":
   "基于模板发布报告工件",
 "Publish a working document Artifact":
   "发布可编辑文档工件",
 "Publish an explainer Artifact from a template":
   "基于模板发布说明讲解工件",
 "Push your design system components to claude.ai/design":
   "将设计系统组件推送到 claude.ai/design",
 "Repeat a prompt or command on an interval (e.g. /loop 5m /foo)":
   "按间隔重复执行提示词或命令（如 /loop 5m）",
 "Review the changed code for reuse, simplification, efficiency, and altitude cleanups, then apply the fixes. Quality only \\u2014 it does not hunt for bugs; use /code-review for that.":
   "审查改动代码的复用、简化、效率与风格清理并应用修复。仅做质量——不找缺陷；找缺陷用 /code-review。",
 "Review the current diff or a PR for bugs and cleanups":
   "审查当前 diff 或 PR 的缺陷与可清理点",
 "Run a prompt or slash command on a recurring interval (e.g. /loop 5m /foo). Omit the interval to let the model self-pace.":
   "按间隔重复执行提示词或斜杠命令（如 /loop 5m /foo），省略则让模型自定节奏。",
 "Runtime capabilities for published Artifacts":
   "已发布工件的运行时能力",
 "See where this session\\u2019s tokens went, in plain words":
   "用通俗的话说明本次会话的 token 去向",
 "Show session cost and plan usage":
   "显示会话开销与用量",
 "TRIGGER \\u2014 read BEFORE opening the target file; don\\'t skip because it \"looks like a one-liner\" \\u2014 whenever: the prompt names Claude/Anthropic in any form (Claude, Anthropic, Fable, Opus, Sonnet, Haiku, `anthropic`, `@anthropic-ai`, `claude-*`, `us.anthropic.*`, `[1m]`); the user asks about an LLM (pricing/model choice/limits/caching) \\u2014 never answer from memory; OR the task is LLM-shaped with provider unstated (agent/MCP/tool-definition/multi-agent/RAG/LLM-judge/computer-use; generate/summarize/extract/classify/rewrite/converse over NL; debugging refusals/cutoffs/streaming/tool-calls/tokens).":
   "触发——打开目标文件前先读它；别因\\u201d像一行的活\\u201d就跳过——当：提示词以任何形式点名 Claude/Anthropic（Claude、Anthropic、Fable、Opus、Sonnet、Haiku、`anthropic`、`@anthropic-ai`、`claude-*`、`us.anthropic.*`、`[1m]`）；用户问 LLM 问题（定价/选型/限额/缓存）——绝不凭记忆；或任务是 LLM 型但未指明提供方（agent/MCP/工具定义/多智能体/RAG/LLM 评审/computer-use；生成/摘要/抽取/分类/改写/对话；调试拒答/截断/流式/工具调用/token）。",
 "TRIGGER when: user asks how Claude Code works (\"Can Claude\\u2026\", \"Does Claude\\u2026\", \"How do I\\u2026\", \"Is there a way to\\u2026\"); user asks about a slash command, CLI flag, settings key, hook, skill, MCP server, subagent, keybinding, or .claude/ directory; user wants to configure, customize, or troubleshoot Claude Code; user asks about Claude in Slack or Claude Tag (\"what is Claude Tag\", \"can Claude live in Slack\", \"@Claude in Slack\", \"/install-slack-app\", \"set up Claude for my Slack workspace\"); YOU are about to recommend a Claude Code slash command, flag, or setting and have not verified it exists in this build.\\n":
   "触发时机：用户问 Claude Code 用法（“Claude 能…”“Claude 支持…”“怎么…”“有没有办法…”）；问斜杠命令、CLI 参数、设置项、钩子、技能、MCP 服务器、子智能体、快捷键或 .claude/ 目录；想配置、定制或排查 Claude Code；问 Slack 中的 Claude 或 Claude Tag（“什么是 Claude Tag”“Claude 能进驻 Slack 吗”“在 Slack 里 @Claude”“/install-slack-app”“为我的 Slack 工作区配置”）；你正打算推荐本构建的 Claude Code 斜杠命令、参数或设置，但尚未验证其存在。\\n",
 "Turn on debug logging and investigate problems":
   "开启调试日志并排查问题",
 "Use this skill to configure the Claude Code harness via settings.json. Automated behaviors (\"from now on when X\", \"each time X\", \"whenever X\", \"before/after X\") require hooks configured in settings.json - the harness executes these, not Claude, so memory/preferences cannot fulfill them. Also use for: permissions (\"allow X\", \"add permission\", \"move permission to\"), env vars (\"set X=Y\"), hook troubleshooting, or any changes to settings.json/settings.local.json files. Examples: \"allow npm commands\", \"add bq permission to global settings\", \"move permission to user settings\", \"set DEBUG=true\", \"when claude stops show X\". For simple settings like theme/model, suggest the /config command.":
   "通过 settings.json 配置 Claude Code 运行框架。自动化行为（“从现在起当 X”“每次 X”“每当 X”“X 之前/之后”）需在 settings.json 配置钩子——由框架而非 Claude 执行，记忆/偏好无法实现。还用于：权限（“允许 X”“添加权限”“移动权限到”）、环境变量（“set X=Y”）、钩子排错，或对 settings.json/settings.local.json 的修改。例如“allow npm commands”“把 bq 权限加到全局设置”“set DEBUG=true”。主题/模型等简单设置建议用 /config。",
 "Use this skill whenever you are about to create ANY chart, graph, plot, dashboard, or data visualization, in ANY output medium \\u2014 an HTML or React artifact, inline SVG, plotting code in any library (matplotlib, plotly, d3, Recharts, \\u2026), an image/PNG you will render and upload, or a chart shared into Slack. Read it BEFORE writing the first line of chart code, choosing chart colors, building a stat tile / meter / KPI row, or laying out a dashboard. When the destination is a first-party document connector (host-designated, never self-described) that renders live charts, hand it the rows (inline, or as an uploaded data file the chart cites) rather than a rendered PNG/SVG \\u2014 a picture of a chart loses hover, data inspection and per-value comments. Produces visualizations that read as one system \\u2014 elegant, accessible, consistent in light and dark \\u2014 using a brand-neutral placeholder palette you swap for your own. Teaches a design-system-agnostic method: a form heuristic, a color formula with a runnable validator, mark specs, and interaction rules. A validated default palette is documented in `references/palette.md` \\u2014 swap that file's values for your brand's. Triggers on: \\\"chart\\\", \\\"graph\\\", \\\"plot\\\", \\\"data viz\\\", \\\"visualization\\\", \\\"dashboard\\\", \\\"analytics\\\", \\\"visualize data\\\", \\\"categorical colors\\\", \\\"sequential / diverging palette\\\", \\\"stat tile\\\", \\\"sparkline\\\", \\\"heatmap\\\", \\\"legend\\\", \\\"axis\\\", \\\"tooltip\\\", \\\"chart colors\\\", \\\"color by series\\\".":
   "每当你要创建任何图表、曲线、绘图、仪表盘或数据可视化时用本技能——无论介质是 HTML/React 工件、内联 SVG、任何绘图库代码（matplotlib、plotly、d3、Recharts、…）、待渲染上传的图片/PNG，还是分享到 Slack 的图表。在写第一行图表代码、选配色、构建指标卡/仪表/KPI 行或布局仪表盘之前先读它。目标是能渲染动态图表的第一方文档连接器（宿主指定，绝不自封）时，交给它数据行（内联或图表引用的上传数据文件）而非渲染好的 PNG/SVG——截图会丢失悬停、数据查看和逐值评论。产出像同一套系统的可视化——优雅、可访问、明暗一致——用品牌中立占位色板，可换成自己的。方法与设计系统无关：形态启发式、带可运行校验器的配色公式、标记规范与交互规则。默认色板见 `references/palette.md`——换成你的品牌值。触发词：\\\"chart\\\" \\\"graph\\\" \\\"plot\\\" \\\"data viz\\\" \\\"visualization\\\" \\\"dashboard\\\" \\\"analytics\\\" \\\"visualize data\\\" \\\"categorical colors\\\" \\\"sequential / diverging palette\\\" \\\"stat tile\\\" \\\"sparkline\\\" \\\"heatmap\\\" \\\"legend\\\" \\\"axis\\\" \\\"tooltip\\\" \\\"chart colors\\\" \\\"color by series\\\"。",
 "Verify that a code change actually does what it's supposed to by exercising it end-to-end and observing behavior \\u2014 drive the affected flow, not just tests or typecheck. Run before committing nontrivial changes; bootstraps this repo's project verify skill if none exists yet. Don't invoke it on a diff that only touches tests, docs, or other code with no runtime surface to drive (a change to product source always has one) \\u2014 there's nothing to observe.":
   "通过端到端实际运行并观察行为，验证代码改动达到预期——驱动受影响流程，而非仅测试或类型检查。提交非琐碎改动前运行；本仓库无项目 verify 技能时引导创建。只涉及测试、文档或无运行面代码的 diff 不要用（产品源码总有运行面）——没有可观察的。",
 "Write a mod: a live pane, view or behaviour change in Claude Code":
   "编写 mod：为 Claude Code 新增实时面板或行为",
}

ZH_HOME = os.path.join(os.environ.get('USERPROFILE', ''), '.claude', 'zh')
BAK_DIR = os.path.join(ZH_HOME, 'backup')
LOG = os.path.join(BAK_DIR, 'kernel-source-patch-log.json')
LOCK = LOG + '.lock'
LOCK_STALE = 120       # 残留锁超过 2 分钟且持锁进程已死，可接管


def _pid_alive(pid):
    """Windows 下判定 PID 是否存活（无 psutil 依赖）。未知返回 None。"""
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        h = k32.OpenProcess(0x1000, False, pid)     # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return None
        try:
            code = ctypes.c_ulong()
            k32.GetExitCodeProcess(h, ctypes.byref(code))
            return code.value == 259                # STILL_ACTIVE
        finally:
            k32.CloseHandle(h)
    except Exception:
        return None


def acquire_lock(wait=300, force=False):
    """跨进程互斥：与 translate-kernel.py 同因（并发读改写内核二进制 +
    日志互相覆盖）。两个模块改同一文件，必须整体串行。force 同见彼处。"""
    import time as _t
    deadline = _t.time() + wait
    while True:
        try:
            fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode('ascii'))
            os.close(fd)
            return True
        except FileExistsError:
            try:
                if force:
                    os.remove(LOCK)
                    continue
                age = _t.time() - os.path.getmtime(LOCK)
                try:
                    holder = int(open(LOCK).read().strip() or 0)
                except (OSError, ValueError):
                    holder = 0
                alive = _pid_alive(holder) if holder else None
                if alive is False or (alive is None and age > LOCK_STALE):
                    try:
                        os.remove(LOCK)
                        continue
                    except OSError:
                        pass
            except OSError:
                pass
            if _t.time() >= deadline:
                return False
            _t.sleep(2)


def release_lock():
    try:
        os.remove(LOCK)
    except OSError:
        pass


def load_translations():
    """词条仓库优先，内置表兜底（仅补仓库里没有的原文）。

    返回 (merged dict, 仓库条数)。仓库值是权威译文，可被人工改写。
    """
    try:
        store_tbl = zhstore.get(zhstore.KERNEL_SOURCE)
    except Exception as e:
        sys.stderr.write('[kernel-src] 读取词条仓库失败(%s)，仅用内置表\n' % e)
        store_tbl = {}
    merged = dict(SOURCE_TRANSLATIONS)
    merged.update(store_tbl)          # 仓库覆盖内置
    return merged, len(store_tbl)


def find_kernel():
    """定位内核 claude.exe（取最新版本目录中 mtime 最新的一个）。"""
    base = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Claude-3p', 'claude-code')
    best = None
    if os.path.isdir(base):
        for ver in os.listdir(base):
            vd = os.path.join(base, ver)
            if not os.path.isdir(vd):
                continue
            for h in os.listdir(vd):
                p = os.path.join(vd, h, 'claude.exe')
                if os.path.isfile(p):
                    mt = os.path.getmtime(p)
                    if best is None or mt > best[1]:
                        best = (p, mt)
    return best[0] if best else None


def load_log():
    if os.path.isfile(LOG):
        try:
            return json.load(io.open(LOG, encoding='utf-8'))
        except Exception:
            pass
    return {}


def save_log(log):
    if not os.path.isdir(BAK_DIR):
        os.makedirs(BAK_DIR)
    io.open(LOG, 'w', encoding='utf-8').write(
        json.dumps(log, ensure_ascii=False, indent=1))


def restore(data, log):
    """按日志把偏移处的字节写回英文原文，返回还原处数。"""
    n = 0
    for en, rec in log.items():
        nb = en.encode('latin-1', 'replace')
        for off in rec.get('offsets', []):
            try:
                data[off:off + len(nb)] = nb
                n += 1
            except Exception:
                pass
    return n


def main():
    if not acquire_lock(wait=300, force=('--restore' in sys.argv)):
        print('[kernel-src] 另一实例正在打补丁，本次跳过（下轮自愈会重试）')
        return 0
    try:
        return _main_locked()
    finally:
        release_lock()


def _main_locked():
    do_restore = '--restore' in sys.argv
    kernel = find_kernel()
    if not kernel:
        print('[kernel-src] 未找到 claude.exe 内核，跳过')
        return 0

    log = load_log()
    data = bytearray(open(kernel, 'rb').read())

    if do_restore:
        n = restore(data, log)
        if n:
            open(kernel, 'wb').write(bytes(data))
        try:
            os.remove(LOG)
        except OSError:
            pass
        print('[kernel-src] 已还原 %d 处源码补丁' % n)
        return 0

    # 1) 先还原旧补丁（幂等 & 译文可更新）
    restored = restore(data, log) if log else 0

    # 2) 取翻译表（词条仓库优先，内置表兜底）
    table, n_store = load_translations()

    # 3) 应用补丁（等长替换）
    # 护栏（v2.6）：只补丁「前一个字节是引号/反引号」的出现点，即 JS 字符串字面量。
    # 原因：同一英文串也会出现在 Bun 字符串表（8 位 Latin-1 条目）和内嵌 SKILL.md
    # 区域中；往那些地方写 UTF-8 中文会被按 Latin-1 解码成乱码（security-review
    # tooltip 乱码事故，2026-10-16）。字符串表条目统一交给 translate-kernel.py 的
    # 8->16 位转换通道处理，两个模块各司其职。
    QUOTE_BYTES = (b'"', b"'", b'`')
    new_log = {}
    applied = {}          # 实际生效的 原文->译文，用于回写仓库
    ok = miss = overflow = skipped_nonliteral = 0
    for en, zh in table.items():
        nb = en.encode('latin-1', 'replace')
        b = zh.encode('utf-8')
        if len(b) > len(nb):
            print('[kernel-src][超长] %r 译文 %d 字节 > 原文 %d 字节'
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
            if i > 0 and bytes(data[i - 1:i]) in QUOTE_BYTES:
                offs.append(i)
            else:
                skipped_nonliteral += 1
            i += 1
        if not offs:
            miss += 1
            continue
        for o in offs:
            data[o:o + len(nb)] = new
        new_log[en] = {'offsets': offs, 'zh': zh}
        applied[en] = zh
        ok += 1

    if ok or restored:
        open(kernel, 'wb').write(bytes(data))
    save_log(new_log)

    # 4) 回写词条仓库：本次真正生效的译文落盘，下次直接复用（无需重翻）
    if applied:
        try:
            st = zhstore.upsert_many(zhstore.KERNEL_SOURCE, applied,
                                     origin='kernel-scan')
            zhstore.save(silent=True)
            if st['added'] or st['updated']:
                print('[kernel-src] 词条仓库: 新增 %d，更新 %d（仓库 %d 条）'
                      % (st['added'], st['updated'], zhstore.count(
                          zhstore.KERNEL_SOURCE)))
        except Exception as e:
            sys.stderr.write('[kernel-src] 词条回写失败(不影响补丁): %s\n' % e)

    print('[kernel-src] %s | 替换 %d 条（共 %d 处），未命中 %d，超长跳过 %d，'
          '非字面量跳过 %d 处 | 仓库词条 %d 条'
          % ('已更新' if ok else '无需更改', ok,
             sum(len(v['offsets']) for v in new_log.values()), miss, overflow,
             skipped_nonliteral, n_store))
    return 0


if __name__ == '__main__':
    sys.exit(main())
