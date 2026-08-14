import base64
import hashlib
import json
import unittest
from unittest.mock import patch, MagicMock

from modless_chat_trans import free_translators
from modless_chat_trans.free_translators import (
    AlibabaService,
    BingService,
    CaiyunService,
    DeeplService,
    GoogleService,
    IflyrecService,
    SogouService,
    YandexService,
    YoudaoService,
    FreeTranslatorError,
    _aes128_cbc_decrypt,
    _pkcs7_unpad,
    _parse_js_object,
    _parse_js_list,
    _check_language,
)


def make_response(payload=None, text="", status_code=200):
    response = MagicMock()
    response.status_code = status_code
    response.text = text
    response.json.return_value = payload
    return response


class AesTests(unittest.TestCase):
    def test_cbc_decrypt_matches_known_vector(self):
        # AES-128-CBC 标准测试向量（NIST SP 800-38A）
        key = bytes.fromhex("2b7e151628aed2a6abf7158809cf4f3c")
        iv = bytes.fromhex("000102030405060708090a0b0c0d0e0f")
        ciphertext = bytes.fromhex(
            "7649abac8119b246cee98e9b12e9197d"
            "5086cb9b507219ee95db113a917678b2"
            "73bed6b8e3c1743b7116e69e22229516"
            "3ff1caa1681fac09120eca307586e1a7"
        )
        plaintext = _aes128_cbc_decrypt(ciphertext, key, iv)
        self.assertEqual(
            plaintext,
            bytes.fromhex(
                "6bc1bee22e409f96e93d7e117393172a"
                "ae2d8a571e03ac9c9eb76fac45af8e51"
                "30c81c46a35ce411e5fbc1191a0a52ef"
                "f69f2445df4f9b17ad2b417be66c3710"
            ),
        )

    def test_pkcs7_unpad(self):
        self.assertEqual(_pkcs7_unpad(b"hello\x0b" * 0 + b"hello" + b"\x0b" * 11), b"hello")
        self.assertEqual(_pkcs7_unpad(b"data" + b"\x0c" * 12), b"data")
        self.assertEqual(_pkcs7_unpad(b"x" + b"\x0f" * 15), b"x")
        with self.assertRaises(ValueError):
            _pkcs7_unpad(b"badpadding!!")
        with self.assertRaises(ValueError):
            _pkcs7_unpad(b"")

    def test_youdao_style_decrypt_rejects_invalid_input(self):
        key, iv = "test-key", "test-iv"
        with self.assertRaises(Exception):
            YoudaoService._decrypt_result("invalid-base64!!!", key, iv)


class JsParseTests(unittest.TestCase):
    def test_parse_js_object(self):
        text = "var params_AbusePreventionHelper = [123, 'abc']; var x = {a: 1, b: 'c'};"
        result = _parse_js_list(text, "params_AbusePreventionHelper")
        self.assertEqual(result, [123, "abc"])

    def test_parse_js_object_quoted_keys(self):
        text = 'window.WIZ = {"cfb2h": "x", "FdrFJe": "y"};'
        result = _parse_js_object(text, "WIZ")
        self.assertEqual(result, {"cfb2h": "x", "FdrFJe": "y"})

    def test_parse_js_object_missing(self):
        with self.assertRaises(FreeTranslatorError):
            _parse_js_object("var other = {};", "missing")


class CheckLanguageTests(unittest.TestCase):
    def setUp(self):
        self.lang_map = {
            "en": ["zh", "ja"],
            "zh": ["en", "ja"],
            "ja": ["en", "zh"],
        }

    def test_auto_source(self):
        from_lang, to_lang = _check_language("auto", "en", self.lang_map, "zh")
        self.assertEqual((from_lang, to_lang), ("auto", "en"))

    def test_zh_alias_normalization(self):
        from_lang, to_lang = _check_language("zh-CN", "en", self.lang_map, "zh")
        self.assertEqual(from_lang, "zh")

    def test_unsupported_language(self):
        with self.assertRaises(FreeTranslatorError):
            _check_language("fr", "en", self.lang_map, "zh")

    def test_same_languages(self):
        with self.assertRaises(FreeTranslatorError):
            _check_language("en", "en", self.lang_map, "zh")


class YandexServiceTests(unittest.TestCase):
    def test_translate_plain(self):
        service = YandexService()
        service.language_map = {"en": ["zh"], "zh": ["en"]}
        fake_response = make_response(payload={"text": ["translated"]})
        mock_session = MagicMock()
        mock_session.post.return_value = fake_response
        service.session = mock_session

        result = service.translate("hello", "en", "zh")
        self.assertEqual(result, "translated")

    def test_detect_language_flow(self):
        service = YandexService()
        service.language_map = {"en": ["zh"], "zh": ["en"]}
        detect_response = make_response(payload={"lang": "en"})
        translate_response = make_response(payload={"text": ["ok"]})
        mock_session = MagicMock()
        mock_session.post.side_effect = [detect_response, translate_response]
        service.session = mock_session

        result = service.translate("hello", "auto", "zh")
        self.assertEqual(result, "ok")


