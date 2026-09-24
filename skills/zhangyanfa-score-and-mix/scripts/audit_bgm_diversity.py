#!/usr/bin/env python3
"""Audit composition-level BGM discovery and reuse before presenting auditions.

This checks declared editorial metadata and actual file identities; it does not
certify musical quality, listening approval, or publishing rights.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

DEFAULTS = {
    "candidate_count": 4,
    "minimum_shortlist_compositions": 12,
    "recent_episode_count": 3,
    "minimum_fresh_leads": 3,
    "maximum_recent_selected_leads": 1,
    "minimum_lead_palettes": 3,
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def audit(catalog: dict, history: dict, plan: dict,
          review_manifest: dict | None = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    tracks: dict[str, dict] = {}
    sha_families: dict[str, str] = {}
    for row in catalog.get("tracks", []):
        tid = row.get("track_id")
        cid = row.get("composition_id")
        if not tid or tid in tracks or not cid or len(row.get("sha256", "")) != 64:
            errors.append("catalog: track IDs, composition IDs and actual SHA values are required")
            continue
        if row["sha256"] in sha_families and sha_families[row["sha256"]] != cid:
            errors.append("catalog: identical source bytes cannot have different composition IDs")
        sha_families[row["sha256"]] = cid
        tracks[tid] = row

    exceptions = {r.get("code"): str(r.get("reason", "")).strip()
                  for r in plan.get("exceptions", []) if isinstance(r, dict)}

    def editorial_issue(code: str, message: str) -> None:
        if exceptions.get(code):
            warnings.append(f"{code}: {message}; editorial exception: {exceptions[code]}")
        else:
            errors.append(f"{code}: {message}")

    # Defaults are deliberately configurable, but reduced discovery must be visible.
    policy = dict(DEFAULTS)
    for key, value in plan.get("policy", {}).items():
        if key not in DEFAULTS or not isinstance(value, int) or isinstance(value, bool) or value < 0:
            errors.append(f"policy: invalid {key}")
            continue
        policy[key] = value
    if policy != DEFAULTS and not str(plan.get("policy_reason", "")).strip():
        errors.append("policy: a project-specific change needs policy_reason")
    if policy["candidate_count"] < 1 or policy["recent_episode_count"] < 1:
        errors.append("policy: candidate count and history window must be positive")
    if not history.get("scope"):
        errors.append("history: explicit scope required; empty history must not imply all projects were checked")
    episodes = history.get("episodes", [])
    if not isinstance(episodes, list):
        errors.append("history: episodes must be an ordered list")
        episodes = []
    recent = episodes[-policy["recent_episode_count"]:]

    def families(ids: list, label: str) -> set[str]:
        result = set()
        for tid in ids:
            if tid not in tracks:
                errors.append(f"{label}: unknown track_id {tid}")
            else:
                result.add(tracks[tid]["composition_id"])
        return result

    recent_presented: set[str] = set()
    recent_selected: set[str] = set()
    for episode in recent:
        recent_presented |= families(episode.get("candidate_track_ids", []), "history candidate")
        recent_selected |= families(episode.get("selected_track_ids", []), "history selected")
    shortlist = plan.get("shortlist", [])
    shortlist_ids = [row.get("track_id") for row in shortlist]
    shortlist_families = families(shortlist_ids, "shortlist")
    if any(not str(row.get("fit_reason", "")).strip() for row in shortlist):
        errors.append("shortlist: each track needs a concrete fit_reason")
    if len(shortlist_families) < policy["minimum_shortlist_compositions"]:
        editorial_issue("shortlist_too_small", f"only {len(shortlist_families)} distinct works were considered")
    candidates = plan.get("candidates", [])
    if len(candidates) != policy["candidate_count"]:
        errors.append("candidates: count does not match the frozen project policy")
    seen_ids: set[str] = set()
    leads: list[str] = []
    palettes: set[str] = set()
    candidate_source_shas: dict[str, set[str]] = {}
    selected_sources: set[str] = set()
    for row in candidates:
        candidate_id = row.get("candidate_id")
        if not candidate_id or candidate_id in seen_ids:
            errors.append("candidates: missing or duplicate candidate_id")
        seen_ids.add(candidate_id)
        lead = row.get("lead_track_id")
        tids = row.get("track_ids", [])
        if lead not in tids or lead not in tracks:
            errors.append(f"{candidate_id}: valid lead must appear in track_ids")
            continue
        if any(tid not in shortlist_ids for tid in tids):
            errors.append(f"{candidate_id}: all tracks must come from the evaluated shortlist")
        families(tids, str(candidate_id))
        leads.append(tracks[lead]["composition_id"])
        palette = tracks[lead].get("palette")
        if palette and palette != "unclassified":
            palettes.add(palette)
        else:
            errors.append(f"{candidate_id}: lead palette must be classified before audition design")
        selected_sources.update(tids)
        candidate_source_shas[str(candidate_id)] = {tracks[t]["sha256"] for t in tids if t in tracks}
        for key in ("rationale", "evidence_strategy", "turn_strategy"):
            if not str(row.get(key, "")).strip():
                errors.append(f"{candidate_id}: {key} required")
        if any(tracks[t].get("vocal_content") not in {"instrumental", "none"}
               for t in tids if t in tracks) and not row.get("vocal_review"):
            errors.append(f"{candidate_id}: vocal or unclassified source needs vocal_review")
    # This invariant is not waived by changing gain, crop, filename, or candidate label.
    if len(set(leads)) != len(leads):
        errors.append("duplicate_lead_composition: alternate mixes/crops are not independent directions")
    fresh = set(leads) - recent_presented
    repeated_selected = set(leads) & recent_selected
    if len(fresh) < policy["minimum_fresh_leads"]:
        editorial_issue("too_few_fresh_leads", f"{len(fresh)} lead works were absent from recent candidates")
    if len(repeated_selected) > policy["maximum_recent_selected_leads"]:
        editorial_issue("recent_selection_overuse", f"{len(repeated_selected)} leads were selected in recent episodes")
    if len(palettes) < policy["minimum_lead_palettes"]:
        editorial_issue("palette_concentration", f"only {len(palettes)} declared instrumental palettes")

    if review_manifest is not None:
        receipts = {r.get("source_id"): r for r in review_manifest.get("source_receipts", [])}
        actual_ids = set()
        for row in review_manifest.get("candidates", []):
            cid = row.get("candidate_id")
            actual_ids.add(cid)
            actual_shas = set()
            for point in row.get("checkpoints", []):
                source = receipts.get(point.get("source_id"), {})
                digest = point.get("source_sha256") or source.get("sha256")
                if digest:
                    actual_shas.add(digest)
                if point.get("source_sha256") and source.get("sha256") != point["source_sha256"]:
                    errors.append(f"{cid}: checkpoint and source receipt disagree")
            # Multi-track manifests may list all exact sources at candidate level.
            for sid in row.get("source_ids", []):
                if sid in receipts:
                    actual_shas.add(receipts[sid].get("sha256"))
            if not actual_shas or actual_shas != candidate_source_shas.get(cid):
                errors.append(f"{cid}: audition source identities differ from discovery plan")
        if actual_ids != seen_ids:
            errors.append("review manifest: candidate set differs from discovery plan")

    return {
        "schema": "bgm_diversity_audit_v1",
        "status": "PASS" if not errors else "FAIL",
        "scope": "declared composition identity, source binding and reuse; not human audition",
        "history_scope": history.get("scope"),
        "history_episode_count": len(recent),
        "shortlist_composition_count": len(shortlist_families),
        "candidate_count": len(candidates),
        "fresh_lead_count": len(fresh),
        "recent_selected_lead_count": len(repeated_selected),
        "lead_palette_count": len(palettes),
        "audition_manifest_checked": review_manifest is not None,
        "referenced_track_ids": sorted(selected_sources),
        "policy": policy,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--review-manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    documents = {}
    bindings = {}
    for key in ("catalog", "history", "plan", "review_manifest"):
        path = getattr(args, key)
        if path:
            documents[key] = json.loads(path.read_text(encoding="utf-8"))
            bindings[key] = {"path": str(path.resolve()), "sha256": sha256_file(path)}
    result = audit(documents["catalog"], documents["history"], documents["plan"],
                   documents.get("review_manifest"))
    tracks = {row["track_id"]: row for row in documents["catalog"].get("tracks", [])}
    for tid in result["referenced_track_ids"]:
        row = tracks[tid]
        path = Path(row.get("path", "")).expanduser()
        if not path.is_absolute():
            path = args.catalog.parent / path
        if not path.is_file() or sha256_file(path) != row["sha256"]:
            result["errors"].append(f"source file missing or changed: {tid}")
    result["status"] = "PASS" if not result["errors"] else "FAIL"
    result["input_bindings"] = bindings
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
