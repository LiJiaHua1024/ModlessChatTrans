# Copyright (C) 2024 LiJiaHua1024
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
import glob
import json
import shelve
from dataclasses import dataclass

base_path = os.path.dirname(os.path.dirname(__file__))
cache = shelve.open("MCT_cache")


def get_path(path, temp_path=True):
    if temp_path:
        return os.path.join(base_path, path)
    else:
        return os.path.join(os.getcwd(), path)


def get_platform():
    return {"nt": 0, "posix": 1}.get(os.name, 2)


@dataclass
class Config:
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
    update_check_frequency: str
    last_check_time: str
    include_prerelease: bool
    enable_optimization: bool


DEFAULT_CONFIG = Config(interface_lang="zh_CN",
                        minecraft_log_folder="",
                        output_method="Graphical",
                        trans_service="LLM",
                        op_src_lang="",
                        op_tgt_lang="zh-CN",
                        self_trans_enabled=True,
                        self_src_lang="zh-CN",
                        self_tgt_lang="en-US",
                        api_url="https://api.openai.com/v1/chat/completions",
                        api_key="",
                        model="gpt-4o-mini",
                        http_port=56552,
                        max_messages=150,
                        always_on_top=False,
                        update_check_frequency="Daily",
                        last_check_time="1970-01-01T00:00:00",
                        include_prerelease=False,
                        enable_optimization=False)


def find_latest_log(directory: str) -> str:
    """
    获取目录中最新的日志文件

    :param directory: 目录
    :return: 最新的日志文件
    """

    log_files = glob.glob(os.path.join(directory, '*.log'))

    # 根据修改时间排序日志文件，最新的文件在最前
    if log_files:
        latest_log_file = max(log_files, key=os.path.getmtime)
        return latest_log_file

    # 如果没有找到任何日志文件，返回空
    return ""


def read_config():
    """
    读取配置文件

    :return: Config 对象
    """

    def create_default_config():
        with open("ModlessChatTrans-config.json", "w", encoding="utf-8") as _config_file:
            # 将默认配置写入文件
            # noinspection PyTypeChecker
            json.dump(vars(DEFAULT_CONFIG), _config_file, indent=4, ensure_ascii=False)

    # 判断文件是否存在，如果不存在则创建一个空文件
    if not os.path.exists('ModlessChatTrans-config.json'):
        create_default_config()

    # 重试一次
    for _ in range(2):
        try:
            # 读取配置文件中的配置
            with open('ModlessChatTrans-config.json', 'r', encoding="utf-8") as config_file:
                config_dict = json.load(config_file)
            merged_config = {key: config_dict.get(key, default) for key, default in vars(DEFAULT_CONFIG).items()}
            return Config(**merged_config)
        except json.JSONDecodeError:
            os.rename("ModlessChatTrans-config.json", "ModlessChatTrans-config.json.bak")
            create_default_config()


def save_config(**config_changes):
    """
    保存配置到文件

    :param config_changes: 配置修改项
    """

    config = read_config()
    for key, value in config_changes.items():
        setattr(config, key, value)
    with open("ModlessChatTrans-config.json", "w", encoding="utf-8") as config_file:
        # noinspection PyTypeChecker
        json.dump(vars(config), config_file, indent=4, ensure_ascii=False)
