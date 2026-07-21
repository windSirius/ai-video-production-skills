#!/usr/bin/env python3
"""Audit or merge adjacent identical SRT captions."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path


TIMING_RE = re.compile(r"^(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})$")


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
        captions.append(Caption(start=start, end=end, text="\n".join(lines[2:])))
    return captions


def adjacent_duplicates(captions: list[Caption], max_gap_ms: int) -> list[dict[str, object]]:
    duplicates: list[dict[str, object]] = []
    for index in range(1, len(captions)):
        previous = captions[index - 1]
        current = captions[index]
        gap = to_ms(current.start) - to_ms(previous.end)
        if previous.text == current.text and gap <= max_gap_ms:
            duplicates.append(
                {
                    "first_entry": index,
                    "second_entry": index + 1,
                    "gap_ms": gap,
                    "text": current.text,
                }
            )
    return duplicates


def merge(captions: list[Caption], max_gap_ms: int) -> list[Caption]:
    merged: list[Caption] = []
    for caption in captions:
        if merged:
            previous = merged[-1]
            gap = to_ms(caption.start) - to_ms(previous.end)
            if previous.text == caption.text and gap <= max_gap_ms:
                if to_ms(caption.end) > to_ms(previous.end):
                    previous.end = caption.end
                continue
        merged.append(Caption(caption.start, caption.end, caption.text))
    return merged


def render_srt(captions: list[Caption]) -> str:
    blocks = [
        f"{index}\n{caption.start} --> {caption.end}\n{caption.text}"
        for index, caption in enumerate(captions, start=1)
    ]
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Input SRT file")
    parser.add_argument("output", type=Path, nargs="?", help="Merged output SRT file")
    parser.add_argument(
        "--max-gap-ms",
        type=int,
        default=100,
        help="Maximum gap allowed between identical entries (default: 100)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Audit only; do not write an output file",
    )
    args = parser.parse_args()

    if args.max_gap_ms < 0:
        parser.error("--max-gap-ms must be non-negative")
    if not args.check and args.output is None:
        parser.error("output is required unless --check is used")

    captions = parse_srt(args.input)
    duplicates = adjacent_duplicates(captions, args.max_gap_ms)
    merged = merge(captions, args.max_gap_ms)

    if not args.check:
        assert args.output is not None
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(render_srt(merged), encoding="utf-8")

    report = {
        "input": str(args.input),
        "output": None if args.check else str(args.output),
        "entries_before": len(captions),
        "entries_after": len(merged),
        "merged_entries": len(captions) - len(merged),
        "adjacent_duplicates": duplicates,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
