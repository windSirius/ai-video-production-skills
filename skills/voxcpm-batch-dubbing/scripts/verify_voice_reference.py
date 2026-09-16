"""Verify the user-pinned Foxjiu voice reference before loading any model."""
import argparse
import hashlib
import json
from pathlib import Path


def digest(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def binding(path):
    return {"path": str(Path(path).resolve()), "sha256": digest(path)}


def checked_binding(value):
    if not isinstance(value, dict) or not value.get("path") or not value.get("sha256"):
        raise ValueError("a path and SHA-256 binding are required")
    if digest(value["path"]) != value["sha256"]:
        raise ValueError("changed bound file: " + value["path"])
    return value


def verify(source_path, rule_path, phase="reference", smoke_review=None):
    rule = json.loads(Path(rule_path).read_text())
    source = json.loads(Path(source_path).read_text())
    failures = []
    config = source.get("generation_config", {})
    for label, path in (
        ("reference_audio", source.get("reference_audio")),
        ("prompt_wav_path", config.get("prompt_wav_path")),
        ("reference_wav_path", config.get("reference_wav_path")),
    ):
        try:
            if not path or digest(path) != rule["sha256"]:
                failures.append(label + ": audio does not match the user-pinned original")
        except OSError as exc:
            failures.append(label + ": " + str(exc))
    if source.get("reference_audio_sha256") != rule["sha256"]:
        failures.append("reference_audio_sha256 does not match the fixed reference")
    for label, value in (
        ("reference_transcript", source.get("reference_transcript")),
        ("prompt_text", config.get("prompt_text")),
    ):
        if value != rule["transcript"]:
            failures.append(label + ": text differs from the exact user transcript")
    if source.get("reference_rule_sha256") != digest(rule_path):
        failures.append("reference_rule_sha256 is missing or stale")
    smoke_binding = None
    canonical_binding = None
    if phase not in {"reference", "bulk", "repair"}:
        failures.append("unknown generation phase")
    if phase == "bulk" or smoke_review:
        try:
            if not smoke_review:
                raise ValueError("bulk generation requires an opening smoke-review receipt")
            smoke_binding = binding(smoke_review)
            smoke = json.loads(Path(smoke_review).read_text())
            if smoke.get("schema") != "voice_opening_smoke_v2" or smoke.get("status") != "PASS":
                raise ValueError("opening smoke review must pass")
            source_binding = checked_binding(smoke.get("source_manifest"))
            if source_binding != binding(source_path):
                raise ValueError("opening sample used another source manifest/configuration")
            checked_binding(smoke.get("sample_audio"))
            canonical_binding = checked_binding(smoke.get("canonical_text"))
            if source.get("canonical_text_sha256") != canonical_binding["sha256"]:
                raise ValueError("opening sample does not bind the generation canonical text")
            if not str(smoke.get("reviewer", "")).strip() or not str(smoke.get("notes", "")).strip():
                raise ValueError("opening review needs a reviewer and listening notes")
            for key in ("opening_prosody", "pause_naturalness", "pronunciation_hotspots", "listened_to_actual_sample"):
                if smoke.get("checks", {}).get(key) is not True:
                    raise ValueError("opening smoke review incomplete: " + key)
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            failures.append(str(exc))
    return {"passed": not failures, "failures": failures, "phase": phase,
            "reference_sha256": rule["sha256"],
            "rule_path": str(Path(rule_path).resolve()),
            "source_manifest": str(Path(source_path).resolve()),
            "source_manifest_binding": binding(source_path),
            "rule_binding": binding(rule_path),
            "smoke_review_binding": smoke_binding,
            "canonical_text_binding": canonical_binding}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--rule", type=Path, default=Path(__file__).resolve().parents[1] / "references/foxjiu-voice-reference.json")
    parser.add_argument("--phase", choices=("reference", "bulk", "repair"), default="reference")
    parser.add_argument("--smoke-review", type=Path)
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()
    try:
        result = verify(args.source_manifest, args.rule, args.phase, args.smoke_review)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        result = {"passed": False, "phase": args.phase, "failures": [str(exc)]}
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
