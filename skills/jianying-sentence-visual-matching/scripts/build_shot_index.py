#!/usr/bin/env python3
"""Sample videos into timestamped frames, contact sheets, and a TSV shot index."""

from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, text=True, capture_output=True)


def probe(path: Path, ffprobe: str) -> dict[str, object]:
    result = run(
        [
            ffprobe, "-v", "error", "-show_entries",
            "format=duration:stream=codec_type,width,height,r_frame_rate",
            "-of", "json", str(path),
        ]
    )
    data = json.loads(result.stdout)
    video = next(s for s in data["streams"] if s.get("codec_type") == "video")
    return {
        "duration": float(data["format"]["duration"]),
        "width": int(video["width"]),
        "height": int(video["height"]),
        "frame_rate": video.get("r_frame_rate", ""),
    }


def timestamps(duration: float, interval: float) -> list[float]:
    if duration <= 0:
        return []
    first = min(0.5, duration / 2)
    values = [first + i * interval for i in range(max(1, math.ceil((duration - first) / interval)))]
    values = [min(value, max(0.0, duration - 0.25)) for value in values]
    last = max(0.0, duration - 0.25)
    if not values or last - values[-1] > interval * 0.35:
        values.append(last)
    return sorted(set(round(value, 3) for value in values))


def make_sheet(frames: list[tuple[float, Path]], output: Path, columns: int, thumb_width: int) -> None:
    if not frames:
        return
    sample = Image.open(frames[0][1])
    thumb_height = round(sample.height * thumb_width / sample.width)
    label_height = 28
    rows = math.ceil(len(frames) / columns)
    sheet = Image.new("RGB", (columns * thumb_width, rows * (thumb_height + label_height)), "#111")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=18)
    for index, (timestamp, frame_path) in enumerate(frames):
        image = Image.open(frame_path).convert("RGB")
        image.thumbnail((thumb_width, thumb_height))
        x = (index % columns) * thumb_width
        y = (index // columns) * (thumb_height + label_height)
        sheet.paste(image, (x, y))
        draw.rectangle((x, y + thumb_height, x + thumb_width, y + thumb_height + label_height), fill="#111")
        draw.text((x + 8, y + thumb_height + 4), f"{timestamp:08.3f}s", fill="white", font=font)
    sheet.save(output, quality=90)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("videos", nargs="+", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--interval", type=float, default=6.0)
    parser.add_argument("--columns", type=int, default=5)
    parser.add_argument("--thumb-width", type=int, default=320)
    parser.add_argument("--ffmpeg", default=shutil.which("ffmpeg") or "ffmpeg")
    parser.add_argument("--ffprobe", default=shutil.which("ffprobe") or "ffprobe")
    args = parser.parse_args()

    if args.interval <= 0 or args.columns <= 0 or args.thumb_width <= 0:
        raise SystemExit("interval, columns, and thumb-width must be positive")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    index_rows: list[dict[str, object]] = []
    for video_number, video in enumerate(args.videos, 1):
        info = probe(video, args.ffprobe)
        clip_dir = args.output_dir / f"{video_number:02d}_{video.stem}"
        clip_dir.mkdir(parents=True, exist_ok=True)
        frames: list[tuple[float, Path]] = []
        for frame_number, timestamp in enumerate(timestamps(float(info["duration"]), args.interval), 1):
            frame = clip_dir / f"frame_{frame_number:04d}_{timestamp:010.3f}.jpg"
            run(
                [
                    args.ffmpeg, "-y", "-ss", f"{timestamp:.3f}", "-i", str(video),
                    "-frames:v", "1", "-q:v", "2", str(frame),
                ]
            )
            frames.append((timestamp, frame))
            index_rows.append(
                {
                    "source_file": str(video.resolve()),
                    "timestamp": f"{timestamp:.3f}",
                    "frame_path": str(frame.resolve()),
                    "duration": f"{info['duration']:.3f}",
                    "resolution": f"{info['width']}x{info['height']}",
                    "frame_rate": info["frame_rate"],
                    "characters": "",
                    "location": "",
                    "action": "",
                    "emotion": "",
                    "notes": "",
                }
            )
        make_sheet(frames, clip_dir / "contact_sheet.jpg", args.columns, args.thumb_width)

    fields = [
        "source_file", "timestamp", "frame_path", "duration", "resolution",
        "frame_rate", "characters", "location", "action", "emotion", "notes",
    ]
    with (args.output_dir / "shot_index.tsv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        writer.writerows(index_rows)
    print(f"indexed {len(args.videos)} videos and {len(index_rows)} frames in {args.output_dir}")


if __name__ == "__main__":
    main()
