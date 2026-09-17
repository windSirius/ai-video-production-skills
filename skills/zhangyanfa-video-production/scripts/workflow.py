#!/usr/bin/env python3
"""Lightweight 13-stage controller for Alan's video-production workflow."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sys
from typing import Any, Iterable


WORKFLOW_VERSION = "zhangyanfa_video_v5"
DEFAULT_HOUSE_STYLE = Path(__file__).resolve().parent.parent / "assets/house_style.v2.json"
_contracts_spec = importlib.util.spec_from_file_location(
    "production_contracts", Path(__file__).with_name("production_contracts.py")
)
contracts = importlib.util.module_from_spec(_contracts_spec)
_contracts_spec.loader.exec_module(contracts)
_workspace_spec = importlib.util.spec_from_file_location('workspace_layout', Path(__file__).with_name('workspace_layout.py'))
workspace = importlib.util.module_from_spec(_workspace_spec)
_workspace_spec.loader.exec_module(workspace)

STAGES = (
    "01_init",
    "02_research_scout",
    "03_script_build",
    "04_script_approval",
    "05_narration",
    "06_subtitle",
    "07_source_freeze",
    "08_track_design",
    "09_integrated_720_review",
    "10_formal_render",
    "11_final_assembly",
    "12_cover",
    "13_seal",
)
STAGE_INDEX = {stage: index for index, stage in enumerate(STAGES, start=1)}

NEXT_ACTION = {
    "01_init": "冻结主题、交付规格、剪镜规则、轨道和整合工具",
    "02_research_scout": "完成证据、反证、现有素材和缺口侦察",
    "03_script_build": "完成正文、传统中文、作者声音和画面锚点审计",
    "04_script_approval": "展示当前稿件并等待用户批准",
    "05_narration": "完成词面、韵律、完整试听并等待用户批准母带",
    "06_subtitle": "生成并确认唯一最终字幕和整数帧时钟",
    "07_source_freeze": "关闭所有P0素材缺口并冻结来源清单",
    "08_track_design": "分别完成并审批A、B、C和BGM",
    "09_integrated_720_review": "生成并审批全长720p整合代理",
    "10_formal_render": "串行渲染2K60正式轨道并完成技术QA",
    "11_final_assembly": "按冻结模式整合成片或打包独立分轨并完成交付QA",
    "12_cover": "制作六稿、选稿并审批三种画幅",
    "13_seal": "核对唯一当前交付并封存",
}

ROLE_STAGE = {
    "evidence_ledger": "02_research_scout",
    "source_scout": "02_research_scout",
    "script": "03_script_build",
    "script_qa": "03_script_build",
    "narration": "05_narration",
    "voice_release": "05_narration",
    "subtitle": "06_subtitle",
    "timing_contract": "06_subtitle",
    "source_freeze": "07_source_freeze",
    "track_plan": "08_track_design",
    "a_review": "08_track_design",
    "b_review": "08_track_design",
    "c_review": "08_track_design",
    "bgm_review": "08_track_design",
    "bgm_master": "08_track_design",
    "integrated_proxy_720": "09_integrated_720_review",
    "a_master": "10_formal_render",
    "b_master": "10_formal_render",
    "c_master": "10_formal_render",
    "render_qa": "10_formal_render",
    "final_video": "11_final_assembly",
    "final_video_qa": "11_final_assembly",
    "split_delivery": "11_final_assembly",
    "split_delivery_qa": "11_final_assembly",
    "cover_candidates": "12_cover",
    "cover_16_9": "12_cover",
    "cover_4_3": "12_cover",
    "cover_3_4": "12_cover",
}

APPROVAL_STAGE = {
    "script": "04_script_approval",
    "narration": "05_narration",
    "subtitle": "06_subtitle",
    "a_review": "08_track_design",
    "b_review": "08_track_design",
    "c_review": "08_track_design",
    "bgm_review": "08_track_design",
    "bgm_master": "08_track_design",
    "integrated_proxy_720": "09_integrated_720_review",
    "final_video": "11_final_assembly",
    "split_delivery": "11_final_assembly",
    "cover_candidates": "12_cover",
    "cover_16_9": "12_cover",
    "cover_4_3": "12_cover",
    "cover_3_4": "12_cover",
}

AUTHORITY_ROLE = {"script", "narration", "subtitle"}
PASSING_OBJECTIVE_STATES = {"pass", "pass_with_warnings"}
APPROVAL_SIGNAL = re.compile(r"通过|批准|审批完成|确认无误|最终(?:版|版本)|定稿|选择|选用|就用|采用|没问题|合格", re.I)
APPROVAL_REJECTION_SIGNAL = re.compile(
    r"不通过|未通过|没有通过|不批准|未批准|不予批准|不确认|未确认|还没确认|"
    r"不是最终(?:版|版本)|未定稿|不选择|不选|不要|别用|不采用|不合格|有问题|未完成|没完成|没有完成|还没做好|"
    r"(?:未|没|还没|尚未|没有)(?:进行|完成)?(?:审核|审查|审批|批准|确认|通过)",
    re.I,
)
WORK_AUTHORIZATION_ONLY = re.compile(
    r"^(?:ok[，, ]*)?(?:继续|开始(?:制作|做|配音|渲染|剪辑)?|制作|去做|先做|接着做|往下做)[。！!，, ]*$",
    re.I,
)
FORMAL_RENDER_SUBJECT = re.compile(
    r"正式(?:渲染|出片|输出)|(?:最终)?母版(?:渲染|出片|输出)|"
    r"2\s*[kK](?:\s*60)?(?:\s*(?:fps|帧))?|2560\s*[x×*]\s*1440",
    re.I,
)
FORMAL_RENDER_ACTION = re.compile(r"批准|同意|授权|确认|通过|可以|开始|进行|执行|渲染|输出|出片|开渲", re.I)
FORMAL_RENDER_REJECTION = re.compile(
    r"暂不|先不|不要|别|不能|不(?:要)?(?:开始|进行|执行|渲染|输出|出片)|"
    r"未批准|未确认|还没确认|不通过",
    re.I,
)
PLACEHOLDER_INTAKE_EXACT = {
    "待定", "未定", "待确认", "未确认", "未命名", "占位", "测试占位",
    "placeholder", "tbd", "tbc", "todo", "none", "null", "n/a",
}
PLACEHOLDER_INTAKE_MARKER = re.compile(
    r"待用户确认|未获用户确认|尚未确认|测试占位|占位(?:标题|主题|文本)|"
    r"(?:标题|主题)(?:待定|未定)|^未命名|\b(?:placeholder|tbd|tbc|todo)\b",
    re.I,
)


class WorkflowError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_iso(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise WorkflowError(f"invalid ISO timestamp: {value}") from exc
    if parsed.tzinfo is None:
        raise WorkflowError("timestamps must include a timezone")
    return parsed.astimezone(timezone.utc)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise WorkflowError(f"missing state file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise WorkflowError(f"invalid JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"expected JSON object: {path}")
    return value


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise WorkflowError(f"invalid JSONL at {path}:{number}") from exc
        if not isinstance(row, dict):
            raise WorkflowError(f"expected JSON object at {path}:{number}")
        rows.append(row)
    return rows


@contextmanager
def project_lock(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    lock_path = root / ".workflow.lock"
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def normalize_stage(value: str) -> str:
    if value in STAGE_INDEX:
        return value
    token = value.strip().zfill(2)
    matches = [stage for stage in STAGES if stage.startswith(f"{token}_")]
    if len(matches) == 1:
        return matches[0]
    raise WorkflowError(f"unknown stage: {value}")


def parse_tracks(value: str) -> list[str]:
    tracks: list[str] = []
    for token in value.split(","):
        track = token.strip().upper()
        if not track:
            continue
        if track not in {"A", "B", "C", "BGM"}:
            raise WorkflowError(f"unknown track: {track}")
        if track not in tracks:
            tracks.append(track)
    if "A" not in tracks or "BGM" not in tracks:
        raise WorkflowError("A and BGM are mandatory tracks")
    return tracks


def validated_intake_text(label: str, value: str) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise WorkflowError(f"{label} must not be blank")
    if normalized.casefold() in PLACEHOLDER_INTAKE_EXACT or PLACEHOLDER_INTAKE_MARKER.search(normalized):
        raise WorkflowError(f"{label} must be confirmed text, not a placeholder")
    return normalized


def target_duration_range(minimum: int | None, maximum: int | None) -> dict[str, int] | None:
    if minimum is None and maximum is None:
        return None
    if minimum is None or maximum is None:
        raise WorkflowError(
            "target duration range requires both --target-duration-min-seconds and --target-duration-max-seconds"
        )
    if not positive_int(minimum) or not positive_int(maximum):
        raise WorkflowError("target duration range values must be positive integer seconds")
    if minimum > maximum:
        raise WorkflowError("target duration minimum cannot exceed maximum")
    return {"min": minimum, "max": maximum}


def relative_artifact_path(root: Path, value: str) -> tuple[str, Path]:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = root / path
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise WorkflowError("registered artifacts must live inside the project root") from exc
    if not resolved.is_file():
        raise WorkflowError(f"artifact is not a file: {resolved}")
    return relative.as_posix(), resolved


def authority_bindings(authority: dict[str, Any]) -> dict[str, str]:
    bindings: dict[str, str] = {}
    for role in ("script", "narration", "subtitle"):
        entry = authority.get(role, {})
        if entry.get("state") == "frozen" and entry.get("sha256"):
            bindings[role] = str(entry["sha256"])
    return bindings


def last_approval_id(rows: list[dict[str, Any]]) -> str | None:
    return str(rows[-1].get("id")) if rows else None


def next_approval_id(rows: list[dict[str, Any]]) -> str:
    maximum = 0
    for row in rows:
        value = str(row.get("id", ""))
        if value.startswith("APR-") and value[4:].isdigit():
            maximum = max(maximum, int(value[4:]))
    return f"APR-{maximum + 1:04d}"


def approval_quote_is_explicit(role: str, quote: str) -> bool:
    normalized = quote.strip()
    if (
        not normalized
        or WORK_AUTHORIZATION_ONLY.fullmatch(normalized)
        or APPROVAL_REJECTION_SIGNAL.search(normalized)
    ):
        return False
    if APPROVAL_SIGNAL.search(normalized):
        return True
    if role in {"split_delivery", "final_video", "cover_16_9", "cover_4_3", "cover_3_4"} and re.search(
        r"(?:这期|本期|视频|交付).{0,12}(?:结束了|完成了|做好了)", normalized
    ):
        return True
    if role in {"bgm_master", "bgm_review"} and re.search(r"\bBGM?\s*=\s*[A-Za-z0-9_-]+\b", normalized, re.I):
        return True
    if role == "cover_candidates" and re.search(r"(?:选|要)(?:第)?[一二三四五六1-6A-Fa-f](?:张|稿|版)?", normalized):
        return True
    return False


def render_authorization_quote_is_explicit(quote: str) -> bool:
    normalized = quote.strip()
    return bool(
        normalized
        and not WORK_AUTHORIZATION_ONLY.fullmatch(normalized)
        and not APPROVAL_REJECTION_SIGNAL.search(normalized)
        and not FORMAL_RENDER_REJECTION.search(normalized)
        and FORMAL_RENDER_SUBJECT.search(normalized)
        and FORMAL_RENDER_ACTION.search(normalized)
    )


def formal_render_authorization_for(
    approvals: list[dict[str, Any]],
    proxy: dict[str, Any] | None,
    authority_revision: Any,
    delivery_spec: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if proxy is None:
        return None
    for row in reversed(approvals):
        artifact = row.get("artifact", {})
        if (
            row.get("gate") == "formal_render_authorization"
            and row.get("role") == "formal_render_authorization"
            and row.get("decision") == "approved"
            and row.get("status") == "approved"
            and row.get("integrated_proxy_path") == proxy.get("path")
            and row.get("integrated_proxy_sha256") == proxy.get("sha256")
            and artifact.get("path") == proxy.get("path")
            and artifact.get("sha256") == proxy.get("sha256")
            and row.get("authority_revision") == authority_revision
            and (not delivery_spec or delivery_spec.get("production_contract_version") != 2
                 or row.get("delivery_spec_sha256") == contracts.json_digest(delivery_spec))
        ):
            return row
    return None


def root_paths(root: Path) -> dict[str, Path]:
    return {
        "current": root / "CURRENT.json",
        "request_contract": root / "request_contract.json",
        "authority": root / "authority_bundle.json",
        "deliverables": root / "deliverables.json",
        "approvals": root / "approvals/approval_ledger.jsonl",
        "stages": root / "state/stages",
        "stage_history": root / "state/stages/history",
    }


def receipt_path(root: Path, stage: str) -> Path:
    return root / "state/stages" / f"{stage}.json"


def load_project(root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]], list[str]]:
    paths = root_paths(root)
    current = read_json(paths["current"])
    request_contract = read_json(paths["request_contract"])
    authority = read_json(paths["authority"])
    deliverables = read_json(paths["deliverables"])
    approvals = read_jsonl(paths["approvals"])
    pointer_errors: list[str] = []
    layout = request_contract.get('workspace_layout')
    if layout:
        layout_path = root / layout['path']
        if not layout_path.is_file() or sha256_file(layout_path) != layout['sha256']:
            pointer_errors.append('frozen workspace path contract is missing or changed')
    expected_contract = current.get("request_contract", {}).get("sha256")
    actual_contract = sha256_file(paths["request_contract"])
    if expected_contract != actual_contract:
        pointer_errors.append("CURRENT request-contract pointer does not match request_contract.json")
    expected_authority = current.get("authority", {}).get("sha256")
    actual_authority = sha256_file(paths["authority"])
    if expected_authority != actual_authority:
        pointer_errors.append("CURRENT authority pointer does not match authority_bundle.json")
    expected_deliverables = current.get("deliverables", {}).get("sha256")
    actual_deliverables = sha256_file(paths["deliverables"])
    if expected_deliverables != actual_deliverables:
        pointer_errors.append("CURRENT deliverables pointer does not match deliverables.json")
    if current.get("approvals", {}).get("last_id") != last_approval_id(approvals):
        pointer_errors.append("CURRENT approval pointer does not match approval ledger")
    return current, authority, deliverables, approvals, pointer_errors


def update_current_receipt(root: Path, current: dict[str, Any]) -> None:
    stage = str(current["current_stage"])
    path = receipt_path(root, stage)
    if path.is_file():
        current["stage_receipt"] = {
            "path": path.relative_to(root).as_posix(),
            "sha256": sha256_file(path),
        }
    else:
        current["stage_receipt"] = None


def save_project(
    root: Path,
    current: dict[str, Any],
    authority: dict[str, Any],
    deliverables: dict[str, Any],
    approvals: list[dict[str, Any]],
) -> None:
    paths = root_paths(root)
    atomic_write_json(paths["authority"], authority)
    atomic_write_json(paths["deliverables"], deliverables)
    current["request_contract"] = {
        "path": "request_contract.json",
        "sha256": sha256_file(paths["request_contract"]),
    }
    current["authority"] = {
        "path": "authority_bundle.json",
        "revision": authority["revision"],
        "sha256": sha256_file(paths["authority"]),
    }
    current["approvals"] = {
        "path": "approvals/approval_ledger.jsonl",
        "last_id": last_approval_id(approvals),
    }
    current["deliverables"] = {
        "path": "deliverables.json",
        "revision": deliverables["revision"],
        "sha256": sha256_file(paths["deliverables"]),
    }
    current["updated_at"] = utc_now()
    update_current_receipt(root, current)
    atomic_write_json(paths["current"], current)
    if (root / 'workspace_paths.json').is_file():
        try:
            workspace.refresh(root)
        except (ValueError, OSError, KeyError, TypeError) as exc:
            # A navigation conflict must not misreport a successfully recorded approval as failed.
            print(f'workspace navigation refresh needs attention: {exc}', file=sys.stderr)


def ensure_pointer_integrity(pointer_errors: Iterable[str]) -> None:
    errors = list(pointer_errors)
    if errors:
        raise WorkflowError("state pointer drift: " + "; ".join(errors))


def artifact_errors(root: Path, item: dict[str, Any], authority: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    path = root / str(item.get("path", ""))
    if not path.is_file():
        return [f"missing artifact: {item.get('path')}"]
    actual = sha256_file(path)
    if actual != item.get("sha256"):
        errors.append(f"artifact SHA drift: {item.get('role')}")
    current_bindings = authority_bindings(authority)
    for role, expected in item.get("authority_bindings", {}).items():
        if current_bindings.get(role) != expected:
            errors.append(f"stale authority binding: {item.get('role')}->{role}")
    return errors


def authority_errors(root: Path, authority: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for role in ("script", "narration", "subtitle"):
        entry = authority.get(role, {})
        if entry.get("state") != "frozen":
            continue
        path = root / str(entry.get("path", ""))
        if not path.is_file():
            errors.append(f"missing frozen authority: {role}")
        elif sha256_file(path) != entry.get("sha256"):
            errors.append(f"frozen authority SHA drift: {role}")
    return errors


def item_for(deliverables: dict[str, Any], role: str) -> dict[str, Any] | None:
    item = deliverables.get("items", {}).get(role)
    return item if isinstance(item, dict) else None


def approval_for(
    approvals: list[dict[str, Any]], item: dict[str, Any], role: str
) -> dict[str, Any] | None:
    approval_id = item.get("approval_id")
    if not approval_id:
        return None
    for row in approvals:
        if (
            row.get("id") == approval_id
            and row.get("decision") == "approved"
            and row.get("role") == role
            and row.get("artifact", {}).get("sha256") == item.get("sha256")
            and row.get("artifact", {}).get("path") == item.get("path")
        ):
            return row
    return None


def require_item(
    root: Path,
    authority: dict[str, Any],
    deliverables: dict[str, Any],
    role: str,
    errors: list[str],
    warnings: list[str],
) -> dict[str, Any] | None:
    item = item_for(deliverables, role)
    if item is None:
        errors.append(f"missing required role: {role}")
        return None
    errors.extend(artifact_errors(root, item, authority))
    objective = item.get("objective_status")
    if objective not in PASSING_OBJECTIVE_STATES:
        errors.append(f"{role}.objective_status must pass")
    if objective == "pass_with_warnings":
        warnings.append(f"{role} has disclosed warnings")
    return item


def require_approval(
    approvals: list[dict[str, Any]],
    item: dict[str, Any] | None,
    role: str,
    errors: list[str],
) -> None:
    if item is not None and approval_for(approvals, item, role) is None:
        errors.append(f"missing current artifact-bound approval: {role}")


def truthy(value: Any) -> bool:
    return value is True


def positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def non_negative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def require_nonempty_artifact(
    root: Path,
    item: dict[str, Any] | None,
    role: str,
    errors: list[str],
) -> None:
    if item is None:
        return
    path = root / str(item.get("path", ""))
    if path.is_file() and path.stat().st_size == 0:
        errors.append(f"{role} artifact must not be empty")


def duration_contract_errors(spec: dict[str, Any]) -> list[str]:
    value = spec.get("target_duration_range_seconds")
    if value is None:
        return []
    if not isinstance(value, dict):
        return ["delivery_spec.target_duration_range_seconds must be an object or null"]
    minimum = value.get("min")
    maximum = value.get("max")
    if not positive_int(minimum) or not positive_int(maximum):
        return ["target duration range must contain positive integer min and max seconds"]
    if minimum > maximum:
        return ["target duration minimum cannot exceed maximum"]
    return []


def duration_frame_count_errors(
    spec: dict[str, Any],
    frame_count: Any,
    label: str,
) -> list[str]:
    duration_range = spec.get("target_duration_range_seconds")
    if duration_range is None or not positive_int(frame_count):
        return []
    if not isinstance(duration_range, dict) or duration_contract_errors(spec):
        return []
    fps = spec.get("fps")
    if not positive_int(fps):
        return []
    minimum_frames = duration_range["min"] * fps
    maximum_frames = duration_range["max"] * fps
    if not minimum_frames <= frame_count <= maximum_frames:
        return [
            f"{label} is outside target duration range "
            f"{duration_range['min']}-{duration_range['max']} seconds at {fps} fps"
        ]
    return []


def track_review_roles(authority: dict[str, Any]) -> list[str]:
    tracks = authority.get("delivery_spec", {}).get("active_tracks", [])
    roles = ["a_review"]
    if "B" in tracks:
        roles.append("b_review")
    if "C" in tracks:
        roles.append("c_review")
    roles.append("bgm_review" if contracts.enabled(authority) else "bgm_master")
    return roles


def master_roles(authority: dict[str, Any]) -> list[str]:
    tracks = authority.get("delivery_spec", {}).get("active_tracks", [])
    roles = ["a_master"]
    if "B" in tracks:
        roles.append("b_master")
    if "C" in tracks:
        roles.append("c_master")
    return roles


def expected_proxy_components(authority: dict[str, Any]) -> set[str]:
    tracks = set(authority.get("delivery_spec", {}).get("active_tracks", []))
    return tracks | {"narration", "subtitle"}


def expected_final_components(authority: dict[str, Any]) -> set[str]:
    components = expected_proxy_components(authority)
    if authority.get("delivery_spec", {}).get("final_subtitle_baked") is False:
        components.discard("subtitle")
    return components


def delivery_mode(authority: dict[str, Any]) -> str:
    return authority.get("delivery_spec", {}).get("delivery_mode", "integrated")


def role_stage(role: str, authority: dict[str, Any]) -> str | None:
    if role == "bgm_master" and contracts.enabled(authority):
        return "09_integrated_720_review"
    return ROLE_STAGE.get(role)


def current_submission_errors(root, authority, deliverables, approvals):
    """Recheck nested evidence at formal-render preflight and seal, not just registration."""
    if not contracts.enabled(authority):
        return []
    errors = []
    items = deliverables.get("items", {})
    for role in ("script_qa", "voice_release", "source_freeze", "a_review"):
        item = items.get(role)
        if not item:
            errors.append(f"missing required submission review: {role}")
            continue
        errors.extend(artifact_errors(root, item, authority))
        errors.extend(contracts.check_submission(root, role, item, authority, items))
    errors.extend(contracts.check_bgm_derivation(root, authority, items, approvals, approval_for))
    return sorted(set(errors))


def check_stage(
    root: Path,
    stage: str,
    authority: dict[str, Any],
    deliverables: dict[str, Any],
    approvals: list[dict[str, Any]],
) -> tuple[list[str], list[str]]:
    spec = authority.get("delivery_spec", {})
    errors = authority_errors(root, authority)
    errors.extend(duration_contract_errors(spec))
    warnings: list[str] = []
    if delivery_mode(authority) not in {"integrated", "independent_tracks", "both"}:
        errors.append("unknown delivery mode")
    # Only opted-in, frozen v2 contracts acquire new submission gates.
    quality_role = {"03_script_build": "script_qa", "05_narration": "voice_release",
                    "07_source_freeze": "source_freeze", "08_track_design": "a_review"}.get(stage)
    if quality_role and item_for(deliverables, quality_role):
        errors.extend(contracts.check_submission(root, quality_role, item_for(deliverables, quality_role),
                                                  authority, deliverables.get("items", {})))

    if stage == "01_init":
        for key in ("width", "height", "fps"):
            if not positive_int(spec.get(key)):
                errors.append(f"delivery_spec.{key} must be positive")
        if "A" not in spec.get("active_tracks", []) or "BGM" not in spec.get("active_tracks", []):
            errors.append("A and BGM must be active")

    elif stage == "02_research_scout":
        evidence = require_item(root, authority, deliverables, "evidence_ledger", errors, warnings)
        scout = require_item(root, authority, deliverables, "source_scout", errors, warnings)
        require_nonempty_artifact(root, evidence, "evidence_ledger", errors)
        require_nonempty_artifact(root, scout, "source_scout", errors)
        if evidence:
            meta = evidence.get("meta", {})
            if not positive_int(meta.get("qa_schema_version")):
                errors.append("evidence_ledger.meta.qa_schema_version must be positive")
            if not positive_int(meta.get("evidence_count")):
                errors.append("evidence_ledger.meta.evidence_count must be positive")
            if not non_negative_int(meta.get("counterevidence_count")):
                errors.append("evidence_ledger.meta.counterevidence_count must be non-negative")
            for key in ("counterevidence_reviewed", "qa_pass"):
                if not truthy(meta.get(key)):
                    errors.append(f"evidence_ledger.meta.{key} must be true")
        if scout:
            meta = scout.get("meta", {})
            if not positive_int(meta.get("qa_schema_version")):
                errors.append("source_scout.meta.qa_schema_version must be positive")
            for key in ("existing_asset_count", "gap_count"):
                if not non_negative_int(meta.get(key)):
                    errors.append(f"source_scout.meta.{key} must be non-negative")
            for key in ("inventory_reviewed", "gaps_reviewed", "qa_pass"):
                if not truthy(meta.get(key)):
                    errors.append(f"source_scout.meta.{key} must be true")

    elif stage == "03_script_build":
        script = require_item(root, authority, deliverables, "script", errors, warnings)
        qa = require_item(root, authority, deliverables, "script_qa", errors, warnings)
        require_nonempty_artifact(root, script, "script", errors)
        require_nonempty_artifact(root, qa, "script_qa", errors)
        if qa:
            meta = qa.get("meta", {})
            if not positive_int(meta.get("qa_schema_version")):
                errors.append("script_qa.meta.qa_schema_version must be positive")
            if not script or meta.get("script_sha256") != script.get("sha256"):
                errors.append("script_qa.meta.script_sha256 must match the current script artifact")
            for key in ("qa_pass", "traditional_chinese_pass", "author_voice_pass", "visual_anchors_pass"):
                if not truthy(meta.get(key)):
                    errors.append(f"script_qa.meta.{key} must be true")

    elif stage == "04_script_approval":
        item = require_item(root, authority, deliverables, "script", errors, warnings)
        require_approval(approvals, item, "script", errors)
        frozen = authority.get("script", {})
        if not item or frozen.get("state") != "frozen" or frozen.get("sha256") != item.get("sha256"):
            errors.append("script authority is not frozen to the approved artifact")

    elif stage == "05_narration":
        narration = require_item(root, authority, deliverables, "narration", errors, warnings)
        release = require_item(root, authority, deliverables, "voice_release", errors, warnings)
        if narration and not positive_int(narration.get("meta", {}).get("duration_frame_count")):
            errors.append("narration.meta.duration_frame_count must be positive")
        if narration:
            errors.extend(
                duration_frame_count_errors(
                    spec,
                    narration.get("meta", {}).get("duration_frame_count"),
                    "narration.meta.duration_frame_count",
                )
            )
        if release:
            meta = release.get("meta", {})
            for key in ("lexical_pass", "prosody_pass", "full_length_file"):
                if not truthy(meta.get(key)):
                    errors.append(f"voice_release.meta.{key} must be true")
        require_approval(approvals, narration, "narration", errors)
        frozen = authority.get("narration", {})
        if not narration or frozen.get("state") != "frozen" or frozen.get("sha256") != narration.get("sha256"):
            errors.append("narration authority is not frozen to the approved artifact")

    elif stage == "06_subtitle":
        subtitle = require_item(root, authority, deliverables, "subtitle", errors, warnings)
        require_item(root, authority, deliverables, "timing_contract", errors, warnings)
        if subtitle:
            meta = subtitle.get("meta", {})
            for key in ("cue_count", "target_frame_count"):
                if not positive_int(meta.get(key)):
                    errors.append(f"subtitle.meta.{key} must be positive")
            final_end = meta.get("final_end_frame")
            target = meta.get("target_frame_count")
            if not isinstance(final_end, int) or final_end < 0:
                errors.append("subtitle.meta.final_end_frame must be non-negative")
            elif positive_int(target) and final_end > target:
                errors.append("subtitle final_end_frame exceeds target_frame_count")
            errors.extend(
                duration_frame_count_errors(
                    spec,
                    target,
                    "subtitle.meta.target_frame_count",
                )
            )
        require_approval(approvals, subtitle, "subtitle", errors)
        frozen = authority.get("subtitle", {})
        if not subtitle or frozen.get("state") != "frozen" or frozen.get("sha256") != subtitle.get("sha256"):
            errors.append("subtitle authority is not frozen to the approved artifact")
        if not positive_int(authority.get("delivery_spec", {}).get("target_frame_count")):
            errors.append("authority target_frame_count is not frozen")

    elif stage == "07_source_freeze":
        item = require_item(root, authority, deliverables, "source_freeze", errors, warnings)
        if item:
            meta = item.get("meta", {})
            if meta.get("p0_gap_count") != 0:
                errors.append("source_freeze.meta.p0_gap_count must be 0")
            if not truthy(meta.get("frozen")):
                errors.append("source_freeze.meta.frozen must be true")

    elif stage == "08_track_design":
        subtitle = authority.get("subtitle", {})
        plan = require_item(root, authority, deliverables, "track_plan", errors, warnings)
        if plan:
            if plan.get("meta", {}).get("cue_count") != subtitle.get("cue_count"):
                errors.append("track_plan cue_count differs from final subtitle")
            if plan.get("meta", {}).get("cut_policy") != authority.get("delivery_spec", {}).get("cut_policy"):
                errors.append("track_plan cut_policy differs from intake")
        for role in track_review_roles(authority):
            item = require_item(root, authority, deliverables, role, errors, warnings)
            if item:
                meta = item.get("meta", {})
                if role == "a_review":
                    if meta.get("cue_count") != subtitle.get("cue_count"):
                        errors.append("a_review cue_count differs from final subtitle")
                    if meta.get("identity_error_count") != 0:
                        errors.append("a_review identity_error_count must be 0")
                    if not truthy(meta.get("semantic_coverage_pass")):
                        errors.append("a_review semantic coverage must pass")
                    if (
                        authority.get("delivery_spec", {}).get("cut_policy") == "per_caption_refresh"
                        and meta.get("unexplained_boundary_reuse_count") != 0
                    ):
                        errors.append("a_review has unexplained caption-boundary reuse")
                elif role in {"b_review", "c_review"}:
                    if meta.get("identity_error_count") != 0:
                        errors.append(f"{role} identity_error_count must be 0")
                    if not truthy(meta.get("visual_gain_pass")):
                        errors.append(f"{role} visual_gain_pass must be true")
                elif role == "bgm_master":
                    if not truthy(meta.get("narration_intelligibility_pass")):
                        errors.append("bgm_master narration intelligibility must pass")
                    if meta.get("duration_frame_count") != authority.get("delivery_spec", {}).get("target_frame_count"):
                        errors.append("bgm_master duration differs from target frame count")
                elif role == "bgm_review":
                    if not str(meta.get("candidate_id", "")).strip():
                        errors.append("bgm_review must identify the exact audition candidate")
            require_approval(approvals, item, role, errors)

    elif stage == "09_integrated_720_review":
        if contracts.enabled(authority):
            require_item(root, authority, deliverables, "bgm_master", errors, warnings)
            errors.extend(contracts.check_bgm_derivation(root, authority, deliverables.get("items", {}), approvals, approval_for))
        item = require_item(root, authority, deliverables, "integrated_proxy_720", errors, warnings)
        if item:
            meta = item.get("meta", {})
            if not truthy(meta.get("full_length")):
                errors.append("integrated proxy must be full length")
            if meta.get("width") != 1280 or meta.get("height") != 720:
                errors.append("integrated proxy must be 1280x720")
            if meta.get("fps") != authority.get("delivery_spec", {}).get("fps"):
                errors.append("integrated proxy fps differs from delivery spec")
            if meta.get("target_frame_count") != authority.get("delivery_spec", {}).get("target_frame_count"):
                errors.append("integrated proxy frame count differs from authority")
            components = set(meta.get("components", []))
            missing = expected_proxy_components(authority) - components
            if missing:
                errors.append(f"integrated proxy missing components: {sorted(missing)}")
            if contracts.enabled(authority) and meta.get("bgm_master_sha256") != (item_for(deliverables, "bgm_master") or {}).get("sha256"):
                errors.append("integrated proxy must bind the actual full-length BGM master")
        require_approval(approvals, item, "integrated_proxy_720", errors)

    elif stage == "10_formal_render":
        proxy = require_item(
            root, authority, deliverables, "integrated_proxy_720", errors, warnings
        )
        if proxy and approval_for(approvals, proxy, "integrated_proxy_720") is None:
            errors.append("integrated_proxy_720 is not currently approved")
        if formal_render_authorization_for(approvals, proxy, authority.get("revision"), spec) is None:
            errors.append("missing current formal_render_authorization")
        for role in master_roles(authority):
            master = require_item(root, authority, deliverables, role, errors, warnings)
            if master and contracts.enabled(authority):
                for key in ("width", "height", "fps", "target_frame_count"):
                    if master.get("meta", {}).get(key) != spec.get(key):
                        errors.append(f"{role} {key} differs from delivery spec")
                if role == "a_master":
                    meta = master.get("meta", {})
                    if meta.get("subtitle_baked") != spec.get("a_subtitle_baked", False):
                        errors.append("a_master subtitle policy differs from delivery spec")
                    if delivery_mode(authority) in {"independent_tracks", "both"} and (
                        meta.get("audio_baked") is not False or meta.get("auxiliary_overlays_baked") is not False
                    ):
                        errors.append("independent A must exclude audio and B/C overlays")
        qa = require_item(root, authority, deliverables, "render_qa", errors, warnings)
        if qa:
            meta = qa.get("meta", {})
            spec = authority.get("delivery_spec", {})
            for key in ("sequential_render", "full_decode"):
                if not truthy(meta.get(key)):
                    errors.append(f"render_qa.meta.{key} must be true")
            for key in ("width", "height", "fps", "target_frame_count"):
                if meta.get(key) != spec.get(key):
                    errors.append(f"render_qa {key} differs from delivery spec")

    elif stage == "11_final_assembly":
        if delivery_mode(authority) in {"independent_tracks", "both"}:
            require_item(root, authority, deliverables, "split_delivery", errors, warnings)
            require_item(root, authority, deliverables, "split_delivery_qa", errors, warnings)
            errors.extend(contracts.check_split_delivery(root, authority, deliverables.get("items", {})))
        if delivery_mode(authority) == "independent_tracks":
            # Technical packaging can proceed to covers; acknowledgement is checked at seal.
            return sorted(set(errors)), sorted(set(warnings))
        video = require_item(root, authority, deliverables, "final_video", errors, warnings)
        qa = require_item(root, authority, deliverables, "final_video_qa", errors, warnings)
        if qa:
            meta = qa.get("meta", {})
            spec = authority.get("delivery_spec", {})
            if not truthy(meta.get("full_decode")):
                errors.append("final_video_qa full_decode must be true")
            if meta.get("target_frame_count") != spec.get("target_frame_count"):
                errors.append("final video frame count differs from authority")
            if meta.get("black_flash_count") != 0:
                errors.append("final video contains unresolved black/white flashes")
            for key in ("subtitle_coverage_pass", "audio_tail_pass"):
                if not truthy(meta.get(key)):
                    errors.append(f"final_video_qa.meta.{key} must be true")
            components = set(meta.get("components", []))
            missing = expected_final_components(authority) - components
            if missing:
                errors.append(f"final video missing components: {sorted(missing)}")
        require_approval(approvals, video, "final_video", errors)

    elif stage == "12_cover":
        candidates = require_item(root, authority, deliverables, "cover_candidates", errors, warnings)
        if candidates and candidates.get("meta", {}).get("candidate_count") != 6:
            errors.append("cover_candidates must contain exactly 6 candidates")
        require_approval(approvals, candidates, "cover_candidates", errors)
        for role, ratio in (
            ("cover_16_9", "16:9"),
            ("cover_4_3", "4:3"),
            ("cover_3_4", "3:4"),
        ):
            item = require_item(root, authority, deliverables, role, errors, warnings)
            if item:
                meta = item.get("meta", {})
                if meta.get("ratio") != ratio:
                    errors.append(f"{role} ratio metadata must be {ratio}")
                for key in ("layout_pass", "aspect_ratio_pass", "thumbnail_pass"):
                    if not truthy(meta.get(key)):
                        errors.append(f"{role}.meta.{key} must be true")
            require_approval(approvals, item, role, errors)

    elif stage == "13_seal":
        errors.extend(seal_errors(root, authority, deliverables, approvals))

    else:
        errors.append(f"unsupported stage: {stage}")

    return sorted(set(errors)), sorted(set(warnings))


def stage_output_roles(stage: str, deliverables: dict[str, Any]) -> list[str]:
    return sorted(
        role
        for role, item in deliverables.get("items", {}).items()
        if isinstance(item, dict) and item.get("stage") == stage
    )


def write_stage_receipt(
    root: Path,
    stage: str,
    authority: dict[str, Any],
    deliverables: dict[str, Any],
    warnings: list[str],
) -> dict[str, Any]:
    path = receipt_path(root, stage)
    if path.exists():
        history = root / "state/stages/history"
        history.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        shutil.copy2(path, history / f"{stage}_{stamp}.json")
    outputs = []
    approval_ids = []
    for role in stage_output_roles(stage, deliverables):
        item = deliverables["items"][role]
        outputs.append({"role": role, "path": item["path"], "sha256": item["sha256"]})
        if item.get("approval_id"):
            approval_ids.append(item["approval_id"])
    receipt = {
        "schema_version": 1,
        "stage": stage,
        "status": "complete",
        "authority_revision": authority["revision"],
        "authority_bindings": authority_bindings(authority),
        "outputs": outputs,
        "warnings": warnings,
        "approval_ids": sorted(set(approval_ids)),
        "completed_at": utc_now(),
    }
    atomic_write_json(path, receipt)
    return receipt


def receipt_current(
    root: Path,
    stage: str,
    authority: dict[str, Any],
    deliverables: dict[str, Any],
) -> bool:
    path = receipt_path(root, stage)
    if not path.is_file():
        return False
    try:
        receipt = read_json(path)
    except WorkflowError:
        return False
    if receipt.get("status") != "complete":
        return False
    current_authorities = authority_bindings(authority)
    for role, sha in receipt.get("authority_bindings", {}).items():
        if current_authorities.get(role) != sha:
            return False
    for output in receipt.get("outputs", []):
        item = item_for(deliverables, str(output.get("role", "")))
        if item is None or item.get("sha256") != output.get("sha256"):
            return False
        if artifact_errors(root, item, authority):
            return False
    return True


def first_incomplete_after(
    root: Path,
    stage: str,
    authority: dict[str, Any],
    deliverables: dict[str, Any],
) -> str:
    start = STAGE_INDEX[stage]
    for candidate in STAGES[start:]:
        if candidate == "13_seal":
            return candidate
        if not receipt_current(root, candidate, authority, deliverables):
            return candidate
    return "13_seal"


def archive_item(deliverables: dict[str, Any], role: str, reason: str) -> None:
    item = deliverables.get("items", {}).pop(role, None)
    if not isinstance(item, dict):
        return
    historical = dict(item)
    historical["state"] = "stale"
    historical["invalidated_at"] = utc_now()
    historical["invalidation_reason"] = reason
    deliverables.setdefault("history", []).append(historical)


def mark_receipts_stale(root: Path, stages: Iterable[int], reason: str) -> None:
    for index in sorted(set(stages)):
        stage = STAGES[index - 1]
        path = receipt_path(root, stage)
        if not path.is_file():
            continue
        receipt = read_json(path)
        receipt["status"] = "stale"
        receipt["invalidated_at"] = utc_now()
        receipt["invalidation_reason"] = reason
        atomic_write_json(path, receipt)


def clear_authority_from(authority: dict[str, Any], role: str) -> bool:
    order = ("script", "narration", "subtitle")
    start = order.index(role)
    changed = False
    for current_role in order[start:]:
        if authority.get(current_role, {}).get("state") == "frozen":
            changed = True
        authority[current_role] = {"state": "unbound"}
    if role in {"script", "narration", "subtitle"}:
        authority["delivery_spec"]["target_frame_count"] = None
    if changed:
        authority["revision"] += 1
        authority["updated_at"] = utc_now()
    return changed


def all_roles_from_stage(start_index: int) -> set[str]:
    return {role for role, stage in ROLE_STAGE.items() if STAGE_INDEX[stage] >= start_index}


def _legacy_role_impact(role: str) -> tuple[set[int], set[str], str | None]:
    if role in {"evidence_ledger", "source_scout"}:
        return set(range(2, 14)), all_roles_from_stage(2), "script"
    if role in {"script", "script_qa"}:
        return set(range(3, 14)), all_roles_from_stage(3), "script"
    if role in {"narration", "voice_release"}:
        stages = {5, 6, 7, 8, 9, 10, 11, 13}
        roles = {
            "narration", "voice_release", "subtitle", "timing_contract", "source_freeze",
            "track_plan", "a_review", "b_review", "c_review", "bgm_master",
            "integrated_proxy_720", "a_master", "b_master", "c_master", "render_qa",
            "final_video", "final_video_qa",
        }
        return stages, roles, "narration"
    if role in {"subtitle", "timing_contract"}:
        stages = {6, 7, 8, 9, 10, 11, 13}
        roles = {
            "subtitle", "timing_contract", "source_freeze", "track_plan", "a_review",
            "b_review", "c_review", "bgm_master", "integrated_proxy_720", "a_master",
            "b_master", "c_master", "render_qa", "final_video", "final_video_qa",
        }
        return stages, roles, "subtitle"
    if role == "source_freeze":
        return set(range(7, 14)), all_roles_from_stage(7), None
    if role == "track_plan":
        return {8, 9, 10, 11, 13}, {
            "track_plan", "a_review", "b_review", "c_review", "bgm_master",
            "integrated_proxy_720", "a_master", "b_master", "c_master", "render_qa",
            "final_video", "final_video_qa",
        }, None
    if role in {"a_review", "b_review", "c_review"}:
        prefix = role[0]
        master = f"{prefix}_master"
        return {8, 9, 10, 11, 13}, {
            role, "integrated_proxy_720", master, "render_qa", "final_video", "final_video_qa"
        }, None
    if role == "bgm_master":
        return {8, 9, 11, 13}, {
            "bgm_master", "integrated_proxy_720", "final_video", "final_video_qa"
        }, None
    if role == "integrated_proxy_720":
        return {9, 11, 13}, {"integrated_proxy_720", "final_video", "final_video_qa"}, None
    if role in {"a_master", "b_master", "c_master"}:
        return {10, 11, 13}, {role, "render_qa", "final_video", "final_video_qa"}, None
    if role == "render_qa":
        return {10, 11, 13}, {"render_qa", "final_video", "final_video_qa"}, None
    if role in {"final_video", "final_video_qa"}:
        return {11, 13}, {"final_video", "final_video_qa"}, None
    if role in {"cover_candidates", "cover_16_9", "cover_4_3", "cover_3_4"}:
        return {12, 13}, {
            "cover_candidates", "cover_16_9", "cover_4_3", "cover_3_4"
        }, None
    raise WorkflowError(f"cannot invalidate unknown role: {role}")


def role_impact(role: str, authority: dict[str, Any] | None = None) -> tuple[set[int], set[str], str | None]:
    if role == "bgm_master" and contracts.enabled(authority or {}):
        return {9, 11, 13}, {"bgm_master", "integrated_proxy_720", "final_video", "final_video_qa", "split_delivery", "split_delivery_qa"}, None
    if role == "bgm_review":
        return {8, 9, 11, 13}, {"bgm_review", "bgm_master", "integrated_proxy_720", "final_video", "final_video_qa", "split_delivery", "split_delivery_qa"}, None
    if role in {"split_delivery", "split_delivery_qa"}:
        return {11, 13}, {"split_delivery", "split_delivery_qa"}, None
    stages, roles, cleared = _legacy_role_impact(role)
    if "final_video" in roles:
        roles |= {"split_delivery", "split_delivery_qa"}
    if role in {"narration", "voice_release", "subtitle", "timing_contract"}:
        roles.add("bgm_review")
    # Independent cover ratios do not invalidate their selected source or siblings.
    if role in {"cover_4_3", "cover_3_4"}:
        roles = {role}
    return stages, roles, cleared


def set_current_stage(current: dict[str, Any], stage: str, status: str = "pending") -> None:
    current["status"] = "active"
    current["current_stage"] = stage
    current["stage_status"] = "awaiting_user" if stage == "04_script_approval" and status == "pending" else status
    current["next_action"] = NEXT_ACTION[stage]
    current["blocked_by"] = ["current script approval"] if current["stage_status"] == "awaiting_user" else []
    current["revision"] += 1


def seal_errors(
    root: Path,
    authority: dict[str, Any],
    deliverables: dict[str, Any],
    approvals: list[dict[str, Any]],
) -> list[str]:
    errors = authority_errors(root, authority)
    if contracts.enabled(authority):
        errors.extend(current_submission_errors(root, authority, deliverables, approvals))
    for role in ("script", "narration", "subtitle"):
        if authority.get(role, {}).get("state") != "frozen":
            errors.append(f"authority not frozen: {role}")
    if not positive_int(authority.get("delivery_spec", {}).get("target_frame_count")):
        errors.append("target_frame_count is not frozen")
    for stage in STAGES[:12]:
        if not receipt_current(root, stage, authority, deliverables):
            errors.append(f"stage receipt is not current: {stage}")
    delivery_roles = ["final_video"] if delivery_mode(authority) == "integrated" else ["split_delivery"]
    if delivery_mode(authority) == "both":
        delivery_roles.append("final_video")
    final_roles = ["script", "narration", "subtitle", *master_roles(authority), "bgm_master", *delivery_roles,
                   "cover_16_9", "cover_4_3", "cover_3_4"]
    for role in final_roles:
        item = item_for(deliverables, role)
        if item is None:
            errors.append(f"missing final deliverable: {role}")
        else:
            errors.extend(artifact_errors(root, item, authority))
    for role in (*delivery_roles, "cover_16_9", "cover_4_3", "cover_3_4"):
        require_approval(approvals, item_for(deliverables, role), role, errors)
    if delivery_mode(authority) in {"independent_tracks", "both"}:
        errors.extend(contracts.check_split_delivery(root, authority, deliverables.get("items", {})))
    return sorted(set(errors))


def command_init(args: argparse.Namespace) -> int:
    root = Path(args.root).expanduser().resolve()
    title = validated_intake_text("title", args.title)
    theme = validated_intake_text("theme", args.theme)
    duration_range = target_duration_range(
        args.target_duration_min_seconds,
        args.target_duration_max_seconds,
    )
    with project_lock(root):
        paths = root_paths(root)
        if paths["current"].exists():
            raise WorkflowError(f"project is already initialized: {root}")
        tracks = parse_tracks(args.tracks)
        if min(args.width, args.height, args.fps) <= 0:
            raise WorkflowError("width, height and fps must be positive")
        house_style_path = Path(args.house_style).expanduser().resolve()
        house_style = read_json(house_style_path)
        if not str(house_style.get("profile_id", "")).strip():
            raise WorkflowError("house style must declare profile_id")
        if house_style.get('workspace_layout', {}).get('version') == 1:
            if not args.episode_key:
                raise WorkflowError('canonical workspace requires --episode-key, for example GI71_EP004')
            try:
                workspace.valid_key(args.episode_key)
            except ValueError as exc:
                raise WorkflowError(str(exc)) from exc
        paths["stages"].mkdir(parents=True, exist_ok=True)
        paths["stage_history"].mkdir(parents=True, exist_ok=True)
        paths["approvals"].parent.mkdir(parents=True, exist_ok=True)
        paths["approvals"].write_text("", encoding="utf-8")
        now = utc_now()
        delivery_spec = {
            "width": args.width,
            "height": args.height,
            "fps": args.fps,
            "target_duration_range_seconds": duration_range,
            "target_frame_count": None,
            "cut_policy": args.cut_policy,
            "active_tracks": tracks,
            "b_output_mode": args.b_output_mode if "B" in tracks else "disabled",
            "c_output_mode": args.c_output_mode if "C" in tracks else "disabled",
            "final_assembly": args.assembly_tool,
            "cover_ratios": ["16:9", "4:3", "3:4"],
        }
        delivery_spec.update(house_style.get("delivery_defaults", {}))
        if args.delivery_mode:
            delivery_spec["delivery_mode"] = args.delivery_mode
        if args.a_subtitles:
            delivery_spec["a_subtitle_baked"] = args.a_subtitles == "burn"
        if args.final_subtitles:
            delivery_spec["final_subtitle_baked"] = args.final_subtitles == "burn"
        request_contract = {
            "schema_version": 1,
            "frozen_at": now,
            "project": {
                "project_id": root.name,
                "title": title,
                "theme": theme,
            },
            "delivery_spec": delivery_spec,
            "house_style_source": {
                "profile_id": house_style["profile_id"],
                "schema_version": house_style.get("schema_version"),
                "template_sha256": sha256_file(house_style_path),
            },
            "house_style": house_style,
        }
        if house_style.get('workspace_layout', {}).get('version') == 1:
            workspace.create(root, args.episode_key, args.media_root, args.cache_root)
            request_contract['workspace_layout'] = {'path':'workspace_paths.json', 'sha256':sha256_file(root/'workspace_paths.json')}
        atomic_write_json(paths["request_contract"], request_contract)
        authority = {
            "schema_version": 2,
            "revision": 0,
            "updated_at": now,
            "delivery_spec": delivery_spec,
            "script": {"state": "unbound"},
            "narration": {"state": "unbound"},
            "subtitle": {"state": "unbound"},
        }
        deliverables = {
            "schema_version": 1,
            "revision": 0,
            "authority_revision": 0,
            "status": "working",
            "items": {},
            "history": [],
            "updated_at": now,
        }
        current = {
            "schema_version": 1,
            "workflow_version": WORKFLOW_VERSION,
            "project_id": root.name,
            "title": title,
            "theme": theme,
            "revision": 1,
            "status": "active",
            "current_stage": "02_research_scout",
            "stage_status": "pending",
            "next_action": NEXT_ACTION["02_research_scout"],
            "blocked_by": [],
            "last_invalidation": None,
            "updated_at": now,
        }
        atomic_write_json(
            receipt_path(root, "01_init"),
            {
                "schema_version": 1,
                "stage": "01_init",
                "status": "complete",
                "authority_revision": 0,
                "authority_bindings": {},
                "outputs": [],
                "warnings": [],
                "approval_ids": [],
                "config": {
                    "title": title,
                    "theme": theme,
                    "delivery_spec": authority["delivery_spec"],
                    "request_contract": {
                        "path": "request_contract.json",
                        "sha256": sha256_file(paths["request_contract"]),
                    },
                },
                "completed_at": now,
            },
        )
        save_project(root, current, authority, deliverables, [])
        print(paths["current"])
    return 0


def parse_meta(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise WorkflowError(f"invalid --meta-json: {exc}") from exc
    if not isinstance(parsed, dict):
        raise WorkflowError("--meta-json must be a JSON object")
    return parsed


def command_register(args: argparse.Namespace) -> int:
    root = Path(args.root).expanduser().resolve()
    with project_lock(root):
        current, authority, deliverables, approvals, pointer_errors = load_project(root)
        ensure_pointer_integrity(pointer_errors)
        if current.get("status") == "sealed":
            raise WorkflowError("sealed project must be invalidated before registering new artifacts")
        stage = normalize_stage(args.stage)
        if stage != current.get("current_stage"):
            raise WorkflowError(f"can only register to current stage {current.get('current_stage')}")
        if args.role not in ROLE_STAGE or role_stage(args.role, authority) != stage:
            raise WorkflowError(f"role {args.role} does not belong to stage {stage}")
        if args.objective_status not in PASSING_OBJECTIVE_STATES:
            raise WorkflowError("objective status must be pass or pass_with_warnings")
        relative, resolved = relative_artifact_path(root, args.path)
        path_errors = workspace.registration_errors(root, args.role, relative)
        if path_errors:
            raise WorkflowError('; '.join(path_errors))
        meta = parse_meta(args.meta_json)
        candidate_item = {"role": args.role, "path": relative, "sha256": sha256_file(resolved), "meta": meta}
        submission_errors = contracts.check_submission(root, args.role, candidate_item, authority, deliverables.get("items", {}))
        if submission_errors:
            raise WorkflowError("; ".join(submission_errors))
        if item_for(deliverables, args.role):
            stages, roles, authority_clear = role_impact(args.role, authority)
            mark_receipts_stale(root, stages, f"replaced {args.role}")
            for role in roles:
                archive_item(deliverables, role, f"replaced {args.role}")
            if authority_clear:
                clear_authority_from(authority, authority_clear)
        now = utc_now()
        deliverables["items"][args.role] = {
            "role": args.role,
            "path": relative,
            "sha256": sha256_file(resolved),
            "stage": stage,
            "state": "current",
            "objective_status": args.objective_status,
            "registered_at": now,
            "authority_revision": authority["revision"],
            "authority_bindings": authority_bindings(authority),
            "meta": meta,
        }
        deliverables["revision"] += 1
        deliverables["authority_revision"] = authority["revision"]
        deliverables["status"] = "working"
        deliverables["updated_at"] = now
        current["stage_status"] = (
            "awaiting_user" if args.role in APPROVAL_STAGE and APPROVAL_STAGE[args.role] == stage else "in_progress"
        )
        current["revision"] += 1
        save_project(root, current, authority, deliverables, approvals)
        print(json.dumps(deliverables["items"][args.role], ensure_ascii=False, indent=2))
    return 0


def legacy_command_approve(args: argparse.Namespace) -> int:
    root = Path(args.root).expanduser().resolve()
    with project_lock(root):
        current, authority, deliverables, approvals, pointer_errors = load_project(root)
        ensure_pointer_integrity(pointer_errors)
        if args.role not in APPROVAL_STAGE:
            raise WorkflowError(f"role does not accept user approval: {args.role}")
        if not approval_quote_is_explicit(args.role, args.quote):
            raise WorkflowError(
                "approval quote is not an explicit artifact decision; work authorization such as 开始/继续 cannot be recorded as approval"
            )
        expected_stage = APPROVAL_STAGE[args.role]
        if current.get("current_stage") != expected_stage:
            raise WorkflowError(f"{args.role} can only be approved at {expected_stage}")
        item = item_for(deliverables, args.role)
        if item is None:
            raise WorkflowError(f"artifact is not registered: {args.role}")
        drift = artifact_errors(root, item, authority)
        if drift:
            raise WorkflowError("; ".join(drift))
        if approval_for(approvals, item, args.role):
            raise WorkflowError(f"current {args.role} artifact is already approved")
        shown_at = parse_iso(args.shown_at)
        registered_at = parse_iso(str(item["registered_at"]))
        decided_at = datetime.now(timezone.utc)
        if shown_at + timedelta(seconds=1) < registered_at:
            raise WorkflowError("shown_at cannot precede artifact registration")
        if shown_at > decided_at:
            raise WorkflowError("shown_at cannot be in the future")
        approval_id = next_approval_id(approvals)
        if args.role in AUTHORITY_ROLE:
            authority["revision"] += 1
            authority["updated_at"] = utc_now()
            entry = {
                "state": "frozen",
                "path": item["path"],
                "sha256": item["sha256"],
                "approval_id": approval_id,
            }
            if args.role == "narration":
                entry["duration_frame_count"] = item.get("meta", {}).get("duration_frame_count")
            if args.role == "subtitle":
                meta = item.get("meta", {})
                entry.update(
                    {
                        "cue_count": meta.get("cue_count"),
                        "final_end_frame": meta.get("final_end_frame"),
                    }
                )
                authority["delivery_spec"]["target_frame_count"] = meta.get("target_frame_count")
            authority[args.role] = entry
        row = {
            "id": approval_id,
            "stage": expected_stage,
            "decision": "approved",
            "role": args.role,
            "artifact": {"path": item["path"], "sha256": item["sha256"]},
            "authority_revision": authority["revision"],
            "artifact_registered_at": item["registered_at"],
            "shown_at": shown_at.isoformat(),
            "decided_at": decided_at.isoformat(),
            "user_quote": args.quote,
            "scope": args.scope,
        }
        append_jsonl(root_paths(root)["approvals"], row)
        approvals.append(row)
        item["approval_id"] = approval_id
        item["approved_at"] = decided_at.isoformat()
        deliverables["revision"] += 1
        deliverables["authority_revision"] = authority["revision"]
        deliverables["updated_at"] = utc_now()
        current["stage_status"] = "in_progress"
        current["revision"] += 1
        save_project(root, current, authority, deliverables, approvals)
        print(json.dumps(row, ensure_ascii=False, indent=2))
    return 0


def decision_text(role: str, quote: str, clause: str | None = None) -> str:
    if clause:
        clauses = {x.strip() for x in re.split(r"[，,、。；;！？!?\n]", quote) if x.strip()}
        if clause.strip() not in clauses:
            raise WorkflowError("decision clause must be a complete verbatim clause of the user message")
        text = clause.strip()
    else:
        text = quote
    if not approval_quote_is_explicit(role, text):
        raise WorkflowError("the user message does not explicitly approve this artifact scope")
    track_tokens = {"a_review": r"(?<![A-Za-z])A(?:轨|審核|审核|通过|通過|批准|[、，,])",
                    "b_review": r"(?<![A-Za-z])B(?:轨|審核|审核|通过|通過|批准|[、，,])",
                    "c_review": r"(?<![A-Za-z])C(?:轨|審核|审核|通过|通過|批准|[、，,])",
                    "bgm_review": r"BGM|配乐|配樂"}
    mentioned = {key for key, pattern in track_tokens.items() if re.search(pattern, text, re.I)}
    if role in track_tokens and mentioned and role not in mentioned and not re.search(r"全部|所有|整体|整體", text):
        raise WorkflowError("the explicit decision names another track, not this artifact")
    return text


def validate_presentation(root: Path, path: str, role: str, item: dict[str, Any], shown_at: str) -> dict[str, Any]:
    if not isinstance(path, str) or not path.strip() or not (root / path).is_file():
        raise WorkflowError("a real presentation receipt is required for this decision")
    file = (root / path).resolve()
    presentation = read_json(file)
    if presentation.get("schema") != "artifact_presentation_v2":
        raise WorkflowError("presentation must use artifact_presentation_v2")
    if parse_iso(presentation.get("shown_at", "")) != parse_iso(shown_at):
        raise WorkflowError("shown_at differs from the actual presentation receipt")
    evidence = presentation.get("display_evidence", {})
    if evidence.get("type") not in {"chat", "webui", "user_supplied_file"} or not str(evidence.get("locator", "")).strip():
        raise WorkflowError("presentation must identify the actual chat, WebUI display or user-supplied file")
    matches = [x for x in presentation.get("items", []) if x.get("role") == role and x.get("artifact", {}).get("sha256") == item.get("sha256")]
    if not matches:
        raise WorkflowError("the current artifact bytes were not included in that presentation")
    try:
        # A delivery copy may have another path, but must be byte-identical to the shown file.
        for row in matches:
            contracts.checked_ref(root, row["artifact"])
    except ValueError as exc:
        raise WorkflowError(str(exc)) from exc
    return {"path": str(file), "sha256": sha256_file(file)}


def record_decisions(root: Path, quote: str, decisions: list[dict[str, Any]], decided_at: str | None = None) -> list[dict[str, Any]]:
    """Validate the whole batch before appending any decisions. Never invent a display."""
    with project_lock(root):
        current, authority, deliverables, approvals, pointer_errors = load_project(root)
        ensure_pointer_integrity(pointer_errors)
        if current.get("status") == "sealed":
            raise WorkflowError("sealed decisions must not be appended again")
        if not decisions or len({x.get("role") for x in decisions}) != len(decisions):
            raise WorkflowError("approval batch must contain distinct explicit roles")
        when = parse_iso(decided_at) if decided_at else datetime.now(timezone.utc)
        if when > datetime.now(timezone.utc):
            raise WorkflowError("user decision cannot be in the future")
        appended = []
        results = []
        for decision in decisions:
            role = decision.get("role")
            if role not in APPROVAL_STAGE:
                raise WorkflowError(f"role does not accept approval: {role}")
            chosen_clause = decision_text(role, quote, decision.get("decision_clause"))
            expected = APPROVAL_STAGE[role]
            allowed = {expected}
            if role == "split_delivery":
                allowed |= {"12_cover", "13_seal"}
            if current["current_stage"] not in allowed:
                raise WorkflowError(f"{role} cannot be approved at {current['current_stage']}")
            item = item_for(deliverables, role)
            if not item:
                raise WorkflowError(f"artifact is not registered: {role}")
            if role == "bgm_review":
                choice = re.search(r"(?:BGM|配乐|配樂)\s*(?:也|就)?\s*(?:选(?:择|定)?|選(?:擇|定)?|=)\s*([A-Za-z0-9_-]+)", chosen_clause, re.I)
                if choice and choice.group(1).lower() != str(item.get("meta", {}).get("candidate_id", "")).lower():
                    raise WorkflowError("the selected BGM ID differs from the registered audition")
            errors = artifact_errors(root, item, authority)
            errors.extend(contracts.check_submission(root, role, item, authority, deliverables.get("items", {})))
            if errors:
                raise WorkflowError("; ".join(errors))
            existing = approval_for(approvals, item, role)
            if existing:
                results.append({"role": role, "status": "already_approved_unchanged", "approval_id": existing["id"]})
                continue
            shown = parse_iso(decision.get("shown_at", ""))
            if shown > when:
                raise WorkflowError("approval must follow the actual display, not precede it")
            if not str(decision.get("scope", "")).strip():
                raise WorkflowError("each decision needs an explicit scope")
            presentation = validate_presentation(root, decision.get("presentation", ""), role, item, decision["shown_at"])
            approval_id = next_approval_id(approvals)
            if role in AUTHORITY_ROLE:
                authority["revision"] += 1
                authority["updated_at"] = utc_now()
                entry = {"state": "frozen", "path": item["path"], "sha256": item["sha256"], "approval_id": approval_id}
                meta = item.get("meta", {})
                if role == "narration":
                    entry["duration_frame_count"] = meta.get("duration_frame_count")
                if role == "subtitle":
                    entry.update(cue_count=meta.get("cue_count"), final_end_frame=meta.get("final_end_frame"))
                    authority["delivery_spec"]["target_frame_count"] = meta.get("target_frame_count")
                authority[role] = entry
            row = {"id": approval_id, "stage": expected, "decision": "approved", "role": role,
                   "artifact": {"path": item["path"], "sha256": item["sha256"]},
                   "authority_revision": authority["revision"], "artifact_registered_at": item["registered_at"],
                   "shown_at": shown.isoformat(), "decided_at": when.isoformat(), "recorded_at": utc_now(),
                   "presentation": presentation, "user_quote": quote, "decision_clause": chosen_clause,
                   "scope": decision["scope"], "new_full_1x_audition_claimed": False}
            # Full audition evidence remains the separate voice release receipt.
            approvals.append(row)
            appended.append(row)
            results.append(row)
            item["approval_id"] = approval_id
            item["approved_at"] = when.isoformat()
        if appended:
            path = root_paths(root)["approvals"]
            original = path.read_bytes()
            addition = b"".join((json.dumps(x, ensure_ascii=False, sort_keys=True)+"\n").encode() for x in appended)
            temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
            temporary.write_bytes(original + (b"\n" if original and not original.endswith(b"\n") else b"") + addition)
            os.replace(temporary, path)
            deliverables["revision"] += 1
            deliverables["authority_revision"] = authority["revision"]
            deliverables["updated_at"] = utc_now()
            current["stage_status"] = "in_progress"
            current["revision"] += 1
            save_project(root, current, authority, deliverables, approvals)
        return results


def command_approve(args: argparse.Namespace) -> int:
    root = Path(args.root).expanduser().resolve()
    authority = read_json(root / "authority_bundle.json")
    if not contracts.enabled(authority) and not getattr(args, "presentation", None):
        return legacy_command_approve(args)
    results = record_decisions(root, args.quote, [{"role": args.role, "shown_at": args.shown_at,
                "scope": args.scope, "presentation": args.presentation, "decision_clause": args.decision_clause}], args.decided_at)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


def command_approve_batch(args: argparse.Namespace) -> int:
    root = Path(args.root).expanduser().resolve()
    data = read_json(Path(args.decisions).expanduser().resolve())
    if data.get("schema") != "approval_batch_v2":
        raise WorkflowError("approval batch schema must be approval_batch_v2")
    print(json.dumps(record_decisions(root, data["user_quote"], data["decisions"], data.get("decided_at")), ensure_ascii=False, indent=2))
    return 0


def command_authorize_render(args: argparse.Namespace) -> int:
    root = Path(args.root).expanduser().resolve()
    with project_lock(root):
        current, authority, deliverables, approvals, pointer_errors = load_project(root)
        ensure_pointer_integrity(pointer_errors)
        if current.get("current_stage") != "10_formal_render":
            raise WorkflowError("formal render can only be authorized at 10_formal_render")
        contextual = False
        if not render_authorization_quote_is_explicit(args.quote) and not (contracts.enabled(authority) and args.presentation):
            raise WorkflowError(
                "render authorization quote must explicitly authorize 正式渲染, 2K, 2K60, or an equivalent; generic or negative wording is not allowed"
            )
        proxy = item_for(deliverables, "integrated_proxy_720")
        if proxy is None:
            raise WorkflowError("current integrated_proxy_720 is missing")
        drift = artifact_errors(root, proxy, authority)
        if drift:
            raise WorkflowError("; ".join(drift))
        if approval_for(approvals, proxy, "integrated_proxy_720") is None:
            raise WorkflowError("integrated_proxy_720 is not currently approved")
        if formal_render_authorization_for(approvals, proxy, authority.get("revision"), authority.get("delivery_spec")):
            raise WorkflowError("current proxy and authority already have formal render authorization")
        shown_at = parse_iso(args.shown_at)
        registered_at = parse_iso(str(proxy["registered_at"]))
        decided_at = datetime.now(timezone.utc)
        presentation = None
        if args.presentation:
            presentation = validate_presentation(root, args.presentation, "integrated_proxy_720", proxy, args.shown_at)
        elif shown_at + timedelta(seconds=1) < registered_at:
            raise WorkflowError("shown_at cannot precede integrated proxy registration")
        if shown_at > decided_at:
            raise WorkflowError("shown_at cannot be in the future")
        if not render_authorization_quote_is_explicit(args.quote):
            decision_text("integrated_proxy_720", args.quote, args.decision_clause)
            shown = read_json(Path(presentation["path"]))
            next_action = shown.get("next_action", {})
            if next_action.get("action") != "formal_render" or next_action.get("delivery_spec_sha256") != contracts.json_digest(authority["delivery_spec"]):
                raise WorkflowError("contextual continuation requires the presented next step and unchanged output specification")
            contextual = True
        authorization_id = next_approval_id(approvals)
        row = {
            "id": authorization_id,
            "stage": "10_formal_render",
            "gate": "formal_render_authorization",
            "role": "formal_render_authorization",
            "decision": "approved",
            "status": "approved",
            "artifact": {"path": proxy["path"], "sha256": proxy["sha256"]},
            "integrated_proxy_path": proxy["path"],
            "integrated_proxy_sha256": proxy["sha256"],
            "authority_revision": authority["revision"],
            "artifact_registered_at": proxy["registered_at"],
            "shown_at": shown_at.isoformat(),
            "decided_at": decided_at.isoformat(),
            "user_quote": args.quote,
            "scope": args.scope,
            "authorization_basis": "contextual_approved_next_step" if contextual else "explicit_render_instruction",
            "presentation": presentation,
            "delivery_spec_sha256": contracts.json_digest(authority["delivery_spec"]),
            "literal_explicit_render_phrase": not contextual,
        }
        append_jsonl(root_paths(root)["approvals"], row)
        approvals.append(row)
        current["stage_status"] = "in_progress"
        current["blocked_by"] = []
        current["revision"] += 1
        save_project(root, current, authority, deliverables, approvals)
        print(json.dumps(row, ensure_ascii=False, indent=2))
    return 0


def command_advance(args: argparse.Namespace) -> int:
    root = Path(args.root).expanduser().resolve()
    with project_lock(root):
        current, authority, deliverables, approvals, pointer_errors = load_project(root)
        ensure_pointer_integrity(pointer_errors)
        if current.get("status") == "sealed":
            raise WorkflowError("project is already sealed")
        stage = str(current.get("current_stage"))
        if stage == "13_seal":
            raise WorkflowError("use seal at stage 13")
        drift: list[str] = []
        for item in deliverables.get("items", {}).values():
            if isinstance(item, dict):
                drift.extend(artifact_errors(root, item, authority))
        if drift:
            raise WorkflowError("; ".join(sorted(set(drift))))
        errors, warnings = check_stage(root, stage, authority, deliverables, approvals)
        if errors:
            raise WorkflowError("stage gate failed: " + "; ".join(errors))
        write_stage_receipt(root, stage, authority, deliverables, warnings)
        next_stage = first_incomplete_after(root, stage, authority, deliverables)
        set_current_stage(current, next_stage)
        save_project(root, current, authority, deliverables, approvals)
        print(json.dumps({"completed": stage, "current_stage": next_stage, "warnings": warnings}, ensure_ascii=False))
    return 0


def command_invalidate(args: argparse.Namespace) -> int:
    root = Path(args.root).expanduser().resolve()
    with project_lock(root):
        current, authority, deliverables, approvals, pointer_errors = load_project(root)
        ensure_pointer_integrity(pointer_errors)
        if args.role:
            stages, roles, authority_clear = role_impact(args.role, authority)
            if item_for(deliverables, args.role) is None and args.role not in AUTHORITY_ROLE:
                raise WorkflowError(f"role is not current: {args.role}")
            for role in roles:
                archive_item(deliverables, role, args.reason)
            if authority_clear:
                clear_authority_from(authority, authority_clear)
            mark_receipts_stale(root, stages, args.reason)
            earliest = min(stages)
        else:
            stage = normalize_stage(args.from_stage)
            earliest = STAGE_INDEX[stage]
            if earliest == 1:
                raise WorkflowError("initialization cannot be invalidated; create a new project for a new intake")
            for role in list(deliverables.get("items", {})):
                item_stage = role_stage(role, authority)
                if item_stage and STAGE_INDEX[item_stage] >= earliest:
                    archive_item(deliverables, role, args.reason)
            if earliest <= 3:
                clear_authority_from(authority, "script")
            elif earliest <= 5:
                clear_authority_from(authority, "narration")
            elif earliest <= 6:
                clear_authority_from(authority, "subtitle")
            mark_receipts_stale(root, range(earliest, 14), args.reason)
        deliverables["revision"] += 1
        deliverables["authority_revision"] = authority["revision"]
        deliverables["status"] = "working"
        deliverables["updated_at"] = utc_now()
        target_stage = STAGES[earliest - 1]
        set_current_stage(current, target_stage, "stale")
        current["last_invalidation"] = {
            "role": args.role,
            "from_stage": target_stage,
            "reason": args.reason,
            "at": utc_now(),
        }
        save_project(root, current, authority, deliverables, approvals)
        print(json.dumps(current["last_invalidation"], ensure_ascii=False, indent=2))
    return 0


def command_status(args: argparse.Namespace) -> int:
    root = Path(args.root).expanduser().resolve()
    current, authority, deliverables, approvals, pointer_errors = load_project(root)
    stage = str(current.get("current_stage"))
    artifact_drift: list[str] = []
    for item in deliverables.get("items", {}).values():
        if isinstance(item, dict):
            artifact_drift.extend(artifact_errors(root, item, authority))
    errors, warnings = check_stage(root, stage, authority, deliverables, approvals)
    payload = {
        "project": str(root),
        "title": current.get("title"),
        "workflow_version": current.get("workflow_version"),
        "status": current.get("status"),
        "current_stage": stage,
        "stage_status": current.get("stage_status"),
        "next_action": current.get("next_action"),
        "authority_revision": authority.get("revision"),
        "active_tracks": authority.get("delivery_spec", {}).get("active_tracks"),
        "delivery_mode": delivery_mode(authority),
        "production_contract_version": authority.get("delivery_spec", {}).get("production_contract_version", 1),
        "current_roles": sorted(deliverables.get("items", {})),
        "pointer_errors": pointer_errors,
        "artifact_drift": sorted(set(artifact_drift)),
        "gate_ready": not pointer_errors and not artifact_drift and not errors,
        "gate_errors": errors,
        "warnings": warnings,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def command_seal(args: argparse.Namespace) -> int:
    root = Path(args.root).expanduser().resolve()
    with project_lock(root):
        current, authority, deliverables, approvals, pointer_errors = load_project(root)
        ensure_pointer_integrity(pointer_errors)
        if current.get("current_stage") != "13_seal":
            raise WorkflowError("seal is only allowed at stage 13")
        errors = seal_errors(root, authority, deliverables, approvals)
        if errors:
            raise WorkflowError("seal gate failed: " + "; ".join(errors))
        write_stage_receipt(root, "13_seal", authority, deliverables, [])
        deliverables["revision"] += 1
        deliverables["status"] = "sealed"
        deliverables["sealed_at"] = utc_now()
        deliverables["updated_at"] = utc_now()
        current["revision"] += 1
        current["status"] = "sealed"
        current["current_stage"] = "13_seal"
        current["stage_status"] = "complete"
        current["next_action"] = ""
        current["blocked_by"] = []
        save_project(root, current, authority, deliverables, approvals)
        print(json.dumps({"status": "sealed", "root": str(root)}, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="initialize and complete stage 01")
    init.add_argument("--root", required=True)
    init.add_argument("--title", required=True)
    init.add_argument("--theme", required=True)
    init.add_argument("--width", type=int, required=True)
    init.add_argument("--height", type=int, required=True)
    init.add_argument("--fps", type=int, required=True)
    init.add_argument("--target-duration-min-seconds", type=int)
    init.add_argument("--target-duration-max-seconds", type=int)
    init.add_argument("--cut-policy", choices=("per_caption_refresh", "semantic_hold"), required=True)
    init.add_argument("--tracks", required=True)
    init.add_argument("--b-output-mode", choices=("green", "alpha"), required=True)
    init.add_argument("--c-output-mode", choices=("green", "alpha"), required=True)
    init.add_argument("--assembly-tool", choices=("jianying", "hyperframes"), required=True)
    init.add_argument("--house-style", default=str(DEFAULT_HOUSE_STYLE))
    init.add_argument("--delivery-mode", choices=("integrated", "independent_tracks", "both"))
    init.add_argument("--a-subtitles", choices=("exclude", "burn"))
    init.add_argument("--final-subtitles", choices=("exclude", "burn"))
    init.add_argument('--episode-key', help='Stable ASCII key, e.g. GI71_EP004; use across the cache and asset index')
    init.add_argument('--media-root', help='Durable common media library; default ~/Documents/视频工作区/02_素材库/00_原始素材库')
    init.add_argument('--cache-root', help='Local cache base; default ~/Documents/视频工作区/03_制作缓存')
    init.set_defaults(func=command_init)

    status = subparsers.add_parser("status", help="show current stage and gate")
    status.add_argument("--root", required=True)
    status.set_defaults(func=command_status)

    register = subparsers.add_parser("register", help="register one current-stage artifact")
    register.add_argument("--root", required=True)
    register.add_argument("--stage", required=True)
    register.add_argument("--role", required=True, choices=tuple(sorted(ROLE_STAGE)))
    register.add_argument("--path", required=True)
    register.add_argument("--objective-status", choices=tuple(sorted(PASSING_OBJECTIVE_STATES)), default="pass")
    register.add_argument("--meta-json", default="{}")
    register.set_defaults(func=command_register)

    approve = subparsers.add_parser("approve", help="bind one user approval to one current artifact")
    approve.add_argument("--root", required=True)
    approve.add_argument("--role", required=True, choices=tuple(sorted(APPROVAL_STAGE)))
    approve.add_argument("--shown-at", required=True)
    approve.add_argument("--quote", required=True)
    approve.add_argument("--scope", required=True)
    approve.add_argument("--presentation", help="Actual display receipt; required for v2 and pre-registration displays")
    approve.add_argument("--decision-clause", help="Complete verbatim positive clause when the same message contains separate corrections")
    approve.add_argument("--decided-at", help="Actual user decision timestamp, distinct from registration and recording")
    approve.set_defaults(func=command_approve)

    batch = subparsers.add_parser("approve-batch", help="Record several scoped decisions from one real user message")
    batch.add_argument("--root", required=True)
    batch.add_argument("--decisions", required=True, help="approval_batch_v2 JSON file")
    batch.set_defaults(func=command_approve_batch)

    authorize_render = subparsers.add_parser(
        "authorize-render",
        help="bind explicit formal-render authorization to the approved integrated 720 proxy",
    )
    authorize_render.add_argument("--root", required=True)
    authorize_render.add_argument("--shown-at", required=True)
    authorize_render.add_argument("--quote", required=True)
    authorize_render.add_argument("--scope", required=True)
    authorize_render.add_argument("--presentation")
    authorize_render.add_argument("--decision-clause")
    authorize_render.set_defaults(func=command_authorize_render)

    advance = subparsers.add_parser("advance", help="complete the current stage after its gate passes")
    advance.add_argument("--root", required=True)
    advance.set_defaults(func=command_advance)

    invalidate = subparsers.add_parser("invalidate", help="invalidate an artifact or a stage and its dependents")
    invalidate.add_argument("--root", required=True)
    group = invalidate.add_mutually_exclusive_group(required=True)
    group.add_argument("--role", choices=tuple(sorted(ROLE_STAGE)))
    group.add_argument("--from-stage")
    invalidate.add_argument("--reason", required=True)
    invalidate.set_defaults(func=command_invalidate)

    seal = subparsers.add_parser("seal", help="seal the unique current delivery")
    seal.add_argument("--root", required=True)
    seal.set_defaults(func=command_seal)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except WorkflowError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
