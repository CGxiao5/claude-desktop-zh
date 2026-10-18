# -*- coding: utf-8 -*-
r"""
免登录网关配置（Claude Desktop 官方第三方推理 3P 模式）——安装写入 / 卸载还原。

依据（均为官方/社区公开资料，不触碰任何鉴权与安全校验逻辑）：
  - 官方文档 claude.com/docs/third-party/claude-desktop：
    * inferenceProvider="gateway" 即激活第三方推理模式；
    * disableDeploymentModeChooser=true 隐藏登录屏的 Claude.ai 登录选项，
      凭有效网关配置启动直达主界面（对应应用内「Skip login-mode chooser」）；
    * 本地配置目录 %LOCALAPPDATA%\Claude-3p\configLibrary\：
      _meta.json 记录当前应用的配置，每个配置为并列的 <id>.json。
  - 配置 ID 须为小写 UUID（/^[a-f0-9-]{36}$/，取自本版 app.asar 的校验逻辑）。

凭据来源（唯一且明确）：汉化包根目录 gateway.json（与 Claude汉化.cmd 同级），
由用户复制 gateway.example.json 并填入自己的网关地址与 API Key。
未提供则跳过本步骤（exit 3），保留官方登录流程，不算错误。

用法：
  python apply-gateway-config.py            # 安装：校验 -> 探测 -> 写入
  python apply-gateway-config.py --restore  # 卸载：按 install-context.json 还原
退出码：0=已写入/已还原/无需还原  3=未提供凭据或已有他人配置（跳过）  1=校验或还原失败
"""
import json
import os
import re
import sys

try:
    from urllib import request as urlreq, error as urlerr
except ImportError:
    # 汉化包内置的**精简** Python 运行时（zh/python）裁剪掉了整个 urllib 包
    # （与 uuid 同理），import 必然失败。URL 格式校验改由下面的 _url_scheme_host
    # 自行实现，不因缺库而失效；仅联网探测这一项可选能力随之关闭。
    urlreq = urlerr = None

PKG_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GW_FILE = os.path.join(PKG_ROOT, 'gateway.json')
ZH_HOME = os.path.join(os.path.expanduser('~'), '.claude', 'zh')
CTX_FILE = os.path.join(ZH_HOME, 'install-context.json')
META_BAK = os.path.join(ZH_HOME, 'backup', 'configLibrary-meta.json')
CFG_ID_RE = re.compile(r'^[a-f0-9-]{36}$')
PLACEHOLDER_RE = re.compile(r'<|YOUR_?API_?KEY|占位|示例|example\.com', re.I)


def log(msg):
    print('[gateway] %s' % msg)


def _url_scheme_host(u):
    """取 URL 的 (scheme, host)；不依赖 urllib。返回 ('','') 表示格式非法。

    精简运行时没有 urllib，而 URL 格式校验是写入凭据前的**安全校验**，不能
    因为环境缺库就跳过，因此按 RFC 3986 做本脚本够用的最小化解析。
    """
    m = re.match(r'^\s*([A-Za-z][A-Za-z0-9+.\-]*)://([^/?#]*)\s*$', u or '')
    if not m:
        return '', ''
    host = m.group(2)
    if '@' in host:                                  # 去掉 userinfo
        host = host.rsplit('@', 1)[1]
    if host.startswith('['):                         # IPv6: [::1]:8080
        idx = host.find(']')
        return (m.group(1).lower(), host[1:idx] if idx > 0 else '')
    return m.group(1).lower(), host.split(':', 1)[0]  # 去端口


def new_config_id():
    """生成配置 ID（36 位小写 UUID，形如 xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx）。

    刻意不用标准库 uuid 模块：本脚本运行于汉化包内置的**精简** Python 运行时
    （zh/python），该运行时裁剪掉了 uuid.py，import 会直接 ModuleNotFoundError
    导致整个免登录步骤失败。os.urandom 在任何运行时都可用。

    按 RFC 4122 置位版本号(4)与变体位(10x)，保证 ID 形态与官方生成的完全一致。
    """
    b = bytearray(os.urandom(16))
    b[6] = (b[6] & 0x0F) | 0x40
    b[8] = (b[8] & 0x3F) | 0x80
    h = b.hex()
    return '%s-%s-%s-%s-%s' % (h[0:8], h[8:12], h[12:16], h[16:20], h[20:32])


