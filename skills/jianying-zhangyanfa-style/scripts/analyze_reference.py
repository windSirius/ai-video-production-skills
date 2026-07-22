#!/usr/bin/env python3
"""Measure a finished reference edit with ffprobe/ffmpeg.

Produces metrics.json, scene_times.tsv, full/intro/outro contact sheets, and an
exact first-frames sheet without changing the source video. The measurements
are evidence for editorial judgment, not an automatic cut prescription.
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
    parser.add_argument("--opening-seconds", type=float, default=10.0)
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


def bounded_interval_metrics(values: list[float], start: float, end: float) -> dict:
    bounded = [value for value in values if start < value <= end]
    edges = [start, *bounded, end]
    intervals = [b - a for a, b in zip(edges, edges[1:])]
    ordered = sorted(intervals)
    return {
        "start_seconds": start,
        "end_seconds": end,
        "transition_count": len(bounded),
        "transition_times_seconds": bounded,
        "mean_interval_seconds": statistics.fmean(intervals) if intervals else None,
        "median_interval_seconds": statistics.median(intervals) if intervals else None,
        "p25_interval_seconds": percentile(ordered, 0.25),
        "p75_interval_seconds": percentile(ordered, 0.75),
        "max_interval_seconds": max(intervals) if intervals else None,
    }


def cadence_windows(values: list[float], duration: float, width: float = 30.0) -> list[dict]:
    windows: list[dict] = []
    start = 0.0
    while start < duration:
        end = min(duration, start + width)
        windows.append(bounded_interval_metrics(values, start, end))
        start = end
    return windows


def opening_metrics(raw: list[float], fps: float, duration: float, seconds: float, gap: float) -> dict:
    frame_duration = 1.0 / fps
    # Permit the requested wall-clock horizon plus two frames because a one-frame
    # platform cover intentionally offsets every narrative lane.
    end = min(duration, seconds + 2.0 * frame_duration)
    opening_raw = [value for value in raw if value <= end]
    first_transition = opening_raw[0] if opening_raw else None
    first_frame_candidate = first_transition is not None and first_transition <= 1.5 * frame_duration
    narrative_raw = [
        value for value in opening_raw if not first_frame_candidate or value > 1.5 * frame_duration
    ]
    narrative_clustered = cluster(narrative_raw, gap)
    occupied_seconds = sorted({int(math.floor(value + 1e-6)) for value in narrative_clustered})
    return {
        "horizon_seconds": seconds,
        "frame_duration_seconds": frame_duration,
        "first_detected_transition_seconds": first_transition,
        "first_frame_discontinuity_candidate": first_frame_candidate,
        "warning": "A first-frame discontinuity is only a cover candidate; verify it with contact_sheet_first_12_frames.jpg and the live timeline.",
        "raw_transition_times_seconds": opening_raw,
        "narrative_clustered_transition_times_seconds": narrative_clustered,
        "whole_seconds_with_detected_refresh": occupied_seconds,
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


def render_contact_sheet_range(video: Path, output: Path, start: float, end: float, samples: int) -> None:
    columns = 5
    rows = math.ceil(samples / columns)
    safe_end = max(start, end - 0.1)
    times = [start + (safe_end - start) * i / max(1, samples - 1) for i in range(samples)]
    filters: list[str] = []
    labels: list[str] = []
    for index, timestamp in enumerate(times):
        label = f"r{index}"
        labels.append(f"[{label}]")
        filters.append(f"[0:v]trim=start={timestamp:.6f}:duration=0.04,setpts=PTS-STARTPTS,scale=384:216[{label}]")
    layout = "|".join(f"{(i % columns) * 384}_{(i // columns) * 216}" for i in range(samples))
    filters.append("".join(labels) + f"xstack=inputs={samples}:layout={layout}:fill=black[sheet]")
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


def render_first_frames_sheet(video: Path, output: Path, frames: int = 12) -> None:
    columns = 4
    rows = math.ceil(frames / columns)
    run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(video),
            "-vf",
            f"select='lt(n,{frames})',scale=427:240,tile={columns}x{rows}:nb_frames={frames}:padding=2:margin=0",
            "-an",
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
    fps = fps_from_probe(metadata)
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
        "fps": fps,
        "probe": metadata,
        "audio": loudness(args.video),
        "scene_detection": {
            "threshold": args.scene_threshold,
            "cluster_gap_seconds": args.cluster_gap,
            "raw_transition_count": len(raw),
            "clustered": interval_metrics(clustered),
        },
        "opening": opening_metrics(raw, fps, duration, args.opening_seconds, args.cluster_gap),
        "cadence_30_second_windows": cadence_windows(clustered, duration),
    }
    (args.out / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    render_contact_sheet(args.video, args.out / "contact_sheet_full.jpg", duration, 16)
    render_contact_sheet(args.video, args.out / "contact_sheet_intro.jpg", min(duration, 24.0), 12)
    render_contact_sheet_range(
        args.video,
        args.out / "contact_sheet_opening_0_10.jpg",
        0.0,
        min(duration, args.opening_seconds + 0.1),
        11,
    )
    render_contact_sheet_range(
        args.video,
        args.out / "contact_sheet_outro_last30.jpg",
        max(0.0, duration - 30.0),
        duration,
        30,
    )
    render_first_frames_sheet(args.video, args.out / "contact_sheet_first_12_frames.jpg")
    print(
        json.dumps(
            {
                "output": str(args.out.resolve()),
                "duration_seconds": duration,
                "fps": fps,
                "audio": metrics["audio"],
                "scene_detection": metrics["scene_detection"],
                "opening": metrics["opening"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
