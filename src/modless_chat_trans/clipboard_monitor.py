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

import pyperclip
import time
from modless_chat_trans.logger import logger

previous_clipboard_content = pyperclip.paste()


def monitor_clipboard(callback):
    """
    监控日志文件的变化

    :param callback: 检测到新内容的回调函数
    """
    logger.info("Starting clipboard monitoring")
    global previous_clipboard_content

    while True:
        try:
            current_clipboard_content = pyperclip.paste()

            if current_clipboard_content != previous_clipboard_content:
                logger.debug("Clipboard content changed")
                if previous_clipboard_content := current_clipboard_content:
                    clip_preview = current_clipboard_content[:30]
                    if len(current_clipboard_content) > 30:
                        clip_preview += "..."
                    logger.debug(f"Processing new clipboard content: {clip_preview}")

                    if result := callback(current_clipboard_content, data_type="clipboard"):
                        previous_clipboard_content = result

            time.sleep(0.3)
        except Exception as e:
            logger.error(f"Error in clipboard monitor: {str(e)}")
            time.sleep(1)  # Longer delay after error


def modify_clipboard(data):
    logger.debug(f"Modifying clipboard with new content (length: {len(data)})")
    global previous_clipboard_content
    try:
        pyperclip.copy(data)
        previous_clipboard_content = data
        logger.debug("Clipboard content updated successfully")
    except Exception as e:
        logger.error(f"Failed to modify clipboard: {str(e)}")
