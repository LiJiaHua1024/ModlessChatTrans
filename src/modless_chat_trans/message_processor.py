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
from json import JSONDecodeError
from requests.exceptions import HTTPError
from modless_chat_trans.i18n import _
from modless_chat_trans.file_utils import cache
from modless_chat_trans.translator import services, LLM_PROVIDERS
from modless_chat_trans.logger import logger
from langdetect import detect_langs, LangDetectException

UNKNOWN_LANGUAGE = "unknown"

trans_sys_message = True
skip_src_lang = []
min_detect_len = 100
glossary = {}
_compiled_glossary_patterns = {}
glossary_compiled = False
replace_garbled_character = False


def init_processor(_trans_sys_message, _skip_src_lang, _min_detect_len, _glossary, _replace_garbled_character):
    """
    :param _trans_sys_message: 是否翻译系统（name为空）消息，仅对log类型有效
    :param _skip_src_lang: 跳过不翻译的源语言集合
    :param _min_detect_len: 触发源语言检测的最小消息长度
    :param _glossary: 自定义术语表
    :param _replace_garbled_character: 是否将乱码字符\ufffd\ufffd替换为\u00A7
    """
    global trans_sys_message, skip_src_lang, min_detect_len, glossary, replace_garbled_character
    trans_sys_message = _trans_sys_message
    skip_src_lang = _skip_src_lang
    min_detect_len = _min_detect_len
    glossary = _glossary
    replace_garbled_character = _replace_garbled_character


def _compile_glossary_patterns():
    """预编译术语表中的模式，处理变量名规则和重复变量"""
    global _compiled_glossary_patterns, glossary_compiled

    logger.info("Compiling glossary patterns...")
    temp_patterns = {}
    # 变量名匹配规则: 允许字母、数字、下划线、连字符，至少一个字符
    variable_pattern = re.compile(r"\{\{([a-zA-Z0-9_-]+)(?::([^}]+))?\}\}")

    for key, value in glossary.items():
        # --- 检查 value 中的变量是否都在 key 中 ---
        value_vars = set(m.group(1) for m in variable_pattern.finditer(value))
        key_vars_found = set()  # 用于记录key中实际出现的变量名

        # --- 构建正则表达式和处理重复变量 ---
        variables = []  # 按捕获组顺序存储变量名 (只存首次出现的)
        regex_parts = []
        last_pos = 0
        variable_to_group_index = {}
        current_group_index = 1

        # 初始化 full_regex_str
        full_regex_str = None
        try:
            for match in variable_pattern.finditer(key):
                var_name = match.group(1)
                custom_regex = match.group(2)

                key_vars_found.add(var_name)  # 记录在key中找到的变量

                # 1. 添加 {{ 前面的普通文本，并进行正则转义
                regex_parts.append(re.escape(key[last_pos:match.start()]))

                # 2. 处理变量: 新变量 or 重复变量?
                if var_name in variable_to_group_index:
                    # 重复变量: 使用反向引用
                    group_index = variable_to_group_index[var_name]
                    regex_parts.append(f"\\{group_index}")  # 添加反向引用 \N
                    logger.debug(
                        f"  Key '{key}': Variable '{{{{{var_name}}}}}' repeated, using backreference \\{group_index}")
                else:
                    # 新变量: 创建捕获组
                    capture_group = f"({custom_regex})" if custom_regex else "(.+?)"
                    regex_parts.append(capture_group)
                    variable_to_group_index[var_name] = current_group_index  # 记录名称和组索引
                    variables.append(var_name)  # 将新变量名按顺序添加到列表
                    current_group_index += 1  # 为下一个新捕获组增加索引

                last_pos = match.end()

            # 3. 添加最后一个变量后面的普通文本
            regex_parts.append(re.escape(key[last_pos:]))

            # 4. 组合成完整正则表达式 (现在 full_regex_str 肯定会被赋值)
            full_regex_str = "^" + "".join(regex_parts) + "$"

            # 5. 检查 value 中的变量是否都已在 key 中定义
            missing_vars = value_vars - key_vars_found
            if missing_vars:
                logger.warning(
                    f"Skipping key '{key}': Value '{value}' contains variables {missing_vars} not present in the key.")
                continue  # 跳过这个无效的条目

            # 6. 编译并存储
            compiled_regex = re.compile(full_regex_str)
            temp_patterns[key] = {
                "regex": compiled_regex,
                "variables": variables,  # 只包含实际捕获组对应的变量名 (无重复)
                "original_value": value
            }
            logger.debug(f"Compiled: '{key}' -> Regex: '{full_regex_str}', Capture Vars: {variables}")

        except re.error as e:
            logger.error(
                f"Error compiling regex for key '{key}' (pattern: '{full_regex_str or 'Error before pattern generation'}'): {e}")
        except Exception as e:  # 捕获其他潜在错误
            logger.error(f"Unexpected error processing key '{key}': {e}")

    _compiled_glossary_patterns = temp_patterns
    glossary_compiled = True


