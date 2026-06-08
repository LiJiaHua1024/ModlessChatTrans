# Copyright (C) 2025 LiJiaHua1024
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

import re
import os
import time
import asyncio
import tempfile
import threading
from collections import deque
from typing import Optional, List

from modless_chat_trans.logger import logger

# ─────────────────────────────────────
# 可选依赖：edge_tts / miniaudio
# 若导入失败则降级：TTS_AVAILABLE=False，功能被禁用
# ─────────────────────────────────────
try:
    import edge_tts
    import miniaudio
    TTS_AVAILABLE = True
    TTS_IMPORT_ERROR: Optional[str] = None
except ImportError as _tts_import_exc:
    edge_tts = None  # type: ignore[assignment]
    miniaudio = None  # type: ignore[assignment]
    TTS_AVAILABLE = False
    TTS_IMPORT_ERROR = str(_tts_import_exc)
    logger.warning(f"[TTS] Optional TTS dependencies not available, TTS disabled: {_tts_import_exc}")

# ─────────────────────────────────────
# 预编译正则（文本预处理）
# ─────────────────────────────────────
_RE_FORMAT_CODE = re.compile(r'§[0-9a-fklmnorA-FKLMNOR]')
_RE_BRACKET_TAGS = re.compile(r'\[.*?\]')
_RE_URL = re.compile(r'https?://\S+')
_RE_REPEATED_PUNCT_EN = re.compile(r'([!?,.:;])\1{2,}')
_RE_REPEATED_PUNCT_CJK = re.compile(r'([。！？，、；：])\1{1,}')
_RE_CONTROL_CHARS = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]')
_RE_MULTI_SPACE = re.compile(r'\s{2,}')

# ─────────────────────────────────────
# 目标语言 → Edge TTS 默认语音
# ─────────────────────────────────────
LANGUAGE_VOICE_MAP: dict[str, str] = {
    "zh-CN": "zh-CN-XiaoxiaoNeural",
    "Simplified Chinese": "zh-CN-XiaoxiaoNeural",
    "chinese": "zh-CN-XiaoxiaoNeural",
    "zh-TW": "zh-TW-HsiaoChenNeural",
    "Traditional Chinese": "zh-TW-HsiaoChenNeural",
    "ja-JP": "ja-JP-NanamiNeural",
    "japanese": "ja-JP-NanamiNeural",
    "en-US": "en-US-JennyNeural",
    "english": "en-US-JennyNeural",
    "ko-KR": "ko-KR-SunHiNeural",
    "korean": "ko-KR-SunHiNeural",
    "fr-FR": "fr-FR-DeniseNeural",
    "french": "fr-FR-DeniseNeural",
    "de-DE": "de-DE-KatjaNeural",
    "german": "de-DE-KatjaNeural",
    "es-ES": "es-ES-ElviraNeural",
    "spanish": "es-ES-ElviraNeural",
    "ru-RU": "ru-RU-SvetlanaNeural",
    "russian": "ru-RU-SvetlanaNeural",
    "pt-BR": "pt-BR-FranciscaNeural",
    "portuguese": "pt-BR-FranciscaNeural",
}

# 获取所有可用语音的缓存（首次调用时从 Edge 拉取）
_voice_list_cache: Optional[List[dict]] = None
_voice_cache_lock = threading.Lock()


