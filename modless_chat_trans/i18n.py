import gettext
from modless_chat_trans.file_utils import get_path

current_language = None
_ = None

supported_languages = [("简体中文", "zh_CN"), ("English", "en_US"), ("日本語", "ja_JP"), ("Français", "fr_FR"),
                       ("Deutsch", "de_DE"), ("Español", "es_ES"), ("한국어", "ko_KR"), ("Русский", "ru_RU"),
                       ("Português do Brasil", "pt_BR")]

lang_window_size_map = {
    "zh_CN": "750x620",
    "en_US": "750x620",
    "ja_JP": "750x620",
    "fr_FR": "780x620",
    "de_DE": "750x620",
    "es_ES": "840x620",
    "ko_KR": "750x620",
    "ru_RU": "860x620",
    "pt_BR": "820x620",
}


def set_language(language):
    global current_language, _
    try:
        current_language = gettext.translation("translations", localedir=get_path("locales"), languages=[language])
        current_language.install()
    finally:
        _ = current_language.gettext if current_language else gettext.gettext
