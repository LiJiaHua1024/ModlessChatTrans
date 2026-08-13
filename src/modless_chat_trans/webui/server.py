# Copyright (C) 2024-2026 LiJiaHua1024
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""主程序 GUI 的 Flask 后端。

与 web_display.py（翻译结果展示）完全独立：本模块只承载
Windows 11 风格的设置界面，路由、模板、静态资源全部位于
webui 包内，不触碰 src/templates / src/static。
"""
import json
import re
import threading
import time
import webbrowser
from datetime import datetime

from flask import Flask, Response, jsonify, request, send_from_directory

from modless_chat_trans.config import (
    FallbackStrategy,
    LLMServiceConfig,
    MessageBlacklistRule,
    MonitorMode,
    ServiceType,
    TraditionalServiceConfig,
    TranslationServiceConfig,
    save_config,
    update_config,
)
from modless_chat_trans.file_utils import (
    clear_pre_tts_cache,
    get_path,
    prune_stale_cache,
)
from modless_chat_trans.i18n import _, supported_languages
from modless_chat_trans.logger import logger
from modless_chat_trans.translator import (
    LLM_PROVIDERS,
    TRADITIONAL_SERVICES,
    service_supported_languages,
)


def _get_markdown():
    try:
        import markdown as _md
        return _md
    except ImportError:
        return None


def _get_netifaces():
    try:
        import netifaces as _nif
        return _nif
    except ImportError:
        return None


def build_i18n():
    """所有界面文案（随当前语言打包，前端通过 t(key) 使用）"""
    return {
        # ── 通用 ──
        "close": _("关闭"),
        "cancel": _("取消"),
        "ok": _("确定"),
        "on": _("开启"),
        "off": _("关闭"),
        "working": _("工作中"),
        "stopped": _("已停止"),
        "unknown": _("未知"),
        # ── 导航 ──
        "navCapture": _("消息捕获"),
        "navTranslation": _("翻译服务"),
        "navPresentation": _("翻译结果显示"),
        "navSend": _("发送消息"),
        "navContext": _("上下文翻译"),
        "navGlossary": _("术语表"),
        "navBlacklist": _("黑名单"),
        "navStart": _("启动"),
        "navAbout": _("关于"),
        "navSettings": _("设置"),
        # ── 消息捕获 ──
        "captureTitle": _("消息捕获设置"),
        "logLocation": _("Minecraft 日志位置："),
        "logLocationPlaceholder": _("请选择Minecraft日志文件夹路径"),
        "srcLanguage": _("源语言："),
        "tgtLanguage": _("目标语言："),
        "srcLangPlaceholder": _("请输入源语言（格式不限，AI可智能识别；留空则自动检测）"),
        "tgtLangPlaceholder": _("请输入目标语言（格式不限，AI可智能识别）"),
        "srcLangSelectPlaceholder": _("请选择源语言"),
        "tgtLangSelectPlaceholder": _("请选择目标语言"),
        "logEncoding": _("日志编码："),
        "logEncodingHelp": _("建议选择自动检测（auto），如果无效可以尝试手动指定GBK等编码"),
        "monitorMode": _("监控模式："),
        "efficientMode": _("高效模式"),
        "efficientModeTip": _("低版本 Minecraft 推荐使用"),
        "compatibleMode": _("兼容模式"),
        "compatibleModeTip": _("高版本 Minecraft 使用"),
        "monitorModeHelp": _("建议优先尝试高效模式，若无法正常获取消息，再切换至兼容模式"),
        "filterServerMessages": _("过滤服务器消息"),
        "filterServerHelp": _("不翻译不带玩家名称的服务器消息（系统消息）"),
        "replaceGarbled": _("替换乱码字符"),
        "replaceGarbledHelp": _("将乱码字符（\\ufffd\\ufffd）替换为用于Minecraft格式化代码的分节符\u00A7（\\u00A7）"),
        # ── 翻译服务 ──
        "translationTitle": _("翻译服务设置"),
        "playerServiceTab": _("玩家消息翻译服务"),
        "sendServiceTab": _("消息发送翻译服务"),
        "independentService": _("独立设置消息发送翻译服务"),
        "aiTranslate": _("                AI翻译                "),
        "traditionalTranslate": _("                传统翻译                "),
        "mainModel": _("主力模型"),
        "fallbackModel": _("备用模型"),
        "selectService": _("选择服务："),
        "selectServicePlaceholder": _("请选择翻译服务"),
        "apiKey": _("API Key："),
        "apiKeyPlaceholder": _("请输入您的API Key"),
        "apiUrl": _("API地址："),
        "defaultEndpoint": _("默认端点"),
        "modelCode": _("模型代号："),
        "modelPlaceholder": _("请输入模型代号，如：gpt-3.5-turbo"),
        "deepTranslate": _("深度翻译模式："),
        "deepTranslateHelp": _("启用显式思维链（Chain of Thought）翻译策略\n"
                               "优点：提供更高质量的翻译\n"
                               "缺点：一定程度增加token消耗，响应延迟提高"),
        "fallbackStrategy": _("备用模型策略："),
        "strategyDirect": _("直接切换（主模型失败立即使用备用）"),
        "strategyRetry": _("重试耗尽后切换（主模型重试全部失败后使用备用）"),
        "strategyRace": _("首次失败竞速（主模型首次失败后并发竞速）"),
        "strategyAlwaysRace": _("始终竞速（始终并发请求两者取最快）"),
        "noApiKey": _("不使用"),
        "yandexFolderId": _("Yandex Folder ID："),
        "yandexFolderIdPlaceholder": _("仅 Yandex Cloud 需要"),
        "azureRegion": _("Azure 区域（可选）："),
        "azureRegionPlaceholder": _("仅区域或多服务 Azure 资源需要"),
        "languageLoadError": _("语言加载错误"),
        "languageLoadErrorContent": _("获取支持语言失败 ({service_id}): {error_msg}"),
        # ── 翻译结果显示 ──
        "presentationTitle": _("翻译结果显示"),
        "ttsCardTitle": _("TTS 朗读设置"),
        "ttsImportError": _("⚠️ TTS 模块导入失败，TTS 功能已禁用。错误信息：{}"),
        "ttsEnable": _("启用朗读："),
        "ttsVoice": _("朗读语音："),
        "ttsVoiceLoading": _("加载中..."),
        "ttsVoiceUnavailable": _("不可用"),
        "ttsVoiceAuto": _("自动（根据目标语言）"),
        "ttsVoiceLoadFailed": _("⚠ 语音列表加载失败，将使用默认语音"),
        "ttsVoicesLoaded": _("已加载 {} 种语音，保存设置后启动翻译生效"),
        "ttsSpeed": _("朗读语速："),
        "ttsSpeedVerySlow": _("很慢"),
        "ttsSpeedSlow": _("较慢"),
        "ttsSpeedNormal": _("正常"),
        "ttsSpeedFast": _("较快"),
        "ttsSpeedVeryFast": _("很快"),
        "ttsReadName": _("朗读玩家名："),
        "ttsReadNameHelp": _("开启后朗读格式为\"玩家名 说：消息内容\"，关闭后只朗读消息内容"),
        "ttsTest": _("测试朗读"),
        "ttsUnavailable": _("TTS 不可用"),
        "ttsUnavailableContent": _("TTS 依赖库未安装或导入失败：{}"),
        "ttsTestDone": _("测试完成"),
        "ttsTestDoneContent": _("TTS 朗读测试已完成，请检查声音输出"),
        "ttsTestFailed": _("测试失败"),
        "ttsTestFailedContent": _("TTS 朗读测试失败：{}"),
        "ttsTestText": _("你好，这是一条来自ModlessChatTrans的TTS朗读测试消息。"),
        "preTts": _("Pre-TTS："),
        "preTtsTrigger": _("预合成热词音频"),
        "preTtsStop": _("停止"),
        "preTtsClear": _("清除音频"),
        "preTtsHelp": _("扫描翻译缓存中的热门译文并预合成音频，避免重复合成以减少加载时间。\n"
                        "朗读时自动使用已预合成的音频，未命中则正常合成。\n"
                        "开启\"朗读玩家名\"时不可用。"),
        "preTtsIdle": _("手动预合成热门音频，朗读时自动命中"),
        "preTtsRunning": _("正在预合成 {}/{}..."),
        "preTtsScanning": _("正在扫描翻译缓存..."),
        "preTtsStopping": _("正在停止..."),
        "preTtsDisabledByReadName": _("开启\"朗读玩家名\"后，Pre-TTS 不可用"),
        "preTtsLastResult": _("本次预合成 {} 条，跳过 {} 条；共 {} 条音频（{:.1f} MB）"),
        "preTtsUnavailable": _("Pre-TTS 不可用"),
        "preTtsEngineFailed": _("Pre-TTS 引擎加载失败"),
        "preTtsConfigMissing": _("配置尚未初始化"),
        "preTtsStartFailed": _("启动预合成失败（TTS 依赖不可用或已在运行）"),
        "preTtsFailed": _("Pre-TTS 失败"),
        "confirmClearPreTts": _("确认清理"),
        "confirmClearPreTtsContent": _("将清除所有已预合成的 Pre-TTS 音频。此操作不可恢复。"),
        "clearFailed": _("清理失败"),
        "clearPreTtsError": _("清除 Pre-TTS 音频时出错"),
        "nothingToClear": _("无需清理"),
        "preTtsNothing": _("尚未预合成任何 Pre-TTS 音频"),
        "clearSuccess": _("清理成功"),
        "preTtsCleared": _("已清除 {} 条 Pre-TTS 音频"),
        "webPort": _("网页端口："),
        # ── 发送消息 ──
        "sendTitle": _("消息发送设置"),
        "monitorClipboard": _("监控剪切板"),
        "monitorClipboardHelp": _("从剪切板获取要发送的消息"),
        # ── 上下文翻译 ──
        "contextTitle": _("上下文翻译设置"),
        "contextStrategy": _("上下文分割策略："),
        "contextStrategyDisabled": _("不启用"),
        "contextStrategyFixed": _("固定长度"),
        "contextStrategyTimeBased": _("基于时间跨度"),
        "contextStrategyHelp": _("配置如何管理上下文对话。\n"
                                 "- 不启用：不保存任何上下文\n"
                                 "- 固定长度：保留固定条数的历史记录\n"
                                 "- 基于时间跨度：在设定的时间跨度内视为同一对话"),
        "contextLength": _("最大保留历史条数："),
        "contextLengthHelp": _("最多保留的历史对话条数（0 表示无限制）"),
        "contextTimeout": _("时间跨度阈值(秒)："),
        "contextTimeoutHelp": _("超过此时长（秒）没有新消息，则视为新对话。\n"
                                "仅在“基于时间跨度”策略下生效。"),
        "contextTruncation": _("分块截断大小："),
        "contextTruncAuto": _("自动"),
        "contextTruncDisabled": _("关闭"),
        "contextTruncCustom": _("自定义"),
        "contextTruncHelp": _("分块截断大小：\n"
                              "- 自动：自动计算为最大保留历史条数的一半\n"
                              "- 关闭：传统逐条滑动窗口\n"
                              "- 自定义：设置具体的截断大小"),
        # ── 术语表 ──
        "glossaryTitle": _("术语表管理"),
        "glossarySrc": _("源术语："),
        "glossaryTgt": _("目标术语："),
        "glossarySrcPlaceholder": _("请输入源术语"),
        "glossaryTgtPlaceholder": _("请输入目标术语"),
        "glossaryAddUpdate": _("添加/更新术语"),
        "clearInput": _("清空输入"),
        "glossaryDelete": _("删除选中术语"),
        "glossaryClearAll": _("清空术语"),
        "inputError": _("输入错误"),
        "glossarySrcEmpty": _("源术语不能为空"),
        "confirmOverwrite": _("确认覆盖"),
        "confirmOverwriteContent": _('源术语 "{}" 已存在，是否覆盖？'),
        "glossarySrcHeader": _("源术语"),
        "glossaryTgtHeader": _("目标术语"),
        "ttsDependencyFailed": _("依赖库导入失败，TTS 功能不可用"),
        "cancelling": _("正在取消..."),
        "deleteSuccess": _("删除成功"),
        "termDeleted": _('术语 "{}" 已删除'),
        "confirmClear": _("确认清空"),
        "confirmClearGlossary": _("确定要清空所有术语吗？此操作不可恢复。"),
        "glossaryEmpty": _("术语表为空，无需清空"),
        "glossaryCleared": _("已清空 {} 个术语"),
        "hint": _("提示"),
        # ── 黑名单 ──
        "blacklistTitle": _("黑名单设置"),
        "userBlacklistTab": _("用户黑名单"),
        "messageBlacklistTab": _("消息内容黑名单"),
        "userBlacklistDesc": _("用户黑名单中的玩家发送的消息将不会被翻译。\n"
                               "支持批量添加，每行一个玩家名称。\n"
                               "黑名单使用净化后的玩家名称进行完全匹配（区分大小写）。"),
        "userInputPlaceholder": _("请输入玩家名称，每行一个\n例如：\nNotch\nHerobrine\nSteve"),
        "addUsers": _("添加用户"),
        "deleteSelectedUser": _("删除选中用户"),
        "clearAllUsers": _("清空所有用户"),
        "playerNameHeader": _("玩家名称"),
        "messageBlacklistDesc": _("消息内容黑名单用于过滤特定内容的消息。\n"
                                  "如果选择\"使用正则表达式\"，则按正则表达式匹配；\n"
                                  "否则按关键词匹配（消息包含任意关键词即命中）。"),
        "rule": _("规则："),
        "rulePlaceholder": _("请输入正则表达式或关键词"),
        "useRegex": _("使用正则表达式"),
        "addRule": _("添加规则"),
        "deleteSelectedRule": _("删除选中规则"),
        "clearAllRules": _("清空所有规则"),
        "ruleHeader": _("规则"),
        "typeHeader": _("类型"),
        "regexType": _("正则表达式"),
        "keywordType": _("关键词"),
        "pleaseEnterNames": _("请输入玩家名称"),
        "usersAdded": _("已添加 {} 个用户到黑名单"),
        "usersDuplicate": _("{} 个用户已在黑名单中"),
        "userRemoved": _('已将 "{}" 从黑名单移除'),
        "usersCleared": _("已清空 {} 个用户"),
        "userBlacklistEmpty": _("用户黑名单为空，无需清空"),
        "confirmClearUsers": _("确定要清空所有用户黑名单吗？此操作不可恢复。"),
        "pleaseEnterRule": _("请输入规则"),
        "regexError": _("正则表达式错误"),
        "invalidRegex": _("无效的正则表达式：{}"),
        "ruleExists": _("该规则已存在"),
        "ruleAdded": _("已添加规则：{}"),
        "ruleDeleted": _("已删除规则：{}（{}）"),
        "rulesCleared": _("已清空 {} 个规则"),
        "messageBlacklistEmpty": _("消息黑名单为空，无需清空"),
        "confirmClearRules": _("确定要清空所有消息黑名单规则吗？此操作不可恢复。"),
        # ── 启动 ──
        "startTitle": _("启动"),
        "startDirect": _("直接启动"),
        "saveAndStart": _("保存配置并启动"),
        "saveConfig": _("保存配置"),
        "started": _("已启动"),
        "startedContent": _("已根据当前界面配置启动"),
        "savedAndStarted": _("已保存并启动"),
        "savedAndStartedContent": _("配置已保存并启动"),
        "startFailed": _("启动失败"),
        "operationFailed": _("操作失败"),
        "saveSuccess": _("保存成功"),
        "saveSuccessContent": _("配置已保存至文件"),
        "saveFailed": _("保存失败"),
        "saveFailedContent": _("写入配置文件失败"),
        "saveConfigFailed": _("保存配置失败"),
        "webAccessTitle": _("Web访问链接"),
        "webAccessDesc": _("请通过以下任一链接打开网页界面，查看翻译并即时发送消息"),
        # ── 关于 ──
        "aboutTitle": _("关于"),
        "appInfo": _("应用信息"),
        "versionLabel": _("版本"),
        "authorLabel": _("作者"),
        "emailLabel": _("邮箱"),
        "relatedLinks": _("相关链接"),
        "licenseTitle": _("许可证"),
        # ── 设置 ──
        "settingsTitle": _("设置"),
        "languageSettings": _("语言设置"),
        "interfaceLanguage": _("界面语言："),
        "save": _("保存"),
        "languageRestartTip": _("* 语言更改将在重启后生效"),
        "settingSaved": _("设置已保存"),
        "languageSavedContent": _("界面语言已设置为 {}，重启后生效。"),
        "updateSettings": _("更新设置"),
        "autoCheck": _("自动检查："),
        "freqStartup": _("启动时"),
        "freqDaily": _("每天"),
        "freqWeekly": _("每周"),
        "freqMonthly": _("每月"),
        "freqNever": _("从不"),
        "prerelease": _("预发布版本："),
        "includePrerelease": _("包含预发布版本"),
        "manualCheck": _("手动检查："),
        "checkUpdate": _("检查更新"),
        "updaterUnavailable": _("⚠ 更新依赖不可用"),
        "currentVersion": _("当前版本："),
        "upToDate": _("您是最新的"),
        "upToDateContent": _("当前版本 v{} 已是最新版本"),
        "updateCheckFailed": _("检查更新失败"),
        "updateCheckError": _("错误: {}"),
        "updateAvailable": _("发现新版本"),
        "versionInfo": _("版本信息"),
        "latestVersion": _("最新版本："),
        "publishTime": _("发布时间："),
        "publisher": _("发布者："),
        "releaseNotes": _("更新说明"),
        "noReleaseNotes": _("暂无更新说明"),
        "prereleaseTag": _("预发布版本"),
        "versionType": _("版本类型："),
        "viewFullNotes": _("在 GitHub 上查看完整说明"),
        "downloadUpdate": _("下载更新"),
        "skipUpdate": _("暂不更新"),
        "downloadingUpdate": _("正在下载更新"),
        "downloadingVersion": _("正在下载版本 {}..."),
        "downloadProgress": _("下载进度："),
        "downloadSpeed": _("下载速度："),
        "remainingTime": _("剩余时间："),
        "downloadMethod": _("下载方式："),
        "detecting": _("检测中..."),
        "multiThreadDownload": _("{} 线程下载"),
        "singleThreadDownload": _("单线程下载"),
        "calculating": _("计算中..."),
        "complete": _("完成"),
        "downloadCancelled": _("下载已取消"),
        "downloadCancelledContent": _("更新下载已取消"),
        "downloadFailed": _("下载失败"),
        "downloadDone": _("下载完成"),
        "downloadDoneContent": _("更新文件已下载到:\n{}\n\n请手动安装更新。"),
        "cacheManagement": _("缓存管理"),
        "clearCache": _("清除缓存："),
        "clearUnusedCache": _("清理不常用缓存"),
        "cacheNothing": _("没有不常用的缓存条目，所有缓存都曾被使用过。"),
        "confirmClearCache": _("确认清理"),
        "confirmClearCacheContent": _("将清理 {} 条不常用缓存条目（从未被读取），总计 {} 条中保留 {} 条。此操作不可恢复。"),
        "cacheCleared": _("已清理 {} 条不常用缓存条目"),
        "cacheQueryError": _("查询缓存时出错：{}"),
        "timeSec": _("{} 秒"),
        "timeMinSec": _("{} 分 {} 秒"),
        "timeMin": _("{} 分钟"),
        "timeHourMin": _("{} 小时 {} 分"),
        "timeHour": _("{} 小时"),
        "error": _("错误"),
        "updaterNotInit": _("更新器未初始化"),
    }


# ═══════════════════════════════════════════════════════════════════
# GuiState —— 后端唯一权威状态（等价于旧 Qt 界面内存中的控件状态）
# ═══════════════════════════════════════════════════════════════════

class GuiState:
    def __init__(self, program_info, updater, config, start_callback):
        self.program_info = program_info
        self.updater = updater
        self.config = config
        self.start_callback = start_callback
        self.lock = threading.RLock()
        self.working = False
        self.user_clicked_link = False
        self.player_language_loading = False
        self.send_language_loading = False
        self._tts_voices = []
        self._tts_voices_loaded = False
        self._tts_voice_status = None  # (i18n_key, args) 或 (None, [])
        self._voice_load_started = False
        self.pending_events = []
        self._sse_queues = []
        self._sse_lock = threading.Lock()
        self.download_active = False
        self._download_cancel_requested = False
        self._check_thread = None
        self._download_thread = None
        self._last_release = None

    # ── SSE ──

    def sse_subscribe(self):
        queue = []
        with self._sse_lock:
            self._sse_queues.append(queue)
        return queue

    def sse_unsubscribe(self, queue):
        with self._sse_lock:
            if queue in self._sse_queues:
                self._sse_queues.remove(queue)

    def emit(self, event, data):
        """向已连接的页面广播事件；无页面连接时暂存，页面加载后补发"""
        with self.lock, self._sse_lock:
            if not self._sse_queues:
                self.pending_events.append({"event": event, "data": data})
                return
            for queue in list(self._sse_queues):
                queue.append({"event": event, "data": data})

    def pop_pending_events(self):
        with self.lock:
            events = self.pending_events
            self.pending_events = []
            return events

    def toast(self, kind, title, content, duration=3000):
        self.emit("toast", {"kind": kind, "title": title, "content": content, "duration": duration})


# ═══════════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════════

def _get_tts_availability():
    try:
        from modless_chat_trans.tts_engine import TTS_AVAILABLE, TTS_IMPORT_ERROR
        return TTS_AVAILABLE, TTS_IMPORT_ERROR
    except Exception as e:
        return False, str(e)


def _get_updater_availability():
    try:
        from modless_chat_trans.updater import UPDATER_AVAILABLE
        return UPDATER_AVAILABLE
    except Exception:
        return False


def _get_sorted_ips():
    """获取所有IP地址并按优先级排序（局域网优先）"""
    ips = []

    netifaces = _get_netifaces()
    if not netifaces:
        ips = [('127.0.0.1', 2)]
    else:
        try:
            for interface in netifaces.interfaces():
                addrs = netifaces.ifaddresses(interface)
                if netifaces.AF_INET in addrs:
                    for addr in addrs[netifaces.AF_INET]:
                        ip = addr['addr']
                        if ip.startswith('192.168.') or ip.startswith('10.'):
                            ips.append((ip, 1))
                        elif ip.startswith('172.'):
                            second_octet = int(ip.split('.')[1])
                            if 16 <= second_octet <= 31:
                                ips.append((ip, 1))
                        elif ip in ['127.0.0.1', '0.0.0.0']:
                            ips.append((ip, 2))
        except Exception as e:
            logger.error(f"Failed to get network interfaces: {e}")
            ips = [('127.0.0.1', 2)]

    ips.append(('localhost', 2))

    seen = set()
    sorted_ips = []
    for ip, priority in sorted(ips, key=lambda x: (x[1], x[0])):
        if ip not in seen:
            seen.add(ip)
            sorted_ips.append(ip)

    return sorted_ips


def _traditional_langs(service_name):
    langs = service_supported_languages[service_name]
    src = list(langs)
    tgt = [l for l in langs if l != 'auto']
    return src, tgt


# ═══════════════════════════════════════════════════════════════════
# 状态快照（GET /api/state）
# ═══════════════════════════════════════════════════════════════════

def _snapshot_translation_section(state, service_config):
    """把 TranslationServiceConfig 转为前端可用的字典"""
    if not service_config:
        return None

    section = {"service_type": service_config.service_type.value}

    if service_config.service_type == ServiceType.LLM and service_config.llm:
        llm = service_config.llm
        section["llm"] = {
            "provider": llm.provider,
            "api_key": llm.api_key or "",
            "api_base": llm.api_base or "",
            "model": llm.model or "",
            "deep_translate": llm.deep_translate,
        }
        fb = service_config.fallback_llm
        if fb:
            section["fallback_llm"] = {
                "provider": fb.provider,
                "api_key": fb.api_key or "",
                "api_base": fb.api_base or "",
                "model": fb.model or "",
                "deep_translate": fb.deep_translate,
            }
        else:
            section["fallback_llm"] = None
        section["fallback_strategy"] = service_config.fallback_strategy.value \
            if hasattr(service_config.fallback_strategy, "value") else str(service_config.fallback_strategy)
    else:
        section["llm"] = None
        section["fallback_llm"] = None
        section["fallback_strategy"] = "direct"

    if service_config.traditional:
        trad = service_config.traditional
        section["traditional"] = {
            "provider": trad.provider,
            "api_key": trad.api_key or "",
            "folder_id": trad.folder_id or "",
            "region": trad.region or "",
        }
    else:
        section["traditional"] = {
            "provider": "",
            "api_key": "",
            "folder_id": "",
            "region": "",
        }

    return section


def build_state_snapshot(state):
    """构建完整 UI 状态（等价于旧 Qt 界面中各控件的当前值）"""
    cfg = state.config
    with state.lock:
        snapshot = {
            "version": state.program_info.version,
            "program": {
                "author": state.program_info.author,
                "email": state.program_info.email,
                "github": state.program_info.github,
                "license_name": state.program_info.license[0],
                "license_url": state.program_info.license[1],
            },
            "llm_providers": LLM_PROVIDERS,
            "traditional_services": TRADITIONAL_SERVICES,
            "supported_languages": [[name, code] for name, code in supported_languages],
            "working": state.working,
        }

        tts_available, tts_import_error = _get_tts_availability()
        updater_available = _get_updater_availability()

        capture_type = ServiceType.LLM
        if cfg.player_translation:
            capture_type = cfg.player_translation.service_type
        send_type = capture_type
        if cfg.send_translation:
            send_type = cfg.send_translation.service_type

        capture_langs = {"src": [], "tgt": []}
        send_langs = {"src": [], "tgt": []}
        if capture_type == ServiceType.TRADITIONAL and cfg.player_translation and cfg.player_translation.traditional:
            try:
                if cfg.player_translation.traditional.provider in service_supported_languages:
                    src, tgt = _traditional_langs(cfg.player_translation.traditional.provider)
                    capture_langs = {"src": src, "tgt": tgt}
            except Exception:
                pass
        if send_type == ServiceType.TRADITIONAL and cfg.send_translation and cfg.send_translation.traditional:
            try:
                if cfg.send_translation.traditional.provider in service_supported_languages:
                    src, tgt = _traditional_langs(cfg.send_translation.traditional.provider)
                    send_langs = {"src": src, "tgt": tgt}
            except Exception:
                pass

        snapshot["capture"] = {
            "log_path": cfg.message_capture.minecraft_log_path,
            "log_encoding": cfg.message_capture.log_encoding,
            "monitor_mode": cfg.message_capture.monitor_mode.value,
            "filter_server_messages": cfg.message_capture.filter_server_messages,
            "replace_garbled_chars": cfg.message_capture.replace_garbled_chars,
            "source_language": cfg.message_capture.source_language,
            "target_language": cfg.message_capture.target_language,
            "service_type": capture_type.value,
            "lang_options": capture_langs,
        }

        snapshot["translation"] = {
            "independent": cfg.send_translation_independent,
            "player": _snapshot_translation_section(state, cfg.player_translation),
            "send": _snapshot_translation_section(state, cfg.send_translation),
        }

        voices = []
        if state._tts_voices_loaded:
            voices = list(state._tts_voices)
        voice_status = None
        if state._tts_voice_status:
            key, args = state._tts_voice_status
            voice_status = {"key": key, "args": list(args)}
        snapshot["presentation"] = {
            "web_port": cfg.message_presentation.web_port,
            "tts_available": tts_available,
            "tts_import_error": tts_import_error or "",
            "tts": {
                "enabled": cfg.tts.enabled,
                "voice": cfg.tts.voice,
                "voices": voices,
                "voices_loaded": state._tts_voices_loaded,
                "voice_status": voice_status,
                "speed": cfg.tts.speed,
                "read_player_name": cfg.tts.read_player_name,
            },
        }

        snapshot["send"] = {
            "monitor_clipboard": cfg.message_send.monitor_clipboard,
            "source_language": cfg.message_send.source_language,
            "target_language": cfg.message_send.target_language,
            "service_type": send_type.value,
            "lang_options": send_langs,
        }

        trunc_val = str(cfg.context.block_truncation_size)
        if trunc_val in ("disabled", "auto"):
            trunc_mode = trunc_val
            trunc_spin = 1
        else:
            trunc_mode = "custom"
            try:
                trunc_spin = int(trunc_val)
            except ValueError:
                trunc_spin = 1

        snapshot["context"] = {
            "strategy": cfg.context.strategy,
            "context_length": cfg.context.context_length,
            "context_timeout": cfg.context.context_timeout,
            "truncation_mode": trunc_mode,
            "truncation_value": trunc_spin,
        }

        glossary_items = [[src, tgt] for src, tgt in sorted(cfg.glossary.items())]
        snapshot["glossary"] = {"items": glossary_items}

        messages = [
            {"pattern": r.pattern, "is_regex": r.is_regex}
            for r in cfg.blacklist.message_blacklist
        ]
        snapshot["blacklist"] = {
            "users": list(cfg.blacklist.user_blacklist),
            "messages": messages,
        }

        snapshot["settings"] = {
            "interface_language": cfg.settings.interface_language,
            "update_frequency": cfg.settings.auto_check_update_frequency,
            "include_prerelease": cfg.settings.include_prerelease,
            "current_version": str(state.updater.current_version) if state.updater else "",
            "updater_available": updater_available,
        }

        engine = _get_pre_tts_engine_safe()
        if engine is not None:
            done, total = engine.progress
            result = engine.last_result or {}
            snapshot["pre_tts"] = {
                "available": tts_available,
                "running": engine.running,
                "done": done,
                "total": total,
                "result": result if result else None,
            }
        else:
            snapshot["pre_tts"] = {
                "available": tts_available,
                "running": False,
                "done": 0,
                "total": 0,
                "result": None,
            }

        snapshot["pending_events"] = state.pop_pending_events()
        return snapshot


def _get_pre_tts_engine_safe():
    try:
        from modless_chat_trans.pre_tts import get_pre_tts_engine
        return get_pre_tts_engine()
    except Exception as e:
        logger.error(f"[Pre-TTS] Failed to load engine: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════
# 表单 → 配置（复刻 _gather_config_from_ui）
# ═══════════════════════════════════════════════════════════════════

def _parse_llm_section(data):
    api_base = data.get("api_base") or None
    return LLMServiceConfig(
        provider=data.get("provider") or "",
        api_key=data.get("api_key") or "",
        api_base=api_base,
        model=data.get("model") or "",
        deep_translate=bool(data.get("deep_translate", False)),
    )


def _gather_config(state, form):
    """将前端表单汇总到 state.config 并返回该对象（复刻 _gather_config_from_ui）"""
    cfg = state.config

    capture = form.get("capture") or {}
    translation = form.get("translation") or {}
    presentation = form.get("presentation") or {}
    send = form.get("send") or {}
    context = form.get("context") or {}
    settings_form = form.get("settings") or {}
    tts_form = presentation.get("tts") or {}

    # 1) 消息捕获
    cfg.message_capture.minecraft_log_path = capture.get("log_path", "")
    cfg.message_capture.log_encoding = capture.get("log_encoding", "auto")
    cfg.message_capture.monitor_mode = (
        MonitorMode.EFFICIENT if capture.get("monitor_mode") == "efficient"
        else MonitorMode.COMPATIBLE
    )
    cfg.message_capture.filter_server_messages = bool(capture.get("filter_server_messages"))
    cfg.message_capture.replace_garbled_chars = bool(capture.get("replace_garbled_chars"))
    cfg.message_capture.source_language = capture.get("src_lang", "") or ""
    cfg.message_capture.target_language = capture.get("tgt_lang", "") or ""

    # 2) 翻译服务
    cfg.send_translation_independent = bool(translation.get("independent"))

    def build_service(section):
        if not section:
            raise ValueError(_("翻译失败，未生成翻译结果。"))
        service_type = section.get("service_type", "llm")
        if service_type == "llm":
            llm_data = section.get("llm") or {}
            llm = _parse_llm_section(llm_data)
            fallback_llm = None
            fb_data = section.get("fallback_llm") or {}
            if (fb_data.get("model") or "").strip():
                fallback_llm = _parse_llm_section(fb_data)
            strategy_value = section.get("fallback_strategy") or "direct"
            try:
                strategy = FallbackStrategy(strategy_value)
            except ValueError:
                strategy = FallbackStrategy.DIRECT
            return TranslationServiceConfig(
                service_type=ServiceType.LLM,
                llm=llm,
                traditional=None,
                fallback_llm=fallback_llm,
                fallback_strategy=strategy,
            )
        else:
            trad_data = section.get("traditional") or {}
            api_key = trad_data.get("api_key") or None
            trad = TraditionalServiceConfig(
                provider=trad_data.get("provider") or "",
                api_key=api_key,
                folder_id=(trad_data.get("folder_id") or "").strip() or None,
                region=(trad_data.get("region") or "").strip() or None,
            )
            return TranslationServiceConfig(
                service_type=ServiceType.TRADITIONAL,
                llm=None,
                traditional=trad,
            )

    cfg.player_translation = build_service(translation.get("player"))

    if cfg.send_translation_independent and translation.get("send"):
        cfg.send_translation = build_service(translation.get("send"))
    else:
        cfg.send_translation = None

    # 3) 翻译结果呈现
    web_port = int(presentation.get("web_port") or 8080)
    web_port = max(1024, min(65535, web_port))
    cfg.message_presentation.web_port = web_port

    # 4) 消息发送
    cfg.message_send.monitor_clipboard = bool(send.get("monitor_clipboard"))
    cfg.message_send.source_language = send.get("src_lang", "") or ""
    cfg.message_send.target_language = send.get("tgt_lang", "") or ""

    # 5) 上下文翻译
    cfg.context.strategy = context.get("strategy") or "disabled"
    cfg.context.context_length = int(context.get("context_length") or 0)
    cfg.context.context_timeout = float(context.get("context_timeout") or 0.0)
    trunc_mode = context.get("truncation_mode") or "disabled"
    if trunc_mode == "custom":
        cfg.context.block_truncation_size = str(int(context.get("truncation_value") or 1))
    else:
        cfg.context.block_truncation_size = str(trunc_mode)

    # 6) 术语表 / 7) 黑名单：由后端权威状态直接使用（前端仅展示）
    # 8) 设置
    lang_code = settings_form.get("interface_language") or cfg.settings.interface_language
    cfg.settings.interface_language = lang_code
    cfg.settings.auto_check_update_frequency = settings_form.get("update_frequency") or cfg.settings.auto_check_update_frequency
    cfg.settings.include_prerelease = bool(settings_form.get("include_prerelease"))

    # 9) TTS
    cfg.tts.enabled = bool(tts_form.get("enabled"))
    cfg.tts.voice = tts_form.get("voice") or "auto"
    cfg.tts.speed = tts_form.get("speed") or "+0%"
    cfg.tts.read_player_name = bool(tts_form.get("read_player_name"))

    return cfg


# ═══════════════════════════════════════════════════════════════════
# 后台任务
# ═══════════════════════════════════════════════════════════════════

def _start_translation_task(state, cfg, is_save_and_start):
    try:
        state.start_callback(cfg)
    except Exception as e:
        logger.error(f"Start failed: {e}")
        state.toast(
            "error",
            _("操作失败") if is_save_and_start else _("启动失败"),
            str(e),
            5000,
        )
        return

    with state.lock:
        state.working = True
        state.user_clicked_link = False

    state.toast(
        "success",
        _("已保存并启动") if is_save_and_start else _("已启动"),
        _("配置已保存并启动") if is_save_and_start else _("已根据当前界面配置启动"),
        2000,
    )
    web_port = cfg.message_presentation.web_port
    state.emit("start-finished", {
        "web_port": web_port,
        "ips": _get_sorted_ips(),
        "is_save_and_start": is_save_and_start,
    })

    # 1 秒后自动打开翻译结果网页（用户已点击链接则跳过）
    def _auto_open():
        time.sleep(1.0)
        with state.lock:
            if not state.user_clicked_link:
                try:
                    webbrowser.open(f"http://127.0.0.1:{web_port}")
                except Exception as e:
                    logger.warning(f"Failed to open web page: {e}")

    threading.Thread(target=_auto_open, daemon=True, name="webui-auto-open").start()


def _load_voices_task(state):
    if state._tts_voices_loaded:
        return
    with state.lock:
        if state._voice_load_started:
            return
        state._voice_load_started = True

    def run():
        try:
            from modless_chat_trans.tts_engine import get_available_voices_sync
            voices = get_available_voices_sync()
        except Exception as e:
            logger.error(f"[TTS] Failed to load voices: {e}")
            voices = []

        with state.lock:
            if not voices:
                state._tts_voices = []
                state._tts_voices_loaded = True
                state._tts_voice_status = ("ttsVoiceLoadFailed", [])
                state.emit("voices-loaded", {"voices": [], "ok": False})
                return

            seen_locales = set()
            voice_items = []
            for v in voices:
                locale = v.get("Locale", "")
                if locale in seen_locales:
                    continue
                seen_locales.add(locale)
                name = v.get("ShortName") or v.get("Name", "")
                display = f"{name}  ({locale})"
                voice_items.append({"display": display, "value": name})

            state._tts_voices = voice_items
            state._tts_voices_loaded = True
            state._tts_voice_status = ("ttsVoicesLoaded", [len(seen_locales)])
            state.emit("voices-loaded", {"voices": voice_items, "ok": True, "count": len(seen_locales)})

    threading.Thread(target=run, daemon=True, name="webui-voices").start()


def _load_languages_task(state, service_name, kind):
    with state.lock:
        if kind == "player":
            if state.player_language_loading:
                return
            state.player_language_loading = True
        else:
            if state.send_language_loading:
                return
            state.send_language_loading = True

    state.emit("languages-loading", {"kind": kind})

    def run():
        try:
            src, tgt = _traditional_langs(service_name)
            state.emit("languages-loaded", {"kind": kind, "src": src, "tgt": tgt})
        except Exception as e:
            logger.error(f"Failed to get supported languages ({kind}): {e}")
            state.emit("languages-error", {"kind": kind, "error": str(e)})
            state.toast(
                "error",
                _("语言加载错误"),
                _("获取支持语言失败 ({service_id}): {error_msg}").format(service_id=kind, error_msg=str(e)),
                -1,
            )
        finally:
            with state.lock:
                if kind == "player":
                    state.player_language_loading = False
                else:
                    state.send_language_loading = False

    threading.Thread(target=run, daemon=True, name=f"webui-languages-{kind}").start()


def _tts_test_task(state, voice, speed):
    import asyncio
    import os
    import tempfile

    test_text = _("你好，这是一条来自ModlessChatTrans的TTS朗读测试消息。")

    def run():
        try:
            import edge_tts

            from modless_chat_trans.tts_engine import infer_voice

            actual_voice = voice
            if actual_voice in ("auto", "", None):
                actual_voice = infer_voice("Simplified Chinese", "auto")

            fd, tmp_path = tempfile.mkstemp(suffix=".mp3", prefix="mct_tts_test_")
            os.close(fd)

            async def synthesize():
                communicate = edge_tts.Communicate(
                    text=test_text,
                    voice=actual_voice,
                    rate=speed,
                )
                await asyncio.wait_for(communicate.save(tmp_path), timeout=15.0)

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(synthesize())
            finally:
                loop.close()

            from modless_chat_trans.tts_engine import _play_mp3_file
            _play_mp3_file(tmp_path)

            try:
                os.unlink(tmp_path)
            except Exception:
                pass

            state.emit("tts-test-result", {"success": True, "error": ""})
        except Exception as e:
            state.emit("tts-test-result", {"success": False, "error": str(e)})

    threading.Thread(target=run, daemon=True, name="webui-tts-test").start()


class _DownloadWorker:
    """更新下载工作器（复刻旧 DownloadWorker，事件通过 SSE 推送）"""

    def __init__(self, state, release_info):
        self.state = state
        self.release_info = release_info
        self.is_cancelled = False
        self.speed_history = []
        self.max_history = 10

    def cancel(self):
        self.is_cancelled = True

    def download(self):
        try:
            def progress_callback(downloaded, total, speed):
                if self.is_cancelled:
                    return False

                self.speed_history.append(speed)
                if len(self.speed_history) > self.max_history:
                    self.speed_history.pop(0)

                if self.speed_history:
                    weights = [i + 1 for i in range(len(self.speed_history))]
                    weighted_sum = sum(s * w for s, w in zip(self.speed_history, weights))
                    weight_total = sum(weights)
                    avg_speed = weighted_sum / weight_total
                else:
                    avg_speed = speed

                self.state.emit("download-progress", {
                    "downloaded": downloaded,
                    "total": total,
                    "speed": avg_speed,
                })
                return True

            def thread_count_callback(count):
                self.state.emit("download-thread-count", {"threads": count})

            file_path = self.state.updater.download_update(
                self.release_info, progress_callback, thread_count_callback
            )

            if file_path:
                self.state.emit("download-finished", {"path": file_path})
            elif self.is_cancelled:
                self.state.emit("download-finished", {"path": ""})
            else:
                self.state.emit("download-error", {"error": _("下载失败")})

        except Exception as e:
            self.state.emit("download-error", {"error": str(e)})
        finally:
            with self.state.lock:
                self.state.download_active = False


def _render_release_note(release_body):
    """将 GitHub Release 的 Markdown 转为 HTML（供更新对话框展示）"""
    _md = _get_markdown()
    if not _md:
        return None
    try:
        return _md.markdown(release_body, extensions=['extra', 'nl2br'])
    except Exception as e:
        logger.error(f"Error processing release note: {e}")
        return None


def _check_update_task(state, silent):
    check_failed = False
    try:
        latest_release = state.updater.check_update()
    except Exception as e:
        check_failed = True
        latest_release = None
        if not silent:
            state.toast("error", _("检查更新失败"), _("错误: {}").format(str(e)), 5000)
        else:
            logger.error(f"Silent update check failed: {e}")

    if latest_release:
        with state.lock:
            state._last_release = latest_release
        release_body = latest_release.get('body') or _('暂无更新说明')
        state.emit("update-available", {
            "release": latest_release,
            "current_version": str(state.updater.current_version),
            "note_html": _render_release_note(release_body),
        })
    elif not check_failed:
        # 未抛出异常且无新版 → 已是最新
        try:
            if not silent:
                state.toast("success", _("您是最新的"),
                           _("当前版本 v{} 已是最新版本").format(state.updater.current_version), 3000)
            else:
                logger.info(f"Current version v{state.updater.current_version} is up to date")
        except Exception:
            pass

    luct = datetime.now().isoformat(timespec='seconds')
    try:
        with state.lock:
            state.config.settings.last_update_check_time = luct
    except Exception:
        pass
    update_config(settings__last_update_check_time=luct)


# ═══════════════════════════════════════════════════════════════════
# Flask 应用
# ═══════════════════════════════════════════════════════════════════

def create_app(state):
    template_dir = get_path("modless_chat_trans/webui/templates")
    static_dir = get_path("modless_chat_trans/webui/static")

    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)

    @app.route("/")
    def index():
        return send_from_directory(template_dir, "gui.html")

    @app.route("/api/state")
    def api_state():
        snapshot = build_state_snapshot(state)
        snapshot["i18n"] = build_i18n()
        return jsonify(snapshot)

    @app.route("/api/save", methods=["POST"])
    def api_save():
        try:
            form = request.get_json(force=True) or {}
            _gather_config(state, form)
        except Exception as e:
            logger.error(f"Save config failed: {e}")
            state.toast("error", _("保存失败"), str(e), 5000)
            return jsonify({"ok": False, "error": str(e)}), 400
        if save_config(state.config):
            state.toast("success", _("保存成功"), _("配置已保存至文件"), 2000)
            return jsonify({"ok": True})
        state.toast("error", _("保存失败"), _("写入配置文件失败"), 4000)
        return jsonify({"ok": False, "error": _("写入配置文件失败")}), 500

    @app.route("/api/start", methods=["POST"])
    def api_start():
        form = request.get_json(force=True) or {}
        mode = form.get("mode", "direct")
        is_save_and_start = mode == "save_and_start"
        try:
            cfg = _gather_config(state, form)
            if is_save_and_start:
                if not save_config(cfg):
                    raise RuntimeError(_("保存配置失败"))
        except Exception as e:
            logger.error(f"Start failed: {e}")
            state.toast(
                "error",
                _("操作失败") if is_save_and_start else _("启动失败"),
                str(e),
                5000,
            )
            return jsonify({"ok": False, "error": str(e)}), 400

        with state.lock:
            if state.working:
                state.toast("info", _("提示"), _("工作中"), 2000)
                return jsonify({"ok": False, "error": "already working"}), 409

        threading.Thread(
            target=_start_translation_task,
            args=(state, cfg, is_save_and_start),
            daemon=True,
            name="webui-start",
        ).start()
        return jsonify({"ok": True})

    @app.route("/api/link-clicked", methods=["POST"])
    def api_link_clicked():
        with state.lock:
            state.user_clicked_link = True
        return jsonify({"ok": True})

    @app.route("/api/languages/load", methods=["POST"])
    def api_languages_load():
        data = request.get_json(force=True) or {}
        service_name = (data.get("service") or "").strip()
        kind = data.get("kind") or "player"
        if not service_name:
            return jsonify({"ok": False, "error": "empty service"}), 400
        _load_languages_task(state, service_name, kind)
        return jsonify({"ok": True})

    @app.route("/api/tts/voices/load", methods=["POST"])
    def api_tts_voices_load():
        _load_voices_task(state)
        return jsonify({"ok": True})

    @app.route("/api/tts/test", methods=["POST"])
    def api_tts_test():
        tts_available, tts_import_error = _get_tts_availability()
        if not tts_available:
            state.toast(
                "error",
                _("TTS 不可用"),
                _("TTS 依赖库未安装或导入失败：{}").format(tts_import_error or _("unknown")),
                5000,
            )
            return jsonify({"ok": False}), 503
        data = request.get_json(force=True) or {}
        voice = data.get("voice") or "auto"
        speed = data.get("speed") or "+0%"
        _tts_test_task(state, voice, speed)
        return jsonify({"ok": True})

    @app.route("/api/pre-tts/status")
    def api_pre_tts_status():
        engine = _get_pre_tts_engine_safe()
        tts_available, _err = _get_tts_availability()
        if engine is None:
            return jsonify({"available": tts_available, "running": False, "done": 0, "total": 0, "result": None})
        done, total = engine.progress
        result = engine.last_result or {}
        return jsonify({
            "available": tts_available,
            "running": engine.running,
            "done": done,
            "total": total,
            "result": result if result else None,
        })

    @app.route("/api/pre-tts/start", methods=["POST"])
    def api_pre_tts_start():
        tts_available, _err = _get_tts_availability()
        if not tts_available:
            return jsonify({"ok": False}), 503
        engine = _get_pre_tts_engine_safe()
        if engine is None:
            state.toast("error", _("Pre-TTS 不可用"), _("Pre-TTS 引擎加载失败"), 3000)
            return jsonify({"ok": False}), 500
        cfg = state.config
        if cfg is None or not hasattr(cfg, 'tts'):
            state.toast("error", _("Pre-TTS 不可用"), _("配置尚未初始化"), 3000)
            return jsonify({"ok": False}), 400
        if engine.running:
            return jsonify({"ok": False, "running": True}), 409
        if not engine.start(cfg):
            state.toast("error", _("Pre-TTS 失败"), _("启动预合成失败（TTS 依赖不可用或已在运行）"), 3000)
            return jsonify({"ok": False}), 500
        state.emit("pre-tts-started", {})
        return jsonify({"ok": True})

    @app.route("/api/pre-tts/stop", methods=["POST"])
    def api_pre_tts_stop():
        engine = _get_pre_tts_engine_safe()
        if engine is None or not engine.running:
            return jsonify({"ok": False}), 409
        engine.stop()
        return jsonify({"ok": True})

    @app.route("/api/pre-tts/clear", methods=["POST"])
    def api_pre_tts_clear():
        try:
            deleted = clear_pre_tts_cache()
        except Exception as e:
            logger.error(f"[Pre-TTS] Failed to load clear helper: {e}")
            state.toast("error", _("清理失败"), str(e), 3000)
            return jsonify({"ok": False}), 500

        if deleted < 0:
            state.toast("error", _("清理失败"), _("清除 Pre-TTS 音频时出错"), 3000)
        elif deleted == 0:
            state.toast("info", _("无需清理"), _("尚未预合成任何 Pre-TTS 音频"), 3000)
        else:
            state.toast("success", _("清理成功"), _("已清除 {} 条 Pre-TTS 音频").format(deleted), 3000)
        return jsonify({"ok": True, "deleted": deleted})

    # ── 术语表 ──

    @app.route("/api/glossary/add", methods=["POST"])
    def api_glossary_add():
        data = request.get_json(force=True) or {}
        src_text = (data.get("src") or "").strip()
        tgt_text = (data.get("tgt") or "").strip()
        old_src = data.get("old_src") or None
        confirmed = bool(data.get("confirmed"))

        if not src_text:
            state.toast("warning", _("输入错误"), _("源术语不能为空"), 3000)
            return jsonify({"ok": False}), 400

        with state.lock:
            glossary = state.config.glossary
            if src_text in glossary and src_text != old_src and not confirmed:
                return jsonify({"ok": False, "needs_confirm": True}), 409

            if old_src and old_src != src_text and old_src in glossary:
                del glossary[old_src]

            glossary[src_text] = tgt_text
            action = _("更新") if old_src else _("添加")
            items = [[s, t] for s, t in sorted(glossary.items())]

        logger.info(f"Term {action}: '{src_text}' -> '{tgt_text}'")
        state.toast("success", _('术语{}成功').format(action), f'"{src_text}" -> "{tgt_text}"', 2000)
        return jsonify({"ok": True, "items": items})

    @app.route("/api/glossary/delete", methods=["POST"])
    def api_glossary_delete():
        data = request.get_json(force=True) or {}
        src_text = data.get("src") or ""
        with state.lock:
            glossary = state.config.glossary
            if src_text not in glossary:
                return jsonify({"ok": False}), 404
            del glossary[src_text]
            items = [[s, t] for s, t in sorted(glossary.items())]
        logger.info(f"Term deleted: {src_text}")
        state.toast("success", _("删除成功"), _('术语 "{}" 已删除').format(src_text), 2000)
        return jsonify({"ok": True, "items": items})

    @app.route("/api/glossary/clear", methods=["POST"])
    def api_glossary_clear():
        with state.lock:
            glossary = state.config.glossary
            if not glossary:
                state.toast("info", _("提示"), _("术语表为空，无需清空"), 2000)
                return jsonify({"ok": False, "empty": True}), 409
            count = len(glossary)
            glossary.clear()
        logger.info(f"Glossary cleared, deleted {count} terms")
        state.toast("success", _("清空成功"), _("已清空 {} 个术语").format(count), 2000)
        return jsonify({"ok": True, "items": []})

    # ── 黑名单 ──

    @app.route("/api/blacklist/users/add", methods=["POST"])
    def api_blacklist_users_add():
        data = request.get_json(force=True) or {}
        text = (data.get("text") or "").strip()
        if not text:
            state.toast("info", _("提示"), _("请输入玩家名称"), 2000)
            return jsonify({"ok": False}), 400

        names = [name.strip() for name in text.split('\n') if name.strip()]
        with state.lock:
            users = state.config.blacklist.user_blacklist
            added_count = 0
            duplicate_count = 0
            for name in names:
                if name and name not in users:
                    users.append(name)
                    added_count += 1
                elif name:
                    duplicate_count += 1
            users_out = list(users)

        if added_count > 0:
            state.toast("success", _("添加成功"), _("已添加 {} 个用户到黑名单").format(added_count), 2000)
        if duplicate_count > 0:
            state.toast("info", _("提示"), _("{} 个用户已在黑名单中").format(duplicate_count), 2000)
        return jsonify({"ok": True, "users": users_out, "added": added_count, "duplicates": duplicate_count})

    @app.route("/api/blacklist/users/delete", methods=["POST"])
    def api_blacklist_users_delete():
        data = request.get_json(force=True) or {}
        username = data.get("name") or ""
        with state.lock:
            users = state.config.blacklist.user_blacklist
            if username not in users:
                return jsonify({"ok": False}), 404
            users.remove(username)
            users_out = list(users)
        state.toast("success", _("删除成功"), _('已将 "{}" 从黑名单移除').format(username), 2000)
        return jsonify({"ok": True, "users": users_out})

    @app.route("/api/blacklist/users/clear", methods=["POST"])
    def api_blacklist_users_clear():
        with state.lock:
            users = state.config.blacklist.user_blacklist
            if not users:
                state.toast("info", _("提示"), _("用户黑名单为空，无需清空"), 2000)
                return jsonify({"ok": False, "empty": True}), 409
            count = len(users)
            users.clear()
        logger.info(f"User blacklist cleared, deleted {count} users")
        state.toast("success", _("清空成功"), _("已清空 {} 个用户").format(count), 2000)
        return jsonify({"ok": True, "users": []})

    @app.route("/api/blacklist/messages/add", methods=["POST"])
    def api_blacklist_messages_add():
        data = request.get_json(force=True) or {}
        pattern = (data.get("pattern") or "").strip()
        is_regex = bool(data.get("is_regex"))

        if not pattern:
            state.toast("info", _("提示"), _("请输入规则"), 2000)
            return jsonify({"ok": False}), 400

        if is_regex:
            try:
                re.compile(pattern)
            except re.error as e:
                state.toast("error", _("正则表达式错误"), _("无效的正则表达式：{}").format(str(e)), 3000)
                return jsonify({"ok": False}), 400

        with state.lock:
            rules = state.config.blacklist.message_blacklist
            if not is_regex:
                exists = any(
                    not r.is_regex and r.pattern.lower() == pattern.lower()
                    for r in rules
                )
            else:
                exists = any(r.is_regex and r.pattern == pattern for r in rules)

            if exists:
                state.toast("info", _("提示"), _("该规则已存在"), 2000)
                return jsonify({"ok": False, "exists": True}), 409

            rules.append(MessageBlacklistRule(pattern=pattern, is_regex=is_regex))
            rules_out = [{"pattern": r.pattern, "is_regex": r.is_regex} for r in rules]

        state.toast("success", _("添加成功"), _("已添加规则：{}").format(pattern), 2000)
        return jsonify({"ok": True, "messages": rules_out})

    @app.route("/api/blacklist/messages/delete", methods=["POST"])
    def api_blacklist_messages_delete():
        data = request.get_json(force=True) or {}
        pattern = data.get("pattern") or ""
        with state.lock:
            rules = state.config.blacklist.message_blacklist
            target = next((r for r in rules if r.pattern == pattern), None)
            if target is None:
                return jsonify({"ok": False}), 404
            rules.remove(target)
            rules_out = [{"pattern": r.pattern, "is_regex": r.is_regex} for r in rules]
        type_text = _('正则表达式') if target.is_regex else _('关键词')
        state.toast("success", _("删除成功"), _('已删除规则：{}（{}）').format(target.pattern, type_text), 2000)
        return jsonify({"ok": True, "messages": rules_out})

    @app.route("/api/blacklist/messages/clear", methods=["POST"])
    def api_blacklist_messages_clear():
        with state.lock:
            rules = state.config.blacklist.message_blacklist
            if not rules:
                state.toast("info", _("提示"), _("消息黑名单为空，无需清空"), 2000)
                return jsonify({"ok": False, "empty": True}), 409
            count = len(rules)
            rules.clear()
        logger.info(f"Message blacklist cleared, deleted {count} rules")
        state.toast("success", _("清空成功"), _("已清空 {} 个规则").format(count), 2000)
        return jsonify({"ok": True, "messages": []})

    # ── 设置 ──

    @app.route("/api/settings/language", methods=["POST"])
    def api_settings_language():
        data = request.get_json(force=True) or {}
        code = data.get("code") or ""
        name = data.get("name") or code
        if not code:
            return jsonify({"ok": False}), 400
        logger.info(f"Language setting applied: {name} ({code})")
        if update_config(settings__interface_language=code):
            state.toast("success", _("设置已保存"), _("界面语言已设置为 {}，重启后生效。").format(name), 3000)
            return jsonify({"ok": True})
        state.toast("error", _("保存失败"), _("写入配置文件失败"), 4000)
        return jsonify({"ok": False}), 500

    # ── 更新 ──

    @app.route("/api/update/check", methods=["POST"])
    def api_update_check():
        if not hasattr(state, 'updater') or state.updater is None:
            state.toast("error", _("错误"), _("更新器未初始化"), 3000)
            return jsonify({"ok": False}), 500
        data = request.get_json(force=True) or {}
        silent = bool(data.get("silent"))
        include_prerelease = bool(data.get("include_prerelease"))
        state.updater.include_prerelease = include_prerelease

        with state.lock:
            if state._check_thread and state._check_thread.is_alive():
                return jsonify({"ok": False, "running": True}), 409

        thread = threading.Thread(
            target=_check_update_task,
            args=(state, silent),
            daemon=True,
            name="webui-update-check",
        )
        with state.lock:
            state._check_thread = thread
        thread.start()
        return jsonify({"ok": True})

    @app.route("/api/update/download", methods=["POST"])
    def api_update_download():
        with state.lock:
            if state.download_active:
                return jsonify({"ok": False, "running": True}), 409
            release = state._last_release
            if not release:
                return jsonify({"ok": False, "error": "no release"}), 400
            state.download_active = True
            state._download_cancel_requested = False
            worker = _DownloadWorker(state, release)
            thread = threading.Thread(target=worker.download, daemon=True, name="webui-download")
            state._download_thread = thread
            state._download_worker = worker
        thread.start()
        return jsonify({"ok": True})

    @app.route("/api/update/cancel", methods=["POST"])
    def api_update_cancel():
        with state.lock:
            worker = getattr(state, "_download_worker", None)
            if worker:
                worker.cancel()
        return jsonify({"ok": True})

    # ── 缓存 ──

    @app.route("/api/cache/inspect", methods=["POST"])
    def api_cache_inspect():
        try:
            stale_count, total_before = prune_stale_cache(dry_run=True)
        except Exception as e:
            logger.error(f"Failed to query cache: {e}")
            state.toast("error", _("清理失败"), _("查询缓存时出错：{}").format(str(e)), 3000)
            return jsonify({"ok": False}), 500
        return jsonify({"ok": True, "stale_count": stale_count, "total": total_before})

    @app.route("/api/cache/clear", methods=["POST"])
    def api_cache_clear():
        try:
            stale_count, _total = prune_stale_cache()
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            state.toast("error", _("清理失败"), str(e), 3000)
            return jsonify({"ok": False}), 500
        if stale_count == 0:
            state.toast("info", _("无需清理"), _("没有不常用的缓存条目，所有缓存都曾被使用过。"), 3000)
        else:
            state.toast("success", _("清理成功"), _("已清理 {} 条不常用缓存条目").format(stale_count), 3000)
        return jsonify({"ok": True, "cleared": stale_count})

    # ── SSE ──

    @app.route("/api/events")
    def api_events():
        queue = state.sse_subscribe()

        def event_stream():
            last_heartbeat = time.time()
            try:
                yield "retry: 3000\n\n"
                while True:
                    while queue:
                        item = queue.pop(0)
                        payload = item["data"]
                        if not isinstance(payload, (dict, list)):
                            payload = {"value": payload}
                        yield f"event: {item['event']}\n"
                        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                        last_heartbeat = time.time()
                    if time.time() - last_heartbeat >= 15:
                        yield ": ping\n\n"
                        last_heartbeat = time.time()
                    time.sleep(0.1)
            except GeneratorExit:
                state.sse_unsubscribe(queue)
            except Exception as e:
                logger.error(f"SSE stream error: {e}", exc_info=True)
                state.sse_unsubscribe(queue)

        response = Response(event_stream(), mimetype="text/event-stream")
        response.headers["Cache-Control"] = "no-cache"
        response.headers["X-Accel-Buffering"] = "no"
        response.headers["Connection"] = "keep-alive"
        return response

    return app
