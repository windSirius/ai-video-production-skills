#!/usr/bin/env python3
"""Audit a sentence-to-shot TSV before picture-track replacement."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path


REQUIRED_FIELDS = {
    "line_id", "start", "end", "duration", "text",
    "candidate_a", "candidate_a_score", "candidate_b", "candidate_b_score",
    "candidate_c", "candidate_c_score", "source_file", "source_in", "source_out",
    "match_reason", "confidence", "retry_round", "reuse_group", "qa_status",
}


def number(value: str, label: str, line_id: str, errors: list[str]) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        errors.append(f"line {line_id}: invalid {label}={value!r}")
        return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("match_sheet", type=Path)
    parser.add_argument("--max-reuse", type=int, default=2)
    args = parser.parse_args()

    with args.match_sheet.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fields = set(reader.fieldnames or [])
        missing = sorted(REQUIRED_FIELDS - fields)
        if missing:
            raise SystemExit(f"missing columns: {', '.join(missing)}")
        rows = list(reader)

    errors: list[str] = []
    warnings: list[str] = []
    reuse = Counter(row["reuse_group"].strip() for row in rows if row["reuse_group"].strip())

    for row_number, row in enumerate(rows, 1):
        line_id = row["line_id"].strip() or str(row_number)
        status = row["qa_status"].strip().lower()
        if status not in {"planned", "verified", "card"}:
            errors.append(f"line {line_id}: qa_status must be planned, verified, or card")

        is_card = status == "card"
        if not is_card:
            candidates = [row[f"candidate_{letter}"].strip() for letter in "abc"]
            scores = [row[f"candidate_{letter}_score"].strip() for letter in "abc"]
            if sum(bool(value) for value in candidates) < 3:
                errors.append(f"line {line_id}: fewer than three recorded candidates")
            if any(candidate and not score for candidate, score in zip(candidates, scores)):
                errors.append(f"line {line_id}: candidate score missing")
            if not row["source_file"].strip():
                errors.append(f"line {line_id}: selected source_file missing")

            source_in = number(row["source_in"], "source_in", line_id, errors)
            source_out = number(row["source_out"], "source_out", line_id, errors)
            duration = number(row["duration"], "duration", line_id, errors)
            if None not in {source_in, source_out, duration}:
                assert source_in is not None and source_out is not None and duration is not None
                if source_out <= source_in:
                    errors.append(f"line {line_id}: source_out must be after source_in")
                if source_out - source_in + 0.04 < duration:
                    errors.append(f"line {line_id}: selected source is shorter than caption")

        if not row["match_reason"].strip():
            errors.append(f"line {line_id}: match_reason missing")

        confidence = row["confidence"].strip().lower()
        retry_round = number(row["retry_round"], "retry_round", line_id, errors)
        if confidence in {"low", "低"} and retry_round is not None and retry_round < 1:
            errors.append(f"line {line_id}: low confidence without expansion retry")

    for group, count in sorted(reuse.items()):
        if count > args.max_reuse:
            warnings.append(f"reuse_group {group!r}: used {count} times (limit {args.max_reuse})")

    print(f"rows={len(rows)} errors={len(errors)} warnings={len(warnings)}")
    for item in errors:
        print(f"ERROR {item}")
    for item in warnings:
        print(f"WARN  {item}")
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
