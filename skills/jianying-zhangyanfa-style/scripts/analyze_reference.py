#!/usr/bin/env python3
"""Measure a finished reference edit with ffprobe/ffmpeg.

Produces metrics.json, scene_times.tsv, and two contact sheets without changing
the source video. The measurements are evidence for editorial judgment, not an
automatic cut prescription.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import statistics
import subprocess
from pathlib import Path


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=True, text=True, capture_output=True)


def require_tool(name: str) -> None:
    if shutil.which(name) is None:
        raise SystemExit(f"Required tool not found: {name}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--scene-threshold", type=float, default=0.18)
    parser.add_argument("--cluster-gap", type=float, default=0.6)
    return parser.parse_args()


def probe(video: Path) -> dict:
    result = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration,size,bit_rate:stream=index,codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate,sample_rate,channels,channel_layout",
            "-of",
            "json",
            str(video),
        ]
    )
    return json.loads(result.stdout)


def loudness(video: Path) -> dict:
    result = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            str(video),
            "-map",
            "0:a:0",
            "-af",
            "ebur128=peak=true",
            "-f",
            "null",
            "-",
        ],
        text=True,
        capture_output=True,
    )
    text = result.stderr
    integrated = re.findall(r"I:\s+(-?[0-9.]+) LUFS", text)
    lra = re.findall(r"LRA:\s+([0-9.]+) LU", text)
    peak = re.findall(r"Peak:\s+(-?[0-9.]+) dBFS", text)
    return {
        "integrated_lufs": float(integrated[-1]) if integrated else None,
        "loudness_range_lu": float(lra[-1]) if lra else None,
        "true_peak_dbfs": float(peak[-1]) if peak else None,
    }


def scene_times(video: Path, threshold: float) -> list[float]:
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
    return [float(x) for x in re.findall(r"pts_time:([0-9.]+)", result.stderr)]


def cluster(values: list[float], gap: float) -> list[float]:
    kept: list[float] = []
    for value in values:
        if not kept or value - kept[-1] >= gap:
            kept.append(value)
    return kept


def percentile(sorted_values: list[float], q: float) -> float | None:
    if not sorted_values:
        return None
    index = min(len(sorted_values) - 1, max(0, int((len(sorted_values) - 1) * q)))
    return sorted_values[index]


def interval_metrics(values: list[float]) -> dict:
    intervals = [b - a for a, b in zip(values, values[1:])]
    ordered = sorted(intervals)
    return {
        "transition_count": len(values),
        "mean_interval_seconds": statistics.fmean(intervals) if intervals else None,
        "median_interval_seconds": statistics.median(intervals) if intervals else None,
        "p25_interval_seconds": percentile(ordered, 0.25),
        "p75_interval_seconds": percentile(ordered, 0.75),
    }


def fps_from_probe(data: dict) -> float:
    stream = next(s for s in data["streams"] if s.get("codec_type") == "video")
    numerator, denominator = stream["avg_frame_rate"].split("/")
    return float(numerator) / float(denominator)


def render_contact_sheet(video: Path, output: Path, duration: float, samples: int) -> None:
    columns = 4
    rows = math.ceil(samples / columns)
    # Sampling at the exact container duration can land after the final frame.
    safe_end = max(0.0, duration - 0.1)
    times = [safe_end * i / max(1, samples - 1) for i in range(samples)]
    filters: list[str] = []
    labels: list[str] = []
    for index, timestamp in enumerate(times):
        label = f"v{index}"
        labels.append(f"[{label}]")
        filters.append(f"[0:v]trim=start={timestamp:.3f}:duration=0.04,setpts=PTS-STARTPTS,scale=427:240[{label}]")
    filters.append("".join(labels) + f"xstack=inputs={samples}:layout=" + "|".join(f"{(i % columns) * 427}_{(i // columns) * 240}" for i in range(samples)) + "[sheet]")
    run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(video),
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[sheet]",
            "-frames:v",
            "1",
            str(output),
        ]
    )


def main() -> None:
    args = parse_args()
    require_tool("ffmpeg")
    require_tool("ffprobe")
    if not args.video.is_file():
        raise SystemExit(f"Video not found: {args.video}")
    args.out.mkdir(parents=True, exist_ok=True)

    metadata = probe(args.video)
    duration = float(metadata["format"]["duration"])
    raw = scene_times(args.video, args.scene_threshold)
    clustered = cluster(raw, args.cluster_gap)

    with (args.out / "scene_times.tsv").open("w", encoding="utf-8") as handle:
        handle.write("raw_time_seconds\tclustered\n")
        clustered_set = set(clustered)
        for value in raw:
            handle.write(f"{value:.6f}\t{1 if value in clustered_set else 0}\n")

    metrics = {
        "source": str(args.video.resolve()),
        "duration_seconds": duration,
        "fps": fps_from_probe(metadata),
        "probe": metadata,
        "audio": loudness(args.video),
        "scene_detection": {
            "threshold": args.scene_threshold,
            "cluster_gap_seconds": args.cluster_gap,
            "raw_transition_count": len(raw),
            "clustered": interval_metrics(clustered),
        },
    }
    (args.out / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    render_contact_sheet(args.video, args.out / "contact_sheet_full.jpg", duration, 16)
    render_contact_sheet(args.video, args.out / "contact_sheet_intro.jpg", min(duration, 24.0), 12)
    print(json.dumps({"output": str(args.out.resolve()), "metrics": metrics}, ensure_ascii=False))


if __name__ == "__main__":
    main()
