#!/usr/bin/env python3
"""Audit a semantically resegmented SRT against the raw Manuscript Match SRT."""

from __future__ import annotations

import argparse
import difflib
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path


TIMING_RE = re.compile(r"^(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})$")
PUNCT_ONLY_RE = re.compile(r"^[\s，。！？；：、,.!?;:…—\-~～·「」『』“”‘’《》〈〉（）()【】\[\]]+$")
QUOTE_PAIRS = (("「", "」"), ("『", "』"), ("“", "”"), ("‘", "’"), ("《", "》"), ("〈", "〉"))
DEFAULT_FORBIDDEN_TERMINAL_PUNCTUATION = "，。；：,.;:"
DEFAULT_TRAILING_CLOSING_MARKS = "」』”’）》〉）】"


@dataclass
class Caption:
    start: str
    end: str
    text: str


def to_ms(value: str) -> int:
    hours, minutes, rest = value.split(":")
    seconds, millis = rest.split(",")
    return (((int(hours) * 60 + int(minutes)) * 60) + int(seconds)) * 1000 + int(millis)


def parse_srt(path: Path) -> list[Caption]:
    raw = path.read_text(encoding="utf-8-sig").strip()
    if not raw:
        return []
    captions: list[Caption] = []
    for block_no, block in enumerate(re.split(r"\r?\n\r?\n+", raw), start=1):
        lines = block.splitlines()
        if len(lines) < 3:
            raise ValueError(f"Block {block_no} is incomplete")
        timing = TIMING_RE.match(lines[1].strip())
        if not timing:
            raise ValueError(f"Block {block_no} has invalid timing: {lines[1]!r}")
        start, end = timing.groups()
        if to_ms(end) < to_ms(start):
            raise ValueError(f"Block {block_no} ends before it starts")
        captions.append(Caption(start, end, "\n".join(lines[2:]).strip()))
    return captions


def normalized_text(captions: list[Caption], ignored_chars: str, lexical: bool) -> str:
    ignored = set(ignored_chars)
    output = []
    for caption in captions:
        for char in unicodedata.normalize("NFKC", caption.text):
            if char.isspace() or char in ignored:
                continue
            if lexical and unicodedata.category(char).startswith("P"):
                continue
            output.append(char)
    return "".join(output)


def visible_chars(text: str) -> int:
    return sum(not char.isspace() for char in text)


