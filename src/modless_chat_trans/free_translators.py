# Copyright (C) 2026 LiJiaHua1024
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
#
# ─────────────────────────────────────────────────────────────────────
# 精简免费翻译引擎（替代 translators 库）
#
# 本模块仅覆盖 ModlessChatTrans 实际使用的 9 个免费 Web 翻译服务：
#   deepl / bing / google / yandex / alibaba / caiyun / youdao / sogou / iflyrec
#
# 请求与解析逻辑基于 translators 库 (GPL-3.0, Copyright (C) 2017 UlionTse)
# 的 server.py 移植，按本项目需要裁剪：
#   - 移除 lxml：改用标准库 re 解析 HTML
#   - 移除 exejs：JS 字面量求值改用正则 + json/ast
#   - 移除 niquests / httpx / cloudscraper / pathos / tqdm：统一 requests
#   - 移除 cryptography：Youdao AES-128-CBC 改为内置纯 Python 实现
#
# 接口保持与 translators 的 translate_text / get_languages 兼容。
# ─────────────────────────────────────────────────────────────────────

import ast
import base64
import hashlib
import json
import random
import re
import time
import uuid
from urllib.parse import quote, urlencode
from typing import Any, Dict, List, Optional, Tuple

import requests

__all__ = [
    "translate_text",
    "get_languages",
    "FreeTranslatorError",
    "SUPPORTED_TRANSLATORS",
]

# 与 translators 库一致的服务池（本项目接入的 9 个）
SUPPORTED_TRANSLATORS = (
    "alibaba", "bing", "caiyun", "deepl", "google", "iflyrec",
    "sogou", "yandex", "youdao",
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
)


class FreeTranslatorError(Exception):
    pass


# ─────────────────────────────────────────────────────────────────────
# 通用工具
# ─────────────────────────────────────────────────────────────────────

def _headers(host_url: str, if_api: bool = False) -> Dict[str, str]:
    """构建与 translators.get_headers 等价的请求头。"""
    if not if_api:
        return {"Referer": host_url, "User-Agent": USER_AGENT}
    origin = f"https://{host_url.split('//', 1)[1].split('/', 1)[0]}"
    return {
        "Origin": origin,
        "Referer": host_url,
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "User-Agent": USER_AGENT,
    }


def _parse_js_object(text: str, label: str) -> Any:
    """从 JS 文本中提取 `label = {...};` 的对象字面量并求值。

    先用 ast.literal_eval 尝试（覆盖 JSON 风格），失败时转 json.loads
    （替换 JS 中未加引号的键）。避免引入 exejs 的外部 JS 运行时依赖。
    """
    match = re.search(re.escape(label) + r"\s*=\s*(\{.*?\});", text, re.DOTALL)
    if not match:
        raise FreeTranslatorError(f"JS object not found: {label}")
    raw = match.group(1)
    try:
        return ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        pass
    normalized = re.sub(r"(\w+)\s*:", r'"\1":', raw)
    try:
        return json.loads(normalized)
    except json.JSONDecodeError as error:
        raise FreeTranslatorError(f"Failed to evaluate JS object {label}: {error}") from error


def _parse_js_list(text: str, label: str) -> list:
    """从 JS 文本中提取 `label = [...];` 的数组字面量并求值。"""
    match = re.search(re.escape(label) + r"\s*=\s*(\[.*?\]);", text, re.DOTALL)
    if not match:
        raise FreeTranslatorError(f"JS array not found: {label}")
    raw = match.group(1)
    try:
        return ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        pass
    normalized = re.sub(r"(\w+)\s*:", r'"\1":', raw)
    try:
        return json.loads(normalized)
    except json.JSONDecodeError as error:
        raise FreeTranslatorError(f"Failed to evaluate JS array {label}: {error}") from error


def _raise_for_status(response: requests.Response, service: str) -> None:
    if response.status_code != 200:
        raise FreeTranslatorError(
            f"{service} free API returned {response.status_code}: {response.text[:200]}"
        )


def _language_set(lang_list: List[str]) -> Dict[str, List[str]]:
    """把语言列表转成 translators 的 {lang: [lang...]} 映射格式。"""
    lang_list = sorted(set(lang_list))
    return {lang: lang_list for lang in lang_list}


def _check_language(from_language: str, to_language: str,
                    language_map: Dict[str, List[str]],
                    output_zh: str, output_auto: str = "auto") -> Tuple[str, str]:
    """语言校验，行为对齐 translators.Tse.check_language。"""
    zh_pool = ("zh", "zh-CN", "zh-cn", "zh-CHS", "zh-Hans", "zh-Hans_CN", "cn", "chi", "Chinese")
    auto_pool = ("auto", "detect", "auto-detect", "all")
    from_language = output_auto if from_language in auto_pool else from_language
    from_language = output_zh if from_language in zh_pool else from_language
    to_language = output_zh if to_language in zh_pool else to_language
    if from_language != output_auto and from_language not in language_map:
        raise FreeTranslatorError(f"Unsupported from_language[{from_language}]")
    if to_language not in language_map:
        raise FreeTranslatorError(f"Unsupported to_language[{to_language}]")
    if from_language != output_auto and to_language not in language_map[from_language]:
        raise FreeTranslatorError(
            f"Unsupported translation: from [{from_language}] to [{to_language}]"
        )
    if from_language == to_language:
        raise FreeTranslatorError(
            f"from_language[{from_language}] and to_language[{to_language}] should not be same."
        )
    return from_language, to_language


# ─────────────────────────────────────────────────────────────────────
# 纯 Python AES-128（仅 CBC 解密 + PKCS7，供 Youdao 使用）
# ─────────────────────────────────────────────────────────────────────

