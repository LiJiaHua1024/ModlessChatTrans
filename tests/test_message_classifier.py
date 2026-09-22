"""消息分类（内置规则 / Jev）的纯逻辑测试。

不联网、不读写配置文件：Jev 请求通过替换 module 内的 _http 打桩。
运行：python -m unittest discover tests
"""

import unittest
from types import SimpleNamespace

import modless_chat_trans.message_classifier as classifier_module
from modless_chat_trans.config import (
    JevProvider,
    MessageClassificationConfig,
    MessageClassifierType,
)
from modless_chat_trans.message_processor import (
    MessageType,
    extract_chat_text,
    extract_speaker,
    init_blacklist,
    init_processor,
    parse_message,
    prepare,
    rule_classify,
)

# 头衔前缀是内置规则的盲区：冒号前的文字去不掉头衔，因此被判为服务器消息
TITLED_PLAYER_LINE = "OP Diamond II Steve: hello everyone"


class FakeResponse:
    def __init__(self, payload, status_code=200, text=None):
        self.payload = payload
        self.status_code = status_code
        self.text = text if text is not None else str(payload)

    def json(self):
        return self.payload


class FakeHttp:
    """替换 classifier_module._http 的打桩客户端"""

    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.error is not None:
            raise self.error
        return self.response


def jev_payload(*probabilities):
    """构造 noul 形状的 Jev 响应：每个参数是一行的玩家概率，None 表示该行缺少答案"""
    answers = {}
    for index, probability in enumerate(probabilities):
        if probability is None:
            answers[f"line_{index}"] = {"type": "noul"}
        else:
            answers[f"line_{index}"] = {"type": "noul", "noul": probability}
    return {"model": "jev-1.13.0", "answers": answers, "usage": {"input_tokens": 1, "output_tokens": 1}}


class MessageClassifierTestBase(unittest.TestCase):
    def setUp(self):
        # 默认：过滤服务器消息开启，黑名单为空，规则模式
        init_processor(SimpleNamespace(filter_server_messages=True, replace_garbled_chars=False), {})
        init_blacklist(SimpleNamespace(user_blacklist=[], message_blacklist=[]))
        classifier_module.init_classifier(None)
        # 用内存 dict 打桩 Jev 分类缓存，避免测试落盘
        self._real_get_jev_cache = classifier_module.get_jev_cache
        self.jev_cache = {}
        classifier_module.get_jev_cache = lambda: self.jev_cache

    def tearDown(self):
        classifier_module.get_jev_cache = self._real_get_jev_cache
        classifier_module.init_classifier(None)

    def install_jev(self, provider=JevProvider.TYPESAFE, api_key="test-key", **overrides):
        config = MessageClassificationConfig(
            classifier=MessageClassifierType.JEV,
            provider=provider,
            api_key=api_key,
            **overrides,
        )
        classifier_module.init_classifier(config)
        return config


