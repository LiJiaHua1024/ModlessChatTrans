import base64
import hashlib
import hmac
import json
import unittest
from types import SimpleNamespace
from urllib.parse import quote

import modless_chat_trans.translator as translator_module
from modless_chat_trans.translator import Translator


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload, ensure_ascii=False)

    def json(self):
        return self.payload


class FakeHttp:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append(("post", url, kwargs))
        return self.response

    def get(self, url, **kwargs):
        self.calls.append(("get", url, kwargs))
        return self.response


def make_translator(api_key="key", folder_id="folder", region=None):
    config = SimpleNamespace(
        traditional=SimpleNamespace(
            api_key=api_key,
            folder_id=folder_id,
            region=region,
        )
    )
    translator = Translator.__new__(Translator)
    translator.translation_service_config = config
    translator.timeout = 10.0
    return translator


class TraditionalRequestTests(unittest.TestCase):
    def setUp(self):
        self.original_http = translator_module._http

    def tearDown(self):
        translator_module._http = self.original_http

    def install_http(self, payload):
        fake_http = FakeHttp(FakeResponse(payload))
        translator_module._http = lambda: fake_http
        return fake_http

    def test_google_uses_plain_text_and_omits_auto_source(self):
        http = self.install_http({"data": {"translations": [{"translatedText": "ok"}]}})

        result = make_translator()._translate_google("<tag>", "google-key", "auto", "zh-TW")

        self.assertEqual(result, "ok")
        params = http.calls[0][2]["params"]
        self.assertEqual(params["target"], "zh-TW")
        self.assertEqual(params["format"], "text")
        self.assertNotIn("source", params)

    def test_deepl_preserves_language_variant(self):
        http = self.install_http({"translations": [{"text": "ok"}]})

        make_translator()._translate_deepl("hello", "deepl-key", "auto", "en-US")

        data = http.calls[0][2]["data"]
        self.assertEqual(data["target_lang"], "EN-US")
        self.assertNotIn("source_lang", data)

    def test_yandex_includes_folder_and_omits_auto_source(self):
        http = self.install_http({"translations": [{"text": "ok"}]})

        make_translator(folder_id="b1-folder")._translate_yandex(
            "hello", "yandex-key", "auto", "en"
        )

        body = http.calls[0][2]["json"]
        self.assertEqual(body["folderId"], "b1-folder")
        self.assertNotIn("sourceLanguageCode", body)

    def test_alibaba_request_contains_required_fields_and_valid_signature(self):
        http = self.install_http({"Code": 200, "Data": {"Translated": "ok"}})

        make_translator()._translate_alibaba("hello world", "access:secret", "en", "zh-tw")

        parameters = http.calls[0][2]["params"]
        self.assertEqual(parameters["FormatType"], "text")
        self.assertEqual(parameters["Scene"], "general")
        unsigned = [(key, value) for key, value in parameters.items() if key != "Signature"]
        canonical = "&".join(
            f"{quote(str(key), safe='-_.~')}={quote(str(value), safe='-_.~')}"
            for key, value in sorted(unsigned)
        )
        string_to_sign = "GET&%2F&" + quote(canonical, safe="-_.~")
        expected = base64.b64encode(
            hmac.new(b"secret&", string_to_sign.encode(), hashlib.sha1).digest()
        ).decode()
        self.assertEqual(parameters["Signature"], expected)

    def test_caiyun_uses_https_and_enables_detection(self):
        http = self.install_http({"target": ["ok"]})

        make_translator()._translate_caiyun("hello", "caiyun-key", "auto", "zh-Hant")

        method, url, kwargs = http.calls[0]
        self.assertEqual(method, "post")
        self.assertTrue(url.startswith("https://"))
        self.assertEqual(kwargs["json"]["trans_type"], "auto2zh-Hant")
        self.assertTrue(kwargs["json"]["detect"])

    def test_youdao_preserves_variant_language(self):
        http = self.install_http({"errorCode": "0", "translation": ["ok"]})

        make_translator()._translate_youdao("hello", "app:secret", "en", "zh-CHT")

        data = http.calls[0][2]["data"]
        self.assertEqual(data["to"], "zh-CHT")
        self.assertEqual(data["from"], "en")

    def test_bing_uses_configured_region_and_preserves_variant(self):
        http = self.install_http([{"translations": [{"text": "ok"}]}])

        make_translator(region="eastus")._translate_bing(
            "hello", "bing-key", "auto", "zh-Hans"
        )

        _, _, kwargs = http.calls[0]
        self.assertEqual(kwargs["params"]["to"], "zh-Hans")
        self.assertNotIn("from", kwargs["params"])
        self.assertEqual(kwargs["headers"]["Ocp-Apim-Subscription-Region"], "eastus")

    def test_sogou_paid_request_is_signed(self):
        http = self.install_http({"errorCode": 0, "translation": "ok"})

        make_translator()._translate_sogou("hello", "pid:secret", "en", "zh-CHS")

        _, url, kwargs = http.calls[0]
        self.assertTrue(url.startswith("https://"))
        data = kwargs["data"]
        expected = hashlib.md5(
            f"pidhello{data['salt']}secret".encode("utf-8")
        ).hexdigest()
        self.assertEqual(data["sign"], expected)
        self.assertEqual(data["to"], "zh-CHS")

    def test_iflyrec_paid_request_is_signed_and_decoded(self):
        encoded_result = base64.b64encode(
            json.dumps({"trans_result": {"dst": "ok"}}).encode("utf-8")
        ).decode("ascii")
        http = self.install_http({
            "header": {"code": 0},
            "payload": {"result": {"text": encoded_result}},
        })

        result = make_translator()._translate_iflyrec(
            "hello", "app:api:secret", "zh", "en"
        )

        self.assertEqual(result, "ok")
        _, url, kwargs = http.calls[0]
        self.assertEqual(url, "https://itrans.xf-yun.com/v1/its")
        self.assertEqual(kwargs["json"]["header"]["app_id"], "app")
        self.assertEqual(kwargs["json"]["parameter"]["its"]["from"], "cn")
        self.assertEqual(kwargs["json"]["parameter"]["its"]["to"], "en")
        self.assertEqual(kwargs["params"]["host"], "itrans.xf-yun.com")
        authorization = base64.b64decode(kwargs["params"]["authorization"]).decode("utf-8")
        self.assertIn('api_key="api"', authorization)
        self.assertIn('headers="host date request-line"', authorization)
        signature_origin = (
            f"host: itrans.xf-yun.com\n"
            f"date: {kwargs['params']['date']}\n"
            "POST /v1/its HTTP/1.1"
        )
        expected_signature = base64.b64encode(
            hmac.new(b"secret", signature_origin.encode("utf-8"), hashlib.sha256).digest()
        ).decode("ascii")
        self.assertIn(f'signature="{expected_signature}"', authorization)

    def test_yandex_requires_folder_id(self):
        with self.assertRaisesRegex(ValueError, "folder ID"):
            make_translator(folder_id=None)._translate_yandex("hello", "key", "en", "zh")

    def test_paid_dispatch_includes_sogou_and_iflyrec(self):
        translator = make_translator(api_key="pid:secret")
        translator._translate_sogou = lambda *args: "sogou-ok"
        self.assertEqual(
            translator._execute_traditional_translation("hello", "Sogou", "en", "zh-CHS"),
            "sogou-ok",
        )

        translator = make_translator(api_key="app:api:secret")
        translator._translate_iflyrec = lambda *args: "iflyrec-ok"
        self.assertEqual(
            translator._execute_traditional_translation("hello", "Iflyrec", "en", "zh"),
            "iflyrec-ok",
        )

    def test_language_loading_falls_back_when_web_service_is_rate_limited(self):
        original_get_languages = translator_module.ts.get_languages
        translator_module.ts.get_languages = lambda service: (_ for _ in ()).throw(
            RuntimeError("429")
        )
        self.addCleanup(setattr, translator_module.ts, "get_languages", original_get_languages)

        languages = translator_module.get_supported_languages("deepl")

        self.assertIn("en-US", languages)
        self.assertIn("zh-Hant", languages)


if __name__ == "__main__":
    unittest.main()
