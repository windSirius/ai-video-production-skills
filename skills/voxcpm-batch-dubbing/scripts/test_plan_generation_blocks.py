#!/usr/bin/env python3

from __future__ import annotations

import unittest

from plan_generation_blocks import (
    DEFAULT_PREFERRED_MAX,
    DEFAULT_PREFERRED_MIN,
    DEFAULT_SHORT_WARNING,
    DEFAULT_SOFT_MAX,
    DEFAULT_TARGET,
    DEFAULT_VERY_SHORT,
    LengthPolicy,
    PlanningError,
    build_plan,
    spoken_char_count,
)


def sentence(character: str, spoken_count: int) -> str:
    return character * spoken_count + "。"


def make_units(
    texts: list[str],
    *,
    force_break_after: set[int] | None = None,
) -> list[dict[str, object]]:
    forced = force_break_after or set()
    return [
        {
            "unit_id": f"U{index:03d}",
            "canonical_text": text,
            "generation_text": text,
            "force_break_after": index in forced,
        }
        for index, text in enumerate(texts, start=1)
    ]


class PlanGenerationBlocksTest(unittest.TestCase):
    def test_default_policy_values(self) -> None:
        policy = LengthPolicy()
        self.assertEqual(policy.target, DEFAULT_TARGET)
        self.assertEqual(policy.preferred_min, DEFAULT_PREFERRED_MIN)
        self.assertEqual(policy.preferred_max, DEFAULT_PREFERRED_MAX)
        self.assertEqual(policy.short_warning_below, DEFAULT_SHORT_WARNING)
        self.assertEqual(policy.very_short_below, DEFAULT_VERY_SHORT)
        self.assertEqual(policy.soft_max, DEFAULT_SOFT_MAX)

    def test_spoken_count_uses_nfkc_and_ignores_punctuation_and_space(self) -> None:
        self.assertEqual(spoken_char_count("甲， 乙！\nＡ1"), 4)

    def test_two_adjacent_75_character_units_pack_to_target(self) -> None:
        texts = [sentence("甲", 75), sentence("乙", 75)]
        canonical = "".join(texts)
        plan = build_plan(canonical, make_units(texts))
        self.assertTrue(plan["coverage"]["exact"])
        self.assertEqual(len(plan["generation_blocks"]), 1)
        block = plan["generation_blocks"][0]
        self.assertEqual(block["spoken_char_count"], 150)
        self.assertEqual(block["length_status"], "preferred")
        self.assertEqual(block["canonical_text"], canonical)
        self.assertEqual(block["source_span"], [0, len(canonical)])

    def test_explicit_spans_may_skip_only_a_double_newline_separator(self) -> None:
        first = sentence("甲", 75)
        second = sentence("乙", 75)
        canonical = first + "\n\n" + second
        units = make_units([first, second])
        units[0]["source_span"] = [0, len(first)]
        units[1]["source_span"] = [len(first) + 2, len(canonical)]

        plan = build_plan(canonical, units)

        self.assertTrue(plan["coverage"]["all_non_whitespace_covered_once"])
        self.assertTrue(plan["coverage"]["no_non_whitespace_gaps"])
        self.assertEqual(plan["coverage"]["separator_gap_count"], 1)
        self.assertEqual(plan["coverage"]["separator_code_points"], 2)
        self.assertEqual(
            plan["separator_gaps"],
            [
                {
                    "gap_id": "GAP001",
                    "kind": "between_units",
                    "after_unit_id": "U001",
                    "before_unit_id": "U002",
                    "source_span": [len(first), len(first) + 2],
                    "separator_text": "\n\n",
                    "separator_sha256": plan["separator_gaps"][0]["separator_sha256"],
                    "code_point_count": 2,
                    "whitespace_only": True,
                }
            ],
        )
        block = plan["generation_blocks"][0]
        self.assertEqual(block["canonical_text"], canonical)
        self.assertEqual(block["generation_text"], canonical)
        self.assertEqual(block["separator_gap_ids"], ["GAP001"])
        self.assertEqual(
            block["covered_source_spans"],
            [[0, len(first)], [len(first) + 2, len(canonical)]],
        )

    def test_non_whitespace_gap_is_rejected(self) -> None:
        first = sentence("甲", 75)
        second = sentence("乙", 75)
        canonical = first + "遗漏" + second
        units = make_units([first, second])
        units[0]["source_span"] = [0, len(first)]
        units[1]["source_span"] = [len(first) + 2, len(canonical)]
        with self.assertRaisesRegex(PlanningError, "non-whitespace source gap"):
            build_plan(canonical, units)

    def test_generation_text_controls_spoken_count_without_changing_canonical(self) -> None:
        canonical = "P46。"
        units = [
            {
                "unit_id": "U001",
                "canonical_text": canonical,
                "generation_text": "P四十六。",
            }
        ]
        plan = build_plan(canonical, units)
        block = plan["generation_blocks"][0]
        self.assertEqual(block["canonical_text"], canonical)
        self.assertEqual(block["generation_text"], "P四十六。")
        self.assertEqual(block["spoken_char_count"], 4)

    def test_force_break_preserves_boundary_and_marks_very_short(self) -> None:
        texts = [sentence("甲", 59), sentence("乙", 150)]
        canonical = "".join(texts)
        plan = build_plan(canonical, make_units(texts, force_break_after={1}))
        self.assertEqual(len(plan["generation_blocks"]), 2)
        self.assertEqual(plan["generation_blocks"][0]["length_status"], "very_short")
        self.assertEqual(plan["warnings"][0]["code"], "very_short_generation_block")

    def test_sixty_is_short_not_very_short(self) -> None:
        texts = [sentence("甲", 60), sentence("乙", 150)]
        plan = build_plan(
            "".join(texts),
            make_units(texts, force_break_after={1}),
        )
        self.assertEqual(plan["generation_blocks"][0]["length_status"], "short")
        self.assertEqual(plan["warnings"][0]["code"], "short_generation_block")

    def test_one_hundred_is_below_preferred_without_short_warning(self) -> None:
        texts = [sentence("甲", 100), sentence("乙", 150)]
        plan = build_plan(
            "".join(texts),
            make_units(texts, force_break_after={1}),
        )
        self.assertEqual(plan["generation_blocks"][0]["length_status"], "below_preferred")
        self.assertEqual(plan["warnings"], [])

    def test_tail_is_rebalanced_by_combining_whole_units_up_to_soft_max(self) -> None:
        texts = [sentence("甲", 130), sentence("乙", 70)]
        plan = build_plan("".join(texts), make_units(texts))
        self.assertEqual(len(plan["generation_blocks"]), 1)
        self.assertEqual(plan["generation_blocks"][0]["spoken_char_count"], 200)
        self.assertEqual(plan["generation_blocks"][0]["length_status"], "above_preferred")

    def test_units_are_not_combined_past_soft_max(self) -> None:
        texts = [sentence("甲", 140), sentence("乙", 140)]
        plan = build_plan("".join(texts), make_units(texts))
        self.assertEqual(
            [block["spoken_char_count"] for block in plan["generation_blocks"]],
            [140, 140],
        )

    def test_indivisible_unit_over_soft_max_is_kept_and_warned(self) -> None:
        canonical = sentence("甲", 201)
        plan = build_plan(canonical, make_units([canonical]))
        self.assertEqual(len(plan["generation_blocks"]), 1)
        self.assertEqual(plan["generation_blocks"][0]["length_status"], "over_soft_max")
        self.assertEqual(plan["warnings"][0]["code"], "generation_block_over_soft_max")

    def test_internal_unit_must_end_at_legal_semantic_boundary(self) -> None:
        texts = ["甲" * 75, sentence("乙", 75)]
        with self.assertRaisesRegex(PlanningError, "legal semantic boundary"):
            build_plan("".join(texts), make_units(texts))

    def test_closing_quote_after_sentence_mark_is_a_legal_boundary(self) -> None:
        texts = ["甲" * 75 + "。”", sentence("乙", 75)]
        plan = build_plan("".join(texts), make_units(texts))
        self.assertEqual(len(plan["generation_blocks"]), 1)

    def test_units_must_cover_approved_source_exactly(self) -> None:
        canonical = sentence("甲", 75)
        units = make_units([sentence("乙", 75)])
        with self.assertRaisesRegex(PlanningError, "does not match the approved source"):
            build_plan(canonical, units)

    def test_supplied_source_span_cannot_skip_non_whitespace(self) -> None:
        spoken = sentence("甲", 75)
        canonical = "漏" + spoken
        units = make_units([spoken])
        units[0]["source_span"] = [1, len(canonical)]
        with self.assertRaisesRegex(PlanningError, "non-whitespace source gap"):
            build_plan(canonical, units)

    def test_plan_is_deterministic(self) -> None:
        texts = [
            sentence("甲", 80),
            sentence("乙", 70),
            sentence("丙", 130),
        ]
        canonical = "".join(texts)
        units = make_units(texts)
        self.assertEqual(build_plan(canonical, units), build_plan(canonical, units))


if __name__ == "__main__":
    unittest.main()