_AES_SBOX = [
    0x63, 0x7C, 0x77, 0x7B, 0xF2, 0x6B, 0x6F, 0xC5, 0x30, 0x01, 0x67, 0x2B, 0xFE, 0xD7, 0xAB, 0x76,
    0xCA, 0x82, 0xC9, 0x7D, 0xFA, 0x59, 0x47, 0xF0, 0xAD, 0xD4, 0xA2, 0xAF, 0x9C, 0xA4, 0x72, 0xC0,
    0xB7, 0xFD, 0x93, 0x26, 0x36, 0x3F, 0xF7, 0xCC, 0x34, 0xA5, 0xE5, 0xF1, 0x71, 0xD8, 0x31, 0x15,
    0x04, 0xC7, 0x23, 0xC3, 0x18, 0x96, 0x05, 0x9A, 0x07, 0x12, 0x80, 0xE2, 0xEB, 0x27, 0xB2, 0x75,
    0x09, 0x83, 0x2C, 0x1A, 0x1B, 0x6E, 0x5A, 0xA0, 0x52, 0x3B, 0xD6, 0xB3, 0x29, 0xE3, 0x2F, 0x84,
    0x53, 0xD1, 0x00, 0xED, 0x20, 0xFC, 0xB1, 0x5B, 0x6A, 0xCB, 0xBE, 0x39, 0x4A, 0x4C, 0x58, 0xCF,
    0xD0, 0xEF, 0xAA, 0xFB, 0x43, 0x4D, 0x33, 0x85, 0x45, 0xF9, 0x02, 0x7F, 0x50, 0x3C, 0x9F, 0xA8,
    0x51, 0xA3, 0x40, 0x8F, 0x92, 0x9D, 0x38, 0xF5, 0xBC, 0xB6, 0xDA, 0x21, 0x10, 0xFF, 0xF3, 0xD2,
    0xCD, 0x0C, 0x13, 0xEC, 0x5F, 0x97, 0x44, 0x17, 0xC4, 0xA7, 0x7E, 0x3D, 0x64, 0x5D, 0x19, 0x73,
    0x60, 0x81, 0x4F, 0xDC, 0x22, 0x2A, 0x90, 0x88, 0x46, 0xEE, 0xB8, 0x14, 0xDE, 0x5E, 0x0B, 0xDB,
    0xE0, 0x32, 0x3A, 0x0A, 0x49, 0x06, 0x24, 0x5C, 0xC2, 0xD3, 0xAC, 0x62, 0x91, 0x95, 0xE4, 0x79,
    0xE7, 0xC8, 0x37, 0x6D, 0x8D, 0xD5, 0x4E, 0xA9, 0x6C, 0x56, 0xF4, 0xEA, 0x65, 0x7A, 0xAE, 0x08,
    0xBA, 0x78, 0x25, 0x2E, 0x1C, 0xA6, 0xB4, 0xC6, 0xE8, 0xDD, 0x74, 0x1F, 0x4B, 0xBD, 0x8B, 0x8A,
    0x70, 0x3E, 0xB5, 0x66, 0x48, 0x03, 0xF6, 0x0E, 0x61, 0x35, 0x57, 0xB9, 0x86, 0xC1, 0x1D, 0x9E,
    0xE1, 0xF8, 0x98, 0x11, 0x69, 0xD9, 0x8E, 0x94, 0x9B, 0x1E, 0x87, 0xE9, 0xCE, 0x55, 0x28, 0xDF,
    0x8C, 0xA1, 0x89, 0x0D, 0xBF, 0xE6, 0x42, 0x68, 0x41, 0x99, 0x2D, 0x0F, 0xB0, 0x54, 0xBB, 0x16,
]
_AES_INV_SBOX = [0] * 256
for _i, _v in enumerate(_AES_SBOX):
    _AES_INV_SBOX[_v] = _i

_AES_RCON = (0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36)


def _aes_xtime(value: int) -> int:
    value <<= 1
    if value & 0x100:
        value ^= 0x11B
    return value & 0xFF


def _aes_multiply(a: int, b: int) -> int:
    result = 0
    while b:
        if b & 1:
            result ^= a
        a = _aes_xtime(a)
        b >>= 1
    return result & 0xFF