class RuleClassificationTest(MessageClassifierTestBase):
    def test_rule_verdicts(self):
        cases = [
            ("<Steve> hello", True),
            ("Steve: hello", True),
            ("[MVP+] Steve: hello", True),
            ("Guild > Steve: hello", True),
            ("From Steve: hello", True),
            ("Welcome to the server", False),
            ("[Server] Restarting in 5 minutes", False),
            ("You are now in lobby 3", False),
            ("[12:34] Steve: hi", False),
        ]
        for chat_message, expected in cases:
            with self.subTest(chat_message=chat_message):
                self.assertEqual(rule_classify(chat_message), expected)

    def test_rule_cannot_handle_custom_titles(self):
        """内置规则对头衔无能为力：这正是 Jev 模式存在的理由"""
        self.assertFalse(rule_classify(TITLED_PLAYER_LINE))
        self.assertFalse(rule_classify("★ Steve: hello"))

    def test_extract_chat_text(self):
        line = "[12:00:00] [Client thread/INFO]: [CHAT] Steve: hello"
        self.assertEqual(extract_chat_text(line), "Steve: hello")
        # 含乱码且开启替换时，两段替换符会还原为 §
        garbled = "[12:00:00] [Client thread/INFO]: [CHAT] \ufffd\ufffd6Steve: hello"
        self.assertEqual(extract_chat_text(garbled, replace_garbled_character=True), "\u00a76Steve: hello")
        # 不含 [CHAT] 时返回空串，而不是抛异常
        self.assertEqual(extract_chat_text("no chat marker here"), "")

    def test_parse_message_rule_mode_keeps_previous_behavior(self):
        name, text, msg_type, core_name = parse_message(
            "[12:00:00] [Client thread/INFO]: [CHAT] [MVP+] Steve: hello", "log"
        )
        self.assertEqual(name, "[MVP+] Steve")
        self.assertEqual(text, "hello")
        self.assertEqual(msg_type, MessageType.PLAYER)
        self.assertEqual(core_name, "Steve")

        name, text, msg_type, _ = parse_message(
            "[12:00:00] [Client thread/INFO]: [CHAT] Server restarting", "log"
        )
        self.assertEqual((name, text, msg_type), ("", "Server restarting", MessageType.SYSTEM))

        # 原始 <name> 格式
        name, text, msg_type, core_name = parse_message(
            "[12:00:00] [Client thread/INFO]: [CHAT] <Alex> hi", "log"
        )
        self.assertEqual((name, text, msg_type, core_name), ("Alex", "hi", MessageType.PLAYER, "Alex"))

        # 剪贴板 / WebUI 输入不参与分类
        self.assertEqual(parse_message("hello", "clipboard"), ("", "hello", MessageType.SEND, ""))


class SpeakerExtractionTest(MessageClassifierTestBase):
    def test_extract_speaker_strips_titles_but_keeps_display_name(self):
        cases = [
            (TITLED_PLAYER_LINE, ("OP Diamond II Steve", "Steve", "hello everyone")),
            ("[MVP+] Steve: hello there", ("[MVP+] Steve", "Steve", "hello there")),
            ("Guild > [VIP] Alex: gg", ("Guild > [VIP] Alex", "Alex", "gg")),
            ("<Steve> hi", ("Steve", "Steve", "hi")),
            ("[12:34] Steve: hi", ("[12:34] Steve", "Steve", "hi")),
            ("no speaker here", ("", "", "no speaker here")),
        ]
        for chat_message, expected in cases:
            with self.subTest(chat_message=chat_message):
                self.assertEqual(extract_speaker(chat_message), expected)

    def test_whitespace_is_stripped_from_body(self):
        self.assertEqual(extract_speaker("Steve:  spaced  ")[2], "spaced")


class PrepareWithVerdictTest(MessageClassifierTestBase):
    def test_jev_verdict_overrides_rules(self):
        """Jev 判定为玩家消息时，带自定义头衔的消息不再被当成服务器消息丢弃"""
        line = f"[12:00:00] [Client thread/INFO]: [CHAT] {TITLED_PLAYER_LINE}"

        # 规则模式下：被判为服务器消息 → 过滤服务器消息开启时直接丢弃
        self.assertIsNone(prepare(line, "log"))

        prepared = prepare(line, "log", is_player=True)
        self.assertIsNotNone(prepared)
        self.assertEqual(prepared.name, "OP Diamond II Steve")
        self.assertEqual(prepared.core_name, "Steve")
        self.assertEqual(prepared.original, "hello everyone")
        self.assertEqual(prepared.message_type, MessageType.PLAYER)

    def test_jev_verdict_false_drops_message(self):
        line = "[12:00:00] [Client thread/INFO]: [CHAT] Server: restarting soon"
        # 规则模式会把它当成玩家消息（Server 恰好是合法玩家名格式）
        self.assertIsNotNone(prepare(line, "log"))
        # Jev 说是服务器消息，开启过滤后即丢弃
        self.assertIsNone(prepare(line, "log", is_player=False))

    def test_blacklist_matches_core_name(self):
        init_blacklist(SimpleNamespace(user_blacklist=["Steve"], message_blacklist=[]))
        line = f"[12:00:00] [Client thread/INFO]: [CHAT] {TITLED_PLAYER_LINE}"
        self.assertIsNone(prepare(line, "log", is_player=True))

    def test_player_message_without_extractable_name_is_kept(self):
        """Jev 判定为玩家消息但提取不出名字时，消息仍然保留（不被服务器消息过滤吃掉）"""
        line = "[12:00:00] [Client thread/INFO]: [CHAT] no speaker here"
        prepared = prepare(line, "log", is_player=True)
        self.assertIsNotNone(prepared)
        self.assertEqual(prepared.name, "")
        self.assertEqual(prepared.message_type, MessageType.PLAYER)