def find_config_library():
    """定位 configLibrary：优先官方默认 Claude-3p，其次任何已存在的 Claude* 副本。"""
    lad = os.environ.get('LOCALAPPDATA')
    if not lad:
        return None
    default = os.path.join(lad, 'Claude-3p', 'configLibrary')
    if os.path.isdir(os.path.dirname(default)):
        return default
    try:
        for name in sorted(os.listdir(lad)):
            cand = os.path.join(lad, name, 'configLibrary')
            if name.startswith('Claude') and os.path.isdir(cand):
                return cand
    except OSError:
        pass
    return default  # 目录尚不存在（首次启动前）：按官方默认路径创建


def probe_gateway(base, key, scheme):
    """GET {base}/v1/models 探测凭据有效性（官方模型发现端点）。
    返回 (状态码或 None, 说明)。base 结尾带 /v1 时自动兼容，不改动用户原值。"""
    if urlreq is None:
        return None, '运行时缺少 urllib，无法联网校验'
    b = base.rstrip('/')
    urls = [b + '/models'] if b.endswith('/v1') else [b + '/v1/models', b + '/models']
    headers = {'anthropic-version': '2023-06-01'}
    if scheme == 'x-api-key':
        headers['x-api-key'] = key
    else:
        headers['Authorization'] = 'Bearer ' + key
    last = None
    for u in urls:
        try:
            req = urlreq.Request(u, headers=headers)
            with urlreq.urlopen(req, timeout=8) as resp:
                return resp.status, u
        except urlerr.HTTPError as e:
            if e.code == 404:
                last = (404, u)
                continue
            return e.code, u
        except Exception as e:
            return None, '%s（%s）' % (u, e.__class__.__name__)
    return last or (None, '无可用探测地址')


def read_json(path):
    try:
        with open(path, encoding='utf-8-sig') as f:
            return json.load(f)
    except Exception:
        return None


def write_json(path, obj):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write('\n')


