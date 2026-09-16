#!/usr/bin/env python3
"""Create a per-caption A-track planning sheet from a frozen SRT."""

from __future__ import annotations

import argparse
import csv
import re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


BLOCK = re.compile(
    r"(?ms)^\s*(\d+)\s*\n"
    r"(\d\d):(\d\d):(\d\d),(\d{3})\s*-->\s*"
    r"(\d\d):(\d\d):(\d\d),(\d{3})\s*\n"
    r"(.*?)(?=\n\s*\n|\Z)"
)


def millis(parts: tuple[str, str, str, str]) -> int:
    hour, minute, second, ms = map(int, parts)
    return ((hour * 60 + minute) * 60 + second) * 1000 + ms


def frame(ms: int, fps: int) -> int:
    return int((Decimal(ms) * Decimal(fps) / Decimal(1000)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def parse_srt(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for match in BLOCK.finditer(path.read_text(encoding="utf-8-sig")):
        text = " ".join(line.strip() for line in match.group(10).splitlines() if line.strip())
        rows.append({
            "cue_id": int(match.group(1)),
            "start_ms": millis(match.group(2, 3, 4, 5)),
            "end_ms": millis(match.group(6, 7, 8, 9)),
            "text": text,
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_srt", type=Path)
    parser.add_argument("output_tsv", type=Path)
    parser.add_argument("--fps", type=int, default=60)
    args = parser.parse_args()
    rows = parse_srt(args.input_srt)
    if not rows:
        raise SystemExit("no SRT cues parsed")
    fields = [
        "cue_id", "start_frame", "end_frame", "text", "track", "candidate_id", "shot_id",
        "source_id", "source_in", "source_out", "visual_family_id", "visual_transform", "match_class", "match_reason",
        "identity_required", "identity_proof_id", "refresh_from_previous",
        "continuity_override_id", "review_status",
    ]
    args.output_tsv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_tsv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        for index, row in enumerate(rows):
            writer.writerow({
                "cue_id": row["cue_id"],
                "start_frame": frame(int(row["start_ms"]), args.fps),
                "end_frame": frame(int(row["end_ms"]), args.fps),
                "text": row["text"],
                "track": "A",
                "identity_required": "false",
                "refresh_from_previous": "true" if index else "start",
                "review_status": "pending",
            })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
