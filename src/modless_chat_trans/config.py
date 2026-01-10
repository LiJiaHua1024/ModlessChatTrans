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

import os
import json
import tomllib
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple, Type

import tomli_w
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError
from pydantic_settings import (
    BaseSettings,
    JsonConfigSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

from modless_chat_trans.file_utils import get_path, is_file_exists


def snake_to_kebab(field_name: str) -> str:
    return field_name.replace('_', '-')


def kebab_to_snake(field_name: str) -> str:
    return field_name.replace('-', '_')


class BaseConfigModel(BaseModel):
    model_config = ConfigDict(alias_generator=snake_to_kebab, populate_by_name=True)


class ServiceType(Enum):
    LLM = "llm"
    TRADITIONAL = "traditional"


class MonitorMode(Enum):
    EFFICIENT = "efficient"
    COMPATIBLE = "compatible"


class LLMServiceConfig(BaseConfigModel):
    provider: str
    api_key: str
    api_base: Optional[str] = None
    model: str
    deep_translate: bool
    timeout: float


class TraditionalServiceConfig(BaseConfigModel):
    provider: str
    api_key: Optional[str] = None
    timeout: float


class TranslationServiceConfig(BaseConfigModel):
    service_type: ServiceType
    llm: Optional[LLMServiceConfig] = None
    traditional: Optional[TraditionalServiceConfig] = None


class MessageCaptureConfig(BaseConfigModel):
    minecraft_log_path: str
    log_encoding: str
    monitor_mode: MonitorMode
    filter_server_messages: bool
    replace_garbled_chars: bool
    source_language: str
    target_language: str


class MessagePresentationConfig(BaseConfigModel):
    web_port: int


class MessageSendConfig(BaseConfigModel):
    monitor_clipboard: bool
    source_language: str
    target_language: str


class SettingConfig(BaseConfigModel):
    debug: bool
    interface_language: str
    auto_check_update_frequency: Literal['startup', 'daily', 'weekly', 'monthly', 'never']
    include_prerelease: bool
    last_update_check_time: str


class MessageBlacklistRule(BaseConfigModel):
    """消息内容黑名单规则"""
    pattern: str  # 正则表达式或关键词
    is_regex: bool = False  # 是否使用正则表达式


class BlacklistConfig(BaseConfigModel):
    """黑名单配置"""
    user_blacklist: List[str] = []  # 用户黑名单（玩家名称全匹配）
    message_blacklist: List[MessageBlacklistRule] = []  # 消息内容黑名单


class ConfigV3FromInit(BaseSettings):
    model_config = SettingsConfigDict(
        alias_generator=snake_to_kebab,
        populate_by_name=True,
    )
    config_version: str
    message_capture: MessageCaptureConfig
    player_translation: TranslationServiceConfig
    send_translation_independent: bool
    send_translation: Optional[TranslationServiceConfig] = None
    message_presentation: MessagePresentationConfig
    message_send: MessageSendConfig
    settings: SettingConfig
    glossary: Dict[str, str]
    blacklist: BlacklistConfig = BlacklistConfig()


class ConfigV3(ConfigV3FromInit):
    model_config = SettingsConfigDict(
        toml_file=[get_path("modless-chat-trans.default.toml"), "modless-chat-trans.toml"],
        alias_generator=snake_to_kebab,
        populate_by_name=True
    )

    @classmethod
    def settings_customise_sources(
            cls,
            settings_cls: type[BaseSettings],
            init_settings: PydanticBaseSettingsSource,
            env_settings: PydanticBaseSettingsSource,
            dotenv_settings: PydanticBaseSettingsSource,
            file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (TomlConfigSettingsSource(settings_cls),)


class ConfigV2(BaseSettings):
    config_version: Optional[str] = "2.2.0"
    interface_lang: str
    minecraft_log_folder: str
    output_method: str
    trans_service: str
    op_src_lang: str  # other player source language
    op_tgt_lang: str  # other player target language
    self_trans_enabled: bool  # self translation enabled
    self_src_lang: str  # self source language
    self_tgt_lang: str  # self target language
    api_url: str
    api_key: str
    model: str
    http_port: int
    max_messages: int
    always_on_top: bool
    update_check_frequency: Optional[Literal['Startup', 'Daily', 'Weekly', 'Monthly', 'Never']] = 'Daily'
    last_check_time: Optional[str] = "1970-01-01T00:00:00"
    include_prerelease: Optional[bool] = False
    enable_optimization: Optional[bool] = False
    use_high_version_fix: Optional[bool] = False
    traditional_api_key: Optional[str] = ""
    trans_sys_message: Optional[bool] = True
    debug: Optional[bool] = False
    skip_src_lang: Optional[list] = []  # ISO 639-1 language code
    min_detect_len: Optional[int] = 100  # minimum length of detected text
    encoding: Optional[str] = ""  # encoding of the log file
    replace_garbled_character: Optional[bool] = False  # Replace garbled characters \ufffd\ufffd with \u00A7
    total_tokens: Optional[int] = 0  # total number of tokens consumed
    glossary: Optional[dict] = {}

    model_config = SettingsConfigDict(
        json_file=[get_path("modless-chat-trans.default.json"), "ModlessChatTrans-config.json"],
        json_file_encoding="utf-8"
    )

    @classmethod
    def settings_customise_sources(
            cls,
            settings_cls: type[BaseSettings],
            init_settings: PydanticBaseSettingsSource,
            env_settings: PydanticBaseSettingsSource,
            dotenv_settings: PydanticBaseSettingsSource,
            file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (JsonConfigSettingsSource(settings_cls),)


def convert_v2_to_v3(config_v2: ConfigV2) -> ConfigV3FromInit:
    from modless_chat_trans.translator import LLM_PROVIDERS, TRADITIONAL_SERVICES

    with open(get_path("modless-chat-trans.default.toml"), 'rb') as f:
        default_v3_dict = tomllib.load(f)

    v2_converted: Dict[str, Any] = {
        "config-version": "3.0.0",
        "message-capture": {
            "minecraft-log-path": config_v2.minecraft_log_folder,
            "monitor-mode": "compatible" if config_v2.use_high_version_fix else "efficient",
            "filter-server-messages": not config_v2.trans_sys_message,
            "replace-garbled-chars": config_v2.replace_garbled_character,
            "source-language": config_v2.op_src_lang,
            "target-language": config_v2.op_tgt_lang,
        },
        "message-presentation": {
            "web-port": config_v2.http_port,
        },
        "message-send": {
            "monitor-clipboard": config_v2.self_trans_enabled,
            "source-language": config_v2.self_src_lang,
            "target-language": config_v2.self_tgt_lang,
        },
        "settings": {
            "debug": config_v2.debug,
            "interface-language": config_v2.interface_lang,
            "auto-check-update-frequency": (
                config_v2.update_check_frequency.lower()
                if config_v2.update_check_frequency
                else "daily"
            ),
            "include-prerelease": config_v2.include_prerelease,
            "last-update-check-time": config_v2.last_check_time,
        },
        "glossary": config_v2.glossary if config_v2.glossary else {},
        "send-translation-independent": False,
    }

    if config_v2.encoding:
        v2_converted["message-capture"]["log-encoding"] = config_v2.encoding

    # 根据服务类型构建 player-translation
    if config_v2.trans_service in LLM_PROVIDERS:
        llm_config: Dict[str, Any] = {
            "provider": config_v2.trans_service,
            "api-key": config_v2.api_key,
            "model": config_v2.model,
            "deep-translate": config_v2.enable_optimization,
        }
        if config_v2.api_url:  # 只有当 api_url 非空时才添加
            llm_config["api-base"] = config_v2.api_url

        v2_converted["player-translation"] = {
            "service-type": "llm",
            "llm": llm_config,
        }
    elif config_v2.trans_service in TRADITIONAL_SERVICES:
        traditional_config: Dict[str, Any] = {
            "provider": config_v2.trans_service,
        }
        if config_v2.traditional_api_key:  # 只有当 api_key 非空时才添加
            traditional_config["api-key"] = config_v2.traditional_api_key

        v2_converted["player-translation"] = {
            "service-type": "traditional",
            "traditional": traditional_config,
        }
    else:
        raise ValueError(f"Unknown translation service: {config_v2.trans_service}")

    # 使用 deep_merge 合并配置
    # v3 配置作为 base，转换后的 v2 配置作为 override
    merged_dict = deep_merge(default_v3_dict, v2_converted)

    return ConfigV3FromInit.model_validate(merged_dict)


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """深合并两个字典，override中的值会覆盖base中的值，支持Pydantic模型的深合并"""
    result = base.copy()
    for key, value in override.items():
        if key in result:
            base_val = result[key]
            # 处理两者都是dict的情况
            if isinstance(base_val, dict) and isinstance(value, dict):
                result[key] = deep_merge(base_val, value)
            # 处理Pydantic模型的情况：将value合并到BaseModel的字典形式
            elif isinstance(base_val, BaseModel) and isinstance(value, dict):
                base_dict = base_val.model_dump()
                merged_dict = deep_merge(base_dict, value)
                result[key] = type(base_val).model_validate(merged_dict)
            else:
                result[key] = value
        else:
            result[key] = value
    return result


def load_default_v2_config() -> ConfigV2:
    with open(get_path("modless-chat-trans.default.json"), 'r', encoding='utf-8') as f:
        default_dict = json.load(f)
    return ConfigV2.model_validate(default_dict)


def load_default_v3_config() -> ConfigV3FromInit:
    with open(get_path("modless-chat-trans.default.toml"), 'rb') as f:
        default_dict = tomllib.load(f)
    return ConfigV3FromInit.model_validate(default_dict)


# noinspection PyArgumentList
def handle_v2_validation_error(error: ValidationError, config_dict: Dict[str, Any]) -> ConfigV2:
    missing_fields = [
        err for err in error.errors()
        if err.get('type') == 'missing'
    ]

    if missing_fields:
        try:
            with open(get_path("modless-chat-trans.default.json"), 'r', encoding='utf-8') as f:
                default_dict = json.load(f)

            merged_dict = deep_merge(default_dict, config_dict)

            try:
                # 尝试用合并后的配置创建ConfigV2
                return ConfigV2.model_validate(merged_dict)
            except ValidationError:
                return ConfigV2.model_validate(default_dict)
        except Exception:
            return load_default_v2_config()
    else:
        return load_default_v2_config()


# noinspection PyArgumentList
def handle_v3_validation_error(error: ValidationError, config_dict: Dict[str, Any]) -> ConfigV3 | ConfigV3FromInit:
    """处理V3配置的ValidationError"""
    missing_fields = [
        err for err in error.errors()
        if err.get('type') == 'missing'
    ]

    if missing_fields:
        try:
            # 加载默认V3配置
            with open(get_path("modless-chat-trans.default.toml"), 'rb') as f:
                default_dict = tomllib.load(f)

            # 深合并
            merged_dict = deep_merge(default_dict, config_dict)

            try:
                # 使用ConfigV3FromInit避免再次触发文件读取
                return ConfigV3FromInit(**merged_dict)
            except ValidationError:
                # 如果还是失败，使用完整的默认配置
                return ConfigV3FromInit(**default_dict)
        except Exception:
            # 如果无法读取默认配置，使用ConfigV3的默认值
            return ConfigV3()
    else:
        return ConfigV3()


# noinspection PyArgumentList
def read_v2_config_safely() -> ConfigV2:
    try:
        return ConfigV2()
    except ValidationError as e:
        try:
            with open("ModlessChatTrans-config.json", 'r', encoding='utf-8') as f:
                config_dict = json.load(f)
            return handle_v2_validation_error(e, config_dict)
        except Exception:
            # 如果无法读取配置文件，使用默认配置
            return load_default_v2_config()


# noinspection PyArgumentList
def read_v3_config_safely() -> ConfigV3 | ConfigV3FromInit:
    try:
        return ConfigV3()
    except ValidationError as e:
        try:
            with open("modless-chat-trans.toml", 'rb') as f:
                config_dict = tomllib.load(f)
            return handle_v3_validation_error(e, config_dict)
        except Exception:
            return load_default_v3_config()


# noinspection PyArgumentList
def read_config() -> ConfigV3 | ConfigV3FromInit:
    if not is_file_exists("modless-chat-trans.toml") and is_file_exists("ModlessChatTrans-config.json"):
        v2_config = read_v2_config_safely()
        return convert_v2_to_v3(v2_config)
    return read_v3_config_safely()


def save_config(config: ConfigV3 | ConfigV3FromInit) -> bool:
    try:
        with open("modless-chat-trans.toml", 'wb') as f:
            tomli_w.dump(config.model_dump(by_alias=True, mode='json', exclude_none=True), f)
        return True
    except:
        return False


def update_config(**updates) -> bool:
    try:
        config = read_config()
        for path, value in updates.items():
            keys = path.split('__')
            obj = config
            for key in keys[:-1]:
                obj = getattr(obj, key)
            setattr(obj, keys[-1], value)
        if save_config(config):
            return True
    except Exception:
        pass
    return False
