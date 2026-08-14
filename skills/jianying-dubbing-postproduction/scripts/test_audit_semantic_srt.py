#!/usr/bin/env python3
"""Regression tests for semantic SRT terminal-punctuation auditing."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from audit_semantic_srt import canonical_document_text, find_forbidden_terminal_punctuation, normalized_plain_text


class TerminalPunctuationTest(unittest.TestCase):
    def test_rejects_house_style_terminal_punctuation(self) -> None:
        for text in ("句子，", "句子。", "句子：", "句子；", "sentence,", "sentence.", "sentence:", "sentence;"):
            with self.subTest(text=text):
                self.assertIsNotNone(find_forbidden_terminal_punctuation(text))

    def test_rejects_punctuation_before_trailing_closing_marks(self) -> None:
        for text in ("「句子，」", "『句子。』", "“句子：”", "《句子；》", "（句子，）", "【句子。】"):
            with self.subTest(text=text):
                self.assertIsNotNone(find_forbidden_terminal_punctuation(text))

    def test_preserves_questions_exclamations_and_internal_punctuation(self) -> None:
        for text in ("句子？", "句子！", "sentence?", "sentence!", "单看一个曲名，长得像某句诗"):
            with self.subTest(text=text):
                self.assertIsNone(find_forbidden_terminal_punctuation(text))

    def test_plain_text_lexical_normalization(self) -> None:
        self.assertEqual(normalized_plain_text("槲寄生，计划。", "。；：", True), "槲寄生计划")

    def test_canonical_document_ignores_markdown_heading(self) -> None:
        self.assertEqual(canonical_document_text("# 口播纯文本\n\n我们继续\n"), "我们继续")


if __name__ == "__main__":
    unittest.main()