def preprocess_for_tts(text: str) -> str:
    """
    清洗聊天文本以适合 TTS 朗读：
    1. 移除 Minecraft 格式化代码 (§[0-9a-fklmnor])
    2. 移除方括号标签（[MVP++], [ADMIN], [SHOUT] 等）
    3. 移除 URL（http/https），替换为 "链接"
    4. 规范化重复标点（!!!! -> !，。。。 -> 。）
    5. 移除不可读的控制字符
    6. 多余空白规范化
    返回干净的朗读文本，如果清洗后为空则返回空字符串
    """
    if not text or not isinstance(text, str):
        return ""

    # 1. 移除 Minecraft 格式化代码
    text = _RE_FORMAT_CODE.sub('', text)

    # 2. 移除方括号标签（但保留尖括号玩家名）
    text = _RE_BRACKET_TAGS.sub('', text)

    # 3. 移除 URL，替换为 "链接"
    text = _RE_URL.sub('链接', text)

    # 4. 规范化重复标点
    text = _RE_REPEATED_PUNCT_EN.sub(r'\1', text)
    text = _RE_REPEATED_PUNCT_CJK.sub(r'\1', text)

    # 5. 移除控制字符
    text = _RE_CONTROL_CHARS.sub('', text)

    # 6. 规范化空白
    text = _RE_MULTI_SPACE.sub(' ', text)

    # 7. 去除首尾空白和非可读字符
    text = text.strip()

    # 8. 处理只有符号/空白的文本
    if not text or all(c in '!@#$%^&*()_+-=[]{}|;:,.<>?/~`\"\' \t\n\r' for c in text):
        return ""

    return text


def format_player_message(name: str, message: str, read_name: bool) -> str:
    """
    格式化玩家消息为自然朗读语句。
    read_name=True:  返回包含玩家名的短语
    read_name=False: 只返回消息内容
    """
    if not message:
        return ""

    cleaned_message = preprocess_for_tts(message)
    if not cleaned_message:
        return ""

    if read_name and name:
        cleaned_name = preprocess_for_tts(name)
        if cleaned_name:
            return f"{cleaned_name} 说：{cleaned_message}"

    return cleaned_message


def infer_voice(target_language: str, configured_voice: str) -> str:
    """
    推断实际使用的 Edge TTS 语音名。
    如果 configured_voice == "auto"，则从 target_language 映射；
    否则直接使用配置的语音名。
    """
    if configured_voice and configured_voice.lower() != "auto":
        return configured_voice

    # 精确匹配
    if target_language in LANGUAGE_VOICE_MAP:
        return LANGUAGE_VOICE_MAP[target_language]

    # 不区分大小写匹配
    target_lower = target_language.lower()
    for key, voice in LANGUAGE_VOICE_MAP.items():
        if key.lower() == target_lower:
            return voice

    # 模糊匹配（检查 key 是否包含在 target_language 中或反之）
    for key, voice in LANGUAGE_VOICE_MAP.items():
        if key.lower() in target_lower or target_lower in key.lower():
            return voice

    # 兜底：简体中文
    logger.debug(f"[TTS] No voice mapping for language '{target_language}', falling back to zh-CN")
    return "zh-CN-XiaoxiaoNeural"


async def get_available_voices() -> List[dict]:
    """
    获取所有可用的 Edge TTS 语音列表。
    返回 [{"Name": "zh-CN-XiaoxiaoNeural", "Locale": "zh-CN", "Gender": "Female"}, ...]
    如果 edge_tts 不可用，直接返回空列表。
    """
    if not TTS_AVAILABLE:
        return []

    global _voice_list_cache
    with _voice_cache_lock:
        if _voice_list_cache is not None:
            return _voice_list_cache

    try:
        voices = await edge_tts.list_voices()
        _voice_list_cache = voices
        logger.info(f"[TTS] Loaded {len(voices)} voices from Edge TTS")
        return voices
    except Exception as e:
        logger.error(f"[TTS] Failed to load voices: {e}")
        return []


def get_available_voices_sync() -> List[dict]:
    """同步包装器，在线程安全的情况下获取可用语音"""
    if not TTS_AVAILABLE:
        return []

    global _voice_list_cache
    if _voice_list_cache is not None:
        return _voice_list_cache

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        voices = loop.run_until_complete(get_available_voices())
        loop.close()
        return voices
    except Exception as e:
        logger.error(f"[TTS] Failed to load voices synchronously: {e}")
        return []


# ─────────────────────────────────────
# miniaudio 播放辅助
# ─────────────────────────────────────

