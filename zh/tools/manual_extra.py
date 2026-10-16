# -*- coding: utf-8 -*-
# 遗漏词条补充（新版 2.37337 核对）
# KEY_EXTRA: key->zh（含 XML 富文本标签，必须保留标签）
KEY_EXTRA = {
 'WUR4bhePMC': 'Claude 会在本账号及你所有关联账号的 Cowork 任务中记住这些内容（遵循 <aupLink>Anthropic 的使用准则</aupLink>）。<learnMoreLink>了解更多</learnMoreLink>',
 'pXnYFOsv9N': 'Claude 会在本账号及你所有关联账号的聊天和 Cowork 中记住这些内容（遵循 <aupLink>Anthropic 的使用准则</aupLink>）。<learnMoreLink>了解更多</learnMoreLink>',
 # 2.31226 中同一文案拆成两个 key
 'S1V7Bqgbot': 'Claude 会在本账号及你所有关联账号的聊天和 Cowork 中记住这些内容（遵循 <aupLink>Anthropic 的使用准则</aupLink>）。<learnMoreLink>了解更多</learnMoreLink>',
 'cQ0opg4YW1': 'Claude 会在本账号及你所有关联账号的聊天和 Cowork 中记住这些内容（遵循 <aupLink>Anthropic 的使用准则</aupLink>）。<learnMoreLink>了解更多</learnMoreLink>',
 '/SxZnig+Bp': '允许组织成员的云端会话和计划任务在其自己的计算机上使用文件、应用和浏览器。从该计算机的桌面应用驱动的会话不受影响。<learnMoreLink>了解更多</learnMoreLink>',
 'WnDvs+LpZm': '允许你的团队从 claude.ai 或 Claude 移动应用控制其计算机上的 Cowork。这些会话可以访问用户计算机上的文件、工具和应用。<learnMoreLink>了解更多</learnMoreLink>',
 'y0GI3NWj2U': '启用后，用户可以让 Claude 自行批准操作，而不是逐项批准——包括使用工具、编辑文件和浏览网站。对于看起来不安全的操作 Claude 会暂停，但 Claude 可能出错。<learnMoreLink>了解更多</learnMoreLink>',
 'uaFXq4QaAu': '允许成员在批准连接器工具时选择“始终允许”。仅适用于可执行更改的工具；只读工具不受此设置影响。这会增加提示注入风险——来自已连接应用的内容可能导致 Claude 未经逐次批准就执行意外操作。<learnMoreLink>了解更多</learnMoreLink>',
 'HXx+J2ojkF': '允许使用你的聊天和编码会话来训练和改进 Anthropic AI 模型。可随时在隐私设置中更改。<learnMoreLink>了解更多</learnMoreLink>',
 'zI4J/bY/sY': '允许使用你的聊天和编码会话来训练和改进 Anthropic AI 模型。<learnMoreLink>了解更多</learnMoreLink>。',
 '/79dwa2C+/': '启用企业合规 API 访问以审计你组织的数据。<learnMoreLink>了解更多</learnMoreLink>',
 'kJZO/LuHF7': '请记得保持计算机唤醒，以便 Claude 继续工作。<learnMoreLink>了解更多</learnMoreLink>',
 '4JFJ+9M97K': 'Cowork 通过 Claude Agent SDK 复用 <docsLink>Claude Code 的 OTel 事件模式</docsLink>。<learnMoreLink>了解更多</learnMoreLink>',
 'fXcHTYDnkk': '<learnMoreLink>了解更多</learnMoreLink>，并阅读<termsLink>《消费者条款》</termsLink>和<privacyLink>《隐私政策》</privacyLink>。',
 # 用量卡片复数格式（2.31226）
 'g7jGYqiRbd': '{searches, plural, one {# 次网页搜索} other {# 次网页搜索}}',
 # 主界面输入框与推荐提示词（2.31226 补译）
 'uSmGqlwE3c': '输入 / 使用技能',
 'gcRrwu3vv4': '输入以筛选',
 'eW2z9yczDM': '安排一份每日简报，在我每天早上开始工作前送达。询问我简报的信息来源：今天的日程、邮件中的紧急事项、我被 @ 的消息，以及我关注的新闻。确认我的时区和要包含的内容，连接所需的应用，并在上线前给我看一份样例。\n\n如果你无法访问我的邮件或日程，先弄清楚我有哪些应用，然后帮我连接。',
 '4L99FK3dkq': '帮我把收件箱整顿起来。先给我一幅概览：未读有多少、积压了多久、主要来源是什么（订阅邮件、促销、通知、真人来信）。\n\n在开始整理之前，先问我希望怎么分类——哪些类别或标签合适、哪些我可以放心归档或删除、哪些发件人我一定想看到。\n\n从最旧的开始清理，因为最容易处理。先给我看你打算归档、删除或标记待回复的样例，让我确认你的判断，然后再批量处理。方案确定后再处理其余的——并且永久删除任何内容之前都要先问我。\n\n如果你无法访问我的邮箱，先帮我连接再开始。',
 # 代码标签页（2.31226 补译）
 '2p0s2iqc26': '你发起的会话将显示在这里',
 '56tkBC2SRR': '你发起的会话将显示在这里。',
 'QyOfAD0vTP': '你发起的会话将显示在这里。',
 'sIl97ARhWm': '描述要构建、修改或修复的内容',
 'Vqv6GUqbKO': '接受编辑',
 'VsPyVYphMe': '编辑侧边栏…',
 'fT4qk5uaS4': '编辑侧边栏',
 'gEzUzVupQI': '引导式设置——选择角色、安装插件、试用技能、连接工具',
 # 代码页斜杠命令描述（cc183b3ab defineMessages，42 条）
 'gANOfDo9W8': '创建可按需运行或按间隔自动运行的例程。',
 '0jPoCTWaT8': '创建可按需运行或按间隔自动运行的计划任务。',
 '4Iu0xDY9v4': '快速提一个顺带的问题，不计入本会话',
 'im+fV1gXT4': '为此仓库启动远程 Ultrareview 会话',
 'qp1Y3ko7m2': '将会话回退到之前的某条消息',
 'PLA5A7IBXa': '将会话分叉为一个新会话',
 'i1j0okYTaw': '管理 MCP 连接器',
 'H6wXnXH4FN': '管理本会话的 MCP 服务器',
 'wpALlbVBy7': '管理 Claude Code 插件',
 'NoJhhT4ajs': '浏览和管理你的技能',
 'ROWC/dVxTx': '发送反馈、报告问题或分享你的会话',
 'Dd2QGejip9': '设置本会话使用的模型',
 'vDC8hqKsFP': '切换到计划模式或查看本会话的计划',
 'wF1YXSRX2h': '设置本会话的输出风格',
 'TtDrZ3njdX': '重命名本会话',
 'lf3xK1KDea': '导出本会话的对话记录',
 'h4Tq920W/Z': '向本会话添加另一个文件夹',
 'O5XKAMPRrM': '将会话移动到新的工作目录',
 'BymdttQBa1': '显示或隐藏本会话的更改',
 '+vginKit6A': '显示本会话的后台任务',
 'EZHj/2HRyC': '浏览工作流历史（运行中和已完成）',
 'dzgwMMQIZP': '显示套餐用量和速率限制',
 '59puvF+dPg': '显示当前上下文用量',
 'ZALmAPCYUa': '编辑 CLAUDE.md 文件',
 'Vyi4mf5XUR': '打开 Claude Code 设置',
 'HKLQHn0B96': '查看 Claude 在这台计算机上占用的空间',
 'haKQrKfVRA': '打开 Claude Code 沙箱设置',
 'kXktj/cq6M': '设置外观（跟随系统、浅色或深色）',
 'IilZDLM33s': '重新加载插件并刷新可用命令',
 'udZRja1msR': '重置本地速率限制计数器',
 'ACsVE4t8Jz': '为本会话的分支创建 Pull 请求',
 'RgZ+JdaERH': '保存诊断日志包并打开 Slack 讨论串进行分享',
 'EdGhWN5pVT': '搜索并继续这台计算机上的 Claude Code 会话',
 'StnyicIZMN': '显示本会话的版本、模型、环境和账户信息',
 'VHP1V5Y2tY': '让 Claude 在关键时刻咨询更强的模型',
 'V5xsNvc+al': '更改权限模式',
 'ahsycWoxUQ': '设置本会话的努力等级',
 '1Iil9SAPHl': '开启或关闭快速模式',
 'sLN5P3cZhl': '打开用量设置',
 'ntBDs3AvHQ': '显示上下文用量或设置自动压缩的运行时机',
 'scfgdMgq4h': '重新登录',
 '+lafIY3KZt': '获取帮助与支持',
 '66djAf//ud': '自定义命令',
 # 全量扫描补译（89 条：思考/努力等级、插件窗格、GitHub 关联、订阅权益等）
 'Xft0R8xbIB': '低',
 'Zk4EtKw26K': '最高',
 'PLBs+fqKwX': '关',
 'oAk189A0OS': '快速',
 'vv9L/MN3/H': '高',
 'HoZQmASaw3': '额外',
 'U0mtsR78v2': '中',
 'u8fFNy1Mu4': '即时',
 'Xads8RoR+/': '默认',
 'x+I9oPD9kV': '查看原文',
 'NKydG2KArY': '扩展',
 'c42Iq1UBqb': '扩展',
 'B4Nw7coGbc': '自适应',
 'DvRKnnUSOG': '思考',
 '4RgMF5iUDm': '扩展',
 'tbBYqyBUY2': '查看文档',
 'S++WdBsywt': '阅读更多',
 'TJnVJ3CHzT': 'Ant 工具',
 'EpijVevLzK': '快速模式',
 '6eNkKSj+Er': '网页搜索',
 'mQRd+O9jEI': '组织默认',
 'Rve6Z5dM8k': '更多用量*',
 'BKT2LjX3Eg': '插件窗格',
 'XKN3/Spkmz': '低严重度',
 'ZBZfPQICJV': '高严重度',
 '2qTZeZCPue': '分析工具',
 '2EcGZn58SU': '自动思考',
 'Tg5Z1QfYcl': '中严重度',
 'GJvQ9rNcBs': '信任并继续',
 '6EhWLLZwj4': '启用快速模式',
 'JxRTAGj5OB': '更多 Opus 用量*',
 'moevKg1AkV': '严重',
 '+8cwUXE6h1': '插件已关闭',
 'u8n5HzNZ2R': '扩展思考',
 'BDqDM65MnU': '自适应思考',
 'QimMWHgE5g': '立即回复',
 'Zyu/cxL2/B': '使用量额度',
 'PaYY/OvJOl': '暂无内容',
 'UMxXdoFjbT': '插件状态行',
 'QQ2UzmdmNN': '轻量、日常任务',
 '0gtp5o1nEE': '复杂、细致的工作',
 'w+qTzeepxX': '适合大多数场景',
 'n6XZvuhMVT': '快速作答最快',
 'Ztf14WwmNM': '日常工作的均衡之选',
 '8iuHf335Ey': '始终使用深度推理',
 'eAZhflTduv': '按复杂度匹配思考',
 'Yrtr74Rv+h': '应对最棘手的挑战',
 'MnpOJUobxY': '为更复杂的任务进行思考',
 'aWuhH8qI9/': '复杂任务思考更久',
 'kT2330ZLic': '重置体验数据失败',
 'LCyVJcnXTZ': '能力最强，适合高难度工作',
 'g8BKYKpvDv': '可为更复杂的任务思考',
 'EGP6HJPOg+': '简单任务最高效',
 'zdSx1K4VL2': '快速回答简单问题',
 '4EGZ/Kv9qH': '日常任务最高效',
 '3m6ScQimzr': '暂时无法关联 {login}。',
 'message_limit_benefit_thinking': '复杂工作的扩展思考',
 'LBtx8hNe6d': '{plugin} 未在此窗格中绘制',
 '4N8a6wReLf': '最适合数学与编程挑战',
 'XBURx2a572': '适合复杂工作与日常任务',
 'oLD1YKsL8P': '最难的问题，耗时最长。',
 'message_limit_benefit_code': '在终端中直接使用 Claude Code',
 'Uwm8gE/+aB': '地址过多，请移除一些后再保存。',
 'KOD/IAe2tu': '更新你的回答失败，请重试。',
 'message_limit_benefit_tools': '可使用研究、网页搜索等工具',
 'QlSw2Nct6O': '你的 IP 不在 GitHub 上 {login} 的允许列表中。',
 '29OLd9bgWw': 'Opus 比其他模型更快消耗用量限制',
 'WwXweMd3IE': '连接 Google Workspace：邮箱、日历和文档',
 'message_limit_benefit_models': '完整使用包括 Opus 在内的最新 Claude 模型',
 'nLwKxPdeCy': 'Claude 现在正忙，请稍等片刻再发送。',
 'HMHhwuzWtx': '你需要是 GitHub 上 {login} 的所有者才能关联。',
 'message_limit_benefit_workspace': '集成 Google Workspace：邮箱、日历和文档',
 'uK9wA9v6Z3': '可创建无限个项目来整理聊天和文档',
 'G67k4TIVtW': 'GitHub 拒绝了 Claude 对你 {login} 访问权限的检查。',
 'AKAFVoLnAA': '这是 {login} 的个人账号——只有本人可以关联。',
 'GoDyM43G4X': 'Claude 会在适当时候利用其网络访问能力来改进回答。',
 'WgLvyohS4F': '发送未成功。你的消息未保存——请重新发送。',
 'JG92nyhvYS': '暂时无法验证你对 {login} 的访问权限，请稍后再试。',
 'cwcAx4UDp5': 'Tab 键用于插入缩进。先按 Esc 再按 Tab 可将焦点移出编辑器。',
 'rqMp86Ar1w': '{count, plural, one {更多插件状态行} other {更多插件状态行}}',
 'dapWFrcWv4': '更高的努力等级意味着更详尽的回复，但耗时更长、更快消耗你的限额。',
 'sA9kR2u6VC': 'Claude 可以编写并运行代码来处理数据、执行分析并实时生成数据可视化。',
 'NJGpN24jdm': 'Claude Code 设置，按其 settings.json 的格式书写，用于此处没有独立设置项的配置。',
 'N+VJI9Z0SU': '上传 CSV，让 Claude 高精度分析定量数据并创建交互式数据可视化。',
 'dbhS3u7cD8': '由于未完成的语音对话导致草稿被重置，文件附件已被移除。请重新添加附件。',
 'RaZ/cp/eey': '可能消耗大量 token，导致响应时间过长并触及 token 上限。请仅在最棘手的任务中谨慎使用。',
 'cG9QCAO7ln': '无法重置此项的服务器曝光记录——仅清除了本地状态。如果该体验仍被过滤，请使用下方的「重置所有体验数据」按钮。',
 'hahKOhzAYF': 'Claude 可以搜索互联网，以提供更新、更相关的回答。当话题需要最新信息时，Claude 会自动决定是否使用网页搜索。网页搜索仅在使用 Claude 3.7 Sonnet 时可用。',
 'dMakafR5Ag': '此环境尚不支持按体验重置服务器状态——仅清除了本地状态。有服务器端冷却或曝光限制的体验仍会被过滤。在按体验重置的接口部署前，请使用下方的「重置所有体验数据」按钮清除服务器状态。',
 # ---- 第二层斜杠命令描述（19 张截图逐项核对，来自前端 bundle 命令注册表）----
 # shared-5 命令注册表（init/review/compact/clear/context/recap/design/dataviz/verify/debug/simplify/run）
 'D8v4Vi6GRc': '审查当前 diff 或 PR，找出缺陷与可清理之处',
 '9tazDfDBM8': '汇总到目前为止的会话内容，以释放上下文空间',
 'IQ1FZYI8vS': '在画布工件上起草设计——启用保存的位置可直接编辑（Claude Design 预览版）',
 'LpxYenaJGp': '图表与仪表盘设计指南',
 'uZAJy1Bwqa': '通过端到端实际运行并观察行为，验证某处代码改动确实做到了它应该做的事——要驱动受影响的流程，而不只是跑测试或类型检查。在提交重要改动前运行；如果本仓库还没有项目 verify 技能，会自动引导创建一个。如果改动只涉及测试、文档或其他没有可运行表面的代码，请不要调用（改动产品源码时总是有可运行表面）——因为那样没有可观察的东西。',
 'iZxcZQIRst': '开启调试日志并排查问题',
 '14WIoxAF6m': '在保持行为不变的前提下清理已改动的代码',
 'JAnU2017+t': '启动本项目的应用，实际查看改动效果',
 '2VMdt9XC8j': '用通俗的话说明本次会话的 token 都用在了哪里',
 'yu7aZ06YmQ': '会话导出失败。',
 # cc183b3ab 主命令注册表（43 条）
 'x1XndMSihP': '显示套餐用量与速率限制',
 '5B10ybRftQ': '从当前会话分叉出去处理一个子任务，而你自己留在原会话中',
 # ---- UI 自动化实测拾遗（读取窗口文本树发现的可见英文）----
 'y6s5jEXe/X': '部分命令未加载完成。请重新输入 / 再试一次。',
 'WB0Ad2QFAl': '隐藏侧边栏',
 'SqMSVyK3mX': '更多导航项',
 'q4rbzXJdqL': '调整侧边栏大小',
 'uxkiTeN6WU': '向 Claude 描述你的需求',
 'OPM183pkH6': '筛选最近会话并按分组显示',
 'OnsnuZtVJO': '添加文件、连接器等',
 # ---- 快速模式 / 用量（UIA 实测发现）----
 '9Vq9GCHhLi': '用量：{parts}',
 '+kYz1no3iT': '快速模式已关闭',
 '/F5UlmMv+P': '快速模式已关闭',
 'UDLD4Ypgpz': '快速模式已开启',
 '9ojXq4eRSB': '快速模式已处于开启状态。',
 'BCJLRHrfvy': '你的组织当前无法使用快速模式。',
 'lkXRh+mFJ4': '快速模式需要用量额度。请在<link>用量</link>中开启。',
 'EpijVevLzK': '快速模式',
}

