#!/usr/bin/env python3
"""Audit a rendered draft for metadata, loudness, black frames, and long no-cut gaps."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True, check=False)


def probe(path: Path, ffprobe: str) -> dict[str, object]:
    result = run([ffprobe, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)])
    if result.returncode:
        raise RuntimeError(result.stderr.strip())
    data = json.loads(result.stdout)
    video = next((s for s in data["streams"] if s.get("codec_type") == "video"), None)
    audio = [s for s in data["streams"] if s.get("codec_type") == "audio"]
    return {
        "duration": float(data["format"].get("duration", 0)),
        "size_bytes": int(data["format"].get("size", 0)),
        "video": {
            "width": video.get("width") if video else None,
            "height": video.get("height") if video else None,
            "frame_rate": video.get("r_frame_rate") if video else None,
            "frames": video.get("nb_frames") if video else None,
        },
        "audio_streams": len(audio),
    }


def black_intervals(path: Path, ffmpeg: str) -> list[dict[str, float]]:
    result = run(
        [ffmpeg, "-hide_banner", "-i", str(path), "-vf", "blackdetect=d=0.10:pix_th=0.10", "-an", "-f", "null", "-"]
    )
    pattern = re.compile(r"black_start:(?P<start>[\d.]+) black_end:(?P<end>[\d.]+) black_duration:(?P<duration>[\d.]+)")
    return [{key: float(value) for key, value in match.groupdict().items()} for match in pattern.finditer(result.stderr)]


def loudness(path: Path, ffmpeg: str, has_audio: bool) -> dict[str, float | None] | None:
    if not has_audio:
        return None
    result = run([ffmpeg, "-hide_banner", "-i", str(path), "-filter_complex", "ebur128=peak=true", "-f", "null", "-"])
    summary = result.stderr.rsplit("Summary:", 1)[-1]
    fields = {
        "integrated_lufs": r"I:\s*(-?[\d.]+) LUFS",
        "loudness_range_lu": r"LRA:\s*(-?[\d.]+) LU",
        "true_peak_dbfs": r"Peak:\s*(-?[\d.]+) dBFS",
    }
    values: dict[str, float | None] = {}
    for key, pattern in fields.items():
        match = re.search(pattern, summary)
        values[key] = float(match.group(1)) if match else None
    return values


def scene_gaps(path: Path, ffmpeg: str, duration: float, threshold: float, minimum_gap: float) -> tuple[list[float], list[dict[str, float]]]:
    expression = f"select='gt(scene,{threshold})',showinfo"
    result = run([ffmpeg, "-hide_banner", "-i", str(path), "-vf", expression, "-an", "-f", "null", "-"])
    cuts = sorted({float(value) for value in re.findall(r"pts_time:([\d.]+)", result.stderr)})
    points = [0.0, *[cut for cut in cuts if 0 < cut < duration], duration]
    gaps = []
    for start, end in zip(points, points[1:]):
        if end - start >= minimum_gap:
            gaps.append({"start": round(start, 3), "end": round(end, 3), "duration": round(end - start, 3)})
    return cuts, gaps


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--scene-threshold", type=float, default=0.35)
    parser.add_argument("--long-gap", type=float, default=8.0)
    parser.add_argument("--ffmpeg", default=shutil.which("ffmpeg") or "ffmpeg")
    parser.add_argument("--ffprobe", default=shutil.which("ffprobe") or "ffprobe")
    args = parser.parse_args()

    metadata = probe(args.video, args.ffprobe)
    cuts, gaps = scene_gaps(
        args.video, args.ffmpeg, float(metadata["duration"]), args.scene_threshold, args.long_gap
    )
    report = {
        "file": str(args.video.resolve()),
        "metadata": metadata,
        "loudness": loudness(args.video, args.ffmpeg, bool(metadata["audio_streams"])),
        "black_intervals": black_intervals(args.video, args.ffmpeg),
        "scene_cut_count": len(cuts),
        "long_no_cut_intervals": gaps,
        "notes": [
            "Scene detection is a review aid; camera motion and crop animation may not create a detected cut.",
            "Report final LUFS only from the exported mix that will be delivered.",
        ],
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
        print(args.output)
    else:
        print(rendered)


if __name__ == "__main__":
    main()
