#!/usr/bin/env python3
"""Freeze the full-span frame clock from Jianying's verified live narration end."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from math import ceil
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def timecode_to_frames(value: str, fps: int) -> int:
    fields = value.split(":")
    if len(fields) != 4 or not all(field.isdigit() for field in fields):
        raise ValueError(f"project_timecode must use HH:MM:SS:FF: {value}")
    hours, minutes, seconds, frames = (int(field) for field in fields)
    if minutes >= 60 or seconds >= 60 or frames >= fps:
        raise ValueError(f"invalid {fps}fps project_timecode: {value}")
    return ((hours * 60 + minutes) * 60 + seconds) * fps + frames


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observation", required=True, help="Fresh verified Jianying live-state JSON")
    parser.add_argument("--output", required=True, help="timing_contract.json destination")
    parser.add_argument("--fps", type=int, default=60)
    parser.add_argument("--expected-narration-clips", type=int)
    parser.add_argument("--narration-seconds", type=float)
    parser.add_argument("--caption-final-end-seconds", type=float)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if args.fps <= 0:
        raise ValueError("fps must be positive")
    observation_path = Path(args.observation).expanduser().resolve()
    observation = json.loads(observation_path.read_text(encoding="utf-8"))
    if observation.get("authoritative_timeline") is not True:
        raise ValueError("observation must identify the authoritative timeline")
    if args.expected_narration_clips is not None:
        actual = observation.get("narration_clip_count")
        if actual != args.expected_narration_clips:
            raise ValueError(
                f"narration_clip_count={actual!r}, expected {args.expected_narration_clips}"
            )
    timecode = str(observation.get("narration_end_timecode", ""))
    if not timecode:
        raise ValueError(
            "live observation requires narration_end_timecode measured from the narration lane; "
            "project_timecode may include longer picture or BGM media"
        )
    target_frame_count = timecode_to_frames(timecode, args.fps)
    if target_frame_count <= 0:
        raise ValueError("live narration end must be greater than zero")

    contract = {
        "fps": args.fps,
        "target_frame_count": target_frame_count,
        "target_seconds": target_frame_count / args.fps,
        "target_timecode": timecode,
        "last_picture_frame_exclusive": target_frame_count,
        "clock_source": "verified_live_jianying_narration_end",
        "clock_policy": (
            "Freeze after every narration WAV is visible in order. "
            "Picture and BGM masters derive from this live integer-frame end, "
            "not from the arithmetic sum of source-file durations."
        ),
        "source_live_observation": {
            "path": str(observation_path),
            "sha256": sha256_file(observation_path),
            "draft_name": observation.get("draft_name"),
            "timeline_name": observation.get("timeline_name"),
            "narration_clip_count": observation.get("narration_clip_count"),
            "project_timecode": observation.get("project_timecode"),
            "narration_end_timecode": timecode,
        },
    }
    if args.narration_seconds is not None:
        contract["source_wav_duration_sum_seconds"] = args.narration_seconds
    if args.caption_final_end_seconds is not None:
        contract["caption_final_end_seconds"] = args.caption_final_end_seconds
        caption_end_frame_exclusive = ceil(args.caption_final_end_seconds * args.fps)
        if caption_end_frame_exclusive > target_frame_count + 1:
            raise ValueError(
                "caption final end exceeds the measured narration end by more than one frame"
            )
        tail_hold_frames = max(0, target_frame_count - caption_end_frame_exclusive)
        contract["caption_final_frame_exclusive"] = caption_end_frame_exclusive
        contract["caption_tail_hold_frames"] = tail_hold_frames
        contract["caption_tail_hold_seconds"] = tail_hold_frames / args.fps
        contract["caption_clock_policy"] = (
            "Caption cues govern sentence-level picture boundaries. "
            "Any nonnegative remainder through the narration end is an intentional final-picture hold."
        )

    output = Path(args.output).expanduser().resolve()
    if output.exists() and not args.force:
        raise ValueError(f"refusing to overwrite existing timing contract without --force: {output}")
    if output.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup = output.with_name(f"{output.stem}.superseded-{stamp}{output.suffix}")
        shutil.copy2(output, backup)
        contract["supersedes"] = {
            "path": str(output),
            "sha256": sha256_file(output),
            "recoverable_backup": str(backup),
        }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
