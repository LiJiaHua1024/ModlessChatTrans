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
import time
from modless_chat_trans.file_utils import find_latest_log


def monitor_log_file(file_directory, callback):
    """
    监控日志文件的变化

    :param file_directory: 要监控的日志文件目录
    :param callback: 检测到新内容的回调函数
    """

    while True:
        if file_path := find_latest_log(file_directory):
            with open(file_path, 'r', encoding='utf-8') as log_file:
                log_file.seek(0, os.SEEK_END)  # 移动到文件末尾
                # 检测新添加的内容
                while True:
                    line = log_file.readline()
                    # 当有新内容时
                    if line:
                        callback(line)
                    if find_latest_log(file_directory) != file_path:
                        # 文件被重命名并重新创建
                        break
                    time.sleep(0.1)
        else:
            print("未找到日志文件")
            time.sleep(1)
            continue
