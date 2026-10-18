# -*- coding: utf-8 -*-
"""
Claude Code 内核（claude.exe）斜杠命令描述汉化补丁。

原理：
  桌面端斜杠菜单 tooltip 的命令描述来自内核 Bun 可执行文件中的字符串表
  （非 i18n 词表）。字符串表条目格式：
      u32  长度头：bit31=1 表示 8 位(Latin-1)条目，长度为字节数；
                   bit31=0 表示 16 位(UTF-16LE)条目，长度为码元数
      u32  哈希（运行时未校验，原样保留）
      data 字符串数据（8 位 = Latin-1 字节 / 16 位 = UTF-16LE）
      pad  零填充到 4 字节对齐

  8 位条目无法表示中文（实测直接写 UTF-8 会被按 Latin-1 解码成乱码），
  因此补丁将条目原地转换为 16 位条目，并保持条目总尺寸不变：
      新码元数 = align4(原字节数) / 2     （8 位 -> 16 位）
      新码元数 = 原码元数                 （16 位 -> 16 位）
  中文译文不足部分用空格补齐（tooltip 中尾部空格不可见）。

幂等：补丁日志记录在 %LOCALAPPDATA%\\claude-zh-hans\\backup\\kernel-patch-log.json，
每次运行先按日志还原旧补丁，再重新应用，因此可安全重复执行。
卸载：uninstall-zh.ps1 调用本脚本 --restore 还原全部补丁。
"""
import io
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import zhstore

