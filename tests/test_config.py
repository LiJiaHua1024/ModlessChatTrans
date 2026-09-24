"""配置兼容性与启动时自动更新的回归测试，只读写临时目录。"""

import copy
import os
import tempfile
import unittest
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib

import tomli_w

from modless_chat_trans.config import (
    ConfigV3FromInit,
    read_config,
    update_config,
)
from modless_chat_trans.file_utils import get_path


class ConfigCompatibilityTests(unittest.TestCase):
    def setUp(self):
        with open(get_path("modless-chat-trans.default.toml"), "rb") as stream:
            self.defaults = tomllib.load(stream)
        self.data = copy.deepcopy(self.defaults)
        self.data["player-translation"]["llm"]["api-key"] = "user-api-key"
        self.data["message-capture"]["minecraft-log-path"] = "user/logs"
        self.data["glossary"] = {"Steve": "史蒂夫"}

        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        original_cwd = Path.cwd()
        os.chdir(directory.name)
        self.addCleanup(os.chdir, original_cwd)
        self.path = Path("modless-chat-trans.toml")

    def write_config(self):
        self.path.write_text(tomli_w.dumps(self.data), encoding="utf-8")
        return self.path.read_bytes()

    def assert_user_settings(self, config):
        self.assertEqual(config.player_translation.llm.api_key, "user-api-key")
        self.assertEqual(config.message_capture.minecraft_log_path, "user/logs")
        self.assertEqual(config.glossary, {"Steve": "史蒂夫"})

    def test_unknown_nested_fields_are_ignored_by_the_model(self):
        for section in (self.data["settings"], self.data["context"],
                        self.data["player-translation"]["llm"]):
            section["future-setting"] = {"enabled": True}
        config = ConfigV3FromInit.model_validate(self.data)
        self.assert_user_settings(config)
        dumped = config.model_dump(by_alias=True)
        for section in (dumped["settings"], dumped["context"],
                        dumped["player-translation"]["llm"]):
            self.assertNotIn("future-setting", section)

    def test_unknown_top_level_fields_preserve_user_settings_on_startup(self):
        self.data["future-setting"] = True
        self.data["future-section"] = {"enabled": True}
        before = self.write_config()

        config = read_config()

        self.assert_user_settings(config)
        self.assertNotIn("future-section", config.model_dump(by_alias=True))
        self.assertEqual(self.path.read_bytes(), before)

    def test_missing_fields_are_filled_even_with_unknown_sections(self):
        for with_unknown_section in (False, True):
            with self.subTest(with_unknown_section=with_unknown_section):
                self.data["player-translation"]["llm"].pop("max-tokens", None)
                if with_unknown_section:
                    self.data["future-section"] = {"enabled": True}
                before = self.write_config()

                config = read_config()

                self.assert_user_settings(config)
                self.assertEqual(config.player_translation.llm.max_tokens,
                                 self.defaults["player-translation"]["llm"]["max-tokens"])
                self.assertEqual(self.path.read_bytes(), before)

    def test_automatic_update_does_not_persist_fallback_defaults(self):
        for with_missing_field in (False, True):
            with self.subTest(with_missing_field=with_missing_field):
                # 模拟新版新增了旧版不支持的枚举值。
                self.data["message-classification"]["classifier"] = "future-classifier"
                if with_missing_field:
                    del self.data["player-translation"]["llm"]["max-tokens"]
                before = self.write_config()

                config = read_config()
                self.assertEqual(config.message_classification.classifier.value, "rule")
                self.assertEqual(self.path.read_bytes(), before)
                self.assertFalse(update_config(settings__last_update_check_time="2026-09-23T12:00:00"))
                self.assertEqual(self.path.read_bytes(), before)

    def test_automatic_update_preserves_known_settings_with_unknown_fields(self):
        self.data["future-section"] = {"enabled": True}
        self.data["settings"]["future-setting"] = True
        del self.data["player-translation"]["llm"]["max-tokens"]
        self.write_config()

        self.assertTrue(update_config(settings__last_update_check_time="2026-09-23T12:00:00"))

        config = read_config()
        self.assert_user_settings(config)
        self.assertEqual(config.settings.last_update_check_time, "2026-09-23T12:00:00")

    def test_automatic_update_does_not_overwrite_malformed_toml(self):
        before = b"[settings\ninvalid toml"
        self.path.write_bytes(before)
        self.assertFalse(update_config(settings__last_update_check_time="2026-09-23T12:00:00"))
        self.assertEqual(self.path.read_bytes(), before)

    def test_first_run_can_still_save_defaults(self):
        self.assertTrue(update_config(settings__last_update_check_time="2026-09-23T12:00:00"))
        self.assertEqual(read_config().settings.last_update_check_time, "2026-09-23T12:00:00")


if __name__ == "__main__":
    unittest.main()
