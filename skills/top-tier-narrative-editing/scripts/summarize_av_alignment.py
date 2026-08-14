#!/usr/bin/env python3
"""Summarize narration cadence and visual-refresh alignment for review samples.

Whisper segments and ffmpeg scene scores are measurement proxies. They do not
identify claims, evidence, cuts, or editorial intent without manual review.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("sample_dirs", type=Path, nargs="+")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--alignment-tolerance", type=float, default=0.35)
    return parser.parse_args()


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.floor((len(ordered) - 1) * q)))
    return ordered[index]


def summary(values: list[float]) -> dict:
    return {
        "count": len(values),
        "median": statistics.median(values) if values else None,
        "p25": percentile(values, 0.25),
        "p75": percentile(values, 0.75),
    }


def tier_times(sample_dir: Path, tier: str) -> list[float]:
    path = sample_dir / f"visual_refresh_{tier}.tsv"
    lines = path.read_text(encoding="utf-8").splitlines()[1:]
    return [float(line) for line in lines if line.strip()]


def count_within(values: list[float], start: float, end: float) -> int:
    return sum(start < value <= end for value in values)


def fraction_near(values: list[float], targets: list[float], tolerance: float) -> float | None:
    if not values:
        return None
    near = sum(
        any(abs(value - target) <= tolerance for target in targets)
        for value in values
    )
    return near / len(values)


def analyze(sample_dir: Path, tolerance: float) -> dict:
    transcript_path = sample_dir / "transcript.json"
    refresh_path = sample_dir / "visual_refresh_metrics.json"
    transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
    refresh = json.loads(refresh_path.read_text(encoding="utf-8"))

    segments = [
        segment
        for segment in transcript.get("segments", [])
        if isinstance(segment, dict)
        and isinstance(segment.get("start"), (int, float))
        and isinstance(segment.get("end"), (int, float))
    ]
    duration = float(refresh["duration_seconds"])
    segment_durations = [
        float(segment["end"]) - float(segment["start"]) for segment in segments
    ]
    gaps = [
        max(0.0, float(right["start"]) - float(left["end"]))
        for left, right in zip(segments, segments[1:])
    ]
    boundaries = [float(segment["end"]) for segment in segments[:-1]]
    text = "".join(str(segment.get("text", "")) for segment in segments)
    nonspace_chars = sum(not char.isspace() for char in text)

    tiers = {
        name: tier_times(sample_dir, name)
        for name in ("subtle", "medium", "strong")
    }
    tier_output = {}
    for name, times in tiers.items():
        intervals = [right - left for left, right in zip(times, times[1:])]
        tier_output[name] = {
            "count": len(times),
            "candidates_per_minute": len(times) / duration * 60 if duration else None,
            "interval_seconds": summary(intervals),
            "first_30_seconds_count": count_within(times, 0.0, min(30.0, duration)),
            "first_90_seconds_count": count_within(times, 0.0, min(90.0, duration)),
            "boundary_fraction_within_tolerance": fraction_near(
                boundaries, times, tolerance
            ),
            "candidate_fraction_near_boundary": fraction_near(
                times, boundaries, tolerance
            ),
        }

    strong_windows = refresh["tiers"]["strong"]["windows_30_seconds"]
    window_counts = [int(window["candidate_count"]) for window in strong_windows]
    return {
        "sample_id": sample_dir.name,
        "sample_dir": str(sample_dir.resolve()),
        "duration_seconds": duration,
        "transcript": {
            "language": transcript.get("language"),
            "segment_count": len(segments),
            "nonspace_character_count": nonspace_chars,
            "characters_per_minute": nonspace_chars / duration * 60
            if duration
            else None,
            "segment_duration_seconds": summary(segment_durations),
            "gap_seconds": summary(gaps),
            "gaps_over_one_second": sum(gap > 1.0 for gap in gaps),
        },
        "visual_refresh": tier_output,
        "strong_refresh_windows_30_seconds": {
            "minimum": min(window_counts) if window_counts else None,
            "median": statistics.median(window_counts) if window_counts else None,
            "maximum": max(window_counts) if window_counts else None,
            "zero_count_windows": sum(count == 0 for count in window_counts),
        },
        "measurement_warning": (
            "Whisper segments and ffmpeg scene scores are proxies. Alignment can "
            "reflect speech chunking, source motion, overlays, or compression and "
            "must be checked against frames and narrative annotations."
        ),
    }


def main() -> None:
    args = parse_args()
    if args.alignment_tolerance <= 0:
        raise SystemExit("--alignment-tolerance must be positive")
    samples = []
    for sample_dir in args.sample_dirs:
        if not sample_dir.is_dir():
            raise SystemExit(f"Sample directory not found: {sample_dir}")
        samples.append(analyze(sample_dir, args.alignment_tolerance))

    output = {
        "schema_version": "1.0",
        "alignment_tolerance_seconds": args.alignment_tolerance,
        "samples": samples,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {"output": str(args.out.resolve()), "sample_count": len(samples)},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