# VAL_EXTRA: 英文值->zh（纯文本，按值复用到所有同值 key）
VAL_EXTRA = {
 'Prevent your computer from sleeping while a Code session is running, so long tasks can finish. Your display can still turn off. Closing the laptop lid will still put it to sleep.':
   '在 Code 会话运行期间阻止计算机进入睡眠，以便长任务完成。显示器仍可关闭；合上笔记本盖子仍会使其睡眠。',
 'Prevent your computer from idle-sleeping while Claude is open so scheduled tasks can run. Your display can still turn off. Closing the laptop lid will still put it to sleep.':
   '在 Claude 打开期间阻止计算机进入空闲睡眠，以便计划任务运行。显示器仍可关闭；合上笔记本盖子仍会使其睡眠。',
 'Automatically archive local sessions after a period of no activity. Sessions that are running or have background work are never archived, and a worktree with uncommitted changes is kept on disk.':
   '在一段时间无活动后自动归档本地会话。正在运行或有后台工作的会话不会被归档；有未提交更改的 worktree 会保留在磁盘上。',
 'Automatically archive desktop sessions when the associated pull request is merged or closed. Archiving also removes the session’s worktree and deletes its branch once the pull request is merged. Work that isn’t pushed is kept.':
   '当关联的 Pull 请求被合并或关闭时自动归档桌面会话。归档还会移除会话的 worktree，并在 Pull 请求合并后删除其分支。未推送的工作会保留。',
 'Automatically archive sessions when the associated pull request is merged.':
   '当关联的 Pull 请求被合并时自动归档会话。',
 'How Claude structures its responses in Code sessions. Applies to new sessions; the session menu can override it for a single session.':
   'Claude 在 Code 会话中组织回复的方式。适用于新会话；会话菜单可为单个会话覆盖此设置。',
 'Save cookies, local storage, and login sessions for Browser tabs across app restarts. Shared uses the same data for every session in a project. Per session gives each session its own copy, so sessions never see each other’s logins.':
   '在应用重启后为浏览器标签页保存 Cookie、本地存储和登录会话。“共享”让项目中的每个会话使用同一份数据；“按会话”为每个会话提供独立副本，会话之间看不到彼此的登录状态。',
 'The view sessions open in. Picking a view from a session’s Transcript view menu changes only that session.':
   '会话打开时使用的视图。从会话的“对话记录视图”菜单中选择视图仅影响该会话。',
 'Font for the whole interface — menus, sidebars, and panels.':
   '整个界面的字体——菜单、侧边栏和面板。',
 'When you trust a folder on this device, you allow Claude to use it and the folders inside it. Trusting a folder doesn’t add it to new tasks. When you add one to a task, you may be asked to allow it again.':
   '当你信任这台设备上的某个文件夹时，即允许 Claude 使用它及其内部的文件夹。信任文件夹不会将其加入新任务；当你把文件夹添加到任务时，可能会再次被要求允许。',
 'Delete chat?':
   '删除聊天？',
 'Delete file?':
   '删除文件？',
 'Delete folder?':
   '删除文件夹？',
 'Delete group?':
   '删除分组？',
 'Delete memory?':
   '删除记忆？',
 'Delete plugin?':
   '删除插件？',
 'Remove skill?':
   '移除技能？',
 'Remove plugin?':
   '移除插件？',
 'Remove access?':
   '移除访问权限？',
 'Save changes?':
   '保存更改？',
 'Save this file?':
   '保存此文件？',
 'Stop review?':
   '停止评审？',
 'Start a call?':
   '发起通话？',
 'Start a text?':
   '发起短信？',
 'Start an email?':
   '发起邮件？',
 'Archive thread?':
   '归档话题？',
 'Archive session?':
   '归档会话？',
 'Change effort?':
   '更改思考强度？',
 'Turn on skill?':
   '启用技能？',
 'Keep cookies?':
   '保留 Cookie？',
 'Delete your data':
   '删除你的数据',
 'Almost done!':
   '即将完成！',
 'Fix started.':
   '修复已开始。',
 'Run started.':
   '运行已开始。',
 'Run cancelled.':
   '运行已取消。',
 'Skill saved.':
   '技能已保存。',
 'Plugin saved.':
   '插件已保存。',
 'Plugin removed.':
   '插件已移除。',
 'Settings saved.':
   '设置已保存。',
 'Comment saved.':
   '评论已保存。',
 'Link copied.':
   '链接已复制。',
 'Request sent.':
   '请求已发送。',
 'New code sent.':
   '新验证码已发送。',
 'Sent to Claude.':
   '已发送给 Claude。',
 'Invite removed.':
   '邀请已移除。',
 'All answered.':
   '已全部回答。',
 'Not accepted.':
   '未接受。',
 'None allowed.':
   '不允许任何项。',
 'Already added.':
   '已添加。',
 'No changes yet.':
   '暂无更改。',
 'No sites match.':
   '没有匹配的站点。',
 'No activity yet.':
   '暂无活动。',
 'No comments yet.':
   '暂无评论。',
 'No issues found.':
   '未发现问题。',
 'No projects yet.':
   '暂无项目。',
 'No routines yet.':
   '暂无例程。',
 'No policy yet.':
   '暂无策略。',
 'No SSH hosts yet':
   '暂无 SSH 主机',
 'Not assigned yet':
   '尚未分配',
 'Still checking.':
   '仍在检查。',
 'Task not found.':
   '未找到任务。',
 'Group not found':
   '未找到分组',
 'Last turn failed':
   '上一轮失败',
 'Check back soon.':
   '请稍后查看。',
 'Try refreshing.':
   '请尝试刷新。',
 'Install Git.':
   '安装 Git。',
 'Enter a name.':
   '请输入名称。',
 'Enter a value.':
   '请输入一个值。',
 'Name and groups.':
   '名称与分组。',
 'Click to edit.':
   '点击编辑。',
 'Click to view.':
   '点击查看。',
 'Drag to reorder.':
   '拖动以重新排序。',
 'Host key changed':
   '主机密钥已更改',
 'Host not trusted':
   '主机不受信任',
 'Not a skill file':
   '不是技能文件',
 'About this tool':
   '关于此工具',
 'Accept and open':
   '接受并打开',
 'Add Claude Tags':
   '添加 Claude 标签',
 'Add group member':
   '添加群组成员',
 'Add text content':
   '添加文本内容',
 'Add your comment':
   '添加你的评论',
 'Ask in side chat':
   '在侧边聊天中提问',
 'Chat and Cowork':
   '聊天与协作',
 'Choose per item':
   '逐项选择',
 'Copy public link':
   '复制公开链接',
 'Copy thread link':
   '复制话题链接',
 'Download the app':
   '下载应用',
 'Drop a file here':
   '将文件拖放到此处',
 'Enter your name':
   '输入你的姓名',
 'Exact text sent':
   '已发送的确切文本',
 'Exit full screen':
   '退出全屏',
 'Expand all files':
   '展开所有文件',
 'File read check':
   '文件读取检查',
 'Fill and arrange':
   '填充与排列',
 'Filter and sort':
   '筛选与排序',
 'Filter log lines':
   '筛选日志行',
 'For personal use':
   '供个人使用',
 'Give edit access':
   '授予编辑权限',
 'Hide full input':
   '隐藏完整输入',
 'Show full input':
   '显示完整输入',
 'Show all skills':
   '显示全部技能',
 'Show more lines':
   '显示更多行',
 'Show start page':
   '显示起始页',
 'Show your edits':
   '显示你的编辑',
 'See all history':
   '查看全部历史',
 'See all results':
   '查看全部结果',
 'Send a new code':
   '发送新验证码',
 'Skipped for now':
   '暂时跳过',
 'Invite your team':
   '邀请你的团队',
 'Keep working now':
   '立即继续工作',
 'Link GitHub App':
   '关联 GitHub 应用',
 'Load older lines':
   '加载更早的行',
 'Loading the item':
   '正在加载该项',
 'Log in with code':
   '使用验证码登录',
 'Looked for files':
   '已查找文件',
 'Make a task list':
   '创建任务列表',
 'Make key private':
   '将密钥设为私有',
 'Map my user flow':
   '梳理我的用户流程',
 'Mark all as read':
   '全部标为已读',
 'Match whole word':
   '全词匹配',
 'Memory file tree':
   '记忆文件树',
 'More you can add':
   '你还可以添加',
 'Most used skills':
   '最常用的技能',
 'Muted for a week':
   '静音一周',
 'Needs your input':
   '需要你的输入',
 'New Code session':
   '新建 Code 会话',
 'New output style':
   '新输出风格',
 'Next Browser tab':
   '下一个浏览器标签页',
 'Next sidebar tab':
   '下一个侧边栏标签页',
 'Nice work so far':
   '目前进展不错',
 'Open in new tab':
   '在新标签页打开',
 'Open model menu':
   '打开模型菜单',
 'Open setup page':
   '打开设置页面',
 'Plain .txt file':
   '纯 .txt 文件',
 'Ran page script':
   '已运行页面脚本',
 'Read the thread':
   '阅读话题',
 'Scroll past end':
   '滚动到末尾之后',
 'Tab key indents':
   'Tab 键缩进',
 'Turn off Cowork':
   '关闭协作',
 'Turn off plugin':
   '关闭插件',
 'View one by one':
   '逐个查看',
 'What do you do?':
   '你是做什么的？',
 'Who can comment':
   '谁可以评论',
 'Whole tool only':
   '仅限整个工具',
 'Why compact now':
   '为何现在压缩',
 'How is it doing?':
   '进展如何？',
 'About error rate':
   '关于错误率',
 'About the folder':
   '关于该文件夹',
 'About this label':
   '关于此标签',
 'About tool calls':
   '关于工具调用',
 'All new messages':
   '所有新消息',
 'Daily usage view':
   '每日用量视图',
 'Date range (UTC)':
   '日期范围（UTC）',
 'Month-end close':
   '月末结算',
 'More side chats':
   '更多侧边聊天',
 'Not enough data':
   '数据不足',
 'Total due today':
   '今日到期总额',
 'Light code theme':
   '浅色代码主题',
 'Invalid SSH host':
   '无效的 SSH 主机',
 'AWS bearer token':
   'AWS 持有者令牌',
 'Any host + auth':
   '任意主机 + 认证',
}
