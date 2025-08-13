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
from enum import Enum
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple, Type

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
    LLM = "LLM"
    TRADITIONAL = "Traditional"


class MonitorMode(Enum):
    EFFICIENT = "efficient"
    COMPATIBLE = "compatible"


class LLMServiceConfig(BaseConfigModel):
    provider: str
    api_key: str
    api_base: Optional[str]
    model: str
    deep_translate: bool


class TraditionalServiceConfig(BaseConfigModel):
    provider: str
    api_key: Optional[str]


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


class ConfigV3FromInit(BaseSettings):
    model_config =SettingsConfigDict(
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
        json_file=[get_path("modless-chat-trans.default.json"), "ModlessChatTrans-config.json"])

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


def convert_v2_to_v3(config_v2: ConfigV2) -> ConfigV3:
    from modless_chat_trans.translator import LLM_PROVIDERS, TRADITIONAL_SERVICES
    # 判断服务类型
    if config_v2.trans_service in LLM_PROVIDERS:
        service_type = ServiceType.LLM
        player_translation = TranslationServiceConfig(
            service_type=service_type,
            llm=LLMServiceConfig(
                provider=config_v2.trans_service,
                api_key=config_v2.api_key,
                api_base=config_v2.api_url,
                model=config_v2.model,
                deep_translate=config_v2.enable_optimization
            )
        )
    elif config_v2.trans_service in TRADITIONAL_SERVICES:
        service_type = ServiceType.TRADITIONAL
        player_translation = TranslationServiceConfig(
            service_type=service_type,
            traditional=TraditionalServiceConfig(
                provider=config_v2.trans_service,
                api_key=config_v2.traditional_api_key
            )
        )
    else:
        raise ValueError(f"Unknown translation service: {config_v2.trans_service}")

    # noinspection PyTypeChecker
    return ConfigV3FromInit(
        config_version="3.0.0",
        message_capture=MessageCaptureConfig(
            minecraft_log_path=config_v2.minecraft_log_folder,
            log_encoding=config_v2.encoding,
            monitor_mode=MonitorMode.COMPATIBLE if config_v2.use_high_version_fix else MonitorMode.EFFICIENT,
            filter_server_messages=not config_v2.trans_sys_message,
            replace_garbled_chars=config_v2.replace_garbled_character,
            source_language=config_v2.op_src_lang,
            target_language=config_v2.op_tgt_lang
        ),
        player_translation=player_translation,
        send_translation_independent=False,
        send_translation=None,
        message_presentation=MessagePresentationConfig(
            web_port=config_v2.http_port
        ),
        message_send=MessageSendConfig(
            monitor_clipboard=config_v2.self_trans_enabled,
            source_language=config_v2.self_src_lang,
            target_language=config_v2.self_tgt_lang
        ),
        settings=SettingConfig(
            debug=config_v2.debug,
            interface_language=config_v2.interface_lang,
            auto_check_update_frequency=config_v2.update_check_frequency.lower(),
            include_prerelease=config_v2.include_prerelease,
            last_update_check_time=config_v2.last_check_time
        ),
        glossary=config_v2.glossary
    )


# noinspection PyArgumentList
def read_config() -> ConfigV3:
    if not is_file_exists("modless-chat-trans.toml") and is_file_exists("ModlessChatTrans-config.json"):
        return convert_v2_to_v3(ConfigV2())
    return ConfigV3()


def save_config(config: ConfigV3) -> bool:
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


if __name__ == "__main__":
    cfg = read_config()
    print(cfg)
    save_config(cfg)