# ---------------- 翻译表：英文原文 -> 中文译文 ----------------
# 原文来自内核命令注册表（thinClientDispatch / type:"local" / menuDescription 对象）
TRANSLATIONS = {
 # 与词条仓库 kernel-table 命名空间同步（仓库为唯一真相源，本表为兜底）
 # ---- 系统通知文案（toast / os_notification，2026-10-18 增补）----
 " needs network access to ":
   " 请求网络访问：",
 " needs permission for ":
   " 请求使用权限：",
 " needs your input":
   " 需要你的输入",
 " needs your input: ":
   " 需要输入：",
 " tool script (script API and gotchas, resume, quality patterns, worked examples). Load before authoring a script for a workflow the user already opted into; it does not itself authorize running one.":
   "工具脚本的参考（脚本 API 与注意事项、恢复、质量模式、示例）。为用户已选择启用的工作流编写脚本前加载；它本身并不授权运行工作流。",
 "(removed) Ask Claude to create/manage subagents, or edit .claude/agents/":
   "（已移除）创建/管理子智能体，或编辑 .claude/agents/",
 "); with no level given, it reuses the level you typed last. Pass --comment to post findings as inline PR comments, or --fix to apply the findings to the working tree after the review. Pass --max-findings <n> to report up to n findings, or --max-findings all for every finding. The choice stays until you pass --max-findings default.":
   "）；未指定等级时沿用你上次输入的等级。传 --comment 将发现作为 PR 行内评论发布，或传 --fix 在审查后把修复应用到工作区。传 --max-findings <n> 最多报告 n 条发现，或 --max-findings all 报告全部。该选择保持有效，直到你传入 --max-findings default。",
 "(unnamed tool)":
   "（未命名工具）",
 ": from few high-confidence findings up to many, some of them uncertain":
   "：从少量高置信发现到大量发现（部分不确定）",
 "Activate pending plugin changes in the current session":
   "在当前会话中激活待生效的插件更改",
 "Add a new working directory":
   "添加新的工作目录",
 "Adjust mouse wheel scroll speed":
   "调整鼠标滚轮滚动速度",
 "Answer questions about Claude Code features and settings":
   "解答 Claude Code 功能和设置相关问题",
 "Ask a quick side question without interrupting the main conversation":
   "快速提一个顺带的问题，不打断主对话",
 "Author or improve the run-<unit> skill - a per-project skill that tells agents how to build, launch, and drive this project's app. Use when the user asks to set up the project, get it running, write run instructions, or verify build/run steps work from a clean environment.":
   "编写或改进 run-<unit> 技能——一种每项目技能，告诉智能体如何构建、启动并运行本项目的应用。当用户要求搭建项目、让它跑起来、编写运行说明，或验证干净环境下构建/运行步骤可用时使用。",
 "Authorize design-system access for /design-sync with your claude.ai account":
   "用 claude.ai 账号授权 /design-sync 访问设计系统",
 "Automates your Chrome browser to interact with web pages - clicking elements, filling forms, capturing screenshots, reading console logs, and navigating sites. Opens pages in new tabs within your existing Chrome session. Requires site-level permissions before executing (configured in the extension).":
   "自动操作你的 Chrome 浏览器与网页交互——点击元素、填写表单、截取屏幕、读取控制台日志和浏览网站。在你现有的 Chrome 会话中以新标签页打开页面。执行前需站点级权限（在扩展中配置）。",
 "Browse running and completed workflows":
   "浏览运行中和已完成的工作流",
 "Browse your published and shared artifacts":
   "浏览你已发布和分享的工件",
 "Build a design together, one decision at a time":
   "一起构建设计，一次一个决策",
 "Build and debug apps that use the Claude API":
   "构建和调试使用 Claude API 的应用",
 "Change settings: hooks, permissions, environment variables":
   "更改设置：钩子、权限、环境变量",
 "Change the theme":
   "更改主题",
 "Chart and dashboard design guidance":
   "图表与仪表盘设计指南",
 "Choose the default environment for cloud agents":
   "选择云智能体的默认环境",
 "Choose whether cloud sessions use the plugins enabled on this machine":
   "选择云端会话是否使用本机启用的插件",
 "Claude Code login needs attention: credentials could not be saved":
   "Claude Code 登录需要注意：凭据未能保存",
 "Claude Code login needs attention: credentials may not have been saved":
   "Claude Code 登录需要注意：凭据可能未保存",
 "Claude Code login successful":
   "Claude 登录成功",
 "Claude is done using your computer":
   "Claude 已停止使用电脑",
 "Claude is waiting for your input":
   "Claude 正在等待你的输入",
 "Claude needs your permission to use ":
   "Claude 请求你允许使用 ",
 "Clean up the changed code without changing behavior":
   "在不改变行为的前提下清理改动的代码",
 "Complete a security review of the pending changes on the current branch":
   "完成对当前分支待提交更改的安全审查",
 "Configure optional break reminders and quiet-hours nudges":
   "配置可选的休息提醒和安静时段提示",
 "Configure the auto-compact window size":
   "配置自动压缩上下文窗口大小",
 "Configure usage credits or request them from your admin when you hit a limit":
   "配置用量额度，或在达到上限时向管理员申请",
 "Continue the current session in Claude Desktop":
   "在 Claude 桌面版中继续当前会话",
 "Copy Claude's last response to clipboard (or /copy N for the Nth-latest)":
   "复制最近回复到剪贴板（/copy N 为倒数第 N 条）",
 "Copy this conversation into a new background session and keep working here":
   "将此对话复制到新的后台会话，并在此继续工作",
 "Create a branch of the current conversation at this point":
   "在当前位置为对话创建分支",
 "Create a git commit":
   "创建 git 提交",
 "Create a pull request":
   "创建 Pull 请求",
 "Create a skill that knows how to run this project’s app":
   "创建一个知道如何运行本项目应用的技能",
 "Create and manage routines: cloud agents on a schedule":
   "创建和管理例程：按计划运行的云智能体",
 "Deep research harness — fan-out web searches, fetch sources, adversarially verify claims, synthesize a cited report.":
   "深度研究工具——并行展开网页搜索、抓取来源、对结论做对抗性核验，最终综合成一份带引用的报告。",
 "Diagramming guidance for Artifacts":
   "工件的图表绘制指南",
 "Discover Claude Code features through quick interactive lessons":
   "通过快速互动课程了解 Claude Code 功能",
 "Dump the JS heap to the Desktop; on Linux with no Desktop folder, the home directory":
   "将 JS 堆转储到桌面；Linux 无桌面文件夹时转储到主目录",
 "Edit CLAUDE.md files and memory settings":
   "编辑 CLAUDE.md 文件和记忆设置",
 "Embed reusable components in an Artifact":
   "在工件中嵌入可复用组件",
 "Enable debug logging for this session and help diagnose issues":
   "为本会话启用调试日志以帮助诊断问题",
 "Enable plan mode or view the current session plan":
   "启用计划模式或查看当前会话计划",
 "Execute a server-launched workflow handoff (workflow_launch event sessions only)":
   "执行服务器启动的工作流交接（仅限 workflow_launch 事件会话）",
 "Export the current conversation to a file or clipboard":
   "导出当前对话到文件或剪贴板",
 "Free up context by summarizing the conversation so far":
   "通过总结当前对话来释放上下文",
 "Generate a one-line session recap now":
   "立即生成一行会话回顾",
 "Generate a report analyzing your Claude Code sessions":
   "生成一份 Claude Code 会话分析报告",
 "Grant Claude agent access to your Design projects":
   "授予 Claude 访问 Design 项目的权限",
 "Guided setup — pick a role, install a plugin, try a skill, connect tools":
   "引导式设置——选择角色、安装插件、试用技能、连接工具",
 "Health-check the user's Claude Code setup and fix issues: diagnose installation health — what the `claude doctor` terminal diagnostics cover — from local data (duplicate or leftover installs, PATH, unparseable settings files, broken or colliding agent definitions, skills whose frontmatter fails to parse); find unused skills, MCP servers, and plugins versus their context cost and disable dead weight; deduplicate local CLAUDE.md files against checked-in ones; trim checked-in CLAUDE.md files by cutting content a session could derive from the codebase (directory layouts, tech-stack lists, architecture overviews) while keeping gotchas, rationale, and non-standard conventions; migrate always-loaded CLAUDE.md guidance into lazy skills and nested CLAUDE.md files; flag slow hooks and context-heavy extensions; check the installed version is current; make auto mode the default permission mode; and pre-approve frequently denied read-only commands. Use when the user asks for a doctor run, checkup, audit, tune-up, or cleanup of their Claude Code setup or configuration.":
   "体检用户的 Claude Code 配置并修复问题：从本地数据诊断安装健康状况——即 `claude doctor` 终端诊断所覆盖的内容（重复或残留的安装、PATH、无法解析的设置文件、损坏或冲突的智能体定义、frontmatter 解析失败的技能）；找出未使用的技能、MCP 服务器和插件，对照其上下文开销，禁用累赘；对照已入库的 CLAUDE.md 去除本地重复；精简已入库的 CLAUDE.md，删掉会话可自行从代码库推导的内容（目录结构、技术栈清单、架构概述），保留坑点、缘由和非标准约定；把常驻加载的 CLAUDE.md 指导迁移为惰性加载的技能和嵌套 CLAUDE.md 文件；标记缓慢的钩子和占用上下文多的扩展；检查已装版本是否最新；把 auto 模式设为默认权限模式；预先批准频繁被拒的只读命令。当用户要求运行 doctor、体检、审计、调优或清理其 Claude Code 配置时使用。",
 "Health-check your setup and fix issues: installation, unused extensions, duplicated or bloated memory files, slow hooks, updates, permissions":
   "检查配置健康状况并修复：安装、未使用的扩展、重复或臃肿的记忆文件、缓慢的钩子、更新、权限",
 "Help teammates ramp on Claude Code with a guide from your usage":
   "按使用情况生成指南，帮助团队上手 Claude Code",
 "Import config from another AI coding agent":
   "从其他 AI 编程智能体导入配置",
 "Initialize a new CLAUDE.md file with codebase documentation":
   "初始化新的 CLAUDE.md 文件，写入代码库文档",
 "Install Claude Code native build":
   "安装原生构建版本",
 "Install the Claude Slack app":
   "安装 Slack 应用",
 "Launch and drive this project's app to see a change working. Use when asked to run, start, or screenshot the app, or to confirm a change works in the real app (not just tests). First looks for a project skill that already covers launching the app; otherwise falls back to built-in patterns per project type (CLI, server, TUI, Electron, browser-driven, library).":
   "启动并运行本项目的应用，实际查看改动效果。当被要求运行、启动或截图应用，或确认改动在真实应用（而不仅是测试）中生效时使用。先查找已覆盖应用启动的项目技能；否则按项目类型（CLI、服务器、TUI、Electron、浏览器驱动、库）回退到内置模式。",
 "Launch this project’s app to see your change working":
   "启动本项目的应用以查看改动效果",
 "Let Claude browse and interact with pages in your Chrome":
   "让 Claude 在你的 Chrome 中浏览网页并交互",
 "Let Claude consult a stronger model at key moments":
   "让 Claude 在关键时刻咨询更强的模型",
 "List available skills":
   "列出可用技能",
 "List output styles or switch to one":
   "列出输出风格或切换",
 "List subagents, teammates, and other Claude sessions you can message":
   "列出可发消息的子智能体、队友和其他 Claude 会话",
 "List, create, and delete loops":
   "列出、创建和删除循环任务",
 "Listen to Claude FM lo-fi radio":
   "收听 Claude FM 电台",
 "Load the reference for writing Workflow tool scripts":
   "加载编写 Workflow 工具脚本的参考",
 "Make a mod: a change to Claude's own interface or behaviour, such as a live pane or panel, a band above the prompt, a status line, a toast, a slash command, or a hook on tool calls or prompts. Use to make, change or debug a mod or its hooks module.":
   "制作 mod：修改 Claude 自身的界面或行为，如实时窗格/面板、输入框上方横幅、状态栏、toast 提示、斜杠命令，或工具调用与提示词的钩子。用于创建、修改或调试 mod 及其 hooks 模块。",
 "Manage Claude Code plugins":
   "管理插件",
 "Manage IDE integrations and show status":
   "管理 IDE 集成并显示状态",
 "Manage MCP servers":
   "管理 MCP 服务器",
 "Manage allow and deny tool permission rules":
   "管理工具权限的允许和拒绝规则",
 "Manage background services and routines":
   "管理后台服务和例程",
 "Manage usage limits and upgrade options":
   "管理用量限制和升级选项",
 "Monitor and autofix any issues with the current PR":
   "监视并自动修复当前 PR 的问题",
 "Move this session to a new working directory":
   "将会话移动到新的工作目录",
 "Open Claude in Chrome settings":
   "打开 Chrome 扩展设置",
 "Open settings":
   "打开设置",
 "Open your keyboard shortcuts file":
   "打开键盘快捷键文件",
 "Options shown when the Pro plan Claude Code trial has ended":
   "Pro 套餐 Claude Code 试用结束时显示的选项",
 "Order Claude Code stickers":
   "订购贴纸",
 "Pair on a whiteboard artifact — you draw, Claude answers on it":
   "在白板工件上协作——你来画，Claude 在上面作答",
 "Pick up skills added or changed on disk during this session":
   "加载本会话期间磁盘上新增或修改的技能",
 "Plan a large change; background agents each open a PR":
   "规划大型变更；后台智能体各自提交 PR",
 "Plugin authoring: Claude knows how a plugin of function hooks is written, typed and debugged against this build":
   "插件编写：Claude 知道如何针对当前构建编写、类型化并调试由函数钩子组成的插件",
 "Pre-approve safe read-only commands based on your usage":
   "根据你的使用情况预先批准安全的只读命令",
 "Print the version this session is running (not what autoupdate downloaded)":
   "打印本会话正在运行的版本（而非自动更新下载的版本）",
 "Prototype an idea as a working Artifact":
   "把一个想法原型化为可运行的工件",
 "Publish a PR review briefing Artifact from a template":
   "从模板发布 PR 审查简报工件",
 "Publish a data-table Artifact from a template":
   "从模板发布数据表工件",
 "Publish a report Artifact from a template":
   "从模板发布报告工件",
 "Publish a working document Artifact":
   "发布工作文档工件",
 "Publish an explainer Artifact from a template":
   "从模板发布讲解工件",
 "Push your design system components to claude.ai/design":
   "推送设计系统组件到 claude.ai/design",
 "Reconfigure Amazon Bedrock authentication, region, or model pins":
   "重新配置 Amazon Bedrock 认证、区域或模型固定",
 "Reconfigure Google Vertex AI authentication, project, region, or model pins":
   "重新配置 Google Vertex AI 认证、项目、区域或模型固定",
 "Reference for the Claude API / Anthropic SDK — model ids, pricing, params, streaming, tool use, MCP, agents, caching, token counting, model migration.":
   "Claude API / Anthropic SDK 参考——模型 ID、定价、参数、流式传输、工具使用、MCP、智能体、缓存、token 计数、模型迁移。",
 "Reference for writing a ":
   "编写",
 "Rename the current conversation":
   "重命名当前对话",
 "Renamed to /usage-credits":
   "/usage-credits",
 "Repeat a prompt or command on an interval (e.g. /loop 5m /foo)":
   "按间隔重复执行提示词或命令（如 /loop 5m /foo）",
 "Report a bug or share your conversation":
   "报告问题或分享你的对话",
 "Research and plan a large-scale change, then execute it in parallel across 5–30 isolated worktree agents that each open a PR.":
   "研究并规划大规模变更，然后由 5–30 个隔离的 worktree 智能体并行执行，各自提交 PR。",
 "Restore the code and/or conversation to a previous point":
   "将代码和/或对话恢复到之前的时间点",
 "Resume a previous conversation":
   "继续之前的对话",
 "Review the changed code for reuse, simplification, efficiency, and altitude cleanups, then apply the fixes. Quality only — it does not hunt for bugs; use /code-review for that.":
   "审查改动代码的复用、简化、效率与风格清理，然后应用修复。仅做质量——不查找缺陷；查缺陷请用 /code-review。",
 "Review the current diff or a PR for bugs and cleanups":
   "审查当前 diff 或 PR 中的问题与可清理之处",
 "Review the current diff, or a PR number/branch/path target, for correctness bugs (plus reuse/simplification/efficiency cleanups where the model's review recipe covers them) at the given effort level (":
   "审查当前 diff 或指定的 PR 号/分支/路径目标，查找正确性缺陷（并附带模型审查配方覆盖的复用/简化/效率清理），按指定努力等级（",
 "Revoke Claude agent access to your Design projects":
   "撤销 Claude 访问 Design 项目的权限",
 "Run a prompt or slash command on a recurring interval (e.g. /loop 5m /foo). Omit the interval to let the model self-pace.":
   "按固定间隔重复运行提示词或斜杠命令（如 /loop 5m /foo）。省略间隔则让模型自行把握节奏。",
 "Run the workflow script delivered in this session environment (server-launched sessions only)":
   "运行在此会话环境中下发的工作流脚本（仅限服务器启动的会话）",
 "Runtime capabilities for published Artifacts":
   "已发布工件的运行时能力",
 "Scan your transcripts for common read-only Bash and MCP tool calls, then add a prioritized allowlist to project .claude/settings.json to reduce permission prompts.":
   "扫描对话记录，找出常用的只读 Bash 与 MCP 工具调用，把按优先级排序的允许清单写入项目的 .claude/settings.json，以减少权限提示。",
 "See where this session’s tokens went, in plain words":
   "用通俗的语言查看本会话的 token 去向",
 "Send a subagent off with your full context; its result comes back here":
   "派出携带完整上下文的子智能体，其结果会返回到这里",
 "Send feedback to Anthropic or report a bug":
   "向 Anthropic 发送反馈或报告问题",
 "Send this session to the background and free the terminal":
   "将本会话转入后台并释放终端",
 "Send this session to the cloud, or resume one from claude.ai":
   "将本会话发送到云端，或从 claude.ai 恢复",
 "Set a goal Claude checks before stopping":
   "设置 Claude 停止前要检查的目标",
 "Set a goal — keep working until the condition is met":
   "设定目标——持续工作直到条件满足",
 "Set a setting by key":
   "按键名设置配置项",
 "Set effort level for model usage":
   "设置模型使用的努力等级",
 "Set how full the context gets before auto-summarizing":
   "设置上下文达到多少时自动总结",
 "Set the AI model for Claude Code":
   "设置 AI 模型",
 "Set the prompt bar color for this session":
   "设置本会话输入栏的颜色",
 "Set the terminal UI renderer (default | fullscreen)":
   "终端渲染器（default|fullscreen）",
 "Set up Claude GitHub Actions for a repository":
   "为仓库配置 GitHub Actions",
 "Set up cloud sessions with your GitHub account":
   "用你的 GitHub 账号设置云端会话",
 "Show Claude Code status including version, model, account, API connectivity, and tool statuses":
   "显示 Claude Code 状态：版本、模型、账号、API 连通性和工具状态",
 "Show QR code to download the Claude mobile app":
   "显示下载 Claude 移动应用的二维码",
 "Show cloud session URL and QR code":
   "显示云端会话 URL 和二维码",
 "Show current context usage":
   "显示当前上下文用量",
 "Show help and available commands":
   "显示帮助和可用命令",
 "Show session cost and plan usage":
   "显示会话费用和套餐用量",
 "Show session cost, plan usage, and activity stats":
   "显示会话费用、套餐用量和活动统计",
 "Show session cost, plan usage, and what's contributing to your limits":
   "显示会话费用、套餐用量及限额构成",
 "Show this session's version (autoupdate may have a newer one)":
   "显示本会话的版本（自动更新可能已有更新版本）",
 "Show which loaded skills are unused and costing context":
   "显示哪些已加载技能未使用且占用上下文",
 "Sign out from your Anthropic account":
   "退出你的 Anthropic 账号",
 "Spawn a background agent that inherits the full conversation":
   "派生一个继承完整对话的后台智能体",
 "Start a new session with empty context; previous session stays on disk (resumable with /resume)":
   "以空上下文开始新会话；之前的会话保留在磁盘上（可用 /resume 恢复）",
 "Stop this background session; transcript and worktree are kept":
   "停止此后台会话；对话记录和 worktree 会保留",
 "TRIGGER when: user asks how Claude Code works (\"Can Claude…\", \"Does Claude…\", \"How do I…\", \"Is there a way to…\"); user asks about a slash command, CLI flag, settings key, hook, skill, MCP server, subagent, keybinding, or .claude/ directory; user wants to configure, customize, or troubleshoot Claude Code; user asks about Claude in Slack or Claude Tag (\"what is Claude Tag\", \"can Claude live in Slack\", \"@Claude in Slack\", \"/install-slack-app\", \"set up Claude for my Slack workspace\"); YOU are about to recommend a Claude Code slash command, flag, or setting and have not verified it exists in this build.\n":
   "触发时机：用户询问 Claude Code 的用法（“Claude 能…”“Claude 支持…”“怎么…”“有没有办法…”）；用户询问斜杠命令、CLI 参数、设置项、钩子、技能、MCP 服务器、子智能体、快捷键或 .claude/ 目录；用户想配置、定制或排查 Claude Code；用户询问 Slack 中的 Claude 或 Claude Tag（“什么是 Claude Tag”“Claude 能进驻 Slack 吗”“在 Slack 里 @Claude”“/install-slack-app”“为我的 Slack 工作区配置 Claude”）；你正准备推荐本构建中的 Claude Code 斜杠命令、参数或设置，但尚未验证它存在。",
 "TRIGGER — read BEFORE opening the target file; don't skip because it \"looks like a one-liner\" — whenever: the prompt names Claude/Anthropic in any form (Claude, Anthropic, Fable, Opus, Sonnet, Haiku, `anthropic`, `@anthropic-ai`, `claude-*`, `us.anthropic.*`, `[1m]`); the user asks about an LLM (pricing/model choice/limits/caching) — never answer from memory; OR the task is LLM-shaped with provider unstated (agent/MCP/tool-definition/multi-agent/RAG/LLM-judge/computer-use; generate/summarize/extract/classify/rewrite/converse over NL; debugging refusals/cutoffs/streaming/tool-calls/tokens).":
   "触发——打开目标文件前先读它；别因为它“看起来像一行的活”就跳过——以下情况：提示词以任何形式点名 Claude/Anthropic（Claude、Anthropic、Fable、Opus、Sonnet、Haiku、`anthropic`、`@anthropic-ai`、`claude-*`、`us.anthropic.*`、`[1m]`）；用户询问 LLM 相关问题（定价/模型选择/限额/缓存）——绝不凭记忆回答；或任务形如 LLM 任务但未指明提供方（agent/MCP/工具定义/多智能体/RAG/LLM 评审/computer-use；对自然语言做生成/摘要/抽取/分类/改写/对话；调试拒答/截断/流式/工具调用/token）。",
 "Teach auto mode about your environment, plus optional rule tweaks":
   "向自动模式介绍你的环境，并可选择性调整规则",
 "Toggle brief-only mode":
   "切换仅简报模式",
 "Toggle focus view: just your prompt, summary, and response":
   "切换专注视图：仅显示你的输入、摘要和回复",
 "Toggle voice mode":
   "切换语音模式",
 "Turn on debug logging and investigate problems":
   "开启调试日志并排查问题",
 "Upgrade to Max for higher rate limits and more Opus":
   "升级到 Max 以获得更高速率限制和更多 Opus",
 "Use this skill to configure the Claude Code harness via settings.json. Automated behaviors (\"from now on when X\", \"each time X\", \"whenever X\", \"before/after X\") require hooks configured in settings.json - the harness executes these, not Claude, so memory/preferences cannot fulfill them. Also use for: permissions (\"allow X\", \"add permission\", \"move permission to\"), env vars (\"set X=Y\"), hook troubleshooting, or any changes to settings.json/settings.local.json files. Examples: \"allow npm commands\", \"add bq permission to global settings\", \"move permission to user settings\", \"set DEBUG=true\", \"when claude stops show X\". For simple settings like theme/model, suggest the /config command.":
   "用本技能通过 settings.json 配置 Claude Code 运行框架。自动化行为（“从现在起当 X”“每次 X”“每当 X”“X 之前/之后”）需要在 settings.json 中配置钩子——由框架执行而非 Claude，记忆/偏好无法实现它们。还用于：权限（“允许 X”“添加权限”“移动权限到”）、环境变量（“set X=Y”）、钩子排错，或对 settings.json/settings.local.json 的任何修改。例如：“allow npm commands”“把 bq 权限加到全局设置”“移动权限到用户设置”“set DEBUG=true”“claude 停止时显示 X”。主题/模型这类简单设置，建议用 /config 命令。",
 "Use this skill whenever you are about to create ANY chart, graph, plot, dashboard, or data visualization, in ANY output medium — an HTML or React artifact, inline SVG, plotting code in any library (matplotlib, plotly, d3, Recharts, …), an image/PNG you will render and upload, or a chart shared into Slack. Read it BEFORE writing the first line of chart code, choosing chart colors, building a stat tile / meter / KPI row, or laying out a dashboard. When the destination is a first-party document connector (host-designated, never self-described) that renders live charts, hand it the rows (inline, or as an uploaded data file the chart cites) rather than a rendered PNG/SVG — a picture of a chart loses hover, data inspection and per-value comments. Produces visualizations that read as one system — elegant, accessible, consistent in light and dark — using a brand-neutral placeholder palette you swap for your own. Teaches a design-system-agnostic method: a form heuristic, a color formula with a runnable validator, mark specs, and interaction rules. A validated default palette is documented in `references/palette.md` — swap that file's values for your brand's. Triggers on: \"chart\", \"graph\", \"plot\", \"data viz\", \"visualization\", \"dashboard\", \"analytics\", \"visualize data\", \"categorical colors\", \"sequential / diverging palette\", \"stat tile\", \"sparkline\", \"heatmap\", \"legend\", \"axis\", \"tooltip\", \"chart colors\", \"color by series\".":
   "每当你要创建任何图表、曲线、绘图、仪表盘或数据可视化时使用本技能——无论输出介质是 HTML/React 工件、内联 SVG、任何绘图库代码（matplotlib、plotly、d3、Recharts、…）、将要渲染上传的图片/PNG，还是分享到 Slack 的图表。在写第一行图表代码、挑选图表配色、构建指标卡/仪表/KPI 行或布局仪表盘之前，先读它。当目标是能渲染动态图表的第一方文档连接器（由宿主指定，绝不自封）时，把数据行交给它（内联，或作为图表引用的上传数据文件），而不是渲染好的 PNG/SVG——图表截图会丢失悬停、数据查看和逐值评论。产出的可视化读起来像同一套系统——优雅、可访问、明暗主题一致——使用品牌中立的占位色板，你可换成自己的品牌色。教授与设计系统无关的方法：形态启发式、带可运行校验器的配色公式、标记规范与交互规则。经验证的默认色板记录在 `references/palette.md`——把该文件的值换成你的品牌色。触发词：\"chart\"\"graph\"\"plot\"\"data viz\"\"visualization\"\"dashboard\"\"analytics\"\"visualize data\"\"categorical colors\"\"sequential / diverging palette\"\"stat tile\"\"sparkline\"\"heatmap\"\"legend\"\"axis\"\"tooltip\"\"chart colors\"\"color by series\"。",
 "Verify that a code change actually does what it's supposed to by exercising it end-to-end and observing behavior — drive the affected flow, not just tests or typecheck. Run before committing nontrivial changes; bootstraps this repo's project verify skill if none exists yet. Don't invoke it on a diff that only touches tests, docs, or other code with no runtime surface to drive (a change to product source always has one) — there's nothing to observe.":
   "通过端到端实际运行并观察行为，验证代码改动确实达到预期——驱动受影响的流程，而不仅是测试或类型检查。提交非琐碎改动前运行；本仓库还没有项目级 verify 技能时会引导创建。不要对只涉及测试、文档或其他无运行面可驱动代码的 diff 使用它（产品源码的改动总有运行面）——那样没有可观察的东西。",
 "View and manage everything running in the background":
   "查看和管理后台运行的一切",
 "View and update your privacy settings":
   "查看和更新你的隐私设置",
 "View hook configurations for tool events":
   "查看工具事件的钩子配置",
 "View release notes":
   "查看版本说明",
 "Visualize current context usage as a colored grid":
   "以彩色网格可视化当前上下文用量",
 "Write a mod: a live pane, view or behaviour change in Claude Code":
   "编写 mod：Claude Code 的实时窗格、视图或行为变更",
}