def _aes_key_expansion(key: bytes) -> List[List[int]]:
    """AES-128 密钥扩展，返回 11 轮轮密钥（每轮 16 字节列表）。"""
    nk, nr = 4, 10
    words = [[key[4 * i + j] for j in range(4)] for i in range(nk)]
    for i in range(nk, 4 * (nr + 1)):
        temp = list(words[i - 1])
        if i % nk == 0:
            temp = temp[1:] + temp[:1]
            temp = [_AES_SBOX[b] for b in temp]
            temp[0] ^= _AES_RCON[i // nk - 1]
        elif nk > 6 and i % nk == 4:
            temp = [_AES_SBOX[b] for b in temp]
        words.append([words[i - nk][j] ^ temp[j] for j in range(4)])
    round_keys = []
    for r in range(nr + 1):
        block = []
        for c in range(4):
            for w in range(4):
                block.append(words[4 * r + c][w])
        round_keys.append(block)
    return round_keys


def _aes_inv_sub_bytes(state: List[int]) -> List[int]:
    return [_AES_INV_SBOX[b] for b in state]


def _aes_inv_shift_rows(state: List[int]) -> List[int]:
    # state 以列主序存储（AES 规范布局）；InvShiftRows 每行循环右移
    result = list(state)
    for row in range(4):
        for col in range(4):
            result[col * 4 + row] = state[((col - row) % 4) * 4 + row]
    return result


def _aes_inv_mix_columns(state: List[int]) -> List[int]:
    result = list(state)
    for col in range(4):
        base = col * 4
        column = state[base:base + 4]
        result[base + 0] = _aes_multiply(column[0], 0x0E) ^ _aes_multiply(column[1], 0x0B) \
            ^ _aes_multiply(column[2], 0x0D) ^ _aes_multiply(column[3], 0x09)
        result[base + 1] = _aes_multiply(column[0], 0x09) ^ _aes_multiply(column[1], 0x0E) \
            ^ _aes_multiply(column[2], 0x0B) ^ _aes_multiply(column[3], 0x0D)
        result[base + 2] = _aes_multiply(column[0], 0x0D) ^ _aes_multiply(column[1], 0x09) \
            ^ _aes_multiply(column[2], 0x0E) ^ _aes_multiply(column[3], 0x0B)
        result[base + 3] = _aes_multiply(column[0], 0x0B) ^ _aes_multiply(column[1], 0x0D) \
            ^ _aes_multiply(column[2], 0x09) ^ _aes_multiply(column[3], 0x0E)
    return result


def _aes_decrypt_block(block: bytes, round_keys: List[List[int]]) -> bytes:
    state = list(block)
    state = [s ^ k for s, k in zip(state, round_keys[10])]
    for rnd in range(9, 0, -1):
        state = _aes_inv_shift_rows(state)
        state = _aes_inv_sub_bytes(state)
        state = [s ^ k for s, k in zip(state, round_keys[rnd])]
        state = _aes_inv_mix_columns(state)
    state = _aes_inv_shift_rows(state)
    state = _aes_inv_sub_bytes(state)
    state = [s ^ k for s, k in zip(state, round_keys[0])]
    return bytes(state)


def _aes128_cbc_decrypt(data: bytes, key: bytes, iv: bytes) -> bytes:
    """AES-128-CBC 解密，data 长度必须是 16 的倍数。"""
    if len(key) != 16:
        raise ValueError("AES-128 key must be 16 bytes")
    if len(iv) != 16:
        raise ValueError("AES-128 IV must be 16 bytes")
    if len(data) % 16 != 0:
        raise ValueError("CBC ciphertext length must be a multiple of 16")
    round_keys = _aes_key_expansion(key)
    plaintext = bytearray()
    previous = iv
    for offset in range(0, len(data), 16):
        chunk = _aes_decrypt_block(data[offset:offset + 16], round_keys)
        plaintext.extend(b ^ p for b, p in zip(chunk, previous))
        previous = data[offset:offset + 16]
    return bytes(plaintext)


def _pkcs7_unpad(data: bytes) -> bytes:
    if not data:
        raise ValueError("Empty plaintext")
    pad_len = data[-1]
    if pad_len < 1 or pad_len > 16 or data[-pad_len:] != bytes([pad_len]) * pad_len:
        raise ValueError("Invalid PKCS7 padding")
    return data[:-pad_len]


# ─────────────────────────────────────────────────────────────────────
# 服务基类：懒加载会话 + 语言映射（对齐 translators 的行为）
# ─────────────────────────────────────────────────────────────────────

class _BaseService:
    name = ""
    output_zh = "zh"
    language_map: Optional[Dict[str, List[str]]] = None

    def __init__(self):
        self.session: Optional[requests.Session] = None
        self._begin_time = 0.0
        self._query_count = 0

    @property
    def _session(self) -> requests.Session:
        if self.session is None:
            self.session = requests.Session()
        return self.session

    def _refresh_if_needed(self, timeout: Optional[float]) -> bool:
        """按频率重建会话；返回是否需要重新初始化。"""
        freq, seconds = 1000, 1500
        fresh_freq = self._query_count % freq != 0
        fresh_time = time.time() - self._begin_time < seconds
        if self.session is not None and fresh_freq and fresh_time:
            return False
        self.session = requests.Session()
        self._begin_time = time.time()
        return True

    def _bump_query(self) -> None:
        self._query_count += 1

    def _init_language_map(self, timeout: Optional[float]) -> None:
        raise NotImplementedError

    def translate(self, query_text: str, from_language: str,
                  to_language: str, timeout: Optional[float] = None) -> str:
        raise NotImplementedError

    def ensure_language_map(self, from_language: str, to_language: str,
                            timeout: Optional[float]) -> None:
        if self.language_map is None:
            self._init_language_map(timeout)


# ─────────────────────────────────────────────────────────────────────
# 1. Yandex（browser.translate.yandex.net，纯 JSON，无签名）
# ─────────────────────────────────────────────────────────────────────

class YandexService(_BaseService):
    name = "yandex"
    output_zh = "zh"
    home_url = "https://www.youtube.com"
    api_url = "https://browser.translate.yandex.net/api/v1/tr.json"
    srv = "browser_video_translation"

    def _init_language_map(self, timeout: Optional[float]) -> None:
        headers = _headers(self.home_url, if_api=True)
        headers["User-Agent"] = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 YaBrowser/24.1.5.825 Yowser/2.5 Safari/537.36"
        )
        response = self._session.post(
            f"{self.api_url}/getLangs",
            params={"srv": self.srv},
            data={"maxRetryCount": 2, "fetchAbortTimeout": 500},
            headers=headers,
            timeout=timeout,
        )
        _raise_for_status(response, "Yandex")
        data = response.json()
        lang_map: Dict[str, List[str]] = {}
        for lang_pair in data.get("dirs", []):
            source, target = lang_pair.split("-")
            lang_map.setdefault(source, []).append(target)
        if not lang_map.get("zh"):
            lang_map["zh"] = ["az", "en", "es", "fr", "it", "ru"]
        self.language_map = lang_map

    def translate(self, query_text: str, from_language: str,
                  to_language: str, timeout: Optional[float] = None) -> str:
        self.ensure_language_map(from_language, to_language, timeout)
        headers = _headers(self.home_url, if_api=True)
        headers["User-Agent"] = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 YaBrowser/24.1.5.825 Yowser/2.5 Safari/537.36"
        )
        if from_language == "auto":
            detect = self._session.post(
                f"{self.api_url}/detect",
                params={"srv": self.srv, "text": query_text},
                data={"maxRetryCount": 2, "fetchAbortTimeout": 500},
                headers=headers,
                timeout=timeout,
            )
            _raise_for_status(detect, "Yandex")
            detected = detect.json().get("lang") or self.output_zh
            from_language = detected
        from_language, to_language = _check_language(
            from_language, to_language, self.language_map, self.output_zh
        )
        response = self._session.post(
            f"{self.api_url}/translate",
            params={"srv": self.srv, "text": query_text,
                    "lang": f"{from_language}-{to_language}"},
            data={"maxRetryCount": 2, "fetchAbortTimeout": 500},
            headers=headers,
            timeout=timeout,
        )
        _raise_for_status(response, "Yandex")
        data = response.json()
        self._bump_query()
        try:
            return data["text"][0]
        except (KeyError, IndexError, TypeError) as error:
            raise FreeTranslatorError(f"Yandex returned no translation: {data}") from error


# ─────────────────────────────────────────────────────────────────────
# 2. Iflyrec（fanyi.iflyrec.com，语言内置索引，无需爬取）
# ─────────────────────────────────────────────────────────────────────