class JevRequestTest(MessageClassifierTestBase):
    def test_defaults_per_provider(self):
        self.install_jev(provider=JevProvider.TYPESAFE)
        self.assertEqual(classifier_module.resolve_model(), "jev-latest")
        self.assertEqual(classifier_module.resolve_endpoint(), "https://api.typesafe.ai/v1/systemone")

        self.install_jev(provider=JevProvider.OPENROUTER)
        self.assertEqual(classifier_module.resolve_model(), "typesafe/jev-latest")
        self.assertEqual(classifier_module.resolve_endpoint(), "https://openrouter.ai/api/alpha/decisions")

    def test_custom_model_and_endpoint_win(self):
        self.install_jev(model="jev-1.13.0", api_base="http://127.0.0.1:8080/systemone")
        self.assertEqual(classifier_module.resolve_model(), "jev-1.13.0")
        self.assertEqual(classifier_module.resolve_endpoint(), "http://127.0.0.1:8080/systemone")

    def test_request_body_shape(self):
        self.install_jev()
        body = classifier_module.build_request_body(["Steve: hi"], ["Alex: yo"])

        self.assertEqual(body["model"], "jev-latest")
        # 最近聊天行作为判定上下文放在 state 里，并带一句共用的材料说明
        self.assertEqual(body["state"]["recent_chat_lines"], ["Alex: yo"])
        self.assertIn("Minecraft", body["state"]["material"])
        # 每行一个 choice 问题，身份写在 criteria 的键上
        question = body["questions"]["line_0"]
        self.assertEqual(question["type"], "noul")
        self.assertEqual(set(question["criteria"]), {"true", "false"})
        self.assertEqual(question["instructions"]["line"], "Steve: hi")
        self.assertIn("`line`", question["instructions"]["question"])

    def test_format_codes_are_stripped(self):
        """发给 Jev 的文本要去掉格式化代码，前缀才不会被切碎"""
        self.install_jev()
        body = classifier_module.build_request_body(
            ["§6[MVP§c+§6] Steve§f: hi"],
            ["§eAlex§f: yo"],
        )
        self.assertEqual(body["questions"]["line_0"]["instructions"]["line"], "[MVP+] Steve: hi")
        self.assertEqual(body["state"]["recent_chat_lines"], ["Alex: yo"])

    def test_long_lines_are_truncated(self):
        long_text = "Steve: " + "a" * (classifier_module.MAX_LINE_CHARS * 2)
        body = classifier_module.build_request_body([long_text], [])
        self.assertEqual(len(body["questions"]["line_0"]["instructions"]["line"]),
                         classifier_module.MAX_LINE_CHARS)


