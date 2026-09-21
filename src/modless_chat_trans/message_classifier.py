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

"""消息分类：判定一条聊天行是玩家消息还是服务器消息。

两种模式（由配置 message-classification.classifier 决定）：

- rule：内置规则（在 message_processor.rule_classify 中实现），不联网、零额外延迟
- jev：由 Jev（TypeSafe 的 System One 决策模型）判定，调用失败或超时自动回退规则

Jev 的接口是「一次请求、多个独立问题」：整批聊天行各自作为一个 question 并行判定，
因此一批消息只产生一次 HTTP 请求。问题用 noul（yes/no）形式，返回的玩家概率按阈值
0.5 取判定；概率只写进日志——概率低仍然采用 Jev 的判定，只有请求失败才回退规则。

两种调用方式（请求体与响应体一致，仅端点、模型名与鉴权不同）：

- TypeSafe 官方：POST https://api.typesafe.ai/v1/systemone，模型 jev-latest
- OpenRouter：POST https://openrouter.ai/api/alpha/decisions，模型 typesafe/jev-latest
"""

import re
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from modless_chat_trans.config import (
    JevProvider,
    MessageClassificationConfig,
    MessageClassifierType,
)
from modless_chat_trans.logger import logger
from modless_chat_trans.message_processor import rule_classify


def _http():
    """懒加载 requests，避免拖慢程序启动"""
    import requests
    return requests


# Minecraft 格式化代码：§ 加一个字符
_RE_FORMAT_CODE = re.compile(r"§.")


# 各服务商的默认端点与模型；配置里留空时使用
JEV_PROVIDER_DEFAULTS: Dict[JevProvider, Dict[str, str]] = {
    JevProvider.TYPESAFE: {
        "api_base": "https://api.typesafe.ai/v1/systemone",
        "model": "jev-latest",
    },
    JevProvider.OPENROUTER: {
        "api_base": "https://openrouter.ai/api/alpha/decisions",
        "model": "typesafe/jev-latest",
    },
}

# 发送给 Jev 的最近聊天行条数：让模型能看到该服务器的说话人格式（头衔、标签等）
RECENT_CONTEXT_LINES = 5
# 单行正文与上下文单行的截断长度，避免异常长的行把请求体撑大
MAX_LINE_CHARS = 400
MAX_CONTEXT_LINE_CHARS = 200

# 连续失败达到该次数后暂停使用 Jev，暂停期间回退规则
FAILURE_THRESHOLD = 3
PAUSE_SECONDS = 60.0

# Noul 概率的判定阈值：0.5 即取概率更高的一侧，与二选一取值等价。
# 按既定策略，低置信度仍然采用 Jev 的判定，只有请求失败才回退规则。
PLAYER_THRESHOLD = 0.5

# 判定问题。用 Noul（yes/no）而不是 Choice：这里只有两种互斥结果，答案直接落到 if 上，
# 而 Noul 返回的概率本身还能当把握程度用。问题必须写成 yes/no，且 yes 对应玩家消息。
_JEV_QUESTION = "Was `line` typed by a player and sent to chat?"

# Noul 的 criteria 分 true/false 两侧描述边界。两侧都写：判定边界本身就是两面，
# 而且 OpenRouter 在带 criteria 时要求两侧齐全（TypeSafe 允许只给其中一侧）。
_JEV_CRITERIA = {
    "true": (
        "`line` was typed by a player and sent to chat. Whatever comes before the message names "
        "that player, and may carry decorations around or before the name: rank, guild / party / "
        "faction tag, level, custom title, emoji or symbol, e.g. 'Steve: hi', '[MVP+] Steve: hi', "
        "'OP Diamond II Steve: hi', 'Guild > Steve: hi', '★ Steve: hi', '<Steve> hi'. "
        "The part after the prefix is conversational text a player wrote; it may be in any language."
    ),
    "false": (
        "`line` was produced by the server, a plugin or the game client, and no player typed it. "
        "Announcements, welcome messages, join / leave notices, tips, warnings, errors, command "
        "feedback, achievements, scoreboards, objective and timer updates, NPC or plugin output, "
        "server advertisements. A colon may appear, but the text before it is not the name of a "
        "player who is speaking."
    ),
}


@dataclass
class JevAnswer:
    """一条聊天行的 Jev 判定结果"""
    is_player: Optional[bool]          # None 表示这一行没有拿到有效答案
    probability: Optional[float] = None  # noul 概率，越接近 1 越像玩家消息


_lock = threading.Lock()
_config: Optional[MessageClassificationConfig] = None
_jev_enabled = False                # Jev 是否可用（已选择且配置完整）
_consecutive_failures = 0
_paused_until = 0.0                 # 熔断截止时间（time.monotonic）
_recent_lines: List[str] = []       # 最近的聊天行，作为 Jev 的判定上下文


