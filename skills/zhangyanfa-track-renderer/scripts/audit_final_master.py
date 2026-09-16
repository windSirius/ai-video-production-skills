#!/usr/bin/env python3
"""Probe, decode and bind the actual final video candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from fractions import Fraction
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def probe(path: Path, ffprobe: str) -> dict[str, Any]:
    result = run([
        ffprobe, "-v", "error", "-count_frames", "-show_streams", "-show_format",
        "-of", "json", str(path),
    ])
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "ffprobe failed")
    return json.loads(result.stdout)


def fps_value(value: object) -> float:
    try:
        return float(Fraction(str(value)))
    except (ValueError, ZeroDivisionError):
        return 0.0


def black_intervals(path: Path, ffmpeg: str) -> list[dict[str, float]]:
    result = run([
        ffmpeg, "-hide_banner", "-nostdin", "-i", str(path),
        "-vf", "blackdetect=d=0.02:pix_th=0.10", "-an", "-f", "null", "-",
    ])
    pattern = re.compile(r"black_start:([0-9.]+) black_end:([0-9.]+) black_duration:([0-9.]+)")
    return [
        {"start": float(a), "end": float(b), "duration": float(c)}
        for a, b, c in pattern.findall(result.stderr)
    ]


def loudness(path: Path, ffmpeg: str) -> dict[str, Any] | None:
    result = run([
        ffmpeg, "-hide_banner", "-nostdin", "-i", str(path),
        "-af", "loudnorm=I=-23:TP=-2:LRA=11:print_format=json", "-vn", "-f", "null", "-",
    ])
    matches = re.findall(r"\{\s*\"input_i\".*?\}", result.stderr, flags=re.S)
    if not matches:
        return None
    try:
        return json.loads(matches[-1])
    except json.JSONDecodeError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=Path)
    parser.add_argument("--width", type=int, required=True)
    parser.add_argument("--height", type=int, required=True)
    parser.add_argument("--fps", type=float, required=True)
    parser.add_argument("--frames", type=int, required=True)
    parser.add_argument("--audio-streams", type=int, default=1)
    parser.add_argument("--manual-review", type=Path, required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--fail-on-black", action="store_true")
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()

    errors: list[str] = []
    data = probe(args.video, args.ffprobe)
    streams = data.get("streams", [])
    videos = [row for row in streams if row.get("codec_type") == "video"]
    audios = [row for row in streams if row.get("codec_type") == "audio"]
    if len(videos) != 1:
        errors.append("exactly one video stream required")
        video = {}
    else:
        video = videos[0]
        if int(video.get("width", 0)) != args.width or int(video.get("height", 0)) != args.height:
            errors.append("resolution mismatch")
        actual_fps = fps_value(video.get("avg_frame_rate") or video.get("r_frame_rate"))
        if abs(actual_fps - args.fps) > 0.01:
            errors.append("fps mismatch")
        frame_count = int(video.get("nb_read_frames") or video.get("nb_frames") or 0)
        if frame_count != args.frames:
            errors.append(f"frame count mismatch: {frame_count} != {args.frames}")
    if len(audios) != args.audio_streams:
        errors.append(f"audio stream mismatch: {len(audios)} != {args.audio_streams}")

    decode = run([args.ffmpeg, "-v", "error", "-nostdin", "-i", str(args.video), "-f", "null", "-"])
    if decode.returncode:
        errors.append("full decode failed")
    blacks = black_intervals(args.video, args.ffmpeg)
    if args.fail_on_black and blacks:
        errors.append("black intervals detected")

    manual: dict[str, Any] = json.loads(args.manual_review.read_text(encoding="utf-8"))
    if str(manual.get("video_sha256", "")) != sha256_file(args.video):
        errors.append("manual review does not bind current video SHA")
    for key in ("seam_review", "green_residue_review", "subtitle_review", "narration_tail_review", "bc_presence_review"):
        if str(manual.get(key, "")).lower() != "pass":
            errors.append(f"manual review {key} must pass")

    report = {
        "status": "PASS" if not errors else "FAIL",
        "path": str(args.video.resolve()),
        "sha256": sha256_file(args.video),
        "video_stream": video,
        "audio_stream_count": len(audios),
        "full_decode": decode.returncode == 0,
        "black_intervals": blacks,
        "loudness": loudness(args.video, args.ffmpeg) if audios else None,
        "manual_review": manual,
        "errors": errors,
    }
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
