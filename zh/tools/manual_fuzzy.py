# -*- coding: utf-8 -*-
# 模糊定位修正：截图中的实际源串与词表略有出入，人工核对后按 key 直接指定译文。
# 原先内联在 build_additions.py 中，现提取为独立模块，便于词条仓库统一纳管。
FUZZY_FIX = {
  'TdTNZZvd7W': '网页搜索',                       # Web searches
  'FhHsMUG/nO': '可用时始终使用 1M',               # Use 1M wherever it's available
  'N2lNsOXNuF': '跳过 WebFetch 域检查',            # Skip WebFetch domain check
  'nZmPQiUhiY': 'WebFetch 域检查',
  'HJx8qzEOBu': '组织托管',                        # Organization-managed
  'XX6zi7GmwV': '让应用和代理的流量通过此 HTTP 代理，而不是操作系统的代理设置。',
  'wER6775GSj': '网络代理',                        # Network proxy
  'ko4KhGaz+7': '工作区 VM 网络',                  # Workspace VM network
  '3Pm9sCaKFE': '会话保留',                        # Session retention
  'dplIdntGrp': '部署标识',                        # Deployment identity
  'qg0hZsga3q': '配置通知',                        # Configuration notices
  'dVIH5Gg6O5': '在后台将此计算机上更早的第三方会话一次性复制到应用中，与 enabled 无关。',
  'nsQDRMwvNu': '当 enabled 为 true 时，允许用户导入 Claude.ai 的聊天和项目，以及此计算机上更早的 Claude 会话。automatic3pImport 是独立的开关。',
  'c4gImpExSh': '允许用户将此计算机上的聊天、Cowork 任务和 Code 会话导出为 zip 文件，供其他安装导入。仅当 enabled 为 true 时有效。',
  'PHP5kjRTiq': '插件不得连接的远程服务器，即使允许列表中包含它们。在 Code 会话中还包括配置文件里的服务器。不设置或留空表示不阻止。',
  'H9VdpjJA2h': '在新建聊天或任务时提示导入。不设置则关闭。show：总是需要 enabled 或登录导入；detect：在 enabled 找到更早的 Claude 会话时显示。',
  'keepAwakeEnabledTitle': '允许保持唤醒',
  'Yx/kiytXbg': '内置浏览器',                      # Built-in browser
  'NHwL+4YYfH': 'Code 界面',                       # Code surface
}
