"""The assertion-verification stage and the configuration surface.

Two things are worth guarding here. First, the strong form of verification
rebuilds the answer from the assertions the evidence supports; it must never
reintroduce text it decided to drop, and it must drop an assertion that claims to
be supported but names no evidence. Second, the runner's configuration table and
the systems actually implemented must stay in step, so a configuration can never
be silently missing from a comparison.
"""
import unittest

from app.backend import systems
from scripts.run_baselines import CONFIGS, MODES, USES_SKELETON

EVIDENCE = [
    {"evidence_id": "UGP001", "normalized_claim": "成绩单可在自助打印系统打印",
     "verbatim_text": "成绩单可在自助打印系统打印。"},
    {"evidence_id": "UGP002", "normalized_claim": "打印需使用校园卡",
     "verbatim_text": "打印需使用校园卡。"},
]


class StubClient:
    """Returns queued replies in call order; records the prompts it received."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def chat_json(self, messages, **kwargs):
        self.calls.append(messages)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    def chat(self, messages, **kwargs):  # pragma: no cover - never expected
        raise AssertionError("chat() should not be called on this path")


class AnswerReadingTests(unittest.TestCase):
    """A reply that files the answer under key_points is still an answer.

    Models occasionally fill `key_points` with the answer prose and omit the
    `answer` key. The reply is complete and valid, so reading only `answer` would
    turn a formatting slip into a missing answer and depress the score.
    """

    def test_answer_key_wins_when_present(self):
        data = {"answer": "成绩单可在自助打印系统打印。",
                "key_points": [{"text": "另一段要点"}]}
        self.assertEqual("成绩单可在自助打印系统打印。", systems.answer_of(data))

    def test_key_points_are_used_when_the_answer_key_is_missing(self):
        data = {"key_points": [{"text": "先登录自助打印系统"},
                               {"text": "再选择需要打印的证明。"}]}
        self.assertEqual("先登录自助打印系统。再选择需要打印的证明。",
                         systems.answer_of(data))

    def test_key_points_are_used_when_the_answer_key_is_blank(self):
        data = {"answer": "   ", "key_points": [{"text": "需先完成注册"}]}
        self.assertEqual("需先完成注册。", systems.answer_of(data))

    def test_plain_string_key_points_are_accepted(self):
        data = {"key_points": ["要点一", "要点二"]}
        self.assertEqual("要点一。要点二。", systems.answer_of(data))

    def test_missing_evidence_returns_empty(self):
        self.assertEqual("", systems.answer_of({}))
        self.assertEqual("", systems.answer_of({"key_points": []}))
        self.assertEqual("", systems.answer_of({"key_points": None}))

    def test_method_returns_the_key_points_instead_of_nothing(self):
        client = StubClient([
            {"response_mode": "answer", "missing_conditions": [], "follow_up_question": None,
             "key_points": [{"text": "成绩单可在自助打印系统打印", "evidence_ids": ["UGP001"]}]},
        ])
        prediction = systems.ablation_no_verify(client, "怎么打印成绩单", EVIDENCE, {})
        self.assertEqual("成绩单可在自助打印系统打印。", prediction.answer_text)


class RebuildFromClaimsTests(unittest.TestCase):
    def test_only_supported_claims_survive_and_keep_their_order(self):
        claims = [
            {"text": "成绩单可在自助打印系统打印。", "verdict": "supported",
             "evidence_ids": ["UGP001"]},
            {"text": "补办需要缴纳工本费。", "verdict": "unsupported", "evidence_ids": []},
            {"text": "打印需使用校园卡。", "verdict": "supported",
             "evidence_ids": ["UGP002"]},
        ]
        rebuilt = systems._rebuild_from_claims(claims, {"UGP001", "UGP002"})
        self.assertEqual("成绩单可在自助打印系统打印。[UGP001]\n打印需使用校园卡。[UGP002]",
                         rebuilt)
        self.assertNotIn("工本费", rebuilt)

    def test_supported_claim_without_evidence_id_is_dropped(self):
        claims = [{"text": "成绩单可当场领取。", "verdict": "supported", "evidence_ids": []}]
        self.assertEqual("", systems._rebuild_from_claims(claims, {"UGP001"}))

    def test_evidence_ids_outside_this_run_are_not_cited(self):
        claims = [{"text": "成绩单可当场领取。", "verdict": "supported",
                   "evidence_ids": ["UGP999"]}]
        self.assertEqual("", systems._rebuild_from_claims(claims, {"UGP001"}))

    def test_partial_verdicts_are_not_kept(self):
        claims = [{"text": "成绩单可当场领取。", "verdict": "partial",
                   "evidence_ids": ["UGP001"]}]
        self.assertEqual("", systems._rebuild_from_claims(claims, {"UGP001"}))


class VerifyClaimsTests(unittest.TestCase):
    def test_rebuild_is_deterministic_and_drops_unsupported_text(self):
        draft = "成绩单可在自助打印系统打印。补办需要缴纳工本费。"
        client = StubClient([{"claims": [
            {"text": "成绩单可在自助打印系统打印。", "verdict": "supported",
             "evidence_ids": ["UGP001"]},
            {"text": "补办需要缴纳工本费。", "verdict": "unsupported", "evidence_ids": []},
        ]}])
        final = systems.verify_claims(client, EVIDENCE, draft)
        self.assertEqual("成绩单可在自助打印系统打印。[UGP001]", final)

    def test_unparsable_reply_falls_back_to_the_draft(self):
        client = StubClient([ValueError("no JSON in reply")])
        draft = "成绩单可在自助打印系统打印。"
        self.assertEqual(draft, systems.verify_claims(client, EVIDENCE, draft))

    def test_empty_claim_list_falls_back_to_the_draft(self):
        client = StubClient([{"claims": []}])
        draft = "成绩单可在自助打印系统打印。"
        self.assertEqual(draft, systems.verify_claims(client, EVIDENCE, draft))

    def test_nothing_surviving_says_so_instead_of_returning_nothing(self):
        """An empty answer is indistinguishable from a failed call, so a check
        that legitimately keeps nothing must say so explicitly."""
        client = StubClient([{"claims": [
            {"text": "补办需要缴纳工本费。", "verdict": "unsupported", "evidence_ids": []},
        ]}])
        result = systems.verify_claims(client, EVIDENCE, "补办需要缴纳工本费。")
        self.assertEqual(systems.NO_SUPPORTED_CLAIM_NOTE, result)
        self.assertTrue(result.strip())


class VerificationLadderTests(unittest.TestCase):
    """Only the verification stage varies between these three configurations."""

    MODE_DECISION = {"response_mode": "answer", "missing_conditions": [],
                     "follow_up_question": None}
    DRAFT = {"key_points": [], "answer": "成绩单可在自助打印系统打印。补办需要缴纳工本费。"}
    CLAIM_VERDICTS = {"claims": [
        {"text": "成绩单可在自助打印系统打印。", "verdict": "supported",
         "evidence_ids": ["UGP001"]},
        {"text": "补办需要缴纳工本费。", "verdict": "unsupported", "evidence_ids": []},
    ]}

    def test_no_verification_returns_the_draft_verbatim(self):
        client = StubClient([dict(self.MODE_DECISION), dict(self.DRAFT)])
        prediction = systems.ablation_v2_no_verify(client, "怎么打印成绩单", EVIDENCE, {})
        self.assertEqual(2, len(client.calls))
        self.assertIn("工本费", prediction.answer_text)

    def test_weak_verification_uses_the_models_rewrite(self):
        client = StubClient([dict(self.MODE_DECISION), dict(self.DRAFT),
                             {"final_answer": "成绩单可在自助打印系统打印。[UGP001]"}])
        prediction = systems.method_v2(client, "怎么打印成绩单", EVIDENCE, {})
        self.assertEqual(3, len(client.calls))
        self.assertNotIn("工本费", prediction.answer_text)

    def test_strong_verification_drops_the_unsupported_assertion(self):
        client = StubClient([dict(self.MODE_DECISION), dict(self.DRAFT),
                             dict(self.CLAIM_VERDICTS)])
        prediction = systems.method_v3(client, "怎么打印成绩单", EVIDENCE, {})
        self.assertEqual(3, len(client.calls))
        self.assertEqual("成绩单可在自助打印系统打印。[UGP001]", prediction.answer_text)


class ConfigurationSurfaceTests(unittest.TestCase):
    def test_every_registered_configuration_is_runnable(self):
        self.assertEqual(set(MODES), set(CONFIGS))
        self.assertEqual(set(MODES), set(systems.SYSTEMS))

    def test_skeleton_usage_matches_the_runner(self):
        for name, function in systems.SYSTEMS.items():
            takes_skeleton = function.__code__.co_argcount == 4
            self.assertEqual(takes_skeleton, name in USES_SKELETON,
                             f"{name}: runner and implementation disagree on the skeleton")


class ModeGuideTests(unittest.TestCase):
    """The guide is now composed from parts; its default rendering is a contract.

    Any drift here silently changes every prompt that embeds it, which would put a
    configuration's before-and-after results on different prompts.
    """

    FROZEN = """先判定响应方式，再作答（response_mode 必填）：