def apply():
    if not os.path.exists(GW_FILE):
        log('未找到 gateway.json，跳过免登录配置（启动后走官方登录流程）。')
        log('  如需启用：复制 gateway.example.json 为 gateway.json，填入网关地址与 API Key 后重装。')
        return 3
    gw = read_json(GW_FILE)
    if not isinstance(gw, dict):
        log('错误：gateway.json 不是合法的 JSON 对象，请对照 gateway.example.json 检查语法。')
        return 1

    base = str(gw.get('baseUrl') or '').strip()
    key = str(gw.get('apiKey') or '').strip()
    scheme = str(gw.get('authScheme') or 'bearer').strip()
    name = str(gw.get('name') or '汉化包网关').strip()
    models = gw.get('models')

    if not base:
        log('错误：gateway.json 缺少 baseUrl（网关地址，形如 https://gateway.example.com）。')
        return 1
    if PLACEHOLDER_RE.search(base):
        log('错误：baseUrl 仍是模板占位值（%r），请改为真实网关地址。' % base)
        return 1
    scheme_name, host = _url_scheme_host(base)
    if scheme_name not in ('http', 'https') or not host:
        log('错误：baseUrl 必须是 http(s):// 开头的完整地址，当前为 %r。' % base)
        return 1
    if not key:
        log('错误：gateway.json 缺少 apiKey。请填入网关真实 API Key。')
        return 1
    if PLACEHOLDER_RE.search(key):
        log('错误：apiKey 仍是模板占位符，请填入网关真实 API Key。')
        return 1
    if scheme not in ('bearer', 'x-api-key'):
        log('错误：authScheme 只支持 bearer 或 x-api-key，当前为 %r。' % scheme)
        return 1
    if models is not None and not (isinstance(models, list) and all(isinstance(m, str) for m in models)):
        log('错误：models 必须是模型名字符串数组（可整项删除，交由网关自动发现）。')
        return 1

    lib = find_config_library()
    if not lib:
        log('错误：未找到 LOCALAPPDATA 环境变量，无法定位 configLibrary。')
        return 1
    meta_path = os.path.join(lib, '_meta.json')

    # 幂等：重装时复用已记录的 ID，避免配置堆积
    ctx = read_json(CTX_FILE) or {}
    cfg_id = ctx.get('gatewayConfigId')
    if not (isinstance(cfg_id, str) and CFG_ID_RE.match(cfg_id)):
        cfg_id = new_config_id()
    cfg_path = os.path.join(lib, cfg_id + '.json')

    meta = read_json(meta_path) or {}
    old_applied = meta.get('appliedId')
    if (isinstance(old_applied, str) and CFG_ID_RE.match(old_applied)
            and old_applied != cfg_id
            and os.path.exists(os.path.join(lib, old_applied + '.json'))):
        log('警告：configLibrary 已应用其它配置（id=%s），为避免覆盖您的现有设置，本次不写入。' % old_applied)
        log('  如需替换，请在 Claude 内 Developer 菜单管理，或删除 %s 后重装。' % lib)
        return 3

    # 启动前校验：探测网关模型发现端点
    code, detail = probe_gateway(base, key, scheme)
    if code == 200:
        log('网关校验通过（GET %s -> 200）。' % detail)
    elif code in (401, 403):
        log('错误：网关拒绝凭据（GET %s -> HTTP %d），API Key 无效或权限不足，未写入任何配置。' % (detail, code))
        return 1
    else:
        log('警告：无法联网校验网关（%s）。仍按提供值写入；启动时若网关不可达，Claude 会提示配置错误。' % detail)

    # 写入 <id>.json（键名与取值均为官方配置参考所载）
    conf = {
        'inferenceProvider': 'gateway',
        'inferenceGatewayBaseUrl': base,
        'inferenceGatewayApiKey': key,
        'inferenceCredentialKind': 'static',
        'inferenceGatewayAuthScheme': scheme,
        'disableDeploymentModeChooser': True,
    }
    if models:
        conf['inferenceModels'] = models
    os.makedirs(lib, exist_ok=True)
    write_json(cfg_path, conf)

    # 备份原始 _meta.json（仅首次；重装保留安装前状态），再写入新索引
    if os.path.exists(meta_path) and not os.path.exists(META_BAK):
        os.makedirs(os.path.dirname(META_BAK), exist_ok=True)
        with open(meta_path, 'rb') as fsrc, open(META_BAK, 'wb') as fdst:
            fdst.write(fsrc.read())
    entries = [e for e in (meta.get('entries') or [])
               if isinstance(e, dict) and e.get('id') != cfg_id]
    entries.append({'id': cfg_id, 'name': name})
    write_json(meta_path, {'appliedId': cfg_id, 'entries': entries})

    ctx['gatewayConfigId'] = cfg_id
    if os.path.isdir(ZH_HOME):
        write_json(CTX_FILE, ctx)
    log('免登录配置已写入: %s（id=%s）' % (cfg_path, cfg_id))
    log('  启动 Claude 将直接进入主界面；如需改回官方账号登录，运行卸载或删除该配置。')
    return 0


def restore():
    ctx = read_json(CTX_FILE) or {}
    cfg_id = ctx.get('gatewayConfigId')
    if not (isinstance(cfg_id, str) and CFG_ID_RE.match(cfg_id)):
        return 0  # 从未配置过，静默结束（避免每次卸载都输出噪音）
    lib = find_config_library()
    if not lib:
        log('警告：无法定位 configLibrary，网关配置未还原。')
        return 1
    cfg_path = os.path.join(lib, cfg_id + '.json')
    if os.path.exists(cfg_path):
        try:
            os.remove(cfg_path)
            log('已删除网关配置: %s' % cfg_path)
        except OSError as e:
            log('警告：网关配置删除失败: %s' % e)
            return 1
    meta_path = os.path.join(lib, '_meta.json')
    try:
        if os.path.exists(META_BAK):
            with open(META_BAK, 'rb') as fsrc, open(meta_path, 'wb') as fdst:
                fdst.write(fsrc.read())
        else:
            # 无备份（安装前本就没有 _meta.json）：摘除我方条目并清空 appliedId
            meta = read_json(meta_path) or {}
            entries = [e for e in (meta.get('entries') or [])
                       if isinstance(e, dict) and e.get('id') != cfg_id]
            out = {'entries': entries}
            if entries and isinstance(meta.get('appliedId'), str) and meta['appliedId'] != cfg_id:
                out['appliedId'] = meta['appliedId']
            write_json(meta_path, out)
        log('已还原 configLibrary 索引（Claude 重启后回到官方登录流程）。')
    except OSError as e:
        log('警告：configLibrary 索引还原失败: %s' % e)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(restore() if '--restore' in sys.argv[1:] else apply())
