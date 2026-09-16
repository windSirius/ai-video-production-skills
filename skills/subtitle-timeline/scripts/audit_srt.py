#!/usr/bin/env python3
"""Audit an offline SRT against canonical text and narration release state."""

from __future__ import annotations

import argparse
import difflib
import json
import re
from pathlib import Path

from srt_utils import normalized_lexical, parse_srt, sha256, visible_chars


PUNCT_ONLY_RE = re.compile(r"^[\s，。！？；：、,.!?;:…—\-~～·「」『』“”‘’《》〈〉（）()【】\[\]]+$")
QUOTE_PAIRS = (("「", "」"), ("『", "』"), ("“", "”"), ("‘", "’"), ("《", "》"), ("〈", "〉"))
REQUIRED_MACHINE_CHECKS = ("lexical", "signal", "joins", "pronunciation", "full_decode")


def load_object(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def validate_script_manifest(script: dict, canonical: Path) -> list[str]:
    errors: list[str] = []
    if script.get("schema_version") != "script_manifest_v1":
        errors.append("script manifest schema is not script_manifest_v1")
    if script.get("state") != "approved":
        errors.append("script manifest is not approved")
    canonical_sha = sha256(canonical)
    if script.get("canonical_sha256") != canonical_sha:
        errors.append("script manifest canonical SHA does not match")
    bound = Path(str(script.get("canonical_path", ""))).expanduser()
    if not bound.is_file() or bound.resolve() != canonical.resolve() or sha256(bound) != canonical_sha:
        errors.append("script manifest does not bind the current canonical path")
    for field in ("approved_by", "approval_ref", "approved_at"):
        if not str(script.get(field, "")).strip():
            errors.append(f"script manifest requires {field}")
    return errors


def release_status(audio: dict, voice: dict | None, canonical: Path, master_path: Path) -> tuple[bool, list[str]]:
    errors: list[str] = []
    canonical_sha = sha256(canonical)
    actual_master_sha = sha256(master_path) if master_path.is_file() else None
    if audio.get("schema_version") != "audio_release_v2":
        errors.append("audio manifest schema is not audio_release_v2")
    released = audio.get("state") == "released" and audio.get("release_ready") is True
    if not released:
        errors.append("audio manifest is not released")
    if audio.get("canonical_sha256") != canonical_sha:
        errors.append("audio manifest canonical SHA does not match")
    if actual_master_sha is None or audio.get("master_sha256") != actual_master_sha:
        errors.append("audio manifest does not bind the actual master")
    checks = audio.get("machine_checks")
    if not isinstance(checks, dict) or any(str(checks.get(name, "")).lower() != "pass" for name in REQUIRED_MACHINE_CHECKS):
        errors.append("audio manifest lacks complete passing machine checks")
    machine_qa_path = Path(str(audio.get("machine_qa_path", ""))).expanduser()
    if not machine_qa_path.is_file() or audio.get("machine_qa_sha256") != sha256(machine_qa_path):
        errors.append("audio manifest machine QA path/SHA is invalid")
    else:
        try:
            machine_qa = load_object(machine_qa_path)
            qa_checks = machine_qa.get("machine_checks")
            if (
                machine_qa.get("status") != "pass"
                or machine_qa.get("canonical_sha256") != canonical_sha
                or machine_qa.get("master_sha256") != actual_master_sha
                or not isinstance(qa_checks, dict)
                or any(str(qa_checks.get(name, "")).lower() != "pass" for name in REQUIRED_MACHINE_CHECKS)
            ):
                errors.append("bound machine QA is incomplete or mismatched")
        except (OSError, ValueError, json.JSONDecodeError):
            errors.append("bound machine QA cannot be validated")
    probe = audio.get("audio_probe")
    if not isinstance(probe, dict) or probe.get("status") != "pass" or probe.get("master_sha256") != actual_master_sha:
        errors.append("audio manifest lacks a bound passing actual-audio probe")
    audition = audio.get("human_audition")
    if not isinstance(audition, dict):
        errors.append("audio manifest human audition is missing")
        audition = {}
    if (
        audition.get("status") != "approved"
        or audition.get("full_speed_1x_audition") is not True
        or audition.get("complete_master_audition") is not True
        or audition.get("approved_master_sha256") != actual_master_sha
    ):
        errors.append("audio manifest lacks complete bound 1x human approval")
    audition_path = Path(str(audition.get("receipt_path", ""))).expanduser()
    audition_sha = str(audition.get("receipt_sha256", ""))
    if not audition_path.is_file() or audition_sha != sha256(audition_path):
        errors.append("audio human audition receipt path/SHA is invalid")
    if voice is None or voice.get("status") != "approved" or voice.get("release_ready") is not True:
        errors.append("voice release receipt is missing or not approved")
    else:
        if voice.get("schema_version") != "voice_release_v2":
            errors.append("voice release schema is not voice_release_v2")
        if voice.get("master_sha256") != actual_master_sha:
            errors.append("voice release SHA does not match audio master SHA")
        if voice.get("canonical_sha256") != canonical_sha:
            errors.append("voice release canonical SHA does not match")
        if voice.get("full_speed_1x_audition") is not True or voice.get("complete_master_audition") is not True:
            errors.append("voice release lacks complete 1x audition confirmation")
        if voice.get("audition_receipt_sha256") != audition_sha:
            errors.append("voice release does not bind the audio audition receipt")
        for field in ("reviewer", "approval_ref", "approved_at"):
            if not str(voice.get(field, "")).strip():
                errors.append(f"voice release requires {field}")
    return not errors, errors


def forbidden_terminal(text: str, style: dict) -> str | None:
    forbidden = set(str(style.get("forbidden_terminal_punctuation", "")))
    candidate = text.rstrip()
    closers = set(str(style.get("trailing_closing_marks", "")))
    while candidate and candidate[-1] in closers:
        candidate = candidate[:-1].rstrip()
    return candidate[-1] if candidate and candidate[-1] in forbidden else None


def audit(args: argparse.Namespace) -> dict:
    captions = parse_srt(args.srt)
    canonical_text = args.canonical.read_text(encoding="utf-8-sig")
    script = load_object(args.script_manifest)
    audio = load_object(args.audio_manifest)
    voice = load_object(args.voice_release) if args.voice_release else None
    style = load_object(args.style)
    actual_srt = normalized_lexical("".join(caption.text for caption in captions))
    actual_canonical = normalized_lexical(canonical_text)
    script_errors = validate_script_manifest(script, args.canonical)

    master_path = Path(str(audio.get("master_path", ""))).expanduser()
    release_ok, release_errors = release_status(audio, voice, args.canonical, master_path)

    failures: dict[str, object] = {}
    if script_errors:
        failures["script_manifest"] = script_errors
    if actual_srt != actual_canonical:
        matcher = difflib.SequenceMatcher(None, actual_canonical, actual_srt, autojunk=False)
        failures["canonical_coverage"] = [
            {
                "operation": tag,
                "canonical": actual_canonical[i1:i2],
                "srt": actual_srt[j1:j2],
            }
            for tag, i1, i2, j1, j2 in matcher.get_opcodes()
            if tag != "equal"
        ]
    duplicates = [
        index + 1
        for index in range(1, len(captions))
        if " ".join(captions[index - 1].text.split()) == " ".join(captions[index].text.split())
    ]
    if duplicates:
        failures["adjacent_duplicates"] = duplicates
    invalid_duration = [i for i, cue in enumerate(captions, 1) if cue.end_ms <= cue.start_ms]
    if invalid_duration:
        failures["non_positive_duration"] = invalid_duration
    overlaps = [
        i + 1 for i in range(1, len(captions)) if captions[i].start_ms < captions[i - 1].end_ms
    ]
    if overlaps:
        failures["unapproved_overlaps"] = overlaps
    empty_or_punct = [
        i for i, cue in enumerate(captions, 1) if not cue.text or PUNCT_ONLY_RE.fullmatch(cue.text)
    ]
    if empty_or_punct:
        failures["empty_or_punctuation_only"] = empty_or_punct
    joined = "".join(cue.text for cue in captions)
    quote_imbalance = [
        {"open": left, "close": right, "open_count": joined.count(left), "close_count": joined.count(right)}
        for left, right in QUOTE_PAIRS
        if joined.count(left) != joined.count(right)
    ]
    if quote_imbalance:
        failures["quote_imbalance"] = quote_imbalance
    terminal = [
        {"entry": i, "punctuation": found, "text": cue.text}
        for i, cue in enumerate(captions, 1)
        if style and (found := forbidden_terminal(cue.text, style))
    ]
    if terminal:
        failures["forbidden_terminal_punctuation"] = terminal
    if args.requested_state == "candidate_final" and not release_ok:
        failures["audio_release"] = release_errors

    warnings: dict[str, object] = {}
    max_chars = int(style.get("max_visible_chars_warning", 24))
    max_cps = float(style.get("max_cps_warning", 12.0))
    long_entries = [
        {"entry": i, "visible_chars": visible_chars(cue.text)}
        for i, cue in enumerate(captions, 1)
        if visible_chars(cue.text) > max_chars
    ]
    fast_entries = []
    for i, cue in enumerate(captions, 1):
        duration = max((cue.end_ms - cue.start_ms) / 1000, 0.001)
        cps = visible_chars(cue.text) / duration
        if cps > max_cps:
            fast_entries.append({"entry": i, "cps": round(cps, 2)})
    if long_entries:
        warnings["long_entries"] = long_entries
    if fast_entries:
        warnings["fast_entries"] = fast_entries
    if args.requested_state == "provisional" and not release_ok:
        warnings["audio_release"] = release_errors

    raw_match = None
    if args.raw_srt:
        raw = parse_srt(args.raw_srt)
        raw_match = normalized_lexical("".join(cue.text for cue in raw)) == actual_srt

    passed = not failures
    return {
        "status": "pass" if passed else "fail",
        "state": args.requested_state if passed else "blocked",
        "downstream_allowed": False,
        "srt_path": str(args.srt.resolve()),
        "srt_sha256": sha256(args.srt),
        "canonical_path": str(args.canonical.resolve()),
        "canonical_sha256": sha256(args.canonical),
        "script_manifest_path": str(args.script_manifest.resolve()),
        "script_manifest_sha256": sha256(args.script_manifest),
        "audio_manifest_path": str(args.audio_manifest.resolve()),
        "audio_manifest_sha256": sha256(args.audio_manifest),
        "audio_master_sha256": audio.get("master_sha256"),
        "audio_master_path": str(master_path.resolve()) if master_path.is_file() else str(master_path),
        "voice_release_path": str(args.voice_release.resolve()) if args.voice_release else None,
        "voice_release_sha256": sha256(args.voice_release) if args.voice_release else None,
        "style_path": str(args.style.resolve()),
        "style_sha256": sha256(args.style),
        "entries": len(captions),
        "last_end_ms": captions[-1].end_ms if captions else 0,
        "audio_released": release_ok,
        "raw_srt_match": raw_match,
        "failures": failures,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--srt", type=Path, required=True)
    parser.add_argument("--canonical", type=Path, required=True)
    parser.add_argument("--script-manifest", type=Path, required=True)
    parser.add_argument("--audio-manifest", type=Path, required=True)
    parser.add_argument("--voice-release", type=Path)
    parser.add_argument("--raw-srt", type=Path)
    parser.add_argument("--style", type=Path, required=True)
    parser.add_argument("--requested-state", choices=("provisional", "candidate_final"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = audit(args)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "fail", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