class IflyrecService(_BaseService):
    name = "iflyrec"
    output_zh = "zh"
    host_url = "https://fanyi.iflyrec.com"
    api_url = "https://fanyi.iflyrec.com/TranslationService/v1/textAutoTranslation"
    detect_lang_url = "https://fanyi.iflyrec.com/TranslationService/v1/languageDetection"
    language_url = "https://fanyi.iflyrec.com/TranslationService/v1/textTranslation/languages"
    lang_index = {
        "zh": 1, "en": 2, "ja": 3, "ko": 4, "ru": 5, "fr": 6,
        "es": 7, "vi": 8, "yue": 9, "ar": 12, "de": 13, "it": 14,
    }

    def _init_language_map(self, timeout: Optional[float]) -> None:
        lang_list = sorted(self.lang_index.keys())
        lang_map = {lang: ["zh"] for lang in lang_list if lang != "zh"}
        lang_map["zh"] = lang_list
        self.language_map = lang_map

    def translate(self, query_text: str, from_language: str,
                  to_language: str, timeout: Optional[float] = None) -> str:
        self.ensure_language_map(from_language, to_language, timeout)
        headers = _headers(self.host_url, if_api=True)
        headers["Content-Type"] = "application/json"
        if from_language == "auto":
            detect = self._session.post(
                self.detect_lang_url,
                params={"t": int(time.time() * 1000)},
                json={"originalText": query_text},
                headers=headers,
                timeout=timeout,
            )
            _raise_for_status(detect, "Iflyrec")
            lang_id = detect.json()["biz"][0]["detectionLanguage"]
            from_language = {v: k for k, v in self.lang_index.items()}[lang_id]
        from_language, to_language = _check_language(
            from_language, to_language, self.language_map, self.output_zh
        )
        payload = {
            "from": self.lang_index[from_language],
            "to": self.lang_index[to_language],
            "openTerminology": "false",
            "contents": [
                {"text": line.strip(), "frontBlankLine": 0}
                for line in query_text.split("\n") if line.strip()
            ],
        }
        response = self._session.post(
            self.api_url,
            params={"t": int(time.time() * 1000)},
            json=payload,
            headers=headers,
            timeout=timeout,
        )
        _raise_for_status(response, "Iflyrec")
        data = response.json()
        self._bump_query()
        try:
            return "\n".join(item["translateResult"] for item in data["biz"])
        except (KeyError, TypeError) as error:
            raise FreeTranslatorError(f"Iflyrec returned no translation: {data}") from error


# ─────────────────────────────────────────────────────────────────────
# 3. Caiyun（彩云小译，JWT + 字符替换解密，无 JS 引擎）
# ─────────────────────────────────────────────────────────────────────

class CaiyunService(_BaseService):
    name = "caiyun"
    output_zh = "zh"
    host_url = "https://fanyi.caiyunapp.com"
    api_url = "https://api.interpreter.caiyunai.com/v1/translator"
    language_url = "https://fanyi.caiyunapp.com/get_config/xiaoyi_translation_languages.json"
    jwt_url = "https://api.interpreter.caiyunai.com/v1/user/jwt/generate"
    normal_key = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789=.+-_/"
    cipher_key = "NOPQRSTUVWXYZABCDEFGHIJKLMnopqrstuvwxyzabcdefghijklm0123456789=.+-_/"
    tk = "token:qgemv4jr1y38jyq6vhvi"

    def __init__(self):
        super().__init__()
        self.browser_id = str(uuid.uuid4()).replace("-", "")
        self.jwt: Optional[str] = None

    def _init_language_map(self, timeout: Optional[float]) -> None:
        headers = _headers(self.host_url, if_api=False)
        response = self._session.get(self.language_url, headers=headers, timeout=timeout)
        _raise_for_status(response, "Caiyun")
        lang_list = sorted(
            item["code"] for item in response.json()["supported_translation_languages"]
        )
        self.language_map = _language_set(lang_list)

    def _ensure_jwt(self, timeout: Optional[float]) -> None:
        if self.jwt is not None:
            return
        headers = _headers(self.host_url, if_api=True)
        headers.update({
            "Content-Type": "application/json",
            "app-name": "xiaoyi",
            "device-id": self.browser_id,
            "os-type": "web",
            "os-version": "",
            "version": "4.6.0",
            "Authorization": "bearer",
            "X-Authorization": self.tk,
        })
        response = self._session.post(
            self.jwt_url, json={"browser_id": self.browser_id},
            headers=headers, timeout=timeout,
        )
        _raise_for_status(response, "Caiyun")
        self.jwt = response.json()["jwt"]

    @staticmethod
    def _decrypt(cipher_text: str) -> str:
        cipher_key = CaiyunService.cipher_key
        normal_key = CaiyunService.normal_key
        decrypt_map = {cipher: plain for plain, cipher in zip(normal_key, cipher_key)}
        try:
            decoded = "".join(decrypt_map[ch] for ch in cipher_text)
            return base64.b64decode(decoded).decode()
        except (KeyError, ValueError) as error:
            raise FreeTranslatorError(f"Caiyun decrypt failed: {error}") from error

    def translate(self, query_text: str, from_language: str,
                  to_language: str, timeout: Optional[float] = None) -> str:
        self.ensure_language_map(from_language, to_language, timeout)
        self._ensure_jwt(timeout)
        headers = _headers(self.host_url, if_api=True)
        headers.update({
            "Content-Type": "application/json",
            "app-name": "xiaoyi",
            "device-id": self.browser_id,
            "os-type": "web",
            "os-version": "",
            "version": "4.6.0",
            "Authorization": "bearer",
            "X-Authorization": self.tk,
            "T-Authorization": self.jwt,
        })
        from_language, to_language = _check_language(
            from_language, to_language, self.language_map, self.output_zh
        )
        payload = {
            "browser_id": self.browser_id,
            "source": query_text.split("\n"),
            "trans_type": f"{from_language}2{to_language}",
            "dict": "true",
            "cached": "true",
            "replaced": "true",
            "media": "text",
            "os_type": "web",
            "request_id": "web_fanyi",
            "model": "",
            "style": "formal",
        }
        if from_language == "auto":
            payload["detect"] = "true"
        response = self._session.post(
            self.api_url, headers=headers, json=payload, timeout=timeout,
        )
        _raise_for_status(response, "Caiyun")
        data = response.json()
        self._bump_query()
        try:
            return "\n".join(self._decrypt(item) for item in data["target"])
        except (KeyError, TypeError) as error:
            raise FreeTranslatorError(f"Caiyun returned no translation: {data}") from error


# ─────────────────────────────────────────────────────────────────────
# 4. Alibaba（translate.alibaba.com V2，CSRF token）
# ─────────────────────────────────────────────────────────────────────