def init_classifier(classification_config: Optional[MessageClassificationConfig]) -> None:
    """
    按配置初始化消息分类器。

    选择 Jev 但未填写 API Key 时回退到内置规则，并写入 warning 日志。
    """
    global _config, _jev_enabled, _consecutive_failures, _paused_until, _recent_lines

    with _lock:
        _config = classification_config
        _consecutive_failures = 0
        _paused_until = 0.0
        _recent_lines = []

        if classification_config is None:
            _jev_enabled = False
            logger.info("[Classifier] 未提供消息分类配置，使用内置规则判定")
            return

        if classification_config.classifier != MessageClassifierType.JEV:
            _jev_enabled = False
            logger.info("[Classifier] 消息分类方式：内置规则")
            return

        provider = classification_config.provider
        if not (classification_config.api_key or "").strip():
            _jev_enabled = False
            logger.warning(
                f"[Classifier] 已选择 Jev 判定，但未配置 {provider.value} 的 API Key，"
                f"已回退到内置规则判定。请在「消息分类设置」界面填写 API Key 后重新启动。"
            )
            return

        _jev_enabled = True
        logger.info(
            f"[Classifier] 消息分类方式：Jev"
            f"（服务商 {provider.value}，模型 {resolve_model() or '?'}，"
            f"端点 {resolve_endpoint() or '?'}，"
            f"超时 {_request_timeout()}s）"
        )


def is_jev_enabled() -> bool:
    """当前是否已启用 Jev 判定（配置完整且未被熔断暂停）"""
    if not _jev_enabled:
        return False
    return time.monotonic() >= _paused_until


def resolve_endpoint() -> str:
    """取实际使用的端点：配置优先，留空用服务商默认值"""
    if _config is None:
        return ""
    default = JEV_PROVIDER_DEFAULTS.get(_config.provider, {}).get("api_base", "")
    return (_config.api_base or "").strip() or default


def resolve_model() -> str:
    """取实际使用的模型：配置优先，留空用服务商默认值"""
    if _config is None:
        return ""
    default = JEV_PROVIDER_DEFAULTS.get(_config.provider, {}).get("model", "")
    return (_config.model or "").strip() or default


def _request_timeout() -> float:
    if _config is None or not _config.timeout:
        return 2.0
    return float(_config.timeout)


def classify_lines(chat_texts: Sequence[str]) -> List[bool]:
    """
    判定一批聊天行是否为玩家消息。

    :param chat_texts: 已从日志行中取出的聊天原文（不含 [CHAT] 前缀）
    :return: 与 chat_texts 等长的布尔列表，True 表示玩家消息

    Jev 判定失败时，失败的那一行（或整批）自动回退到内置规则。
    """
    if not chat_texts:
        return []

    with _lock:
        _resume_if_paused()
        answers = _classify_with_jev(list(chat_texts)) if is_jev_enabled() else None
        verdicts = [
            (answers[index].is_player if answers is not None and index < len(answers) else None)
            for index in range(len(chat_texts))
        ]
        results = [
            rule_classify(text) if verdict is None else verdict
            for text, verdict in zip(chat_texts, verdicts)
        ]
        if _jev_enabled:
            _remember_lines(chat_texts)

    return results


def _resume_if_paused() -> None:
    """熔断暂停结束后恢复 Jev 判定"""
    global _paused_until

    if _paused_until and time.monotonic() >= _paused_until:
        _paused_until = 0.0
        logger.info("[Classifier] Jev 暂停结束，恢复使用 Jev 判定")


def _remember_lines(chat_texts: Sequence[str]) -> None:
    """记录最近的聊天行，供下一批判定参考"""
    global _recent_lines
    _recent_lines = (_recent_lines + [text for text in chat_texts])[-RECENT_CONTEXT_LINES:]


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit]


def strip_format_codes(text: str) -> str:
    """去掉 Minecraft 格式化代码（§ 加一个字符），让 Jev 看到玩家眼里的文字。

    日志里的聊天行常夹着 §6/§l 这类颜色样式码，它们会把说话人前缀切碎
    （如 "§6[MVP§c+§6] Steve§f: hi"），既占 token 又干扰判断。
    """
    return _RE_FORMAT_CODE.sub("", text)