class JevTransportTest(MessageClassifierTestBase):
    def test_answers_are_used(self):
        self.install_jev()
        classifier_module._http = lambda: FakeHttp(FakeResponse(jev_payload(0.97, 0.03)))
        verdicts = classifier_module.classify_lines(["Steve: hi", "Welcome to the server"])
        self.assertEqual(verdicts, [True, False])

    def test_low_confidence_still_uses_jev_verdict(self):
        """概率贴近阈值（0.51）时仍然采用 Jev 的判定，不因把握不大而回退规则"""
        self.install_jev()
        classifier_module._http = lambda: FakeHttp(FakeResponse(jev_payload(0.51)))
        self.assertEqual(classifier_module.classify_lines([TITLED_PLAYER_LINE]), [True])
        # 换一个判定结果前先清缓存，否则第二次会命中上一次的缓存条目
        self.jev_cache.clear()
        classifier_module._http = lambda: FakeHttp(FakeResponse(jev_payload(0.49)))
        self.assertEqual(classifier_module.classify_lines([TITLED_PLAYER_LINE]), [False])

    def test_missing_answer_falls_back_for_that_line_only(self):
        self.install_jev()
        classifier_module._http = lambda: FakeHttp(FakeResponse(jev_payload(None, 0.99)))
        verdicts = classifier_module.classify_lines([TITLED_PLAYER_LINE, "Steve: hi"])
        # 第 0 行没有答案 → 回退规则（规则判它非玩家）；第 1 行采用 Jev
        self.assertEqual(verdicts, [False, True])

    def test_request_carries_previous_lines_as_context(self):
        self.install_jev()
        http = FakeHttp(FakeResponse(jev_payload(0.99, 0.98)))
        classifier_module._http = lambda: http

        classifier_module.classify_lines(["Steve: first"])
        classifier_module.classify_lines(["Steve: second"])

        self.assertEqual(len(http.calls), 2)
        second_body = http.calls[1][1]["json"]
        self.assertEqual(second_body["state"]["recent_chat_lines"], ["Steve: first"])
        # 请求头带 Bearer 鉴权
        self.assertEqual(http.calls[1][1]["headers"]["Authorization"], "Bearer test-key")

    def test_timeout_falls_back_to_rules(self):
        self.install_jev()
        classifier_module._http = lambda: FakeHttp(error=TimeoutError("timed out"))
        verdicts = classifier_module.classify_lines([TITLED_PLAYER_LINE, "Steve: hi"])
        self.assertEqual(verdicts, [False, True])

    def test_http_error_falls_back_to_rules(self):
        self.install_jev()
        classifier_module._http = lambda: FakeHttp(
            FakeResponse({}, status_code=529, text="overloaded")
        )
        self.assertEqual(classifier_module.classify_lines(["Steve: hi"]), [True])

    def test_malformed_payload_falls_back_to_rules(self):
        self.install_jev()
        classifier_module._http = lambda: FakeHttp(FakeResponse({"answers": "nope"}))
        self.assertEqual(classifier_module.classify_lines(["Steve: hi"]), [True])

    def test_repeated_failures_pause_jev(self):
        self.install_jev()
        classifier_module._http = lambda: FakeHttp(error=TimeoutError("timed out"))

        for _ in range(classifier_module.FAILURE_THRESHOLD):
            classifier_module.classify_lines(["Steve: hi"])

        self.assertFalse(classifier_module.is_jev_enabled())
        # 暂停期间不再发起请求，直接使用规则
        calls_http = FakeHttp(FakeResponse(jev_payload(0.99)))
        classifier_module._http = lambda: calls_http
        self.assertEqual(classifier_module.classify_lines(["Steve: hi"]), [True])
        self.assertEqual(calls_http.calls, [])


class JevActivationTest(MessageClassifierTestBase):
    def test_rule_mode_is_default_and_needs_no_network(self):
        classifier_module._http = lambda: FakeHttp(error=AssertionError("不该发起网络请求"))
        self.assertEqual(classifier_module.classify_lines(["Steve: hi"]), [True])
        self.assertFalse(classifier_module.is_jev_enabled())

    def test_jev_without_api_key_falls_back_to_rules(self):
        self.install_jev(api_key="")
        self.assertFalse(classifier_module.is_jev_enabled())
        classifier_module._http = lambda: FakeHttp(error=AssertionError("不该发起网络请求"))
        self.assertEqual(classifier_module.classify_lines([TITLED_PLAYER_LINE]), [False])

    def test_jev_with_api_key_is_enabled(self):
        self.install_jev()
        self.assertTrue(classifier_module.is_jev_enabled())

    def test_none_config_keeps_rules(self):
        classifier_module.init_classifier(None)
        self.assertFalse(classifier_module.is_jev_enabled())


class ParseAnswersTest(MessageClassifierTestBase):
    def test_unknown_choice_is_treated_as_missing(self):
        payload = {"answers": {"line_0": {"type": "noul", "noul": "maybe"}}}
        parsed = classifier_module.parse_answers(payload, 1)
        self.assertIsNone(parsed[0].is_player)

    def test_absent_answers_block_returns_none(self):
        self.assertIsNone(classifier_module.parse_answers({"model": "jev-1.13.0"}, 1))
        self.assertIsNone(classifier_module.parse_answers({"answers": []}, 1))

    def test_probability_is_read(self):
        parsed = classifier_module.parse_answers(jev_payload(0.42), 1)
        self.assertEqual(parsed[0].is_player, False)
        self.assertEqual(parsed[0].probability, 0.42)