class AlibabaService(_BaseService):
    name = "alibaba"
    output_zh = "zh"
    host_url = "https://translate.alibaba.com"
    api_url = "https://translate.alibaba.com/api/translate/text"
    csrf_url = "https://translate.alibaba.com/api/translate/csrftoken"

    def _init_language_map(self, timeout: Optional[float]) -> None:
        headers = _headers(self.host_url, if_api=False)
        response = self._session.get(self.host_url, headers=headers, timeout=timeout)
        _raise_for_status(response, "Alibaba")
        host_html = response.text
        lang_url_match = re.search(
            r"//lang\.alicdn\.com/mcms/translation-open-portal/(.*?)/"
            r"translation-open-portal_interface\.json",
            host_html,
        )
        if not lang_url_match:
            raise FreeTranslatorError("Alibaba language config URL not found")
        lang_html = self._session.get(
            f"https:{lang_url_match.group(0)}", headers=headers, timeout=timeout
        ).text
        paragraph_match = re.search(r'"en_US":\{(.*?)\},"zh_CN":\{', lang_html, re.DOTALL)
        if not paragraph_match:
            raise FreeTranslatorError("Alibaba language map not found")
        paragraph = paragraph_match.group(0).replace('",', '",\n')
        items = re.findall(r"interface\.(.*?)\":\"(.*?)\"", paragraph)
        lang_list = sorted(
            k for k, v in items
            if (len(k) <= 3 or (len(k) == 5 and "-" in k)) and len(v.split(" ")) <= 2
        )
        self.language_map = _language_set(lang_list)

    def _ensure_csrf(self, timeout: Optional[float]) -> str:
        headers = _headers(self.host_url, if_api=False)
        response = self._session.get(self.csrf_url, headers=headers, timeout=timeout)
        _raise_for_status(response, "Alibaba")
        token_info = response.json()
        return token_info["token"], token_info["headerName"]

    def translate(self, query_text: str, from_language: str,
                  to_language: str, timeout: Optional[float] = None) -> str:
        self.ensure_language_map(from_language, to_language, timeout)
        token, header_name = self._ensure_csrf(timeout)
        headers = _headers(self.host_url, if_api=True)
        headers.pop("Content-Type")
        headers.update({header_name: token})
        from_language, to_language = _check_language(
            from_language, to_language, self.language_map, self.output_zh
        )
        files = {
            "query": (None, query_text),
            "srcLang": (None, from_language),
            "tgtLang": (None, to_language),
            "_csrf": (None, token),
            "domain": (None, "general"),
        }
        response = self._session.post(
            self.api_url, files=files, headers=headers, timeout=timeout,
        )
        _raise_for_status(response, "Alibaba")
        data = response.json()
        self._bump_query()
        try:
            return data["data"]["translateText"]
        except (KeyError, TypeError) as error:
            raise FreeTranslatorError(f"Alibaba returned no translation: {data}") from error


# ─────────────────────────────────────────────────────────────────────
# 5. Bing（www.bing.com/Translator，AbusePrevention token 用 ast 求值）
# ─────────────────────────────────────────────────────────────────────

class BingService(_BaseService):
    name = "bing"
    output_zh = "zh-Hans"
    output_auto = "auto-detect"
    host_url = "https://www.bing.com/Translator"
    api_url = "https://www.bing.com/ttranslatev3"

    def _init_language_map(self, timeout: Optional[float]) -> None:
        host_html = self._fetch_host_html(timeout)
        lang_list = re.findall(
            r'<option[^>]+value="([^"]+)"[^>]*>', host_html
        )
        lang_list = [lang for lang in lang_list if lang and lang != "auto-detect"]
        self.language_map = _language_set(lang_list)

    def _fetch_host_html(self, timeout: Optional[float]) -> str:
        headers = _headers(self.host_url, if_api=False)
        response = self._session.get(self.host_url, headers=headers, timeout=timeout)
        _raise_for_status(response, "Bing")
        return response.text

    def _get_tk(self, host_html: str) -> Dict[str, str]:
        result_str = re.search(
            r"var params_AbusePreventionHelper = (.*?);", host_html
        )
        if not result_str:
            raise FreeTranslatorError("Bing abuse prevention token not found")
        result = _parse_js_list(host_html, "params_AbusePreventionHelper")
        return {"key": result[0], "token": result[1]}

    def _get_ig_iid(self, host_html: str) -> Dict[str, str]:
        iid_match = re.search(r'id="tta_outGDCont"[^>]*data-iid="([^"]+)"', host_html)
        ig_match = re.search(r'IG:"(.*?)"', host_html)
        if not iid_match or not ig_match:
            raise FreeTranslatorError("Bing IG/IID not found")
        return {"iid": iid_match.group(1), "ig": ig_match.group(1)}

    def translate(self, query_text: str, from_language: str,
                  to_language: str, timeout: Optional[float] = None) -> str:
        host_html = self._fetch_host_html(timeout)
        tk = self._get_tk(host_html)
        ig_iid = self._get_ig_iid(host_html)
        if self.language_map is None:
            self._init_language_map(timeout)
        from_language, to_language = _check_language(
            from_language, to_language, self.language_map,
            self.output_zh, self.output_auto,
        )
        headers = _headers(self.host_url, if_api=False)
        payload = {
            "text": query_text,
            "fromLang": from_language,
            "to": to_language,
            "tryFetchingGenderDebiasedTranslations": "true",
            **tk,
        }
        api_url = (
            f"{self.api_url}?isVertical=1&&IG={ig_iid['ig']}&IID={ig_iid['iid']}"
        )
        response = self._session.post(
            api_url, headers=headers, data=payload, timeout=timeout,
        )
        _raise_for_status(response, "Bing")
        self._bump_query()
        try:
            data = response.json()
            return data[0]["translations"][0]["text"]
        except (KeyError, IndexError, TypeError) as error:
            raise FreeTranslatorError(f"Bing returned no translation: {response.text[:200]}") from error


# ─────────────────────────────────────────────────────────────────────
# 6. Sogou（fanyi.sogou.com，MD5 签名 + JS 语言列表）
# ─────────────────────────────────────────────────────────────────────

