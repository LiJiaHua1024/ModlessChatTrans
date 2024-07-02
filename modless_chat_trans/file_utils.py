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
from dataclasses import dataclass


@dataclass
class Config:
    minecraft_log_folder: str
    output_method: str
    source_language: str
    target_language: str
    api_url: str
    api_key: str
    model: str
    http_port: int


DEFAULT_CONFIG = Config(minecraft_log_folder="",
                        output_method="graphical",
                        source_language="",
                        target_language="zh-CN",
                        api_url="https://api.openai.com/v1/chat/completions",
                        api_key="",
                        model="gpt-3.5-turbo",
                        http_port=5000)


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

    # 判断文件是否存在，如果不存在则创建一个空文件
    if not os.path.exists('ModlessChatTrans-config.json'):
        with open('ModlessChatTrans-config.json', 'w') as config_file:
            # 将默认配置写入文件
            json.dump(vars(DEFAULT_CONFIG), config_file)

    # 读取配置文件中的配置
    with open('ModlessChatTrans-config.json', 'r') as config_file:
        config_dict = json.load(config_file)
        return Config(**config_dict)


def save_config(**config_changes):
    """
    保存配置到文件

    :param config_changes: 配置修改项
    """

    config = read_config()
    for key, value in config_changes.items():
        setattr(config, key, value)
    with open('ModlessChatTrans-config.json', 'w') as config_file:
        json.dump(vars(config), config_file)
