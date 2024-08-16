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

import pyperclip
import time


def monitor_clipboard(callback):
    """
    监控日志文件的变化

    :param callback: 检测到新内容的回调函数
    """

    previous_clipboard_content = pyperclip.paste()
    while True:
        current_clipboard_content = pyperclip.paste()
        if current_clipboard_content != previous_clipboard_content:
            if previous_clipboard_content := current_clipboard_content:
                previous_clipboard_content = callback(current_clipboard_content, data_type="clipboard")

        time.sleep(0.3)


def modify_clipboard(data):
    pyperclip.copy(data)
