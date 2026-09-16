#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_lore_script import TRADITIONAL_CHINESE_PROFILE, SYNTAX_DIMENSIONS, audit, sha256_file


class LoreAuditTest(unittest.TestCase):
    def write_script(self, text: str) -> Path:
        directory = Path(tempfile.mkdtemp())
        path = directory / "口播纯文本.md"
        path.write_text(text, encoding="utf-8")
        return path

    def audit_legacy(self, path: Path, **kwargs: object) -> dict:
        return audit(path, path, syntax_profile="legacy", **kwargs)

    def write_review(self, path: Path, *, full_speed_1x_read: bool = True) -> Path:
        diagnostic = audit(path, path, syntax_profile="legacy")
        diagnostic_path = path.parent / "script_diagnostic.json"
        diagnostic_path.write_text(json.dumps(diagnostic, ensure_ascii=False), encoding="utf-8")
        risks = diagnostic["traditional_chinese"]["risk_items"]
        paragraph_count = diagnostic["traditional_chinese"]["paragraph_count"]
        review = {
            "profile": TRADITIONAL_CHINESE_PROFILE,
            "status": "pass",
            "script_path": str(path),
            "script_sha256": sha256_file(path),
            "diagnostic_path": str(diagnostic_path),
            "diagnostic_sha256": sha256_file(diagnostic_path),
            "full_sentence_reviewed": True,
            "full_referent_register_reviewed": True,
            "full_paragraph_transition_reviewed": True,
            "full_speed_1x_read": full_speed_1x_read,
            "sentence_count": diagnostic["traditional_chinese"]["sentence_count"],
            "paragraph_count": paragraph_count,
            "dimensions": {name: "pass" for name in SYNTAX_DIMENSIONS},
            "risk_resolutions": [
                {
                    "risk_id": row["risk_id"],
                    "disposition": "accepted_with_reason",
                    "reason": "人工逐句复核后确认自然",
                    "final_excerpt": row["text"],
                }
                for row in risks
            ],
            "transition_review": {
                "status": "pass",
                "expected_transition_count": max(paragraph_count - 1, 0),
                "reviewed_transition_count": max(paragraph_count - 1, 0),
                "dangling_transition_count": 0,
                "ambiguous_subject_handoff_count": 0,
            },
            "open_issue_count": 0,
            "reviewer": "tester",
            "reviewed_at": "2026-08-30T00:00:00Z",
        }
        review_path = path.parent / "traditional_chinese_review.json"
        review_path.write_text(json.dumps(review, ensure_ascii=False), encoding="utf-8")
        return review_path

    def test_hook_second_person_is_allowed(self) -> None:
        path = self.write_script("你真的看懂这场布局了吗？\n\n公司等着开拓者自己请缨。\n")
        result = self.audit_legacy(path, second_person_policy="hook_only", hook_paragraphs=1)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["second_person"]["hook_count"], 1)
        self.assertEqual(result["second_person"]["body_count"], 0)

    def test_body_second_person_is_blocked(self) -> None:
        path = self.write_script("这场布局从投票开始。\n\n你会发现公司没有付出代价。\n")
        result = self.audit_legacy(path, second_person_policy="hook_only", hook_paragraphs=1)
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["second_person"]["body_count"], 1)

    def test_quoted_second_person_does_not_count(self) -> None:
        path = self.write_script("原文先给了答案。\n\n阿哈说：“你只是我的影子。”\n")
        result = self.audit_legacy(path, second_person_policy="hook_only", hook_paragraphs=1)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["second_person"]["body_count"], 0)

    def test_no_default_length_floor(self) -> None:
        path = self.write_script("这一句已经说清了结论。\n")
        result = self.audit_legacy(path, style_profile="author_voice_v1")
        self.assertEqual(result["status"], "pass")
        self.assertIsNone(result["author_voice"]["target_min_han"])

    def test_explicit_length_limit_remains_a_gate(self) -> None:
        path = self.write_script("这是一段超过限制的文字。\n")
        result = self.audit_legacy(path, style_profile="author_voice_v1", target_max_han=3)
        self.assertEqual(result["status"], "fail")

    def test_natural_contrast_is_diagnostic_not_blocker(self) -> None:
        path = self.write_script("这不是退让，而是公司在等更便宜的解法。\n")
        result = self.audit_legacy(path)
        self.assertEqual(result["status"], "pass")
        self.assertTrue(any("对比模板" in warning for warning in result["warnings"]))

    def test_multiline_hook_paragraph_stays_in_hook(self) -> None:
        path = self.write_script(
            "你真的看懂这场布局了吗？\n第二行仍属于同一个钩子段落。\n\n"
            "公司等着开拓者自己请缨。\n"
        )
        result = self.audit_legacy(path, second_person_policy="hook_only", hook_paragraphs=1)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["second_person"]["hook_count"], 1)
        self.assertEqual(result["second_person"]["body_count"], 0)

    def test_later_casual_second_person_in_same_hook_paragraph_is_blocked(self) -> None:
        path = self.write_script("你真的看懂这场布局了吗？稍后你看，公司没有付出代价。\n")
        result = self.audit_legacy(path)
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["second_person"]["hook_count"], 1)
        self.assertEqual(result["second_person"]["body_count"], 1)

    def test_strict_defaults_require_bound_review(self) -> None:
        path = self.write_script("这场布局从投票开始。\n\n公司等待开拓者自己请缨。\n")
        result = audit(path, path)
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["author_voice"]["profile"], "author_voice_v1")
        self.assertIn("缺少传统中文逐句审校收据", result["errors"])

    def test_strict_review_requires_full_1x_read(self) -> None:
        path = self.write_script("这场布局从投票开始。\n\n公司等待开拓者自己请缨。\n")
        review = self.write_review(path, full_speed_1x_read=False)
        result = audit(path, path, syntax_review=review)
        self.assertEqual(result["status"], "fail")
        self.assertIn("traditional_chinese_review.full_speed_1x_read", result["errors"])

    def test_strict_review_can_pass_when_fully_bound(self) -> None:
        path = self.write_script("这场布局从投票开始。\n\n公司等待开拓者自己请缨。\n")
        review = self.write_review(path)
        result = audit(path, path, syntax_review=review)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["traditional_chinese"]["review"]["status"], "pass")

    def test_v1_review_is_rejected_after_semantic_upgrade(self) -> None:
        path = self.write_script("这场布局从投票开始。\n")
        review = self.write_review(path)
        payload = json.loads(review.read_text(encoding="utf-8"))
        payload["profile"] = "traditional_chinese_v1"
        review.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        result = audit(path, path, syntax_review=review)
        self.assertEqual(result["status"], "fail")
        self.assertIn("traditional_chinese_review.profile", result["errors"])

    def test_v2_review_requires_semantic_referent_dimension(self) -> None:
        path = self.write_script("这场布局从投票开始。\n")
        review = self.write_review(path)
        payload = json.loads(review.read_text(encoding="utf-8"))
        del payload["dimensions"]["semantic_referent"]
        review.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        result = audit(path, path, syntax_review=review)
        self.assertEqual(result["status"], "fail")
        self.assertIn("traditional_chinese_review.dimensions.semantic_referent", result["errors"])

    def test_v2_review_requires_explicit_referent_register_pass(self) -> None:
        path = self.write_script("这场布局从投票开始。\n")
        review = self.write_review(path)
        payload = json.loads(review.read_text(encoding="utf-8"))
        del payload["full_referent_register_reviewed"]
        review.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        result = audit(path, path, syntax_review=review)
        self.assertEqual(result["status"], "fail")
        self.assertIn("traditional_chinese_review.full_referent_register_reviewed", result["errors"])

    def test_default_strict_profile_requires_review_for_suspect_collocation(self) -> None:
        path = self.write_script("这场布局从投票开始。\n\n这个世界会替公司签名。\n")
        result = audit(path, path)
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["traditional_chinese"]["blocker_count"], 0)
        self.assertEqual(result["traditional_chinese"]["risk_counts"].get("word_choice_collocation"), 1)

    def test_missing_canonical_is_a_failure(self) -> None:
        path = self.write_script("这一句已经说清了结论。\n")
        result = audit(path, None, syntax_profile="legacy")
        self.assertEqual(result["status"], "fail")
        self.assertIn("缺少正典口播纯文本，无法验证逐字一致", result["errors"])

    def test_user_rejected_house_style_frames_are_blocked(self) -> None:
        rejected = (
            "编剧把这层关系写成了组织结构。",
            "4.5版本真正追问的是，何为同谐？",
            "这段旁白写得很准。",
            "这一幕定调只说清一个共同目标：一起赢。",
            "朽叶要阻止生命工业继续升级。",
            "她面对的问题，是该不该直接杀掉研究者？",
            "现有文本没有交代两件事的先后。",
            "许多声音怎样才能合到一起，她还没有答案。",
            "三只晴空乐手就在此时诞生。",
            "公司把方案、筹码和舆论全摆上桌。",
            "研究院替生命命名、安排用途。",
            "等生命不肯服从，她便把它销毁。",
            "公司替众生安排用途。",
        )
        for sentence in rejected:
            with self.subTest(sentence=sentence):
                path = self.write_script(sentence + "\n")
                result = self.audit_legacy(path, second_person_policy="free")
                self.assertEqual(result["status"], "fail")
                self.assertTrue(result["house_style_rejections"])

    def test_user_approved_replacements_pass_house_style_gate(self) -> None:
        path = self.write_script(
            "4.5版本真正探讨的主题是：同谐如何容纳不同的声音。\n\n"
            "旁白给出的比喻很恰当。\n\n"
            "这一幕只负责一个共同目标，那就是一起跨越终点。\n\n"
            "许多声音怎样才能合到一起？她暂时还没有答案。\n\n"
            "而就在此时，三只晴空乐手诞生了。\n\n"
            "各方终于把分歧摆上台面。\n"
            "生研院造出生命以后，又替众生命名、安排命运。\n"
        )
        result = self.audit_legacy(path, second_person_policy="free")
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["house_style_rejections"], [])

    def test_literal_object_on_table_is_not_overblocked(self) -> None:
        path = self.write_script("他把杯子摆上桌，随后坐了下来。\n")
        result = self.audit_legacy(path)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["house_style_rejections"], [])

    def test_rejected_phrase_inside_canonical_quote_is_not_blocked(self) -> None:
        path = self.write_script("原文写道：“旁白写得很准。”随后镜头转向舞台。\n")
        result = self.audit_legacy(path)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["house_style_rejections"], [])

    def test_normal_system_collocation_is_review_not_blocker(self) -> None:
        path = self.write_script("系统执行了管理员下达的命令。\n")
        result = self.audit_legacy(path)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["traditional_chinese"]["blocker_count"], 0)
        self.assertEqual(result["traditional_chinese"]["risk_counts"].get("word_choice_collocation"), 1)

    def test_normal_causative_and_passive_are_review_not_blocker(self) -> None:
        path = self.write_script("知更鸟让乐手给同伴留下位置。这个名字后来被历史所遗忘。\n")
        result = self.audit_legacy(path)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["traditional_chinese"]["blocker_count"], 0)
        self.assertEqual(result["traditional_chinese"]["risk_counts"].get("passive_tangle"), 2)

    def test_official_quote_is_exempt_from_traditional_chinese_patterns(self) -> None:
        path = self.write_script("原文写道：“这个世界会替公司签名。”这句话随后成为关键证据。\n")
        result = self.audit_legacy(path)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["traditional_chinese"]["blocker_count"], 0)
        self.assertIsNone(result["traditional_chinese"]["risk_counts"].get("word_choice_collocation"))

    def test_product_language_for_living_beings_requires_review(self) -> None:
        path = self.write_script("在公司的记录里，这些尘灵会被当作产品销毁。\n")
        result = self.audit_legacy(path)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["traditional_chinese"]["blocker_count"], 0)
        self.assertEqual(result["traditional_chinese"]["risk_counts"].get("semantic_referent_register"), 1)

    def test_ordinary_machine_utility_is_not_flagged_as_personhood_problem(self) -> None:
        path = self.write_script("这台机器有三种用途，损坏以后可以报废。\n")
        result = self.audit_legacy(path)
        self.assertEqual(result["status"], "pass")
        self.assertIsNone(result["traditional_chinese"]["risk_counts"].get("semantic_referent_register"))

    def test_blind_regression_subtle_identity_phrases_require_review(self) -> None:
        sentences = (
            "研究院又替他们安排一生。",
            "谁有权决定这些生灵应当是谁？",
            "她要为这些生灵争回决定自身命运的机会。",
        )
        for sentence in sentences:
            with self.subTest(sentence=sentence):
                path = self.write_script(sentence + "\n")
                result = self.audit_legacy(path)
                self.assertEqual(result["status"], "pass")
                self.assertEqual(
                    result["traditional_chinese"]["risk_counts"].get("semantic_referent_register"),
                    1,
                )

    def test_ba_construction_cannot_force_lingjia(self) -> None:
        path = self.write_script("研究院把自己的命令凌驾于众生的意愿之上。\n")
        result = self.audit_legacy(path)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(
            result["traditional_chinese"]["risk_counts"].get("word_choice_collocation"),
            1,
        )

    def test_parallel_nouns_must_each_fit_shared_predicate(self) -> None:
        path = self.write_script("编号、身份和工作原本都是研究院强加给他们的。\n")
        result = self.audit_legacy(path)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(
            result["traditional_chinese"]["risk_counts"].get("word_choice_collocation"),
            1,
        )


if __name__ == "__main__":
    unittest.main()