def find_forbidden_terminal_punctuation(
    text: str,
    forbidden_punctuation: str = DEFAULT_FORBIDDEN_TERMINAL_PUNCTUATION,
    trailing_closing_marks: str = DEFAULT_TRAILING_CLOSING_MARKS,
) -> str | None:
    candidate = text.rstrip()
    closing_marks = set(trailing_closing_marks)
    while candidate and candidate[-1] in closing_marks:
        candidate = candidate[:-1].rstrip()
    if candidate and candidate[-1] in set(forbidden_punctuation):
        return candidate[-1]
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw_srt", type=Path, help="Unedited Manuscript Match SRT")
    parser.add_argument("final_srt", type=Path, help="Semantically edited final SRT")
    parser.add_argument("--ignore-chars", default="。；：", help="Style punctuation ignored in coverage comparison")
    parser.add_argument(
        "--coverage-mode",
        choices=("lexical", "exact"),
        default="lexical",
        help="lexical ignores Unicode punctuation while checking word coverage; exact preserves it",
    )
    parser.add_argument("--max-visible-chars", type=int, default=24)
    parser.add_argument("--max-cps", type=float, default=12.0, help="Warning threshold for visible characters per second")
    parser.add_argument(
        "--forbidden-terminal-punctuation",
        default=DEFAULT_FORBIDDEN_TERMINAL_PUNCTUATION,
        help="Terminal punctuation rejected by the user's house style",
    )
    parser.add_argument(
        "--terminal-closing-marks",
        default=DEFAULT_TRAILING_CLOSING_MARKS,
        help="Closing marks ignored while locating the effective caption ending",
    )
    parser.add_argument(
        "--allow-forbidden-terminal-punctuation",
        action="store_true",
        help="Explicitly override the house-style terminal-punctuation gate",
    )
    args = parser.parse_args()

    raw = parse_srt(args.raw_srt)
    final = parse_srt(args.final_srt)
    lexical = args.coverage_mode == "lexical"
    raw_text = normalized_text(raw, args.ignore_chars, lexical)
    final_text = normalized_text(final, args.ignore_chars, lexical)

    coverage_differences = []
    if raw_text != final_text:
        matcher = difflib.SequenceMatcher(None, raw_text, final_text, autojunk=False)
        for tag, raw_start, raw_end, final_start, final_end in matcher.get_opcodes():
            if tag == "equal":
                continue
            coverage_differences.append(
                {
                    "operation": tag,
                    "raw": raw_text[raw_start:raw_end],
                    "final": final_text[final_start:final_end],
                    "raw_context": raw_text[max(0, raw_start - 12):min(len(raw_text), raw_end + 12)],
                    "final_context": final_text[max(0, final_start - 12):min(len(final_text), final_end + 12)],
                }
            )

    duplicates = [
        index + 1
        for index in range(1, len(final))
        if " ".join(final[index].text.split()) == " ".join(final[index - 1].text.split())
    ]
    punctuation_only = [
        index for index, caption in enumerate(final, start=1)
        if not caption.text or PUNCT_ONLY_RE.fullmatch(caption.text)
    ]
    forbidden_terminal_punctuation = []
    if not args.allow_forbidden_terminal_punctuation:
        forbidden_terminal_punctuation = [
            {
                "entry": index,
                "punctuation": punctuation,
                "text": caption.text,
            }
            for index, caption in enumerate(final, start=1)
            if (
                punctuation := find_forbidden_terminal_punctuation(
                    caption.text,
                    args.forbidden_terminal_punctuation,
                    args.terminal_closing_marks,
                )
            )
        ]
    long_entries = [
        {"entry": index, "visible_chars": visible_chars(caption.text)}
        for index, caption in enumerate(final, start=1)
        if visible_chars(caption.text) > args.max_visible_chars
    ]
    fast_entries = []
    invalid_order = []
    previous_end = -1
    for index, caption in enumerate(final, start=1):
        start = to_ms(caption.start)
        end = to_ms(caption.end)
        if start < previous_end:
            invalid_order.append(index)
        previous_end = max(previous_end, end)
        duration_s = max((end - start) / 1000.0, 0.001)
        cps = visible_chars(caption.text) / duration_s
        if cps > args.max_cps:
            fast_entries.append({"entry": index, "cps": round(cps, 2)})

    joined = "".join(caption.text for caption in final)
    quote_imbalances = [
        {"open": opening, "close": closing, "open_count": joined.count(opening), "close_count": joined.count(closing)}
        for opening, closing in QUOTE_PAIRS
        if joined.count(opening) != joined.count(closing)
    ]

    failures = {
        "coverage_mismatch": raw_text != final_text,
        "adjacent_duplicate_entries": duplicates,
        "punctuation_only_entries": punctuation_only,
        "forbidden_terminal_punctuation_entries": forbidden_terminal_punctuation,
        "invalid_time_order_entries": invalid_order,
        "quote_imbalances": quote_imbalances,
    }
    passed = not any(bool(value) for value in failures.values())
    report = {
        "pass": passed,
        "raw_srt": str(args.raw_srt),
        "final_srt": str(args.final_srt),
        "entries_raw": len(raw),
        "entries_final": len(final),
        "normalized_characters_raw": len(raw_text),
        "normalized_characters_final": len(final_text),
        "coverage_mode": args.coverage_mode,
        "terminal_punctuation_policy": {
            "enabled": not args.allow_forbidden_terminal_punctuation,
            "forbidden": args.forbidden_terminal_punctuation,
            "trailing_closing_marks": args.terminal_closing_marks,
            "preserved": "？！?!",
        },
        "coverage_differences": coverage_differences,
        "failures": failures,
        "warnings": {
            "long_entries": long_entries,
            "fast_entries": fast_entries,
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
