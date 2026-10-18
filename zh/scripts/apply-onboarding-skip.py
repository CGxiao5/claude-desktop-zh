# -*- coding: utf-8 -*-
r"""
跳过 Claude Code 初次安装确认——在 ~/.claude.json 根对象写入 hasCompletedOnboarding=true。

说明：
  - 该字段由 Claude Code CLI（命令行 claude，含桌面版内嵌的 Code 功能）在首次启动时检查，
    为 true 则跳过“选择主题 + 选择登录方式”的引导向导。
  - 仅增量写这一个字段：文件不存在则新建；已存在则解析后覆盖/新增该键，
    其余字段与结构完整保留；写出为 UTF-8 无 BOM 的合法 JSON。
  - 本步骤只跳过引导，不提供凭据；也不影响 Claude for Windows 桌面版主界面的登录流程。

生命周期（由调用方决定，本脚本只做写入）：
  - 安装/更新汉化：install-zh.ps1 [7i] 调用本脚本。
  - 仅卸载汉化：不读取、不修改、不删除该文件。
  - 彻底卸载：由 Claude汉化.cmd 随用户数据一并删除该文件。

退出码：0=已写入/已存在无需修改  1=失败（JSON 非法、根不是对象、IO 错误等）
"""
import json
import os
import sys

TARGET = os.path.join(os.environ.get('USERPROFILE') or os.path.expanduser('~'), '.claude.json')
KEY = 'hasCompletedOnboarding'


def log(msg):
    print('[onboarding] %s' % msg)


def main():
    root = {}
    if os.path.exists(TARGET):
        try:
            # utf-8-sig：容忍带 BOM 的已有文件；写出时统一为 UTF-8 无 BOM
            with open(TARGET, 'r', encoding='utf-8-sig') as f:
                root = json.load(f)
        except ValueError as e:
            log('错误：%s 不是合法 JSON（%s），为避免破坏原有内容未做修改。' % (TARGET, e))
            return 1
        except OSError as e:
            log('错误：读取 %s 失败：%s' % (TARGET, e))
            return 1
        if not isinstance(root, dict):
            log('错误：%s 的 JSON 根必须是对象，为避免破坏原有内容未做修改。' % TARGET)
            return 1
        if root.get(KEY) is True:
            log('已存在 %s=true，无需修改。' % KEY)
            return 0

    root[KEY] = True
    tmp = TARGET + '.tmp-zh'
    try:
        # 先写临时文件再替换，避免写入中途失败损坏原有 .claude.json
        with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(root, f, ensure_ascii=False, indent=2)
            f.write('\n')
        os.replace(tmp, TARGET)
    except OSError as e:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass
        log('错误：写入 %s 失败：%s' % (TARGET, e))
        return 1
    log('已写入 %s：%s=true（其余字段保留）。' % (TARGET, KEY))
    return 0


if __name__ == '__main__':
    sys.exit(main())