class IflyrecServiceTests(unittest.TestCase):
    def test_translate(self):
        service = IflyrecService()
        service.language_map = {
            "zh": list(IflyrecService.lang_index.keys()),
            "en": ["zh"],
        }
        fake_response = make_response(payload={"biz": [{"translateResult": "你好"}]})
        mock_session = MagicMock()
        mock_session.post.return_value = fake_response
        service.session = mock_session

        result = service.translate("hello", "en", "zh")
        self.assertEqual(result, "你好")

    def test_auto_detect(self):
        service = IflyrecService()
        service.language_map = {
            "zh": list(IflyrecService.lang_index.keys()),
            "en": ["zh"],
        }
        detect_response = make_response(payload={"biz": [{"detectionLanguage": 2}]})
        translate_response = make_response(payload={"biz": [{"translateResult": "ok"}]})
        mock_session = MagicMock()
        mock_session.post.side_effect = [detect_response, translate_response]
        service.session = mock_session

        result = service.translate("hello", "auto", "zh")
        self.assertEqual(result, "ok")


class CaiyunServiceTests(unittest.TestCase):
    def test_decrypt(self):
        normal_key = CaiyunService.normal_key
        cipher_key = CaiyunService.cipher_key
        encrypt_map = {plain: cipher for plain, cipher in zip(normal_key, cipher_key)}
        plaintext = "你好"
        encoded = base64.b64encode(plaintext.encode()).decode()
        cipher_text = "".join(encrypt_map[ch] for ch in encoded)
        self.assertEqual(CaiyunService._decrypt(cipher_text), plaintext)

    def test_translate(self):
        service = CaiyunService()
        service.language_map = {"zh": ["en"], "en": ["zh"]}
        service.jwt = "fake-jwt"
        plaintext = "你好"
        encrypt_map = {
            plain: cipher
            for plain, cipher in zip(CaiyunService.normal_key, CaiyunService.cipher_key)
        }
        encoded = base64.b64encode(plaintext.encode()).decode()
        cipher_text = "".join(encrypt_map[ch] for ch in encoded)
        fake_response = make_response(payload={"target": [cipher_text]})
        mock_session = MagicMock()
        mock_session.post.return_value = fake_response
        service.session = mock_session

        result = service.translate("hello", "en", "zh")
        self.assertEqual(result, "你好")


class AlibabaServiceTests(unittest.TestCase):
    def test_translate(self):
        service = AlibabaService()
        service.language_map = {"zh": ["en"], "en": ["zh"]}
        csrf_response = make_response(payload={"token": "csrf123", "headerName": "X-CSRF-TOKEN"})
        translate_response = make_response(payload={"data": {"translateText": "你好"}})
        mock_session = MagicMock()
        mock_session.get.return_value = csrf_response
        mock_session.post.return_value = translate_response
        service.session = mock_session

        result = service.translate("hello", "en", "zh")
        self.assertEqual(result, "你好")


class BingServiceTests(unittest.TestCase):
    def test_translate(self):
        service = BingService()
        service.language_map = {"en": ["zh-Hans"], "zh-Hans": ["en"]}
        host_html = (
            '<html><select id="tta_srcsl"><option value="en"></option>'
            '<option value="zh-Hans"></option></select>'
            '<div id="tta_outGDCont" data-iid="translator.5028"></div>'
            '<script>var params_AbusePreventionHelper = [12345, "token-abc"]; IG:"IG1";</script></html>'
        )
        host_response = make_response(text=host_html)
        translate_response = make_response(
            payload=[{"translations": [{"text": "你好"}]}]
        )
        mock_session = MagicMock()
        mock_session.get.return_value = host_response
        mock_session.post.return_value = translate_response
        service.session = mock_session

        result = service.translate("hello", "en", "zh-Hans")
        self.assertEqual(result, "你好")

    def test_language_map_from_html(self):
        service = BingService()
        host_html = (
            '<select id="tta_srcsl"><option value="en"></option>'
            '<option value="zh-Hans"></option><option value="auto-detect"></option></select>'
        )
        mock_session = MagicMock()
        mock_session.get.return_value = make_response(text=host_html)
        service.session = mock_session

        service._init_language_map(timeout=None)
        self.assertIn("en", service.language_map)
        self.assertIn("zh-Hans", service.language_map)