class JevCacheTest(MessageClassifierTestBase):
    """Jev 判定结果缓存：重复的固定文本直接命中，不再发起请求"""

    def test_repeated_line_hits_cache_for_both_verdicts(self):
        self.install_jev()
        http = FakeHttp(FakeResponse(jev_payload(0.97, 0.03)))
        classifier_module._http = lambda: http

        self.assertEqual(
            classifier_module.classify_lines([TITLED_PLAYER_LINE, "Welcome to the server"]),
            [True, False],
        )
        self.assertEqual(
            classifier_module.classify_lines([TITLED_PLAYER_LINE, "Welcome to the server"]),
            [True, False],
        )
        # 两批共 4 行，但只发了一次请求：第二次全部命中缓存
        self.assertEqual(len(http.calls), 1)

    def test_format_code_line_shares_cache_entry(self):
        """带色码的行与裸文本剥离后同键，共享缓存条目"""
        self.install_jev()
        http = FakeHttp(FakeResponse(jev_payload(0.99)))
        classifier_module._http = lambda: http

        self.assertEqual(classifier_module.classify_lines(["Steve: hi"]), [True])
        self.assertEqual(classifier_module.classify_lines(["§6Steve§f: hi"]), [True])
        self.assertEqual(len(http.calls), 1)

    def test_mixed_batch_only_sends_misses(self):
        self.install_jev()
        classifier_module._http = lambda: FakeHttp(FakeResponse(jev_payload(0.03)))
        classifier_module.classify_lines(["Welcome to the server"])

        http = FakeHttp(FakeResponse(jev_payload(0.97)))
        classifier_module._http = lambda: http
        verdicts = classifier_module.classify_lines([TITLED_PLAYER_LINE, "Welcome to the server"])

        # 请求体只含未命中的第一行；缓存里的第二行直接取值
        self.assertEqual(verdicts, [True, False])
        questions = http.calls[0][1]["json"]["questions"]
        self.assertEqual(list(questions), ["line_0"])
        self.assertEqual(questions["line_0"]["instructions"]["line"], TITLED_PLAYER_LINE)

    def test_duplicate_lines_in_one_batch_send_once(self):
        self.install_jev()
        http = FakeHttp(FakeResponse(jev_payload(0.97)))
        classifier_module._http = lambda: http

        verdicts = classifier_module.classify_lines([TITLED_PLAYER_LINE, TITLED_PLAYER_LINE])

        self.assertEqual(verdicts, [True, True])
        self.assertEqual(len(http.calls[0][1]["json"]["questions"]), 1)

    def test_failed_request_is_not_cached(self):
        self.install_jev()
        classifier_module._http = lambda: FakeHttp(error=TimeoutError("timed out"))
        # 回退规则得到 False，且不写缓存
        self.assertEqual(classifier_module.classify_lines([TITLED_PLAYER_LINE]), [False])
        self.assertEqual(self.jev_cache, {})

        http = FakeHttp(FakeResponse(jev_payload(0.97)))
        classifier_module._http = lambda: http
        self.assertEqual(classifier_module.classify_lines([TITLED_PLAYER_LINE]), [True])
        self.assertEqual(len(http.calls), 1)

    def test_missing_answer_is_not_cached(self):
        self.install_jev()
        classifier_module._http = lambda: FakeHttp(FakeResponse(jev_payload(None)))
        self.assertEqual(classifier_module.classify_lines([TITLED_PLAYER_LINE]), [False])
        self.assertEqual(self.jev_cache, {})

        http = FakeHttp(FakeResponse(jev_payload(0.97)))
        classifier_module._http = lambda: http
        self.assertEqual(classifier_module.classify_lines([TITLED_PLAYER_LINE]), [True])
        self.assertEqual(len(http.calls), 1)

    def test_rule_mode_never_touches_cache(self):
        def boom():
            raise AssertionError("规则模式不该访问缓存")

        classifier_module.get_jev_cache = boom
        self.assertEqual(classifier_module.classify_lines(["Steve: hi"]), [True])


if __name__ == "__main__":
    unittest.main()
