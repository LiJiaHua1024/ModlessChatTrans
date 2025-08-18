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

import gettext
from typing import Callable
from modless_chat_trans.file_utils import get_path
from modless_chat_trans.logger import logger

current_language = None
_: Callable[[str], str] = lambda x: x

supported_languages = [("简体中文", "zh_CN"), ("English", "en_US"), ("日本語", "ja_JP"), ("Français", "fr_FR"),
                       ("Deutsch", "de_DE"), ("Español", "es_ES"), ("한국어", "ko_KR"), ("Русский", "ru_RU"),
                       ("Português do Brasil", "pt_BR"), ("繁體中文", "zh_TW")]


def set_language(language):
    global current_language, _

    if language == "zh_CN":
        return

    logger.info(f"Setting application language to: {language}")
    try:
        logger.debug(f"Loading translation files from: {get_path('locales')}")
        current_language = gettext.translation("translations", localedir=get_path("locales"), languages=[language])
        current_language.install()
        logger.info(f"Language set successfully to: {language}")
    except FileNotFoundError as e:
        logger.error(f"Translation file not found: {str(e)}")
        logger.warning("Falling back to default gettext")
    except Exception as e:
        logger.error(f"Failed to set language: {str(e)}")
    finally:
        _ = current_language.gettext if current_language else gettext.gettext
        logger.debug("Translation function initialized")
