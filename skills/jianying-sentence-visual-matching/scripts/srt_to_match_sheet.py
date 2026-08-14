#!/usr/bin/env python3
"""Convert SRT captions into a TSV template for sentence-to-shot matching."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


TIME_RE = re.compile(
    r"(?P<sh>\d{1,2}):(?P<sm>\d{2}):(?P<ss>\d{2})[,.](?P<sms>\d{3})\s*-->\s*"
    r"(?P<eh>\d{1,2}):(?P<em>\d{2}):(?P<es>\d{2})[,.](?P<ems>\d{3})"
)


def seconds(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def parse_srt(path: Path) -> list[dict[str, object]]:
    text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    entries: list[dict[str, object]] = []
    for block in re.split(r"\n{2,}", text.strip()):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        timing_index = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if timing_index is None:
            continue
        match = TIME_RE.search(lines[timing_index])
        if not match:
            raise ValueError(f"Unrecognized timing line: {lines[timing_index]}")
        start = seconds(match["sh"], match["sm"], match["ss"], match["sms"])
        end = seconds(match["eh"], match["em"], match["es"], match["ems"])
        caption = " ".join(lines[timing_index + 1 :]).strip()
        if not caption:
            continue
        entries.append({"start": start, "end": end, "text": caption})
    return entries


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_srt", type=Path)
    parser.add_argument("output_tsv", type=Path)
    args = parser.parse_args()

    entries = parse_srt(args.input_srt)
    args.output_tsv.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "line_id", "start", "end", "duration", "text", "subject", "action",
        "object_location", "emotion", "narrative_job", "candidate_a",
        "candidate_a_score", "candidate_b", "candidate_b_score", "candidate_c",
        "candidate_c_score", "source_file", "source_in", "source_out", "treatment",
        "selected_candidate_id", "source_id", "match_reason", "confidence",
        "retry_round", "reuse_group", "crop_mode", "uid_visible",
        "identity_review", "risk_flags", "qa_status",
    ]
    with args.output_tsv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        for number, entry in enumerate(entries, 1):
            writer.writerow(
                {
                    "line_id": number,
                    "start": f"{entry['start']:.3f}",
                    "end": f"{entry['end']:.3f}",
                    "duration": f"{entry['end'] - entry['start']:.3f}",
                    "text": entry["text"],
                    "retry_round": 0,
                    "crop_mode": "full_frame",
                    "uid_visible": "pending",
                    "qa_status": "unmatched",
                }
            )
    print(f"wrote {len(entries)} rows to {args.output_tsv}")


if __name__ == "__main__":
    main()