class SogouServiceTests(unittest.TestCase):
    def test_translate(self):
        service = SogouService()
        service.language_map = {"en": ["zh-CHS"], "zh-CHS": ["en"]}
        service.uuid = "test-uuid"
        fake_response = make_response(
            payload={"data": {"translate": {"dit": "你好"}}}
        )
        mock_session = MagicMock()
        mock_session.post.return_value = fake_response
        service.session = mock_session

        result = service.translate("hello", "en", "zh-CHS")
        self.assertEqual(result, "你好")
        sent_payload = mock_session.post.call_args[1]["data"]
        expected_sign = hashlib.md5(
            f"enzh-CHShello{service.secret_code}".encode()
        ).hexdigest()
        self.assertEqual(sent_payload["s"], expected_sign)


class YoudaoServiceTests(unittest.TestCase):
    def test_decrypt_result_requires_16_byte_aligned_input(self):
        # 非 16 字节对齐的密文应报错（AES-CBC 分组约束）
        key, iv = "k", "i"
        bad = base64.urlsafe_b64encode(b"0123456789abc").decode()
        with self.assertRaises(Exception):
            YoudaoService._decrypt_result(bad, key, iv)

    def test_sign(self):
        sign = YoudaoService._get_sign("secret-key", 1234567890)
        expected = hashlib.md5(
            "client=fanyideskweb&mysticTime=1234567890&product=webfanyi&key=secret-key".encode()
        ).hexdigest()
        self.assertEqual(sign, expected)


class DeeplServiceTests(unittest.TestCase):
    def test_split_payload_shape(self):
        service = DeeplService()
        service.request_id = 1000004
        payload = service._split_sentences_param("hello\nworld", "en")
        self.assertEqual(payload["method"], "LMT_split_text")
        self.assertEqual(payload["params"]["texts"], ["hello", "world"])
        self.assertEqual(payload["params"]["lang"]["lang_user_selected"], "en")
        self.assertIn("lang_computed", payload["params"]["lang"])

    def test_context_payload_shape(self):
        service = DeeplService()
        service.request_id = 1000004
        payload = service._context_sentences_param(["hello", "world"], "EN", "ZH")
        self.assertEqual(payload["method"], "LMT_handle_jobs")
        self.assertEqual(payload["params"]["lang"]["target_lang"], "ZH")
        self.assertEqual(len(payload["params"]["jobs"]), 2)


class GoogleServiceTests(unittest.TestCase):
    def test_wiz_global_data_parse(self):
        service = GoogleService()
        html = '<script>window.WIZ_global_data = {"cfb2h": "BL123", "FdrFJe": "SID456"};</script>'
        info = service._get_info(html)
        self.assertEqual(info, {"bl": "BL123", "f.sid": "SID456"})

    def test_wiz_unquoted_keys(self):
        service = GoogleService()
        html = "<script>window.WIZ_global_data = {cfb2h: 'BL123', FdrFJe: 'SID456'};</script>"
        info = service._get_info(html)
        self.assertEqual(info, {"bl": "BL123", "f.sid": "SID456"})

    def test_rpc_shape(self):
        service = GoogleService()
        rpc = service._get_rpc("hello", "en", "zh-CN")
        self.assertIn("f.req", rpc)
        decoded = json.loads(json.loads(rpc["f.req"])[0][0][1])
        self.assertEqual(decoded[0], ["hello", "en", "zh-CN", True])

    def test_translate(self):
        service = GoogleService()
        service.language_map = {"en": ["zh-CN"], "zh-CN": ["en"]}
        host_html = (
            '<html><div data-language-code="en"></div>'
            '<div data-language-code="zh-CN"></div>'
            '<script>window.WIZ_global_data = {"cfb2h": "BL", "FdrFJe": "SID"};</script></html>'
        )
        host_response = make_response(text=host_html)
        inner = json.dumps(
            [None, [[[None, None, None, None, True, [["ok", None]]]]], None, "generic"]
        )
        translate_response = make_response(
            text=")]}'" + json.dumps([["wrb.fr", None, inner]])
        )
        mock_session = MagicMock()
        mock_session.get.return_value = host_response
        mock_session.post.return_value = translate_response
        service.session = mock_session

        result = service.translate("hello", "en", "zh-CN")
        self.assertIsNotNone(result)


class DispatchTests(unittest.TestCase):
    def test_unknown_service(self):
        with self.assertRaises(FreeTranslatorError):
            free_translators.translate_text("hi", translator="baidu")

    def test_service_cache(self):
        first = free_translators._get_service("yandex")
        second = free_translators._get_service("yandex")
        self.assertIs(first, second)


if __name__ == "__main__":
    unittest.main()