def _play_mp3_file(filepath: str, stop_flag: callable = None) -> bool:
    """
    使用 miniaudio 播放 MP3 文件，阻塞直到播放完成或收到停止信号。

    :param filepath:  MP3 文件路径
    :param stop_flag: 可调用对象，返回 True 表示需要停止播放
    :return: True 表示正常播放完成，False 表示被中断
    """
    device = None
    try:
        # 获取音频时长用于估算播放时间
        try:
            info = miniaudio.mp3_get_file_info(filepath)
            duration = info.duration
        except Exception:
            duration = 10.0  # 安全的默认值

        stream = miniaudio.stream_file(filepath)
        device = miniaudio.PlaybackDevice()
        device.start(stream)

        # 按音频时长等待，期间检查停止信号
        check_interval = 0.05
        elapsed = 0.0
        while elapsed < duration + 0.3:  # 加 0.3s 缓冲
            if stop_flag and stop_flag():
                try:
                    device.stop()
                except Exception:
                    pass
                return False
            time.sleep(check_interval)
            elapsed += check_interval

        return True
    except Exception as e:
        logger.error(f"[TTS] Playback error: {e}")
        return False
    finally:
        if device is not None:
            try:
                device.close()
            except Exception:
                pass


# ─────────────────────────────────────
# TTS 引擎
# ─────────────────────────────────────