def build_request_body(chat_texts: Sequence[str], context_lines: Sequence[str]) -> dict:
    """
    构造 Jev 请求体。

    每一行聊天是一个独立的 noul 问题（是否由玩家发出），最近聊天行放在 state 里作为
    判定上下文。发给 Jev 的文本会先去掉格式化代码，判定结果不受影响。
    """
    questions = {}
    for index, text in enumerate(chat_texts):
        questions[f"line_{index}"] = {
            "type": "noul",
            "instructions": {
                "line": _truncate(strip_format_codes(text), MAX_LINE_CHARS),
                "question": _JEV_QUESTION,
            },
            "criteria": _JEV_CRITERIA,
        }

    return {
        "model": resolve_model(),
        "state": {
            # 每个问题共用的背景：说明这是什么材料
            "material": "Lines from Minecraft multiplayer chat, as written in the game log.",
            "recent_chat_lines": [
                _truncate(strip_format_codes(line), MAX_CONTEXT_LINE_CHARS) for line in context_lines
            ],
        },
        "questions": questions,
    }


def parse_answers(payload: dict, count: int) -> Optional[List[JevAnswer]]:
    """
    解析 Jev 响应，取出每行的判定与概率。

    响应缺少 answers 时返回 None（调用方回退规则）；某一行的答案缺失或非法时，
    该项的 is_player 为 None，仅该行回退规则。
    """
    answers = payload.get("answers") if isinstance(payload, dict) else None
    if not isinstance(answers, dict):
        return None

    parsed: List[JevAnswer] = []
    for index in range(count):
        answer = answers.get(f"line_{index}")
        if not isinstance(answer, dict):
            parsed.append(JevAnswer(is_player=None))
            continue

        probability = answer.get("noul")
        if isinstance(probability, (int, float)):
            parsed.append(JevAnswer(
                is_player=probability >= PLAYER_THRESHOLD,
                probability=float(probability),
            ))
        else:
            parsed.append(JevAnswer(is_player=None))
    return parsed


def _classify_with_jev(chat_texts: List[str]) -> Optional[List[JevAnswer]]:
    """
    调用 Jev 判定一批聊天行。失败（超时、网络错误、非 200、响应非法）时返回 None。
    """
    global _consecutive_failures, _paused_until

    endpoint = resolve_endpoint()
    api_key = (_config.api_key or "").strip()
    timeout = _request_timeout()
    body = build_request_body(chat_texts, list(_recent_lines))
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    started = time.monotonic()
    try:
        # 连接超时单独限制，避免服务不可达时长时间阻塞消息流水线
        response = _http().post(endpoint, json=body, headers=headers, timeout=(min(timeout, 3.0), timeout))
        elapsed = time.monotonic() - started
        if response.status_code != 200:
            raise RuntimeError(f"HTTP {response.status_code}: {_truncate(response.text or '', 200)}")
        payload = response.json()
    except Exception as error:
        _on_failure(f"{type(error).__name__}: {error}")
        return None

    answers = parse_answers(payload, len(chat_texts))
    if answers is None:
        _on_failure(f"响应缺少 answers 字段：{_truncate(str(payload), 200)}")
        return None

    _consecutive_failures = 0
    model = payload.get("model") if isinstance(payload, dict) else None
    usage = payload.get("usage") if isinstance(payload, dict) else None
    logger.debug(
        f"[Classifier] Jev 判定完成：{len(chat_texts)} 行，耗时 {elapsed * 1000:.0f}ms，"
        f"模型 {model or '?'}，用量 {usage or '?'}"
    )
    for index, answer in enumerate(answers):
        if answer.is_player is None:
            logger.warning(
                f"[Classifier] Jev 未返回第 {index} 行的有效判定，该行回退内置规则："
                f"{_truncate(chat_texts[index], 80)}"
            )
        else:
            probability = answer.probability
            margin = "" if probability is None else f"（距阈值 {abs(probability - PLAYER_THRESHOLD):.2f}）"
            logger.debug(
                f"[Classifier] Jev 判定第 {index} 行为"
                f"{'玩家消息' if answer.is_player else '服务器消息'}，"
                f"玩家概率 {probability if probability is not None else '?'}{margin}"
            )
    return answers


def _on_failure(message: str) -> None:
    """记录一次调用失败，连续失败达到阈值时暂停使用 Jev"""
    global _consecutive_failures, _paused_until

    _consecutive_failures += 1
    logger.warning(
        f"[Classifier] Jev 调用失败（连续第 {_consecutive_failures} 次），本次回退内置规则：{message}"
    )
    if _consecutive_failures >= FAILURE_THRESHOLD:
        _consecutive_failures = 0
        _paused_until = time.monotonic() + PAUSE_SECONDS
        logger.warning(
            f"[Classifier] Jev 连续失败，暂停 {int(PAUSE_SECONDS)} 秒后重试，暂停期间使用内置规则"
        )
