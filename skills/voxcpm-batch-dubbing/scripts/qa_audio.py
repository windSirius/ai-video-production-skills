#!/usr/bin/env python3
"""Inspect generated audio with ffprobe and ffmpeg and emit JSON."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, capture_output=True, text=True)


def parse_number(value: str) -> float | None:
    if value.lower() == "-inf":
        return float("-inf")
    try:
        return float(value)
    except ValueError:
        return None


def inspect_audio(path: Path, noise: str, silence_duration: float) -> dict:
    probe = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=codec_name,sample_rate,channels,bits_per_sample",
            "-show_entries",
            "format=duration,size",
            "-of",
            "json",
            str(path),
        ]
    )
    metadata = json.loads(probe.stdout)
    streams = metadata.get("streams", [])
    audio_stream = streams[0] if streams else {}
    fmt = metadata.get("format", {})

    analysis = run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i",
            str(path),
            "-af",
            f"silencedetect=noise={noise}:d={silence_duration},astats=metadata=1:reset=0",
            "-f",
            "null",
            "-",
        ]
    )
    diagnostics = analysis.stderr
    peak_values = re.findall(r"Peak level dB:\s*([-+\w.]+)", diagnostics)
    peak_counts = re.findall(r"(?:Abs )?Peak count:\s*([-+\w.]+)", diagnostics)
    silence_events = [
        {
            "end": float(end),
            "duration": float(duration),
        }
        for end, duration in re.findall(
            r"silence_end:\s*([0-9.]+)\s*\|\s*silence_duration:\s*([0-9.]+)",
            diagnostics,
        )
    ]

    duration = float(fmt.get("duration", 0) or 0)
    peak_level = parse_number(peak_values[-1]) if peak_values else None
    peak_count = parse_number(peak_counts[-1]) if peak_counts else None
    warnings: list[str] = []
    if duration <= 0:
        warnings.append("non-positive duration")
    if not audio_stream:
        warnings.append("no audio stream")
    if peak_level is not None and peak_level >= -0.01 and (peak_count or 0) > 10:
        warnings.append("possible sustained clipping")
    if any(event["duration"] >= 2.5 for event in silence_events):
        warnings.append("silence of at least 2.5 seconds")

    return {
        "path": str(path.resolve()),
        "duration_seconds": duration,
        "size_bytes": int(fmt.get("size", 0) or 0),
        "codec": audio_stream.get("codec_name"),
        "sample_rate": int(audio_stream.get("sample_rate", 0) or 0),
        "channels": audio_stream.get("channels"),
        "bits_per_sample": audio_stream.get("bits_per_sample"),
        "peak_level_db": peak_level,
        "peak_count": peak_count,
        "silence_events": silence_events,
        "warnings": warnings,
        "status": "ok" if not warnings else "review",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", nargs="+", type=Path)
    parser.add_argument("--noise", default="-45dB")
    parser.add_argument("--silence-duration", type=float, default=0.8)
    args = parser.parse_args()

    missing_tools = [name for name in ("ffprobe", "ffmpeg") if not shutil.which(name)]
    if missing_tools:
        print(json.dumps({"error": f"missing tools: {', '.join(missing_tools)}"}))
        return 2

    results = []
    failed = False
    for path in args.audio:
        try:
            if not path.is_file():
                raise FileNotFoundError(path)
            results.append(inspect_audio(path, args.noise, args.silence_duration))
        except Exception as exc:  # Report every file in one run.
            failed = True
            results.append({"path": str(path), "status": "error", "error": str(exc)})

    print(json.dumps(results, ensure_ascii=False, indent=2, allow_nan=True))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