BAK_DIR = os.path.join(os.environ.get('USERPROFILE', ''), '.claude', 'zh', 'backup')
LOG = os.path.join(BAK_DIR, 'kernel-patch-log.json')
LOCK = LOG + '.lock'
LOCK_STALE = 120       # 残留锁超过 2 分钟且持锁进程已死，可接管


def _pid_alive(pid):
    """Windows 下判定 PID 是否存活（无 psutil 依赖）。

    OpenProcess 失败（可能无权限）时返回 None=未知，由调用方按锁龄兜底。
    """
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
    """跨进程互斥：防止两个实例并发读改写同一内核二进制、互相覆盖补丁日志。

    实测竞态（2026-10-15）：安装脚本直启的实例 A 补丁完成并写入日志后，
    守护进程 boot 自检的实例 B 以空日志快照读到 A 已补丁的二进制（全部
    miss、ok=0），save_log({}) 把还原日志覆盖为空，卸载从此无法还原内核。

    force=True（卸载 --restore）：卸载前已停止守护进程，残留锁必属死进程，
    直接接管。普通路径：持锁进程已死立即接管；未知/存活则等待至超时。
    """
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
                # 持锁进程确认已死 → 立即接管（沙箱/崩溃残留）
                # 状态未知（无权限判定）→ 按锁龄兜底
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
    """词条仓库优先，内置 TRANSLATIONS 兜底（仅补仓库里没有的原文）。

    译文的唯一真相源是统一词条仓库（zhstore.KERNEL_TABLE）；本文件的
    TRANSLATIONS 退化为首次 seed 的兜底。返回 (merged, 仓库条数)。
    """
    try:
        store_tbl = zhstore.get(zhstore.KERNEL_TABLE)
    except Exception as e:
        sys.stderr.write('[kernel] 读取词条仓库失败(%s)，仅用内置表\n' % e)
        store_tbl = {}
    merged = dict(TRANSLATIONS)
    merged.update(store_tbl)          # 仓库覆盖内置
    return merged, len(store_tbl)