class SogouService(_BaseService):
    name = "sogou"
    output_zh = "zh-CHS"
    host_url = "https://fanyi.sogou.com/text"
    api_url = "https://fanyi.sogou.com/api/transpc/text/result"
    language_old_url = "https://search.sogoucdn.com/translate/pc/static/js/app.7016e0df.js"
    secret_code = "109984457"

    def __init__(self):
        super().__init__()
        self._get_language_url: Optional[str] = None
        self.uuid: Optional[str] = None

    def _init_language_map(self, timeout: Optional[float]) -> None:
        headers = _headers(self.host_url, if_api=False)
        host_html = self._session.get(self.host_url, headers=headers, timeout=timeout).text
        if not self._get_language_url:
            match = re.search(r"//search\.sogoucdn\.com/translate/pc/static/js/vendors\.(.*?)\.js", host_html)
            if match:
                self._get_language_url = f"https:{match.group(0)}"
        try:
            lang_html = self._session.get(
                self._get_language_url or self.language_old_url,
                headers=headers, timeout=timeout,
            ).text
        except requests.RequestException:
            lang_html = self._session.get(
                self.language_old_url, headers=headers, timeout=timeout
            ).text
        lang_list_str = re.search(r'"ALL":\[(.*?)\]', lang_html)
        if not lang_list_str:
            raise FreeTranslatorError("Sogou language list not found")
        raw = lang_list_str.group(1).replace("!0", "1").replace("!1", "0")
        items = json.loads(raw)
        lang_list = [item["lang"] for item in items if item.get("play") == 1]
        self.language_map = _language_set(lang_list)

    def translate(self, query_text: str, from_language: str,
                  to_language: str, timeout: Optional[float] = None) -> str:
        self.ensure_language_map(from_language, to_language, timeout)
        if self.uuid is None:
            self.uuid = str(uuid.uuid4())
        from_language, to_language = _check_language(
            from_language, to_language, self.language_map, self.output_zh
        )
        sign_text = f"{from_language}{to_language}{query_text}{self.secret_code}"
        payload = {
            "from": from_language,
            "to": to_language,
            "text": query_text,
            "uuid": self.uuid,
            "s": hashlib.md5(sign_text.encode()).hexdigest(),
            "client": "pc",
            "fr": "browser_pc",
            "needQc": "1",
        }
        headers = _headers(self.host_url, if_api=True)
        response = self._session.post(
            self.api_url, headers=headers, data=payload, timeout=timeout,
        )
        _raise_for_status(response, "Sogou")
        data = response.json()
        self._bump_query()
        try:
            return data["data"]["translate"]["dit"]
        except (KeyError, TypeError) as error:
            raise FreeTranslatorError(f"Sogou returned no translation: {data}") from error


# ─────────────────────────────────────────────────────────────────────
# 7. Youdao（dict.youdao.com/webtranslate，AES-128-CBC 解密）
# ─────────────────────────────────────────────────────────────────────

class YoudaoService(_BaseService):
    name = "youdao"
    output_zh = "zh-CHS"
    host_url = "https://fanyi.youdao.com"
    api_url = "https://dict.youdao.com/webtranslate"
    api_host = "https://dict.youdao.com"
    language_url = "https://api-overmind.youdao.com/openapi/get/luna/dict/luna-front/prod/langType"
    key_url = "https://dict.youdao.com/webtranslate/key"
    login_url = "https://dict.youdao.com/login/acc/query/accountinfo"
    keyid = "webfanyi-key-getter-2025"

    def __init__(self):
        super().__init__()
        self._get_js_url: Optional[str] = None
        self.secret_key: Optional[str] = None
        self.decode_key: Optional[str] = None
        self.decode_iv: Optional[str] = None

    def _init_language_map(self, timeout: Optional[float]) -> None:
        headers = _headers(self.host_url, if_api=False)
        response = self._session.get(self.language_url, headers=headers, timeout=timeout)
        _raise_for_status(response, "Youdao")
        data = response.json()
        lang_list = sorted(
            item["code"] for item in data["data"]["value"]["textTranslate"]["specify"]
        )
        self.language_map = _language_set(lang_list)

    def _get_js_url(self, host_html: str) -> str:
        match = re.search(
            r"https://shared\.ydstatic\.com/dict/translation-website/"
            r"([^/]+)/js/app\.([^\.]+)\.js",
            host_html,
        )
        if not match:
            raise FreeTranslatorError("Youdao app.js URL not found")
        return match.group(0)

    def _get_default_key(self, js_html: str, keyid: str) -> str:
        match = re.search(re.escape(f'="{keyid}",') + r"(\w+)=\"(\w+)\";", js_html)
        if not match:
            raise FreeTranslatorError("Youdao default key not found")
        return match.group(2)

    @staticmethod
    def _get_sign(key: str, timestamp: int) -> str:
        value = f"client=fanyideskweb&mysticTime={timestamp}&product=webfanyi&key={key}"
        return hashlib.md5(value.encode()).hexdigest()

    def _get_payload(self, keyid: str, key: str, timestamp: int,
                     **kwargs: str) -> Dict[str, str]:
        payload = {
            "keyid": keyid,
            "mysticTime": str(timestamp),
            "sign": self._get_sign(key, timestamp),
            "client": "fanyideskweb",
            "product": "webfanyi",
            "appVersion": "12.0.0",
            "vendor": "web",
            "keyfrom": "fanyi.web",
            "pointParam": "client,mysticTime,product",
            "yduuid": "abcdefg",
            "mid": "1",
            "screen": "1",
            "model": "1",
            "network": "wifi",
            "abtest": "0",
        }
        if keyid == "webfanyi":
            payload.update(kwargs)
        return payload

    def _ensure_keys(self, timeout: Optional[float]) -> None:
        if self.secret_key is not None:
            return
        headers = _headers(self.host_url, if_api=False)
        host_html = self._session.get(self.host_url, headers=headers, timeout=timeout).text
        _ = self._session.get(self.login_url, headers=headers, timeout=timeout)

        js_url = self._get_js_url(host_html)
        js_html = self._session.get(js_url, headers=headers, timeout=timeout).text
        decode_key_match = re.search(r'decodeKey:"(.*?)",', js_html)
        decode_iv_match = re.search(r'decodeIv:"(.*?)",', js_html)
        self.decode_key = decode_key_match.group(1) if decode_key_match else None
        self.decode_iv = decode_iv_match.group(1) if decode_iv_match else None

        default_key = self._get_default_key(js_html, self.keyid)
        timestamp = int(time.time() * 1000)
        params = self._get_payload(keyid=self.keyid, key=default_key, timestamp=timestamp)
        key_response = self._session.get(
            self.key_url, params=params, headers=headers, timeout=timeout,
        )
        _raise_for_status(key_response, "Youdao")
        keys_data = key_response.json()["data"]
        self.secret_key = keys_data["secretKey"]
        self.decode_key = keys_data.get("aesKey") or self.decode_key
        self.decode_iv = keys_data.get("aesIv") or self.decode_iv
        if not self.decode_key or not self.decode_iv:
            raise FreeTranslatorError("Youdao AES key/iv unavailable")

    @staticmethod
    def _decrypt_result(text: str, key: str, iv: str) -> str:
        key_bytes = hashlib.md5(key.encode()).digest()[:16]
        iv_bytes = hashlib.md5(iv.encode()).digest()[:16]
        text_bytes = base64.urlsafe_b64decode(text.encode())
        plaintext = _aes128_cbc_decrypt(text_bytes, key_bytes, iv_bytes)
        return _pkcs7_unpad(plaintext).decode()

    def translate(self, query_text: str, from_language: str,
                  to_language: str, timeout: Optional[float] = None) -> str:
        self.ensure_language_map(from_language, to_language, timeout)
        self._ensure_keys(timeout)
        from_language, to_language = _check_language(
            from_language, to_language, self.language_map, self.output_zh
        )
        headers = _headers(self.host_url, if_api=True)
        translate_form = {
            "i": query_text,
            "from": from_language,
            "to": "" if from_language == "auto" else to_language,
            "dictResult": "true",
            "useTerm": "false",
        }
        payload = self._get_payload(
            keyid="webfanyi", key=self.secret_key,
            timestamp=int(time.time() * 1000), **translate_form,
        )
        response = self._session.post(
            self.api_url, headers=headers, data=urlencode(payload), timeout=timeout,
        )
        _raise_for_status(response, "Youdao")
        decrypted = self._decrypt_result(
            response.text, self.decode_key, self.decode_iv
        )
        data = json.loads(decrypted)
        self._bump_query()
        try:
            return "".join(item["tgt"] for dt in data["translateResult"] for item in dt)
        except (KeyError, TypeError) as error:
            raise FreeTranslatorError(f"Youdao returned no translation: {data}") from error


