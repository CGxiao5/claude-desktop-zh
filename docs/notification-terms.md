# Claude 系统通知文案 · 中英对照词条表

> 适用范围：Claude Desktop（MSIX）+ Claude Code 内核 **2.1.299**（`f0584be0fbaf`）
> 更新日期：2026-10-18 ｜ 词条均已入 `zh/resources/translations/zh-store.json`
>
> 截图所示的 Windows toast（标题为会话名，如 “Model capabilities overview”，正文
> “Claude is waiting for your input”）由 **Claude Code 内核 `claude.exe`** 发出：
> 内核把 `{message, notificationType}` 交给桌面端，桌面端再以系统通知形式弹出。
> 因此正文文案走 **内核字符串表补丁**（`kernel-table` 命名空间，等长替换），
> 标题是会话名（用户数据），不翻译。

---

## 一、内核通知词条（本次新增 11 条，已打补丁）

| # | 英文原文 | 中文译文 | 适用场景（notificationType） | 变量占位符 |
|---|---|---|---|---|
| 1 | `Claude is waiting for your input` | Claude 正在等待你的输入 | 空闲提醒：任务完成或回合结束后等待用户继续输入（`idle_prompt`） | 无 |
| 2 | `Claude needs your permission to use ` | Claude 请求你允许使用 ➊ | 权限请求：Claude 要使用某个工具前征求许可（`permission_prompt`） | 后缀拼接 `${tool}`（工具名，如 Bash、Edit） |
| 3 | `Claude Code login successful` | Claude 登录成功 ➋ | 登录成功（`auth_success`） | 无 |
| 4 | `Claude Code login needs attention: credentials may not have been saved` | Claude Code 登录需要注意：凭据可能未保存 | 登录凭据写入失败（临时性，`auth_storage_failure`） | 无 |
| 5 | `Claude Code login needs attention: credentials could not be saved` | Claude Code 登录需要注意：凭据未能保存 | 登录凭据写入失败（`auth_storage_failure`） | 无 |
| 6 | `Claude is done using your computer` | Claude 已停止使用电脑 | 计算机操作（Computer Use）回合结束（`computer_use_exit`） | 无 |
| 7 | ` needs your input` |  需要你的输入 ➌ | 后台/并行会话被阻塞等待输入（`agent_needs_input`） | 前缀拼接 `${label}`（会话/任务标题） |
| 8 | ` needs your input: ` |  需要输入：➌ | 同上，但附带阻塞原因摘要（`agent_needs_input`） | 前缀 `${label}`；后缀 `${reason}`（截断的阻塞原因） |
| 9 | ` needs permission for ` |  请求使用权限： | 后台工作线程请求工具权限（`worker_permission_prompt`） | 前缀 `${worker}`（工作线程名）；后缀 `${tool}` |
| 10 | ` needs network access to ` |  请求网络访问： | 会话请求访问某个网络主机 | 前缀 `${name}`；后缀 `${host}` |
| 11 | `(unnamed tool)` | （未命名工具） | 工具名缺失时的占位显示（配合第 9 条） | 无 |

**注解**

- ➊ 原文以空格结尾，译文同样保留尾部空格，拼接后显示为「Claude 请求你允许使用 Bash」。
- ➋ 受等长槽位限制（原文 28 字节 → 槽位 14 码元），「Claude Code 登录成功」（16 码元）
  放不下，故译作「Claude 登录成功」。语义影响极小：该通知本身就由 Claude Code 发出。
- ➌ 这是**后缀片段**（模板 `` `${label} needs your input` `` 的 literal 部分），
  译文的词序是「任务名 + 需要你的输入」，在通知里读作「XX 任务 需要你的输入」。

**长度约束（重要）**：内核字符串表为等长替换，槽位容量 =
`align4(原文字节数) / 2`（码元）。上表译文已全部通过校验（最短富余 1 码元，
最富余 10 码元）。修改译文时不得超过槽位，否则补丁脚本会跳过该条并打印
`[kernel][溢出]`。

---

## 二、前端已收录的通知类文案（`fe-val` 命名空间，随词表部署生效）

以下为桌面端界面内与「任务完成 / 等待处理」相关的既有词条，无需内核补丁，
供对照参考（译文以仓库为准，此处为快照）：