def find_kernel():
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


def align4(n):
    return (n + 3) & ~3


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
    io.open(LOG, 'w', encoding='utf-8').write(json.dumps(log, ensure_ascii=False, indent=1))


def restore(data, log, strict=True):
    """按日志还原补丁。strict=True（卸载）仅还原与当前译文精确匹配的表项；
    strict=False（重装前幂等）还原任何含中文的 16 位表项。返回还原条数。"""
    n = 0
    for en, rec in log.items():
        off = rec['offset']
        zh = TRANSLATIONS.get(en)
        try:
            cur_hdr = struct.unpack_from('<I', data, off - 8)[0]
        except struct.error:
            continue
        if cur_hdr >> 31 != 0:
            continue
        cur_units = cur_hdr & 0x7FFFFFFF
        cur = bytes(data[off:off + cur_units * 2])
        try:
            cur_text = cur.decode('utf-16-le').rstrip(' ')
        except UnicodeDecodeError:
            continue
        if strict:
            if zh is None or cur_text != zh:
                continue
        else:
            if not any('一' <= c <= '鿿' for c in cur_text):
                continue
        payload = bytes.fromhex(rec['orig_payload_hex'])
        struct.pack_into('<I', data, off - 8, rec['orig_header'])
        data[off:off + len(payload)] = payload
        n += 1
    return n