# ─────────────────────────────────────────────────────────────────────
# 8. DeepL（www2.deepl.com/jsonrpc，LMT 两段式）
# ─────────────────────────────────────────────────────────────────────

class DeeplService(_BaseService):
    name = "deepl"
    output_zh = "zh"
    host_url = "https://www.deepl.com/translator"
    api_url = "https://www2.deepl.com/jsonrpc"
    login_url = "https://login-wall.deepl.com"

    def __init__(self):
        super().__init__()
        self.request_id = int(random.randrange(100, 10000) * 10000 + 4)

    def _init_language_map(self, timeout: Optional[float]) -> None:
        headers = _headers(self.host_url, if_api=False)
        response = self._session.get(self.host_url, headers=headers, timeout=timeout)
        _raise_for_status(response, "DeepL")
        lang_list = sorted(set(
            re.findall(r"\['selectLang_source_(\w+)'\]", response.text)
        ))
        self.language_map = _language_set(lang_list)

    def _split_sentences_param(self, query_text: str, from_language: str) -> Dict[str, Any]:
        data = {
            "id": self.request_id,
            "jsonrpc": "2.0",
            "params": {
                "texts": query_text.split("\n"),
                "commonJobParams": {"mode": "translate"},
                "lang": {
                    "lang_user_selected": from_language,
                    "preference": {"weight": {}, "default": "default"},
                },
            },
        }
        if from_language != "auto":
            data["params"]["lang"]["lang_computed"] = from_language
        return {"method": "LMT_split_text", **data}

    def _context_sentences_param(self, sentences: List[str], from_language: str,
                                 to_language: str) -> Dict[str, Any]:
        sentences = [""] + sentences + [""]
        data = {
            "id": self.request_id + 1,
            "jsonrpc": "2.0",
            "params": {
                "priority": 1,
                "timestamp": int(time.time() * 1000),
                "commonJobParams": {
                    "browserType": 1,
                    "mode": "translate",
                    "textType": "plaintext",
                },
                "jobs": [
                    {
                        "kind": "default",
                        "sentences": [{"id": i - 1, "prefix": "", "text": sentences[i]}],
                        "raw_en_context_before": sentences[1:i] if sentences[i - 1] else [],
                        "raw_en_context_after": [sentences[i + 1]] if sentences[i + 1] else [],
                        "preferred_num_beams": 1 if len(sentences) >= 4 else 4,
                    }
                    for i in range(1, len(sentences) - 1)
                ],
                "lang": {
                    "preference": {"weight": {}, "default": "default"},
                    "source_lang_computed": from_language,
                    "target_lang": to_language,
                },
            },
        }
        return {"method": "LMT_handle_jobs", **data}

    def translate(self, query_text: str, from_language: str,
                  to_language: str, timeout: Optional[float] = None) -> str:
        self.ensure_language_map(from_language, to_language, timeout)
        headers = _headers(self.host_url, if_api=True)
        headers["Content-Type"] = "application/json"
        _ = self._session.get(self.login_url, headers=headers, timeout=timeout)
        from_language, to_language = _check_language(
            from_language, to_language, self.language_map, self.output_zh
        )
        from_language = from_language.upper() if from_language != "auto" else "auto"
        to_language = to_language.upper()

        split_payload = self._split_sentences_param(query_text, from_language)
        split_response = self._session.post(
            self.api_url, params={"method": "LMT_split_text"},
            json=split_payload, headers=headers, timeout=timeout,
        )
        _raise_for_status(split_response, "DeepL")
        split_data = split_response.json()
        try:
            detected = split_data["result"]["lang"]["detected"]
            sentences = [
                item["sentences"][0]["text"]
                for chunk in split_data["result"]["texts"]
                for item in chunk["chunks"]
            ]
        except (KeyError, IndexError, TypeError) as error:
            raise FreeTranslatorError(f"DeepL split failed: {split_data}") from error

        handle_payload = self._context_sentences_param(sentences, detected, to_language)
        handle_response = self._session.post(
            self.api_url, params={"method": "LMT_handle_jobs"},
            json=handle_payload, headers=headers, timeout=timeout,
        )
        _raise_for_status(handle_response, "DeepL")
        data = handle_response.json()
        self.request_id += 3
        self._bump_query()
        try:
            return "\n".join(
                item["beams"][0]["sentences"][0]["text"]
                for item in data["result"]["translations"]
            )
        except (KeyError, IndexError, TypeError) as error:
            raise FreeTranslatorError(f"DeepL returned no translation: {data}") from error