| 英文原文 | 中文译文 | 适用场景 | 变量占位符 |
|---|---|---|---|
| `Claude finished a task` | Claude 完成了一个任务 | 任务完成提示 | 无 |
| `Claude finished and is waiting for your input.` | Claude 已完成，正在等待你的输入。 | 任务完成后的状态提示 | 无 |
| `Claude finished in the chat without replying here.` | Claude 已在聊天中完成，但没有在这里回复。 | 跨会话完成提示 | 无 |
| `Claude finished in your Claude Code session without replying here.` | Claude 已在你的 Claude Code 会话中完成，但没有在这里回复。 | Claude Code 会话完成提示 | 无 |
| `Claude is asking you to choose between options.` | Claude 正在要求你在多个选项之间做出选择。 | 等待用户选择 | 无 |
| `Claude is asking: {question} Send your message to respond.` | Claude 正在询问：{question} 发送消息即可回应。 | 等待用户回答 | `{question}` |
| `Claude is asking: {name} Find it just before the message box.` | Claude 正在询问：{name} 它就在输入框上方。 | 指引用户找到提问位置 | `{name}` |
| `Flash the taskbar button when Claude needs your attention and the app isn't focused.` | 当 Claude 需要你注意而应用未处于焦点状态时，闪烁任务栏按钮。 | 设置项：任务栏闪烁提醒 | 无 |

---

## 三、暂不处理的内核通知（附原因）

| 英文原文 / 片段 | 场景 | 不处理原因 |
|---|---|---|
| `` `${label} failed` `` / `` `${label} finished` ``（`agent_completed`） | 后台任务失败/完成通知 | `failed` / `finished` 是**逻辑共用常量**（与状态判断 `outcome==="failure"` 等共用字符串表项），改写会破坏内核逻辑，风险不可接受 |
| `Elicitation response for server "${e}": ${action}`（`elicitation_response`） | MCP 服务器征询响应 | 模板碎片化（`"`、`": ` 等碎片无法单独成句），按槽位译不出自然中文 |
| `MCP server "${Q}" confirmed elicitation ${id} complete`（`elicitation_complete`） | MCP 征询完成确认 | 同上；前缀 `MCP server "` 槽位仅 8 码元，放不下「MCP 服务器 "」（9 码元） |
| 插件自定义通知（`plugin_notification`） | 插件经 `$.ui.notify` 发出的文本 | 文案由插件运行时动态生成，无静态词条可译 |
| 推送通知正文（`push_notification`） | 移动端推送 | 正文为动态消息内容，非固定词条 |
| toast 通知的**粗体标题**（如 “Model capabilities overview”） | 所有内核通知 | 标题 = 会话/任务名，属用户数据，不做翻译 |

---

## 四、维护与扩展指南

**新增 / 修改通知词条的标准流程**

1. 把词条写入 `zh/resources/translations/zh-store.json` 的 `kernel-table` 命名空间
   （推荐用 `zhstore.upsert_many(..., origin='manual')`，勿直接手改 JSON）。
2. **先停服务再写入**：`Claude_zh` 服务进程会缓存词条仓库并在每次内核重打补丁时
   整库回写。若服务运行中改仓库，旧缓存会覆盖你的修改（2026-10-18 实测确认）。
   顺序：`zh_service.py stop` → 改仓库 → 跑补丁 → `zh_service.py start`。
3. 同步 `zh/scripts/translate-kernel.py` 的 `TRANSLATIONS` 兜底表（保持两份一致）。
4. 运行补丁：`zh\python\python.exe zh\scripts\translate-kernel.py`，
   确认输出中「未命中 / 溢出跳过」均为 0（未命中 = 该原文在当前内核版本不存在）。
5. 校验译文长度：`len(译文) ≤ align4(len(原文 Latin-1 字节)) / 2`。

**排查清单**

- 通知仍是英文 → 先看 `zh\tools\verify_state.py installed`，再看
  `%USERPROFILE%\.claude\zh\backup\kernel-patch-log.json` 是否包含该词条。
- Claude Code 内核自动更新后通知回退英文 → 服务会在 10 秒轮询内重打补丁；
  若新版本新增了通知文案，需按上面流程补词条。
