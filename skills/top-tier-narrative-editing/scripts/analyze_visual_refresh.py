#!/usr/bin/env python3
"""Measure strong, medium, and subtle visual refresh candidates with ffmpeg.

The tiers are detector evidence, not semantic labels. A subtle candidate may be
an overlay, graphic insertion, camera motion, or ordinary subject movement.
Always inspect sampled frames before interpreting it as an editorial event.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import statistics
import subprocess
from pathlib import Path


DEFAULT_THRESHOLDS = {
    "subtle": 0.03,
    "medium": 0.06,
    "strong": 0.18,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--cluster-gap", type=float, default=0.6)
    return parser.parse_args()


def require_tool(name: str) -> None:
    if shutil.which(name) is None:
        raise SystemExit(f"Required tool not found: {name}")


def probe_duration(video: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video),
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    return float(result.stdout.strip())


def detect(video: Path, threshold: float) -> list[float]:
    result = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            str(video),
            "-vf",
            f"select='gt(scene,{threshold})',showinfo",
            "-an",
            "-f",
            "null",
            "-",
        ],
        text=True,
        capture_output=True,
    )
    return [float(value) for value in re.findall(r"pts_time:([0-9.]+)", result.stderr)]


def cluster(values: list[float], gap: float) -> list[float]:
    kept: list[float] = []
    for value in values:
        if not kept or value - kept[-1] >= gap:
            kept.append(value)
    return kept


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int((len(ordered) - 1) * q)))
    return ordered[index]


def interval_summary(values: list[float]) -> dict:
    intervals = [right - left for left, right in zip(values, values[1:])]
    return {
        "candidate_count": len(values),
        "mean_interval_seconds": statistics.fmean(intervals) if intervals else None,
        "median_interval_seconds": statistics.median(intervals) if intervals else None,
        "p25_interval_seconds": percentile(intervals, 0.25),
        "p75_interval_seconds": percentile(intervals, 0.75),
    }


def window_counts(values: list[float], duration: float, width: float = 30.0) -> list[dict]:
    windows: list[dict] = []
    start = 0.0
    while start < duration:
        end = min(duration, start + width)
        bounded = [value for value in values if start < value <= end]
        windows.append(
            {
                "start_seconds": start,
                "end_seconds": end,
                "candidate_count": len(bounded),
                "candidate_times_seconds": bounded,
            }
        )
        start = end
    return windows


def exclusive(values: list[float], stronger: list[float], tolerance: float = 0.25) -> list[float]:
    return [
        value
        for value in values
        if not any(abs(value - strong_value) <= tolerance for strong_value in stronger)
    ]


def main() -> None:
    args = parse_args()
    require_tool("ffmpeg")
    require_tool("ffprobe")
    if not args.video.is_file():
        raise SystemExit(f"Video not found: {args.video}")
    args.out.mkdir(parents=True, exist_ok=True)

    duration = probe_duration(args.video)
    raw = {name: detect(args.video, threshold) for name, threshold in DEFAULT_THRESHOLDS.items()}
    clustered = {name: cluster(values, args.cluster_gap) for name, values in raw.items()}

    strong = clustered["strong"]
    medium_only = exclusive(clustered["medium"], strong)
    subtle_only = exclusive(clustered["subtle"], [*strong, *medium_only])
    exclusive_tiers = {
        "strong": strong,
        "medium_only": medium_only,
        "subtle_only": subtle_only,
    }

    for name, values in clustered.items():
        path = args.out / f"visual_refresh_{name}.tsv"
        path.write_text(
            "time_seconds\n" + "".join(f"{value:.6f}\n" for value in values),
            encoding="utf-8",
        )

    metrics = {
        "source": str(args.video.resolve()),
        "duration_seconds": duration,
        "cluster_gap_seconds": args.cluster_gap,
        "thresholds": DEFAULT_THRESHOLDS,
        "tiers": {
            name: {
                "raw_candidate_count": len(raw[name]),
                "clustered": interval_summary(clustered[name]),
                "windows_30_seconds": window_counts(clustered[name], duration),
            }
            for name in DEFAULT_THRESHOLDS
        },
        "exclusive_candidate_counts": {
            name: len(values) for name, values in exclusive_tiers.items()
        },
        "interpretation_warning": (
            "These are visual-change candidates, not verified cuts. Subtle and medium "
            "tiers can include overlays, gestures, camera motion, or compression changes."
        ),
    }
    output_path = args.out / "visual_refresh_metrics.json"
    output_path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(output_path.resolve()),
                "duration_seconds": duration,
                "candidate_counts": {
                    name: len(values) for name, values in clustered.items()
                },
                "exclusive_candidate_counts": metrics["exclusive_candidate_counts"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
