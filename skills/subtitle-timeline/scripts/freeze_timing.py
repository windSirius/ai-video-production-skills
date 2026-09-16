#!/usr/bin/env python3
"""Freeze an approved SRT into one integer-frame timing contract."""

from __future__ import annotations

import argparse
import json
import subprocess
import wave
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP
from pathlib import Path

from audit_srt import release_status, validate_script_manifest
from srt_utils import parse_srt, sha256


def load_object(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def write_object(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def duration_seconds(path: Path) -> Decimal:
    try:
        with wave.open(str(path), "rb") as handle:
            return Decimal(handle.getnframes()) / Decimal(handle.getframerate())
    except (wave.Error, EOFError):
        completed = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return Decimal(completed.stdout.strip())


def frame_at(milliseconds: int, fps_num: int, fps_den: int, policy: str, is_end: bool) -> int:
    value = Decimal(milliseconds) * Decimal(fps_num) / (Decimal(1000) * Decimal(fps_den))
    if policy == "nearest":
        rounding = ROUND_HALF_UP
    elif policy == "cover":
        rounding = ROUND_CEILING if is_end else ROUND_FLOOR
    else:
        raise ValueError(f"unknown frame rounding policy: {policy}")
    return int(value.to_integral_value(rounding=rounding))


def verify_release(audio: dict, voice: dict, master: Path, canonical: Path) -> None:
    valid, errors = release_status(audio, voice, canonical, master)
    if not valid:
        raise ValueError("audio release chain is invalid: " + "; ".join(errors))


def freeze(args: argparse.Namespace) -> tuple[dict, dict, dict]:
    audit = load_object(args.audit)
    script = load_object(args.script_manifest)
    audio = load_object(args.audio_manifest)
    voice = load_object(args.voice_release)
    load_object(args.style)
    if audit.get("status") != "pass" or audit.get("state") != "candidate_final":
        raise ValueError("subtitle audit must pass as candidate_final")
    if audit.get("srt_sha256") != sha256(args.srt):
        raise ValueError("subtitle audit does not bind the current SRT")
    if audit.get("canonical_sha256") != sha256(args.canonical):
        raise ValueError("subtitle audit does not bind the current canonical text")
    if audit.get("script_manifest_sha256") != sha256(args.script_manifest):
        raise ValueError("subtitle audit does not bind the current script manifest")
    if audit.get("audio_manifest_sha256") != sha256(args.audio_manifest):
        raise ValueError("subtitle audit does not bind the current audio manifest")
    if audit.get("voice_release_sha256") != sha256(args.voice_release):
        raise ValueError("subtitle audit does not bind the current voice release")
    if audit.get("style_sha256") != sha256(args.style):
        raise ValueError("subtitle audit does not bind the required project style")
    script_errors = validate_script_manifest(script, args.canonical)
    if script_errors:
        raise ValueError("script manifest is invalid: " + "; ".join(script_errors))
    if not args.reviewer.strip() or not args.approval_ref.strip():
        raise ValueError("reviewer and approval_ref are required")
    master = Path(str(audio.get("master_path", ""))).expanduser()
    if not master.is_file():
        raise ValueError("bound narration master is missing")
    verify_release(audio, voice, master, args.canonical)
    captions = parse_srt(args.srt)
    if not captions:
        raise ValueError("cannot freeze an empty SRT")
    if args.fps_num <= 0 or args.fps_den <= 0:
        raise ValueError("FPS numerator and denominator must be positive")
    audio_duration = duration_seconds(master)
    last_end = Decimal(captions[-1].end_ms) / Decimal(1000)
    tolerance = Decimal(args.tail_tolerance_ms) / Decimal(1000)
    if last_end - audio_duration > tolerance:
        raise ValueError("final caption extends beyond the released audio tolerance")
    if args.out_seconds is not None:
        clock_duration = Decimal(args.out_seconds)
        if clock_duration < audio_duration or clock_duration < last_end:
            raise ValueError("explicit out point cannot truncate released audio or final caption")
    else:
        clock_duration = max(audio_duration, last_end)

    cue_rows = []
    for index, cue in enumerate(captions, start=1):
        start_frame = frame_at(cue.start_ms, args.fps_num, args.fps_den, args.rounding, False)
        end_frame = frame_at(cue.end_ms, args.fps_num, args.fps_den, args.rounding, True)
        if end_frame <= start_frame:
            end_frame = start_frame + 1
        cue_rows.append(
            {
                "cue_id": f"S{index:04d}",
                "start_ms": cue.start_ms,
                "end_ms": cue.end_ms,
                "start_frame": start_frame,
                "end_frame": end_frame,
                "text": cue.text,
            }
        )
    fps = Decimal(args.fps_num) / Decimal(args.fps_den)
    total_frames = int((clock_duration * fps).to_integral_value(rounding=ROUND_CEILING))
    total_frames = max(total_frames, max(row["end_frame"] for row in cue_rows))
    timestamp = args.approved_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    cues = {
        "schema_version": "subtitle_cues_frames_v1",
        "srt_sha256": sha256(args.srt),
        "interval_semantics": "[start_frame,end_frame)",
        "fps_num": args.fps_num,
        "fps_den": args.fps_den,
        "frame_rounding_policy": args.rounding,
        "cue_count": len(cue_rows),
        "cues": cue_rows,
    }
    contract = {
        "schema_version": "timing_contract_v1",
        "status": "frozen",
        "audio_master_path": str(master.resolve()),
        "audio_master_sha256": sha256(master),
        "canonical_sha256": sha256(args.canonical),
        "script_manifest_sha256": sha256(args.script_manifest),
        "style_sha256": sha256(args.style),
        "final_srt_sha256": sha256(args.srt),
        "fps_num": args.fps_num,
        "fps_den": args.fps_den,
        "frame_rounding_policy": args.rounding,
        "interval_semantics": "[start_frame,end_frame)",
        "audio_duration_seconds": float(audio_duration),
        "clock_duration_seconds": float(clock_duration),
        "total_frames": total_frames,
        "cue_count": len(cue_rows),
        "approved_by": args.reviewer,
        "approval_ref": args.approval_ref,
        "approved_at": timestamp,
    }
    return contract, cues, {
        "schema_version": "final_srt_manifest_v1",
        "state": "final_frozen",
        "downstream_allowed": True,
        "srt_path": str(args.srt.resolve()),
        "srt_sha256": sha256(args.srt),
        "canonical_path": str(args.canonical.resolve()),
        "canonical_sha256": sha256(args.canonical),
        "script_manifest_sha256": sha256(args.script_manifest),
        "style_sha256": sha256(args.style),
        "audio_master_sha256": sha256(master),
        "audio_manifest_sha256": sha256(args.audio_manifest),
        "voice_release_sha256": sha256(args.voice_release),
        "subtitle_qa_sha256": sha256(args.audit),
        "approval_ref": args.approval_ref,
        "approved_by": args.reviewer,
        "approved_at": timestamp,
        "total_frames": total_frames,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--srt", type=Path, required=True)
    parser.add_argument("--canonical", type=Path, required=True)
    parser.add_argument("--script-manifest", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--audio-manifest", type=Path, required=True)
    parser.add_argument("--voice-release", type=Path, required=True)
    parser.add_argument("--style", type=Path, required=True)
    parser.add_argument("--fps-num", type=int, required=True)
    parser.add_argument("--fps-den", type=int, default=1)
    parser.add_argument("--rounding", choices=("nearest", "cover"), default="nearest")
    parser.add_argument("--tail-tolerance-ms", type=int, default=100)
    parser.add_argument("--out-seconds")
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--approval-ref", required=True)
    parser.add_argument("--approved-at")
    parser.add_argument("--timing-output", type=Path, required=True)
    parser.add_argument("--cues-output", type=Path, required=True)
    parser.add_argument("--manifest-output", type=Path, required=True)
    args = parser.parse_args()
    if args.tail_tolerance_ms < 0:
        parser.error("tail tolerance must be non-negative")
    try:
        contract, cues, manifest = freeze(args)
        write_object(args.timing_output, contract)
        write_object(args.cues_output, cues)
        manifest["timing_contract_path"] = str(args.timing_output.resolve())
        manifest["timing_contract_sha256"] = sha256(args.timing_output)
        manifest["cues_frames_path"] = str(args.cues_output.resolve())
        manifest["cues_frames_sha256"] = sha256(args.cues_output)
        write_object(args.manifest_output, manifest)
    except (OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"status": "fail", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