class TTSEngine:
    """Edge TTS 朗读引擎，队列式顺序朗读，绝不重叠"""

    def __init__(self, config):
        """
        :param config: TTSConfig from config.py
        """
        from modless_chat_trans.config import TTSConfig
        self._config: TTSConfig = config
        self._message_queue: deque[tuple[str, str]] = deque(
            maxlen=config.max_queue_size
        )
        self._lock = threading.Lock()
        self._running = False
        # 若依赖库不可用，强制禁用 TTS
        self._enabled = config.enabled and TTS_AVAILABLE
        self._playback_thread: Optional[threading.Thread] = None
        self._last_spoken_text: Optional[str] = None
        self._currently_playing = False
        self._stop_requested = False

    # ── 属性 ──────────────────────────

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def is_playing(self) -> bool:
        return self._currently_playing

    @property
    def queue_size(self) -> int:
        with self._lock:
            return len(self._message_queue)

    # ── 公开方法 ──────────────────────

    def start(self):
        """启动 TTS 播放线程"""
        if self._running:
            return

        if not self._enabled:
            logger.debug("[TTS] Engine disabled, not starting")
            return

        self._running = True
        self._stop_requested = False
        self._playback_thread = threading.Thread(
            target=self._playback_loop,
            name="tts-playback",
            daemon=True,
        )
        self._playback_thread.start()
        logger.info("[TTS] Engine started")

    def stop(self):
        """停止 TTS 引擎，中断当前播放，清空队列"""
        logger.info("[TTS] Stopping engine...")
        self._stop_requested = True
        self._running = False

        with self._lock:
            self._message_queue.clear()
            self._last_spoken_text = None

        if self._playback_thread and self._playback_thread.is_alive():
            self._playback_thread.join(timeout=3.0)

        self._currently_playing = False
        logger.info("[TTS] Engine stopped")

    def enqueue(self, name: str, message: str, target_language: str):
        """
        将消息加入朗读队列。
        如果引擎未启用、消息为空或触发去重，则跳过。

        :param name: 玩家名
        :param message: 翻译后的消息文本
        :param target_language: 目标语言（用于自动选择语音）
        """
        if not self._enabled or not self._running:
            return

        if not message:
            return

        # 文本预处理
        cleaned = preprocess_for_tts(message)
        if not cleaned:
            return

        # 用户静音检查
        mute_users = self._config.mute_users if hasattr(self._config, 'mute_users') else []
        if name and mute_users:
            cleaned_name = preprocess_for_tts(name)
            if cleaned_name and cleaned_name in mute_users:
                logger.debug(f"[TTS] User '{cleaned_name}' is muted, skipping")
                return

        # 格式化最终朗读文本
        read_name = self._config.read_player_name if hasattr(self._config, 'read_player_name') else True
        speak_text = format_player_message(name, message, read_name)
        if not speak_text:
            return

        # 去重检查
        with self._lock:
            if self._last_spoken_text and speak_text == self._last_spoken_text:
                logger.debug(f"[TTS] Duplicate text skipped: {speak_text[:40]}...")
                return

            # 与队尾比较
            if self._message_queue:
                last_queued = self._message_queue[-1][1]
                if speak_text == last_queued:
                    logger.debug(f"[TTS] Same as tail, skipped: {speak_text[:40]}...")
                    return

            self._message_queue.append((speak_text, target_language))
            queue_len = len(self._message_queue)

        logger.debug(f"[TTS] Enqueued ({queue_len} in queue): {speak_text[:50]}...")

    def set_enabled(self, enabled: bool):
        """动态启用/禁用 TTS；若依赖库不可用则始终保持禁用"""
        if not TTS_AVAILABLE and enabled:
            logger.warning("[TTS] Cannot enable TTS: dependencies not available")
            return
        if enabled == self._enabled:
            return
        self._enabled = enabled
        if enabled:
            self.start()
        else:
            self.stop()

    def set_config(self, config):
        """运行时更新配置"""
        self._config = config

        # 更新队列最大长度
        with self._lock:
            new_queue = deque(self._message_queue, maxlen=config.max_queue_size)
            self._message_queue = new_queue

        # 如果之前禁用现在启用，且未在运行，则启动
        if config.enabled and not self._running:
            self._enabled = True
            self.start()

    # ── 内部方法 ──────────────────────

    def _playback_loop(self):
        """播放主循环（在线程中运行）"""
        # 为这个线程创建专属的 asyncio 事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        logger.info("[TTS] Playback loop started")

        while self._running:
            speak_text: Optional[str] = None
            target_language: str = ""

            with self._lock:
                if self._message_queue:
                    speak_text, target_language = self._message_queue.popleft()

            if speak_text is None:
                # 队列空，等待后重试
                time.sleep(0.2)
                continue

            self._currently_playing = True

            try:
                loop.run_until_complete(
                    self._synthesize_and_play(speak_text, target_language)
                )
            except Exception as e:
                logger.error(f"[TTS] Playback error: {e}")
            finally:
                with self._lock:
                    self._last_spoken_text = speak_text
                self._currently_playing = False

        loop.close()
        logger.info("[TTS] Playback loop ended")

    async def _synthesize_and_play(self, text: str, target_language: str):
        """
        合成语音并播放。
        1. 通过 edge-tts 合成到临时 MP3 文件
        2. miniaudio 加载并播放
        3. 等待播放完成或中断
        4. 清理临时文件
        """
        voice = infer_voice(
            target_language,
            self._config.voice if hasattr(self._config, 'voice') else "auto",
        )
        speed = self._config.speed if hasattr(self._config, 'speed') else "+0%"
        pitch = self._config.pitch if hasattr(self._config, 'pitch') else "+0Hz"

        tmp_path: Optional[str] = None

        if not TTS_AVAILABLE:
            return

        try:
            # 1. 创建临时文件用于音频输出
            fd, tmp_path = tempfile.mkstemp(suffix=".mp3", prefix="mct_tts_")
            os.close(fd)

            # 2. 使用 edge-tts 合成语音
            communicate = edge_tts.Communicate(
                text=text,
                voice=voice,
                rate=speed,
                pitch=pitch,
            )

            logger.debug(f"[TTS] Synthesizing: voice={voice}, text={text[:50]}...")
            await asyncio.wait_for(
                communicate.save(tmp_path),
                timeout=15.0,
            )

            if self._stop_requested:
                return

            # 3. 播放音频（在线程池中执行以避免阻塞事件循环）
            loop = asyncio.get_running_loop()
            completed = await loop.run_in_executor(
                None,
                _play_mp3_file,
                tmp_path,
                lambda: self._stop_requested,
            )

            if not completed:
                logger.debug("[TTS] Playback interrupted by stop signal")

        except asyncio.TimeoutError:
            logger.warning(f"[TTS] Synthesis timeout for text: {text[:50]}...")
        except Exception as e:
            logger.error(f"[TTS] Synthesis error: {e}")
        finally:
            # 4. 清理临时文件
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
