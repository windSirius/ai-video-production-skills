#!/usr/bin/env python3
"""Refuse formal rendering without current state, proxy approval and authorization."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any


PASS_VALUES = {"pass", "approved"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{number} is not an object")
        rows.append(value)
    return rows


def pointer_file(root: Path, current: dict[str, Any], key: str, default: str, errors: list[str]) -> Path:
    pointer = current.get(key, {})
    path = root / str(pointer.get("path", default)) if isinstance(pointer, dict) else root / default
    if not path.is_file():
        errors.append(f"CURRENT {key} pointer file missing")
        return path
    expected = str(pointer.get("sha256", "")) if isinstance(pointer, dict) else ""
    if expected and sha256_file(path) != expected:
        errors.append(f"CURRENT {key} pointer SHA mismatch")
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()

    root = args.project_root.resolve()
    errors: list[str] = []
    current_path = root / "CURRENT.json"
    if not current_path.is_file():
        errors.append("CURRENT.json missing")
        current: dict[str, Any] = {}
    else:
        current = read_json(current_path)
    if current.get("current_stage") != "10_formal_render":
        errors.append("CURRENT current_stage must be 10_formal_render")
    if current.get("status") != "active":
        errors.append("CURRENT project status must be active")
    if current.get("stage_status") not in {"pending", "in_progress"}:
        errors.append("CURRENT formal-render stage must be pending or in_progress")

    deliverables_path = pointer_file(root, current, "deliverables", "deliverables.json", errors)
    authority_path = pointer_file(root, current, "authority", "authority_bundle.json", errors)
    approvals_pointer = current.get("approvals", {})
    approvals_path = root / str(
        approvals_pointer.get("path", "approvals/approval_ledger.jsonl")
        if isinstance(approvals_pointer, dict)
        else "approvals/approval_ledger.jsonl"
    )
    if not approvals_path.is_file():
        errors.append("CURRENT approvals pointer file missing")
        approvals: list[dict[str, Any]] = []
    else:
        approvals = read_jsonl(approvals_path)
    if isinstance(approvals_pointer, dict) and approvals_pointer.get("last_id"):
        last_id = str(approvals[-1].get("id") or approvals[-1].get("approval_id") or "") if approvals else ""
        if last_id != str(approvals_pointer.get("last_id")):
            errors.append("CURRENT approvals last_id mismatch")

    deliverables = read_json(deliverables_path) if deliverables_path.is_file() else {}
    authority = read_json(authority_path) if authority_path.is_file() else {}
    item = deliverables.get("items", {}).get("integrated_proxy_720") if isinstance(deliverables.get("items"), dict) else None
    proxy_sha = ""
    proxy_path: Path | None = None
    if not isinstance(item, dict):
        errors.append("current integrated_proxy_720 deliverable missing")
    else:
        proxy_path = root / str(item.get("path", ""))
        proxy_sha = str(item.get("sha256", "")).lower()
        if not proxy_path.is_file():
            errors.append("integrated_proxy_720 file missing")
        elif len(proxy_sha) != 64 or sha256_file(proxy_path) != proxy_sha:
            errors.append("integrated_proxy_720 SHA mismatch")
        approval_id = str(item.get("approval_id", ""))
        proxy_approval = any(
            str(row.get("id") or row.get("approval_id") or "") == approval_id
            and str(row.get("decision", row.get("status", ""))).lower() in PASS_VALUES
            and row.get("role") == "integrated_proxy_720"
            and isinstance(row.get("artifact"), dict)
            and str(row["artifact"].get("sha256", "")).lower() == proxy_sha
            and str(row["artifact"].get("path", "")) == str(item.get("path", ""))
            for row in approvals
        )
        if not approval_id or not proxy_approval:
            errors.append("integrated_proxy_720 lacks current artifact-bound approval")

    authority_revision = authority.get("revision")
    authorization = None
    for row in approvals:
        gate_ok = row.get("gate") == "formal_render_authorization" or row.get("role") == "formal_render_authorization"
        decision = str(row.get("decision", row.get("status", ""))).lower()
        if (
            gate_ok
            and decision in PASS_VALUES
            and str(row.get("integrated_proxy_sha256", "")).lower() == proxy_sha
            and row.get("authority_revision") == authority_revision
            and str(row.get("user_quote", "")).strip()
            and (row.get("id") or row.get("approval_id"))
        ):
            authorization = row
    if authorization is None:
        errors.append("current formal_render_authorization bound to proxy SHA is required")

    if authority.get("delivery_spec", {}).get("production_contract_version") == 2:
        # Use the canonical controller, never an episode-specific relaxed adapter.
        controller = Path(__file__).resolve().parents[2] / "zhangyanfa-video-production/scripts/workflow.py"
        loader = importlib.util.spec_from_file_location("formal_controller_v2", controller)
        workflow = importlib.util.module_from_spec(loader)
        loader.loader.exec_module(workflow)
        try:
            _, current_authority, current_deliverables, current_approvals, pointer_errors = workflow.load_project(root)
            errors.extend(pointer_errors)
            errors.extend(workflow.current_submission_errors(root, current_authority, current_deliverables, current_approvals))
            for stage in ("08_track_design", "09_integrated_720_review"):
                stage_errors, _ = workflow.check_stage(root, stage, current_authority, current_deliverables, current_approvals)
                errors.extend(stage_errors)
            authorization = workflow.formal_render_authorization_for(
                current_approvals, workflow.item_for(current_deliverables, "integrated_proxy_720"),
                current_authority.get("revision"), current_authority.get("delivery_spec"))
            if authorization is None:
                errors.append("v2 authorization must bind the exact proxy, authority and frozen delivery specification")
        except (OSError, ValueError, KeyError, TypeError, workflow.WorkflowError) as exc:
            errors.append("v2 controller preflight: " + str(exc))
    errors = sorted(set(errors))

    report = {
        "status": "PASS" if not errors else "FAIL",
        "project_root": str(root),
        "current_stage": current.get("current_stage"),
        "integrated_proxy_path": str(proxy_path) if proxy_path else None,
        "integrated_proxy_sha256": proxy_sha or None,
        "formal_render_authorization_id": (
            authorization.get("id") or authorization.get("approval_id") if authorization else None
        ),
        "errors": errors,
    }
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
