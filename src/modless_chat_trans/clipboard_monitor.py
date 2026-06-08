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

import time
from modless_chat_trans.logger import logger

# ──────────────────────────────
# 可选依赖：pyperclip
# 导入失败时禁用剪切板监听功能
# ──────────────────────────────
try:
    import pyperclip
    CLIPBOARD_AVAILABLE = True
    CLIPBOARD_IMPORT_ERROR = None
except ImportError as _clip_exc:
    pyperclip = None  # type: ignore[assignment]
    CLIPBOARD_AVAILABLE = False
    CLIPBOARD_IMPORT_ERROR = str(_clip_exc)
    logger.warning(f"[Clipboard] 'pyperclip' not available, clipboard monitoring disabled: {_clip_exc}")

# 初始化剪贴板内容
previous_clipboard_content = None


def monitor_clipboard(callback):
    """
    监控剪贴板的变化

    :param callback: 检测到新内容的回调函数
    """
    if not CLIPBOARD_AVAILABLE:
        logger.warning("[Clipboard] pyperclip not available, clipboard monitoring is a no-op")
        return

    logger.info("Starting clipboard monitoring")
    global previous_clipboard_content

    # 初始化剪贴板内容，避免启动时的误检测
    if previous_clipboard_content is None:
        previous_clipboard_content = pyperclip.paste()
        logger.debug("Initial clipboard content")

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
    if not CLIPBOARD_AVAILABLE:
        logger.warning("[Clipboard] pyperclip not available, cannot modify clipboard")
        return
    logger.debug(f"Modifying clipboard with new content (length: {len(data)})")
    global previous_clipboard_content
    try:
        pyperclip.copy(data)
        previous_clipboard_content = data
        logger.debug("Clipboard content updated successfully")
    except Exception as e:
        logger.error(f"Failed to modify clipboard: {str(e)}")