# ─────────────────────────────────────────────────────────────────────
# 9. Google（translate.google.com V2 batchexecute）
# ─────────────────────────────────────────────────────────────────────

class GoogleService(_BaseService):
    name = "google"
    output_zh = "zh-CN"
    host_url = "https://translate.google.com"
    api_url = "https://translate.google.com/_/TranslateWebserverUi/data/batchexecute"
    consent_url = "https://consent.google.com/save"
    rpcid = "MkEWBc"

    def _init_language_map(self, timeout: Optional[float]) -> None:
        headers = _headers(self.host_url, if_api=False)
        response = self._session.get(self.host_url, headers=headers, timeout=timeout)
        _raise_for_status(response, "Google")
        host_html = response.text
        lang_list = sorted(set(re.findall(r'data-language-code="([^"]+)"', host_html)))
        self.language_map = _language_set(lang_list)

    def _get_info(self, host_html: str) -> Dict[str, str]:
        match = re.search(r"window\.WIZ_global_data = (.*?);</script>", host_html, re.DOTALL)
        if not match:
            raise FreeTranslatorError("Google WIZ_global_data not found")
        raw = match.group(1)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            normalized = re.sub(r"(\w+)\s*:", r'"\1":', raw)
            normalized = normalized.replace("'", '"')
            data = json.loads(normalized)
        try:
            return {"bl": data["cfb2h"], "f.sid": data["FdrFJe"]}
        except KeyError as error:
            raise FreeTranslatorError(f"Google WIZ keys missing: {error}") from error

    def _get_consent_data(self, consent_html: str) -> Dict[str, str]:
        form_match = re.search(r"<form[^>]*action=\"([^\"]+)\"", consent_html)
        if not form_match:
            raise FreeTranslatorError("Google consent form not found")
        self.consent_url = form_match.group(1)
        hidden = re.findall(
            r'<input[^>]+type="hidden"[^>]+name="([^"]+)"[^>]+value="([^"]*)"',
            consent_html,
        )
        if not hidden:
            hidden = re.findall(
                r'<input[^>]+value="([^"]*)"[^>]+type="hidden"[^>]+name="([^"]+)"',
                consent_html,
            )
            hidden = [(name, value) for value, name in hidden]
        return dict(hidden)

    def _get_rpc(self, query_text: str, from_language: str, to_language: str) -> Dict[str, str]:
        param = json.dumps([[query_text, from_language, to_language, True], [1]])
        rpc = json.dumps([[[self.rpcid, param, None, "generic"]]])
        return {"f.req": rpc}

    def _refresh_session(self, from_language: str, timeout: Optional[float]) -> None:
        """刷新会话并抓取 WIZ_global_data（含 consent 处理）。"""
        headers = _headers(self.host_url, if_api=False)
        response = self._session.get(self.host_url, headers=headers, timeout=timeout)
        _raise_for_status(response, "Google")
        if response.url.split("/")[2] == self.consent_url.split("/")[2]:
            form_data = self._get_consent_data(response.text)
            response = self._session.post(
                self.consent_url, data=form_data, headers=headers, timeout=timeout,
            )
            _raise_for_status(response, "Google")
        host_html = response.text
        self._google_info = self._get_info(host_html)
        if self.language_map is None:
            self._init_language_map(timeout)

    def translate(self, query_text: str, from_language: str,
                  to_language: str, timeout: Optional[float] = None) -> str:
        if self.language_map is None:
            self._init_language_map(timeout)
        self._google_info = self._get_info(
            self._session.get(self.host_url, headers=_headers(self.host_url, if_api=False),
                              timeout=timeout).text
        )
        from_language, to_language = _check_language(
            from_language, to_language, self.language_map, self.output_zh
        )
        headers = _headers(self.host_url, if_api=True)
        rpc_data = self._get_rpc(query_text, from_language, to_language)
        response = self._session.post(
            self.api_url, headers=headers, data=urlencode(rpc_data), timeout=timeout,
        )
        _raise_for_status(response, "Google")
        cleaned = re.sub(r"^\)\]\}'\s*", "", response.text)
        outer = json.loads(cleaned)
        inner_str = None
        if isinstance(outer, list) and outer and isinstance(outer[0], list):
            row = outer[0]
            for index in (2, 1):
                if len(row) > index and isinstance(row[index], str):
                    inner_str = row[index]
                    break
        if inner_str is None:
            raise FreeTranslatorError(f"Google returned unexpected structure: {cleaned[:200]}")
        data = json.loads(inner_str)
        self._bump_query()
        try:
            segments = data[1][0][0][5] or data[1][0]
            return " ".join(seg[0] for seg in segments if seg[0])
        except (KeyError, IndexError, TypeError) as error:
            raise FreeTranslatorError(f"Google returned no translation: {data}") from error


# ─────────────────────────────────────────────────────────────────────
# 分发器（对齐 translators 的 translate_text / get_languages 接口）
# ─────────────────────────────────────────────────────────────────────

_SERVICES: Dict[str, _BaseService] = {}


def _get_service(translator: str) -> _BaseService:
    translator = translator.lower()
    if translator not in SUPPORTED_TRANSLATORS:
        raise FreeTranslatorError(
            f"Unsupported translator[{translator}] in free_translators"
        )
    if translator not in _SERVICES:
        _SERVICES[translator] = {
            "alibaba": AlibabaService,
            "bing": BingService,
            "caiyun": CaiyunService,
            "deepl": DeeplService,
            "google": GoogleService,
            "iflyrec": IflyrecService,
            "sogou": SogouService,
            "yandex": YandexService,
            "youdao": YoudaoService,
        }[translator]()
    return _SERVICES[translator]


def translate_text(query_text: str, translator: str = "bing",
                   from_language: str = "auto", to_language: str = "en",
                   timeout: Optional[float] = None, **kwargs: Any) -> str:
    """免费 Web 翻译。接口对齐 translators.translate_text 的核心参数。"""
    return _get_service(translator).translate(
        query_text, from_language, to_language, timeout=timeout,
    )


def get_languages(translator: str = "bing",
                  timeout: Optional[float] = None, **kwargs: Any) -> Dict[str, List[str]]:
    """获取服务支持的语言映射（首次调用会在线抓取并缓存）。"""
    service = _get_service(translator)
    if service.language_map is None:
        service._init_language_map(timeout)
    return service.language_map
