#!/usr/bin/env python3
"""Create and validate the narration release state machine."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ALLOWED_TRANSITIONS = {
    "machine_verified": "awaiting_human_audition",
    "awaiting_human_audition": "released",
}
LEGAL_STATES = {
    "generating",
    "machine_verified",
    "awaiting_human_audition",
    "released",
    "repair_required",
}
REQUIRED_MACHINE_CHECKS = ("lexical", "signal", "joins", "pronunciation", "full_decode")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def require_current_master(manifest: dict[str, Any], override: Path | None = None) -> Path:
    master = override or Path(str(manifest.get("master_path", ""))).expanduser()
    if not master.is_file():
        raise ValueError(f"master does not exist: {master}")
    expected = str(manifest.get("master_sha256", "")).lower()
    actual = sha256(master)
    if not expected or actual != expected:
        raise ValueError("current master SHA does not match the machine-verified manifest")
    return master.resolve()


def probe_audio(master: Path) -> dict[str, Any]:
    missing = [name for name in ("ffprobe", "ffmpeg") if not shutil.which(name)]
    if missing:
        raise ValueError("required audio probe tools are missing: " + ", ".join(missing))
    try:
        probe = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream=codec_name,sample_rate,channels:format=duration",
                "-of",
                "json",
                str(master),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        metadata = json.loads(probe.stdout)
        streams = metadata.get("streams") or []
        duration = float((metadata.get("format") or {}).get("duration", 0) or 0)
        if not streams or duration <= 0:
            raise ValueError("audio probe found no decodable stream or non-positive duration")
        decoded = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(master), "-map", "0:a:0", "-f", "null", "-"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, json.JSONDecodeError, ValueError) as exc:
        detail = exc.stderr.strip() if isinstance(exc, subprocess.CalledProcessError) else str(exc)
        raise ValueError(f"actual narration master failed audio probe/decode: {detail}") from exc
    stream = streams[0]
    return {
        "status": "pass",
        "master_sha256": sha256(master),
        "duration_seconds": duration,
        "codec": stream.get("codec_name"),
        "sample_rate": int(stream.get("sample_rate", 0) or 0),
        "channels": int(stream.get("channels", 0) or 0),
        "full_decode_exit_code": decoded.returncode,
    }


def validate_machine_qa(canonical: Path, master: Path, machine_qa: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    qa = read_json(machine_qa)
    if str(qa.get("status", "")).lower() != "pass":
        raise ValueError("machine QA must have status=pass")
    checks = qa.get("machine_checks", {})
    if not isinstance(checks, dict):
        raise ValueError("machine_checks must be an object")
    missing = [name for name in REQUIRED_MACHINE_CHECKS if name not in checks]
    if missing:
        raise ValueError("machine QA is missing required checks: " + ", ".join(missing))
    failed = [name for name in REQUIRED_MACHINE_CHECKS if str(checks.get(name, "")).lower() != "pass"]
    if failed:
        raise ValueError("required machine checks must pass: " + ", ".join(failed))
    if str(qa.get("canonical_sha256", "")).lower() != sha256(canonical):
        raise ValueError("machine QA does not bind the current canonical text SHA")
    if str(qa.get("master_sha256", "")).lower() != sha256(master):
        raise ValueError("machine QA does not bind the actual narration master SHA")
    return qa, checks


def validate_audition_receipt(
    receipt_path: Path,
    master: Path,
    canonical_sha256: str,
) -> dict[str, Any]:
    receipt = read_json(receipt_path)
    if receipt.get("schema_version") != "human_audition_v1":
        raise ValueError("human audition receipt schema_version must be human_audition_v1")
    if receipt.get("status") != "approved":
        raise ValueError("human audition receipt must have status=approved")
    if receipt.get("full_speed_1x_audition") is not True:
        raise ValueError("human audition receipt must confirm full_speed_1x_audition=true")
    if receipt.get("complete_master_audition") is not True:
        raise ValueError("human audition receipt must confirm complete_master_audition=true")
    master_sha = sha256(master)
    if str(receipt.get("master_sha256", "")).lower() != master_sha:
        raise ValueError("human audition receipt does not bind the current master SHA")
    if str(receipt.get("canonical_sha256", "")).lower() != canonical_sha256:
        raise ValueError("human audition receipt does not bind the canonical SHA")
    receipt_master = Path(str(receipt.get("master_path", ""))).expanduser()
    if not receipt_master.is_file() or receipt_master.resolve() != master.resolve():
        raise ValueError("human audition receipt does not bind the current master path")
    for field in ("reviewer", "approval_ref", "approved_at"):
        if not str(receipt.get(field, "")).strip():
            raise ValueError(f"human audition receipt requires {field}")
    return receipt


def machine_verified(canonical: Path, master: Path, machine_qa: Path) -> dict[str, Any]:
    qa, checks = validate_machine_qa(canonical, master, machine_qa)
    audio_probe = probe_audio(master)
    timestamp = now_iso()
    return {
        "schema_version": "audio_release_v2",
        "state": "machine_verified",
        "release_ready": False,
        "canonical_path": str(canonical.resolve()),
        "canonical_sha256": sha256(canonical),
        "master_path": str(master.resolve()),
        "master_sha256": sha256(master),
        "machine_qa_path": str(machine_qa.resolve()),
        "machine_qa_sha256": sha256(machine_qa),
        "machine_checks": checks,
        "audio_probe": audio_probe,
        "human_audition": {
            "status": "not_started",
            "reviewer": None,
            "approval_ref": None,
            "approved_master_sha256": None,
        },
        "history": [{"state": "machine_verified", "at": timestamp}],
    }


def transition_to_audition(manifest: dict[str, Any]) -> dict[str, Any]:
    if manifest.get("state") != "machine_verified":
        raise ValueError("only machine_verified may enter awaiting_human_audition")
    validation = validate(manifest)
    if validation["status"] != "pass":
        raise ValueError("machine-verified manifest is invalid: " + "; ".join(validation["errors"]))
    result = deepcopy(manifest)
    result["state"] = "awaiting_human_audition"
    result["release_ready"] = False
    result["human_audition"] = {
        "status": "pending",
        "reviewer": None,
        "approval_ref": None,
        "approved_master_sha256": None,
    }
    result.setdefault("history", []).append({"state": "awaiting_human_audition", "at": now_iso()})
    return result


def release(
    manifest: dict[str, Any],
    master: Path,
    audition_receipt: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if manifest.get("state") != "awaiting_human_audition":
        raise ValueError("only awaiting_human_audition may be released")
    validation = validate(manifest)
    if validation["status"] != "pass":
        raise ValueError("awaiting-audition manifest is invalid: " + "; ".join(validation["errors"]))
    current = require_current_master(manifest, master)
    source_receipt = validate_audition_receipt(
        audition_receipt,
        current,
        str(manifest.get("canonical_sha256", "")),
    )
    reviewer = str(source_receipt["reviewer"]).strip()
    approval_ref = str(source_receipt["approval_ref"]).strip()
    timestamp = str(source_receipt["approved_at"]).strip()
    master_sha = sha256(current)
    audition = {
        "status": "approved",
        "reviewer": reviewer,
        "approval_ref": approval_ref,
        "approved_at": timestamp,
        "approved_master_sha256": master_sha,
        "full_speed_1x_audition": True,
        "complete_master_audition": True,
        "receipt_path": str(audition_receipt.resolve()),
        "receipt_sha256": sha256(audition_receipt),
    }
    result = deepcopy(manifest)
    result["state"] = "released"
    result["release_ready"] = True
    result["human_audition"] = audition
    result.setdefault("history", []).append({"state": "released", "at": timestamp})
    receipt = {
        "schema_version": "voice_release_v2",
        "status": "approved",
        "release_ready": True,
        "master_path": str(current),
        "master_sha256": master_sha,
        "canonical_sha256": result["canonical_sha256"],
        "reviewer": reviewer,
        "approval_ref": approval_ref,
        "approved_at": timestamp,
        "full_speed_1x_audition": True,
        "complete_master_audition": True,
        "audition_receipt_path": str(audition_receipt.resolve()),
        "audition_receipt_sha256": sha256(audition_receipt),
    }
    return result, receipt


def validate(manifest: dict[str, Any]) -> dict[str, Any]:
    state = str(manifest.get("state", ""))
    ready = bool(manifest.get("release_ready"))
    audition = manifest.get("human_audition") or {}
    errors: list[str] = []
    if state not in LEGAL_STATES:
        errors.append(f"unknown audio release state: {state}")
    try:
        master = require_current_master(manifest)
    except ValueError as exc:
        master = None
        errors.append(str(exc))
    canonical = Path(str(manifest.get("canonical_path", ""))).expanduser()
    if not canonical.is_file() or str(manifest.get("canonical_sha256", "")).lower() != sha256(canonical):
        errors.append("canonical path/SHA binding is invalid")
    machine_qa = Path(str(manifest.get("machine_qa_path", ""))).expanduser()
    if not machine_qa.is_file() or str(manifest.get("machine_qa_sha256", "")).lower() != sha256(machine_qa):
        errors.append("machine QA path/SHA binding is invalid")
    elif canonical.is_file() and master is not None:
        try:
            validate_machine_qa(canonical, master, machine_qa)
        except ValueError as exc:
            errors.append(str(exc))
    checks = manifest.get("machine_checks")
    if not isinstance(checks, dict):
        errors.append("machine_checks must be an object")
    else:
        for name in REQUIRED_MACHINE_CHECKS:
            if str(checks.get(name, "")).lower() != "pass":
                errors.append(f"required machine check is not pass: {name}")
    if state == "released":
        if not ready:
            errors.append("released manifest must set release_ready=true")
        if audition.get("status") != "approved":
            errors.append("released manifest must have approved human audition")
        if master is None or audition.get("approved_master_sha256") != sha256(master):
            errors.append("human approval is not bound to the current master SHA")
        receipt_path = Path(str(audition.get("receipt_path", ""))).expanduser()
        if not receipt_path.is_file() or str(audition.get("receipt_sha256", "")).lower() != sha256(receipt_path):
            errors.append("human audition receipt path/SHA binding is invalid")
        elif master is not None:
            try:
                validate_audition_receipt(
                    receipt_path,
                    master,
                    str(manifest.get("canonical_sha256", "")),
                )
            except ValueError as exc:
                errors.append(str(exc))
    elif ready:
        errors.append("non-released manifest cannot set release_ready=true")
    history = manifest.get("history")
    if not isinstance(history, list) or not history:
        errors.append("audio release history is missing")
    else:
        bad_history = [row for row in history if not isinstance(row, dict) or row.get("state") not in LEGAL_STATES]
        if bad_history:
            errors.append("audio release history contains an illegal state")
    return {"status": "pass" if not errors else "fail", "state": state, "errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    machine = sub.add_parser("machine-verify")
    machine.add_argument("--canonical", type=Path, required=True)
    machine.add_argument("--master", type=Path, required=True)
    machine.add_argument("--machine-qa", type=Path, required=True)
    machine.add_argument("--output", type=Path, required=True)

    audition = sub.add_parser("await-audition")
    audition.add_argument("--manifest", type=Path, required=True)
    audition.add_argument("--output", type=Path, required=True)

    approve = sub.add_parser("release")
    approve.add_argument("--manifest", type=Path, required=True)
    approve.add_argument("--master", type=Path, required=True)
    approve.add_argument("--audition-receipt", type=Path, required=True)
    approve.add_argument("--output", type=Path, required=True)
    approve.add_argument("--release-output", type=Path, required=True)

    check = sub.add_parser("validate")
    check.add_argument("--manifest", type=Path, required=True)

    args = parser.parse_args()
    try:
        if args.command == "machine-verify":
            result = machine_verified(args.canonical, args.master, args.machine_qa)
            write_json(args.output, result)
        elif args.command == "await-audition":
            result = transition_to_audition(read_json(args.manifest))
            write_json(args.output, result)
        elif args.command == "release":
            result, receipt = release(
                read_json(args.manifest),
                args.master,
                args.audition_receipt,
            )
            write_json(args.output, result)
            write_json(args.release_output, receipt)
        else:
            result = validate(read_json(args.manifest))
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["status"] == "pass" else 1
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "fail", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