- answer：条件完整，且提问的前提与证据的适用范围一致。
- scoped_correction：提问中的对象、步骤或材料前提与证据的适用范围不符（例如把研究生当成本科生、
  按已不适用的步骤办理、把两种材料各自的适用条件混在一起），必须先明确指出哪一部分不适用，
  再给出适用于正确对象或条件的回答。
- clarification：问题缺少会改变答案的关键条件（对象、学历层次、学籍状态、时间等），必须先问清楚。
- version_qualified：证据中同一事项存在不同版本且互相矛盾，或问题涉及未经正式文件确认的新版本；
  此时说明依据的是哪个来源版本，并明确未获证据确认的部分不能当事实。
- conversation_resolution：多轮对话，需先合并前一轮遗留的条件或指代，再作答。
- abstention：证据中没有任何内容能回答该问题。
不要为了回避而滥用 clarification 或 abstention；也不要把前提不符当成 answer 直接作答。"""

    def test_default_rendering_is_unchanged(self):
        guide, options = systems.build_mode_guide()
        self.assertEqual(self.FROZEN, guide)
        self.assertEqual(
            "answer | scoped_correction | clarification | version_qualified | "
            "conversation_resolution | abstention", options)

    def test_version_limit_ablation_withholds_only_that_mode(self):
        guide, options = systems.build_mode_guide(drop=("version_qualified",))
        self.assertNotIn("version_qualified", guide)
        self.assertNotIn("version_qualified", options)
        for mode in ("answer", "scoped_correction", "clarification",
                     "conversation_resolution", "abstention"):
            self.assertIn(f"- {mode}：", guide)
            self.assertIn(mode, options)

    def test_dropping_clarification_and_abstention_rewrites_the_closing_line(self):
        guide, options = systems.build_mode_guide(drop=("clarification", "abstention"))
        self.assertNotIn("clarification：", guide)
        self.assertNotIn("abstention：", guide)
        self.assertEqual("不要把前提不符当成 answer 直接作答。", guide.splitlines()[-1])
        self.assertEqual("answer | scoped_correction | version_qualified | "
                         "conversation_resolution", options)


if __name__ == "__main__":
    unittest.main()