def find_entry(data, en):
    """在字符串表中定位条目，返回 (payload_offset, orig_header, slot_units, is16) 或 None。"""
    # 16 位条目（原文含非 Latin-1 字符）
    try:
        en.encode('latin-1')
        is_latin1 = True
    except UnicodeEncodeError:
        is_latin1 = False

    if not is_latin1:
        needle = en.encode('utf-16-le')
        start = 0
        while True:
            i = data.find(needle, start)
            if i < 0:
                return None
            # 表项头部在命中点前 8 字节；命中落在文件头 8 字节内说明不是真表项，
            # 直接跳过，避免负偏移让 struct 抛 error。
            if i < 8:
                start = i + 1
                continue
            hdr = struct.unpack_from('<I', data, i - 8)[0]
            if hdr >> 31 == 0 and (hdr & 0x7FFFFFFF) == len(en):
                return (i, hdr, len(en), True)
            start = i + 1
    else:
        needle = en.encode('latin-1')
        start = 0
        while True:
            i = data.find(needle, start)
            if i < 0:
                return None
            # 同上：头部在命中点前 8 字节，命中过前则跳过
            if i < 8:
                start = i + 1
                continue
            hdr = struct.unpack_from('<I', data, i - 8)[0]
            if hdr >> 31 == 1 and (hdr & 0x7FFFFFFF) == len(needle):
                return (i, hdr, align4(len(needle)) // 2, False)
            start = i + 1


def main():
    if not acquire_lock(wait=300, force=('--restore' in sys.argv)):
        print('[kernel] 另一实例正在打补丁，本次跳过（下轮自愈会重试）')
        return 0
    try:
        return _main_locked()
    finally:
        release_lock()


def _main_locked():
    do_restore = '--restore' in sys.argv
    kernel = find_kernel()
    if not kernel:
        print('[kernel] 未找到 claude.exe 内核，跳过')
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
        print('[kernel] 已还原 %d 条内核补丁' % n)
        return 0

    # 1) 先还原旧补丁（幂等 & 译文更新）
    restored = restore(data, log, strict=False) if log else 0

    # 2) 取翻译表（词条仓库优先，内置表兜底）
    table, n_store = load_translations()

    # 3) 应用新补丁
    new_log = {}
    applied = {}          # 实际生效的 原文->译文，用于回写仓库
    ok = miss = overflow = 0
    for en, zh in table.items():
        found = find_entry(data, en)
        if not found:
            miss += 1
            continue
        off, hdr, slot_units, _is16 = found
        if len(zh) > slot_units:
            print('[kernel][溢出] %r 译文 %d 码元 > 槽位 %d' % (en[:40], len(zh), slot_units))
            overflow += 1
            continue
        zh_padded = zh + ' ' * (slot_units - len(zh))
        payload_orig = bytes(data[off:off + align4((hdr & 0x7FFFFFFF) * (1 if hdr >> 31 else 2))])
        new_log[en] = {
            'offset': off,
            'orig_header': hdr,
            'orig_payload_hex': payload_orig.hex(),
        }
        struct.pack_into('<I', data, off - 8, len(zh_padded))
        payload = zh_padded.encode('utf-16-le')
        data[off:off + len(payload)] = payload
        # 槽位剩余部分清零（保持总尺寸不变）
        slot_bytes = len(payload_orig)
        if len(payload) < slot_bytes:
            data[off + len(payload):off + slot_bytes] = b'\x00' * (slot_bytes - len(payload))
        applied[en] = zh
        ok += 1

    if ok or restored:
        open(kernel, 'wb').write(bytes(data))
    save_log(new_log)

    # 4) 回写词条仓库：本次真正生效的译文落盘，下次直接复用（无需重翻）
    if applied:
        try:
            st = zhstore.upsert_many(zhstore.KERNEL_TABLE, applied,
                                     origin='kernel-scan')
            zhstore.save(silent=True)
            if st['added'] or st['updated']:
                print('[kernel] 词条仓库: 新增 %d，更新 %d（仓库 %d 条）'
                      % (st['added'], st['updated'],
                         zhstore.count(zhstore.KERNEL_TABLE)))
        except Exception as e:
            sys.stderr.write('[kernel] 词条回写失败(不影响补丁): %s\n' % e)

    print('[kernel] %s | 补丁 %d 条，未命中 %d，溢出跳过 %d（内核: %s）| 仓库词条 %d 条'
          % ('已更新' if ok else '无需更改', ok, miss, overflow,
             os.path.basename(os.path.dirname(kernel)), n_store))
    return 0


if __name__ == '__main__':
    sys.exit(main())
