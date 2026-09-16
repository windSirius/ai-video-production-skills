#!/usr/bin/env python3
"""Extract exact frames around client-supplied timecodes for before/after QA."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path


def run(command: list[str]) -> str:
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.strip())
    return result.stdout


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=Path)
    parser.add_argument("--time", type=float, action="append", required=True, help="Seconds; repeat as needed")
    parser.add_argument("--radius-frames", type=int, default=1)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--ffmpeg", default=shutil.which("ffmpeg") or "ffmpeg")
    parser.add_argument("--ffprobe", default=shutil.which("ffprobe") or "ffprobe")
    args = parser.parse_args()
    if args.radius_frames < 0 or any(value < 0 for value in args.time):
        parser.error("times and radius must be nonnegative")
    video = args.video.expanduser().resolve()
    data = json.loads(run([args.ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=avg_frame_rate,nb_frames", "-of", "json", str(video)]))
    stream = data["streams"][0]
    fps = Fraction(stream["avg_frame_rate"])
    total = int(stream["nb_frames"]) if str(stream.get("nb_frames", "")).isdigit() else None
    frames = sorted({
        max(0, min(total - 1, round(value * float(fps)) + delta) if total else round(value * float(fps)) + delta)
        for value in args.time
        for delta in range(-args.radius_frames, args.radius_frames + 1)
    })
    output = args.output_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    expression = "+".join(f"eq(n\\,{frame})" for frame in frames)
    pattern = output / "frame_%06d.png"
    run([args.ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(video), "-vf", f"select='{expression}'", "-fps_mode", "passthrough", str(pattern)])
    extracted = sorted(output.glob("frame_*.png"))
    if len(extracted) != len(frames):
        raise RuntimeError(f"expected {len(frames)} frames, extracted {len(extracted)}")
    records = []
    for sequence, (frame, path) in enumerate(zip(frames, extracted), start=1):
        target = output / f"n{frame:08d}.png"
        path.replace(target)
        records.append({"sequence": sequence, "frame": frame, "seconds": float(Fraction(frame, 1) / fps), "path": str(target), "sha256": sha256_file(target)})
    manifest = {"video": str(video), "video_sha256": sha256_file(video), "fps": str(fps), "radius_frames": args.radius_frames, "requested_times": args.time, "frames": records}
    manifest_path = output / "feedback_frames_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