def match_and_translate(original_chat_message: str) -> str | None:
    """
    使用更新后的规则（包括重复变量检查）来匹配和翻译消息。
    """

    if not glossary_compiled:
        _compile_glossary_patterns()

    # 1. 尝试通过编译后的模式进行匹配
    for pattern_key, pattern_data in _compiled_glossary_patterns.items():
        compiled_regex = pattern_data["regex"]
        match = compiled_regex.match(original_chat_message)

        if match:
            variables = pattern_data["variables"]  # 这些是按捕获组顺序的变量名
            original_value = pattern_data["original_value"]
            captured_values = match.groups()  # 捕获到的内容

            # 安全检查: 捕获组数量应与记录的变量数一致
            if len(variables) != len(captured_values):
                logger.error(
                    f"Internal Error: Mismatch between expected variables {variables} ({len(variables)}) and captured groups {captured_values} ({len(captured_values)}) for key '{pattern_key}' and message '{original_chat_message}'. Skipping.")
                continue  # 理论上不应发生

            # 创建变量名到捕获值的映射
            variable_map = dict(zip(variables, captured_values))

            logger.debug(
                f"Glossary match found for '{original_chat_message}' using key '{pattern_key}'. Variables captured: {variable_map}")

            # 在 value 中替换变量占位符
            translated_message = original_value
            # 使用原始的 value 字符串中的所有变量进行替换尝试
            # （因为 value 中可能包含重复的 {{name}}，而 variable_map 只有一个 'name'）
            value_variable_pattern = re.compile(r"\{\{([a-zA-Z0-9_-]+)\}\}")  # 再次匹配value中的变量
            placeholders_found_in_value = value_variable_pattern.findall(translated_message)

            for var_name in placeholders_found_in_value:
                if var_name in variable_map:
                    # 执行替换
                    placeholder = f"{{{{{var_name}}}}}"
                    translated_message = translated_message.replace(placeholder, variable_map[var_name])
                else:
                    # 这个变量在 key 中存在但未在 value 中使用 (或者 key 中的重复变量导致它不在 variable_map 中)
                    # 这种情况是允许的（如丢弃变量），但如果 value 真的需要它，编译阶段应该已警告
                    # 如果是因为反向引用匹配失败，这里也不会有对应的 key
                    logger.warning(
                        f"Variable '{{{{{var_name}}}}}' found in value '{original_value}' but not in captured variables map {variable_map} for key '{pattern_key}'. It might be intentionally discarded or indicate an issue.")
                    # 保留原样或根据需要处理

            logger.debug(f"Substituting variables in value: '{original_value}' -> '{translated_message}'")
            return translated_message

    # 2. 如果模式匹配失败，尝试精确匹配 (无变量的 key)
    if original_chat_message in glossary:
        # 检查这个 key 是否不是一个被编译的模式 (或者模式编译失败)
        # 或者它是一个没有变量的模式 (这种模式应该精确匹配)
        is_pattern = original_chat_message in _compiled_glossary_patterns
        has_variables_in_pattern = is_pattern and _compiled_glossary_patterns[original_chat_message]['variables']

        if not is_pattern or not has_variables_in_pattern:
            logger.debug(
                f"Using exact glossary match (no variables or pattern failed/skipped): '{original_chat_message}' -> '{glossary[original_chat_message]}'")
            return glossary[original_chat_message]
        # else: # 如果精确匹配的 key 是一个带变量的模式，则它应该在上面的循环中处理
        # logger.debug(f"Exact key '{original_chat_message}' is a pattern with variables, should have matched via regex if valid.")

    # 3. 如果都失败，返回 None
    return None


