#!/usr/bin/env python3
"""Repair bounded adjacent duplicate SRT entries without overwriting the source."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from srt_utils import Caption, parse_srt, render_srt, sha256


def normalized_display(text: str) -> str:
    return " ".join(text.split())


def merge_duplicates(
    captions: list[Caption], max_gap_ms: int, max_overlap_ms: int
) -> tuple[list[Caption], list[dict], list[dict]]:
    merged: list[Caption] = []
    changes: list[dict] = []
    rejected_overlaps: list[dict] = []
    for source_index, caption in enumerate(captions, start=1):
        if merged and normalized_display(merged[-1].text) == normalized_display(caption.text):
            previous = merged[-1]
            gap = caption.start_ms - previous.end_ms
            if -max_overlap_ms <= gap <= max_gap_ms:
                old_end = previous.end_ms
                previous.end_ms = max(previous.end_ms, caption.end_ms)
                changes.append(
                    {
                        "source_entry": source_index,
                        "merged_into_output_entry": len(merged),
                        "gap_ms": gap,
                        "old_end_ms": old_end,
                        "new_end_ms": previous.end_ms,
                        "text": caption.text,
                    }
                )
                continue
            if gap < -max_overlap_ms:
                rejected_overlaps.append(
                    {
                        "previous_output_entry": len(merged),
                        "source_entry": source_index,
                        "overlap_ms": -gap,
                        "text": caption.text,
                    }
                )
        merged.append(Caption(caption.start_ms, caption.end_ms, caption.text))
    return merged, changes, rejected_overlaps


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--max-gap-ms", type=int, default=100)
    parser.add_argument("--max-overlap-ms", type=int, default=0)
    args = parser.parse_args()
    if args.max_gap_ms < 0 or args.max_overlap_ms < 0:
        parser.error("gap and overlap tolerances must be non-negative")
    if args.input.resolve() == args.output.resolve():
        parser.error("input and output must be different files")
    try:
        captions = parse_srt(args.input)
        merged, changes, rejected = merge_duplicates(captions, args.max_gap_ms, args.max_overlap_ms)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(render_srt(merged), encoding="utf-8")
        receipt = {
            "status": "pass",
            "input_path": str(args.input.resolve()),
            "input_sha256": sha256(args.input),
            "output_path": str(args.output.resolve()),
            "output_sha256": sha256(args.output),
            "entries_before": len(captions),
            "entries_after": len(merged),
            "max_gap_ms": args.max_gap_ms,
            "max_overlap_ms": args.max_overlap_ms,
            "merged": changes,
            "rejected_large_overlaps": rejected,
        }
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "fail", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
