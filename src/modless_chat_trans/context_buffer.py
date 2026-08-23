# Copyright (C) 2024-2025 LiJiaHua1024
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
from collections import deque
from dataclasses import dataclass
from datetime import datetime, time as dt_time
from typing import Optional

from modless_chat_trans.logger import logger

# 支持 Vanilla / Forge / Fabric / BungeeCord 等常见 MC 日志时间格式
# 匹配 [HH:MM:SS] 或行首 HH:MM:SS
_RE_LOG_TIMESTAMP = re.compile(r'\[?(\d{2}):(\d{2}):(\d{2})\]?')


def extract_log_time(line: str, fallback: float) -> float:
    """
    从 Minecraft 日志行提取时间戳（epoch 秒）。

    :param line: 日志行原文
    :param fallback: 提取失败时使用的系统时间（time.time()）
    :return: epoch 秒
    """
    m = _RE_LOG_TIMESTAMP.search(line)
    if m:
        try:
            h, mi, s = int(m.group(1)), int(m.group(2)), int(m.group(3))
            today = datetime.now().date()
            dt = datetime.combine(today, dt_time(h, mi, s))
            ts = dt.timestamp()
            # 跨午夜修正：若解析时间与系统时间偏差超过 12 小时，说明已跨天
            diff = fallback - ts
            if diff > 43200:
                # 解析时间在 fallback 之前超过 12 小时（如昨天凌晨）：加一天
                ts += 86400
            elif diff < -43200:
                # 解析时间在 fallback 之后超过 12 小时（如昨晚日志跨零点）：减一天
                ts -= 86400
            return ts
        except (ValueError, OverflowError):
            pass
    return fallback


@dataclass
class ContextEntry:
    """一条消息的上下文记录"""
    original: str           # 原文（单条聊天内容）
    timestamp: float        # epoch 秒（日志时间或行到达系统时间）
    player_name: str = ""   # 发送者玩家名（可为空，系统消息等）


class ContextBuffer:
    """
    维护有序的翻译上下文历史，以单条汇总消息的形式注入后续翻译请求。

    支持三种策略：
    - "disabled"  : 不启用上下文翻译（所有操作无实际效果）
    - "fixed"     : 固定保留最近 context_length 条，不基于时间分割
    - "time_based": 同时检测时间跨度，超过 context_timeout 秒则清空缓冲区

    支持分块截断（Block Truncation）以提升 LLM prefix-cache 命中率：
    当 block_truncation_size 非 "disabled" 且 context_length > 0 时，使用 list
    代替 deque，在缓冲达到 context_length 时一次性剔除开头 block_size 条，
    使前缀在后续 block_size 条消息中保持稳定，从而被 LLM 缓存命中。
    """

    def __init__(
        self,
        strategy: str = "time_based",
        context_length: int = 10,
        context_timeout: float = 120.0,
        block_truncation_size: str = "disabled",
    ):
        """
        :param strategy:              "disabled", "fixed" 或 "time_based"
        :param context_length:        最多保留的历史条数（0 = 无限制）
        :param context_timeout:       时间跨度阈值（秒），仅 time_based 策略生效
        :param block_truncation_size: "disabled", "auto", 或正整数字符串（如 "5"）
        """
        if strategy not in ("disabled", "fixed", "time_based"):
            logger.warning(
                f"Unknown context strategy '{strategy}', falling back to 'time_based'."
            )
            strategy = "time_based"

        self.strategy = strategy
        self.context_length = context_length       # 0 = 无限制
        self.context_timeout = max(0.0, context_timeout)

        # 解析分块截断大小
        self._block_size: Optional[int] = None
        if strategy != "disabled" and context_length > 0:
            self._block_size = self._resolve_block_size(block_truncation_size)
        self._use_block_truncation = self._block_size is not None

        # 选择底层存储
        if self._use_block_truncation:
            self._history: list[ContextEntry] = []                # list 用于分块截断
        elif context_length > 0:
            self._history: deque[ContextEntry] = deque(maxlen=context_length)  # 传统滑动窗口
        else:
            self._history: deque[ContextEntry] = deque()          # 无限制

        self._last_timestamp: Optional[float] = None

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    def _resolve_block_size(self, value: str) -> Optional[int]:
        """
        解析 block_truncation_size 配置值。

        :param value: "disabled", "auto", 或正整数字符串
        :return: 整型 block_size，或 None（表示禁用分块截断）
        """
        if value == "disabled":
            return None
        if value == "auto":
            return max(1, self.context_length // 2)
        try:
            size = int(value)
            if size <= 0:
                logger.warning(
                    f"[ContextBuffer] block_truncation_size must be positive, "
                    f"got {value!r}, falling back to disabled."
                )
                return None
            return size
        except ValueError:
            logger.warning(
                f"[ContextBuffer] Invalid block_truncation_size {value!r}, "
                f"falling back to disabled."
            )
            return None

    @property
    def block_size(self) -> Optional[int]:
        """已解析的分块截断大小，None 表示未启用"""
        return self._block_size

    # ------------------------------------------------------------------
    # 写入
    # ------------------------------------------------------------------

    def push(self, entry: ContextEntry) -> None:
        """
        添加一条已翻译记录。
        如果 strategy == "disabled" 则无操作。
        如果 time_based 策略判断需要重置，先清空再添加。
        如果启用了分块截断且缓冲达到上限，移除最早的一个数据块。
        """
        # 禁用策略：不维护任何历史
        if self.strategy == "disabled":
            return

        if self.strategy == "time_based" and self.should_reset(entry.timestamp):
            logger.debug(
                f"[ContextBuffer] Time gap detected "
                f"({entry.timestamp - (self._last_timestamp or 0):.1f}s > "
                f"{self.context_timeout}s), resetting context."
            )
            self.clear()

        self._history.append(entry)
        self._last_timestamp = entry.timestamp

        # 分块截断：达到阈值时一次性剔除开头 block_size 条
        if self._use_block_truncation and len(self._history) >= self.context_length:
            del self._history[:self._block_size]

    # ------------------------------------------------------------------
    # 读取
    # ------------------------------------------------------------------

    def get_context_messages(self) -> list[dict]:
        """
        返回一条汇总的 user 消息，包含最近聊天历史。
        格式：[{"role": "user", "content": "14:30 | [PlayerA] 你好\n14:31 | [SYSTEM] 服务器消息"}]
        无历史时返回空列表。

        注意：此返回值会被 translator 注入到 user message 中。
        """
        if self.strategy == "disabled" or not self._history:
            return []

        lines = []
        for entry in self._history:
            time_str = datetime.fromtimestamp(entry.timestamp).strftime("%H:%M")
            name = entry.player_name if entry.player_name else "[SYSTEM]"
            lines.append(f"{time_str} | [{name}] {entry.original}")

        content = "\n".join(lines)
        return [{"role": "user", "content": content}]

    # ------------------------------------------------------------------
    # 控制
    # ------------------------------------------------------------------

    def should_reset(self, current_timestamp: float) -> bool:
        """
        判断当前消息是否触发上下文重置（仅 time_based 策略）。

        :param current_timestamp: 当前消息的时间戳（epoch 秒）
        :return: True 表示应当清空上下文
        """
        if self.strategy != "time_based":
            return False
        if self._last_timestamp is None:
            return False
        return (current_timestamp - self._last_timestamp) > self.context_timeout

    def clear(self) -> None:
        """清空上下文缓冲区"""
        self._history.clear()
        self._last_timestamp = None

    def __len__(self) -> int:
        return len(self._history)
