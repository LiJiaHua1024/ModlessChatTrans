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
from dataclasses import dataclass, field
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
    """一条已翻译消息的上下文记录"""
    original: str           # 原文（单条聊天内容）
    translated: str         # 译文
    timestamp: float        # epoch 秒（日志时间或行到达系统时间）
    player_name: str = ""   # 发送者玩家名（可为空，系统消息等）


class ContextBuffer:
    """
    维护有序的翻译上下文历史，供后续消息的 messages 列表使用。

    支持两种分割策略：
    - "fixed"     : 固定保留最近 context_length 条，不基于时间分割
    - "time_based": 同时检测时间跨度，超过 context_timeout 秒则清空缓冲区
    """

    def __init__(
        self,
        strategy: str = "time_based",
        context_length: int = 10,
        context_timeout: float = 120.0,
    ):
        """
        :param strategy:        "fixed" 或 "time_based"
        :param context_length:  最多保留的历史条数（两种策略均生效）
        :param context_timeout: 时间跨度阈值（秒），仅 time_based 策略生效
        """
        if strategy not in ("fixed", "time_based"):
            logger.warning(
                f"Unknown context strategy '{strategy}', falling back to 'time_based'."
            )
            strategy = "time_based"

        self.strategy = strategy
        self.context_length = max(1, context_length)
        self.context_timeout = max(0.0, context_timeout)

        self._history: deque[ContextEntry] = deque(maxlen=self.context_length)
        self._last_timestamp: Optional[float] = None

    # ------------------------------------------------------------------
    # 写入
    # ------------------------------------------------------------------

    def push(self, entry: ContextEntry) -> None:
        """
        添加一条已翻译记录。
        如果 time_based 策略判断需要重置，先清空再添加。
        """
        if self.strategy == "time_based" and self.should_reset(entry.timestamp):
            logger.debug(
                f"[ContextBuffer] Time gap detected "
                f"({entry.timestamp - (self._last_timestamp or 0):.1f}s > "
                f"{self.context_timeout}s), resetting context."
            )
            self.clear()

        self._history.append(entry)
        self._last_timestamp = entry.timestamp

    def push_batch(self, entries: list[ContextEntry]) -> None:
        """
        批量添加（打包翻译完成后调用），按顺序逐条 push。
        只用第一条做时间跨度判断（避免批次内部误清空）。
        """
        if not entries:
            return
        # 仅对批次第一条做时间重置判断
        first = entries[0]
        if self.strategy == "time_based" and self.should_reset(first.timestamp):
            logger.debug(
                f"[ContextBuffer] Time gap detected at batch start, resetting context."
            )
            self.clear()

        for entry in entries:
            self._history.append(entry)
        self._last_timestamp = entries[-1].timestamp

    # ------------------------------------------------------------------
    # 读取
    # ------------------------------------------------------------------

    def get_context_messages(self) -> list[dict]:
        """
        返回可直接拼入 litellm messages 的历史列表，格式：
        [
            {"role": "user",      "content": "<原文>"},
            {"role": "assistant", "content": "<译文>"},
            ...
        ]
        注意：此处 user content 只包含原文本身（不含 "Translate..." 前缀），
        以保持简洁并最大化 LLM prefix caching 效果。
        """
        messages = []
        for entry in self._history:
            messages.append({"role": "user",      "content": entry.original})
            messages.append({"role": "assistant", "content": entry.translated})
        return messages

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
