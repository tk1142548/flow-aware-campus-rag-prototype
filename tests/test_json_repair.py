"""Recovering a JSON reply that a stray aside pushed out of syntax.

A model reply that is valid JSON except for text sitting between a string literal
and its enclosing bracket is still an answer, and the score should reflect what it
says. These tests pin the repair to that case and make sure it never rewrites the
content of a string.
"""
import json
import unittest

from app.backend.api_client import extract_json, strip_text_outside_strings


class StripOutsideStringsTests(unittest.TestCase):
    def test_the_aside_after_a_string_is_removed(self):
        broken = '{"dropped": ["所需材料", "办理入口"（因证据中没有相关内容）]}'
        self.assertEqual('{"dropped": ["所需材料", "办理入口"]}',
                         strip_text_outside_strings(broken))

    def test_string_contents_are_never_touched(self):
        payload = {"answer": "成绩单是 20 元/份，附中文说明（含印章）。", "n": 3}
        text = json.dumps(payload, ensure_ascii=False)
        self.assertEqual(text, strip_text_outside_strings(text))

    def test_valid_json_is_left_alone(self):
        text = '{"a": 1, "b": [true, null, 1.5e3], "c": {"d": "e"}}'
        self.assertEqual(text, strip_text_outside_strings(text))
        self.assertEqual(json.loads(text), strip_text_outside_strings(text) and json.loads(text))

    def test_structure_survives(self):
        broken = '["a"（注）,"b"]'
        self.assertEqual(["a", "b"], json.loads(strip_text_outside_strings(broken)))


class ExtractJsonRepairTests(unittest.TestCase):
    def test_valid_json_is_returned_as_is(self):
        self.assertEqual({"a": 1}, extract_json('{"a": 1}'))

    def test_the_stray_aside_is_repaired(self):
        broken = '{"dropped": ["所需材料", "办理入口"（因证据中没有相关内容）], "answer": "缺四个环节。"}'
        repaired = extract_json(broken)
        self.assertEqual("缺四个环节。", repaired["answer"])
        self.assertEqual(["所需材料", "办理入口"], repaired["dropped"])

    def test_a_reply_without_any_json_still_raises(self):
        with self.assertRaises(ValueError):
            extract_json("不好意思，我无法回答这个问题。")


if __name__ == "__main__":
    unittest.main()


class TruncatedReplyTests(unittest.TestCase):
    """A reply cut off before its closing bracket still holds an answer."""

    TRUNCATED = ('{\n  "response_mode": "scoped_correction",\n'
                 '  "answer": "不能办理。不满足办理对象的前提条件 [UGC001]。"')

    def test_candidate_stops_at_the_real_end(self):
        from app.backend.api_client import _json_candidate
        self.assertEqual(self.TRUNCATED, _json_candidate(self.TRUNCATED))

    def test_truncated_reply_is_repaired(self):
        value, repaired = None, None
        from app.backend.api_client import parse_json_reply
        value, repaired = parse_json_reply(self.TRUNCATED)
        self.assertTrue(repaired)
        self.assertEqual("不能办理。不满足办理对象的前提条件 [UGC001]。", value["answer"])
        self.assertEqual("scoped_correction", value["response_mode"])

    def test_a_bracket_inside_a_string_does_not_end_the_slice(self):
        text = '{"answer": "见[UGC001]"}'
        from app.backend.api_client import extract_json
        self.assertEqual({"answer": "见[UGC001]"}, extract_json(text))

    def test_trailing_prose_after_the_object_is_ignored(self):
        text = '{"a": 1}\n以上是回答，参考【证据】中的说明。'
        from app.backend.api_client import extract_json
        self.assertEqual({"a": 1}, extract_json(text))

    def test_unparsable_reply_still_raises(self):
        from app.backend.api_client import extract_json
        with self.assertRaises(ValueError):
            extract_json("不好意思，我无法回答这个问题。")