def process_decorator(function):
    """
    为process_message添加翻译步骤
    """

    def wrapper(data, data_type, translator, translation_service,
                model=None, source_language=None, target_language=None):
        """
        处理日志文件中的一行（包括翻译）

        :param data: 需要处理的数据
        :param data_type: 数据类型
        :param translator: Translator类的实例
        :param translation_service: 翻译服务
        :param model: 模型名称
        :param source_language: 源语言
        :param target_language: 目标语言
        :return:
            - None：应被丢弃的数据（可能是不包含[CHAT]的日志行，也可能是系统消息且trans_sys_message为False）
            - 长度为3的元组：
                - data_type == "log":
                    - [0]: 名称（如果有）, if [0] == "[ERROR]": 翻译失败，此时[1]为错误信息
                    - [1]: 翻译后的消息
                    - [2]: 相关信息（如是否命中缓存、消耗token等）
                - data_type == "clipboard":
                    - [0]: 是否翻译失败，if [0]: 翻译失败，此时[1]为错误信息
                    - [1]: 翻译后的消息
                    - [2]: 相关信息（如是否命中缓存、消耗token等）
        """

        name, original_chat_message = function(data, data_type)
        translated_chat_message: str = ""
        info: dict = {}
        if data_type == "log" and not trans_sys_message and not name:
            return ""
        if original_chat_message:
            if len(original_chat_message) >= min_detect_len:
                try:
                    langs = detect_langs(original_chat_message)
                    best_lang = langs[0]
                    if best_lang.prob >= 0.9:
                        detected_lang = best_lang.lang
                        logger.debug(f"Detected languages: {detected_lang}, confidence: {best_lang.prob}")
                    else:
                        detected_lang = UNKNOWN_LANGUAGE
                        logger.debug(f"Detected languages: {detected_lang}, but confidence {best_lang.prob} is too low")
                except LangDetectException as e:
                    logger.info(f"Language detection failed: {e} Proceeding with translation")
                    detected_lang = UNKNOWN_LANGUAGE
            else:
                detected_lang = UNKNOWN_LANGUAGE

            if matched_translated_message := match_and_translate(original_chat_message):
                logger.debug(f"Using custom glossary: {original_chat_message} -> {matched_translated_message}")
                translated_chat_message = matched_translated_message
                info["glossary_match"] = True
            elif detected_lang != UNKNOWN_LANGUAGE and detected_lang in skip_src_lang:
                logger.debug(f"Skipping translation for \"{original_chat_message}\" due to skip_src_lang")
                translated_chat_message = original_chat_message
                info["skip_src_lang"] = True
            elif original_chat_message in cache:
                logger.debug(f"Translation cache hit: {original_chat_message}")
                translated_chat_message = cache[original_chat_message]
                info["cache_hit"] = True
            else:
                try:
                    # 向后兼容旧配置中的 "LLM" 值
                    if translation_service == "LLM":
                        translation_service = LLM_PROVIDERS[0]

                    if translation_service in LLM_PROVIDERS:
                        if result := translator.llm_translate(
                            original_chat_message,
                            model=model,
                            source_language=source_language,
                            target_language=target_language,
                            provider=translation_service
                        ):
                            translated_chat_message = result["result"]
                            info["usage"] = result["usage"]
                    elif translation_service in services:
                        translated_chat_message = translator.traditional_translate(
                            original_chat_message,
                            translation_service,
                            source_language=source_language,
                            target_language=target_language
                        )
                except HTTPError as http_err:
                    response = getattr(http_err, "response", None)
                    if response:
                        if response.status_code == 429:
                            # 请求过多
                            return "[ERROR]", _("Translation failed: Too many requests. Please try again later."), info
                        elif 500 <= response.status_code < 600:
                            # 服务器错误
                            return "[ERROR]", _("Translation failed: Server error. Please try again later."), info
                        else:
                            # 其他 HTTP 错误
                            return "[ERROR]", _("Translation failed: HTTP error occurred."), info
                    else:
                        # 无法获取响应对象，可能是网络问题
                        return "[ERROR]", _("Translation failed: Network issue or HTTP error occurred."), info
                except JSONDecodeError:
                    # JSON 解码错误，可能是网络问题或服务器返回了非 JSON 数据
                    return "[ERROR]", _("Translation failed: Invalid response from server. Please check your network connection."), info
                except Exception as e:
                    # 捕获其他未知错误
                    return "[ERROR]", f"{_('Translation failed, error:')} {e}", info

                if translated_chat_message:
                    logger.debug(f"Translation successful, caching result: {original_chat_message} -> {translated_chat_message}")
                    cache[original_chat_message] = translated_chat_message

            if data_type == "log":
                return name or "", translated_chat_message, info
            elif data_type == "clipboard":
                return False, translated_chat_message, info

        return None

    return wrapper


@process_decorator
def process_message(data, data_type):
    """
    处理日志文件中的一行

    :param data: 需要处理的数据
    :param data_type: 数据类型
    :return: 元组 (玩家名称, 聊天内容)
    """

    chat_message: str = ""
    if data_type == "log":
        if "[CHAT]" in data:
            chat_message = data.split("[CHAT]")[1].strip()
    elif data_type == "clipboard":
        return "", data.strip()
    else:
        return "", ""

    if replace_garbled_character:
        chat_message = chat_message.replace("\ufffd\ufffd", "\u00A7")

    if chat_message.startswith("<"):
        name, text = chat_message[1:].split(">", 1)
    else:  # Hypixel Chat
        if ":" not in chat_message:
            return "", chat_message.strip()

        name, text = chat_message.split(":", 1)

    name = name.strip()
    text = text.strip()

    return name, text
