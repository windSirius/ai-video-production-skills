#!/usr/bin/env python3
from __future__ import annotations

import copy
import csv
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def write_tsv(path: Path, fields: list[str], rows: list[list[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(fields)
        writer.writerows(rows)


def run(script: Path, *args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *map(str, args)],
        check=False, capture_output=True, text=True,
    )


class VisualModuleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="visual-modules-")
        self.base = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def assertPass(self, result: subprocess.CompletedProcess[str]) -> None:
        self.assertEqual(result.returncode, 0, f"stdout={result.stdout}\nstderr={result.stderr}")

    def assertFail(self, result: subprocess.CompletedProcess[str], needle: str | None = None) -> None:
        self.assertNotEqual(result.returncode, 0, f"unexpected PASS: {result.stdout}")
        if needle:
            self.assertIn(needle, result.stdout + result.stderr)

    def image(self, name: str, size: str, color: str) -> Path:
        path = self.base / f"{name}.png"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"color=c={color}:s={size}", "-frames:v", "1", "-y", str(path)],
            check=True,
        )
        return path

    def ingest_fixture(self) -> tuple[list[str], Path]:
        source = self.base / "source.bin"
        source.write_bytes(b"source")
        proof = self.base / "proof.jpg"
        proof.write_bytes(b"proof")
        manifest = self.base / "source_manifest.jsonl"
        write_jsonl(manifest, [{
            "source_id": "s1", "path": str(source), "sha256": sha(source),
            "rights_status": "official", "probe": {"duration_s": 2.0},
        }])
        rights = self.base / "rights.tsv"
        write_tsv(rights, ["source_id", "rights_status"], [["s1", "official"]])
        shots = self.base / "shots.tsv"
        write_tsv(shots, ["shot_id", "source_id", "start_s", "end_s", "visual_family_id"], [
            ["sh1", "s1", 0, 1, "fam1"], ["sh2", "s1", 1, 2, "fam2"],
        ])
        ocr = self.base / "ocr.tsv"
        write_tsv(ocr, ["source_id", "shot_id", "start_s", "end_s", "ocr_text", "asr_text", "transcript_status"], [
            ["s1", "sh1", 0, 1, "", "", "not_present"],
            ["s1", "sh2", 1, 2, "角色甲", "", "complete"],
        ])
        coverage = self.base / "coverage.jsonl"
        write_jsonl(coverage, [{
            "source_id": "s1", "source_sha256": sha(source), "reviewer": "tester",
            "review_status": "pass", "intervals": [
                {"start_s": 0, "end_s": 1, "classification": "content"},
                {"start_s": 1, "end_s": 2, "classification": "dialogue"},
            ],
        }])
        identities = self.base / "identities.json"
        write_json(identities, {"identities": [{
            "canonical_identity": "角色甲", "visible_features": ["红衣"], "confusables": [],
            "proof_frames": [{"path": str(proof), "sha256": sha(proof)}],
        }]})
        p0 = self.base / "p0.tsv"
        write_tsv(p0, ["p0_id", "status", "source_id", "notes"], [["p1", "available", "s1", ""]])
        args = [
            "--source-manifest", str(manifest), "--rights-ledger", str(rights),
            "--shot-index", str(shots), "--ocr-asr-index", str(ocr),
            "--coverage-receipts", str(coverage), "--identity-registry", str(identities),
            "--p0-coverage", str(p0),
        ]
        return args, coverage

    def test_ingest_requires_ocr_and_full_coverage_receipt(self) -> None:
        script = ROOT / "game-footage-ingest-index/scripts/audit_ingest.py"
        args, coverage = self.ingest_fixture()
        self.assertPass(run(script, *args))
        no_ocr = [value for index, value in enumerate(args) if not (index > 0 and args[index - 1] == "--ocr-asr-index")]
        no_ocr.remove("--ocr-asr-index")
        self.assertFail(run(script, *no_ocr), "--ocr-asr-index")
        data = json.loads(coverage.read_text(encoding="utf-8").splitlines()[0])
        data["intervals"][1]["start_s"] = 1.2
        write_jsonl(coverage, [data])
        self.assertFail(run(script, *args), "uncovered interval")

    def track_fixture(self) -> tuple[list[str], Path, Path, list[dict]]:
        source = self.base / "track-source.bin"
        source.write_bytes(b"track")
        proof = self.base / "selected-proof.jpg"
        proof.write_bytes(b"visible-character")
        shot_index = self.base / "track-shots.tsv"
        write_tsv(shot_index, ["shot_id", "source_id", "start_s", "end_s", "visual_family_id"], [
            ["sh1", "s1", 0, 1, "fam1"], ["sh2", "s1", 1, 2, "fam2"], ["sh3", "s1", 2, 3, "fam3"],
        ])
        rights = self.base / "track-rights.tsv"
        write_tsv(rights, ["source_id", "rights_status"], [["s1", "official"]])
        fields = [
            "cue_id", "start_frame", "end_frame", "text", "track", "candidate_id", "shot_id",
            "source_id", "source_in", "source_out", "visual_family_id", "visual_transform",
            "match_class", "match_reason", "identity_required", "identity_proof_id",
            "refresh_from_previous", "continuity_override_id", "review_status",
        ]
        rows = [
            [1, 0, 60, "引子", "A", "a1", "sh1", "s1", 0, 1, "fam1", "none", "direct", "场景", "false", "", "start", "", "pass"],
            [2, 60, 120, "角色甲出现", "A", "a2", "sh2", "s1", 1, 2, "fam2", "none", "direct", "角色可见", "true", "proof-2", "true", "", "pass"],
            [3, 120, 180, "继续", "A", "a3", "sh3", "s1", 2, 3, "fam3", "none", "strong", "动作", "false", "", "true", "", "pass"],
            [2, 60, 120, "角色甲出现", "B", "b2", "card2", "s1", 1, 2, "card-fam", "none", "direct", "证据卡", "false", "", "start", "", "pass"],
            [2, 60, 120, "角色甲出现", "C", "c2", "symbol2", "s1", 1, 2, "symbol-fam", "none", "support", "象征层", "false", "", "start", "", "pass"],
        ]
        plan = self.base / "track_plan.tsv"
        write_tsv(plan, fields, rows)
        identity = self.base / "identity.jsonl"
        proof_row = {
            "proof_id": "proof-2", "cue_id": 2, "track": "A", "candidate_id": "a2",
            "source_id": "s1", "source_in": 1, "source_out": 2,
            "canonical_identity": "角色甲", "identity_basis": "visible_character_features",
            "visible_features": ["red coat", "round badge"], "confusables_checked": [],
            "identity_verdict": "verified", "reviewer": "tester", "review_status": "pass",
            "head_frame": str(proof), "head_sha256": sha(proof), "head_source_time": 1,
            "mid_frame": str(proof), "mid_sha256": sha(proof), "mid_source_time": 1.5,
            "tail_frame": str(proof), "tail_sha256": sha(proof), "tail_source_time": 2,
        }
        write_jsonl(identity, [proof_row])
        approvals: list[dict] = []
        track_reviews = {"tracks": {}}
        for track in "ABC":
            artifact = self.base / f"review-{track}.mp4"
            artifact.write_bytes(track.encode())
            approval_id = f"review-{track}"
            track_reviews["tracks"][track] = {
                "artifact": {"path": str(artifact), "sha256": sha(artifact)}, "approval_id": approval_id,
            }
            approvals.append({
                "approval_id": approval_id, "gate": f"{track.lower()}_track_review", "status": "approved",
                "artifact": {"path": str(artifact), "sha256": sha(artifact)},
            })
        review_path = self.base / "track_reviews.json"
        write_json(review_path, track_reviews)
        approval_path = self.base / "track_approvals.jsonl"
        write_jsonl(approval_path, approvals)
        args = [
            str(plan), "--identity-proof", str(identity), "--approvals", str(approval_path),
            "--track-reviews", str(review_path), "--shot-index", str(shot_index),
            "--rights-ledger", str(rights), "--expected-cue-count", "3",
            "--required-tracks", "A,B,C", "--stage", "reviewed",
        ]
        return args, identity, shot_index, rows

    def test_track_allows_same_cue_across_tracks_and_blocks_ocr_or_crop_reuse(self) -> None:
        script = ROOT / "zhangyanfa-track-design/scripts/audit_track_plan.py"
        args, identity, shot_index, rows = self.track_fixture()
        self.assertPass(run(script, *args))
        proof = json.loads(identity.read_text(encoding="utf-8").splitlines()[0])
        proof["visible_features"] = ["OCR name 角色甲"]
        write_jsonl(identity, [proof])
        self.assertFail(run(script, *args), "OCR/dialogue/name")
        proof["visible_features"] = ["red coat"]
        write_jsonl(identity, [proof])
        write_tsv(shot_index, ["shot_id", "source_id", "start_s", "end_s", "visual_family_id"], [
            ["sh1", "s1", 0, 1, "fam1"], ["sh2", "s1", 1, 2, "fam2"], ["sh3", "s1", 2, 3, "fam2"],
        ])
        plan = Path(args[0])
        rows[2][10] = "fam2"
        with plan.open(encoding="utf-8") as handle:
            fields = next(csv.reader(handle, delimiter="\t"))
        write_tsv(plan, fields, rows)
        self.assertFail(run(script, *args), "A per_caption_refresh")

    def test_reverse_source_order_only_blocks_actual_interval_overlap(self) -> None:
        script = ROOT / "zhangyanfa-track-design/scripts/audit_track_plan.py"
        args, identity, shot_index, rows = self.track_fixture()
        plan = Path(args[0])
        with plan.open(encoding="utf-8") as handle:
            fields = next(csv.reader(handle, delimiter="\t"))
        rows[0][8:10] = [3, 4]
        rows[2][8:10] = [4, 5]
        write_tsv(plan, fields, rows)
        shot_fields = ["shot_id", "source_id", "start_s", "end_s", "visual_family_id"]
        write_tsv(shot_index, shot_fields, [
            ["sh1", "s1", 3, 4, "fam1"], ["sh2", "s1", 1, 2, "fam2"],
            ["sh3", "s1", 4, 5, "fam3"],
        ])
        self.assertPass(run(script, *args))
        rows[0][8:10] = [1.5, 2.5]
        write_tsv(plan, fields, rows)
        write_tsv(shot_index, shot_fields, [
            ["sh1", "s1", 1.5, 2.5, "fam1"], ["sh2", "s1", 1, 2, "fam2"],
            ["sh3", "s1", 4, 5, "fam3"],
        ])
        self.assertFail(run(script, *args), "A per_caption_refresh")

    def bgm_fixture(self) -> tuple[list[str], Path, Path]:
        narration = self.base / "narration.wav"
        narration.write_bytes(b"narration")
        srt = self.base / "final.srt"
        srt.write_text("1\n00:00:00,000 --> 00:00:02,000\ntext\n", encoding="utf-8")
        auditions: dict[str, Path] = {}
        for letter in "ABCD":
            path = self.base / f"audition-{letter}.wav"
            path.write_bytes(f"audition-{letter}".encode())
            auditions[letter] = path
        master = self.base / "bgm-master.wav"
        master.write_bytes(b"master")
        manifest = self.base / "bgm.json"
        data = {
            "source_mode": "local_library",
            "authority_bindings": {
                "narration": {"path": str(narration), "sha256": sha(narration)},
                "srt": {"path": str(srt), "sha256": sha(srt)}, "fps": 60, "target_frame_count": 120,
            },
            "candidates": [{
                "candidate_id": letter, "direction": f"方向-{letter}",
                "audition_mix": {"path": str(auditions[letter]), "sha256": sha(auditions[letter])},
                "narration_sha256": sha(narration), "review_range_frames": [0, 120],
            } for letter in "ABCD"],
            "selected_candidate_id": "D",
            "sections": [
                {"chapter": "前", "mood": "紧张", "rhetorical_job": "设问", "vocal_content": "instrumental", "candidate_id": "D", "start_frame": 0, "end_frame": 60},
                {"chapter": "后", "mood": "克制", "rhetorical_job": "结论", "vocal_content": "instrumental", "candidate_id": "D", "start_frame": 60, "end_frame": 120},
            ],
            "bgm_master": {"path": str(master), "sha256": sha(master)},
            "approved_audition_mix": {"path": str(auditions["D"]), "sha256": sha(auditions["D"])},
            "approval_id": "bgm-1",
        }
        write_json(manifest, data)
        approvals = self.base / "bgm-approvals.jsonl"
        write_jsonl(approvals, [{
            "approval_id": "bgm-1", "gate": "bgm_review", "status": "approved",
            "artifact": {"path": str(auditions["D"]), "sha256": sha(auditions["D"])},
        }])
        return [str(manifest), "--approvals", str(approvals)], manifest, approvals

    def test_bgm_blocks_fake_authority_duplicate_audio_gaps_and_unbound_approval(self) -> None:
        script = ROOT / "zhangyanfa-score-and-mix/scripts/audit_bgm_manifest.py"
        args, manifest, approvals = self.bgm_fixture()
        self.assertPass(run(script, *args))
        baseline = json.loads(manifest.read_text(encoding="utf-8"))
        duplicate = copy.deepcopy(baseline)
        duplicate["candidates"][1]["audition_mix"] = duplicate["candidates"][0]["audition_mix"]
        write_json(manifest, duplicate)
        self.assertFail(run(script, *args), "duplicates another candidate")
        gap = copy.deepcopy(baseline)
        gap["sections"][1]["start_frame"] = 70
        write_json(manifest, gap)
        self.assertFail(run(script, *args), "contiguously cover")
        write_json(manifest, baseline)
        write_jsonl(approvals, [{"approval_id": "bgm-1", "gate": "bgm_review", "status": "approved"}])
        self.assertFail(run(script, *args), "artifact-bound")

    def cover_fixture(self) -> tuple[list[str], Path, dict]:
        source = self.image("cover-source", "160x90", "white")
        recent = [self.image(f"recent-{i}", "160x90", color) for i, color in enumerate(["red", "green", "blue"])]
        concepts = [self.image(f"concept-{letter}", "160x90", color) for letter, color in zip("ABCDEF", ["yellow", "cyan", "magenta", "orange", "purple", "pink"])]
        ratio43 = self.image("ratio-43", "160x120", "green")
        ratio34 = self.image("ratio-34", "90x120", "blue")
        gates = {
            "identity_pass": "pass", "shot_pass": "pass", "same_space_pass": "pass",
            "text_pass": "pass", "thumbnail_pass": "pass", "edge_artifact_pass": "pass",
            "source_rights_pass": "pass", "recent_cover_compare_pass": "pass",
        }
        rows = [{
            "concept_id": letter, "narrative_direction": f"方向-{letter}", "source_ids": ["official-1"],
            "artifact": {"path": str(path), "sha256": sha(path)}, **gates,
        } for letter, path in zip("ABCDEF", concepts)]
        data = {
            "cover_promise": "角色甲掌控局势",
            "cover_sources": [{
                "source_id": "official-1", "role": "identity_model", "rights_status": "official",
                "artifact": {"path": str(source), "sha256": sha(source)},
            }],
            "recent_covers": [{"path": str(path), "sha256": sha(path)} for path in recent],
            "concepts_16_9": rows, "selected_concept_id": "A",
            "approved_16_9": {"path": str(concepts[0]), "sha256": sha(concepts[0])},
            "ratio_reviews": {
                "4:3": {"artifact": {"path": str(ratio43), "sha256": sha(ratio43)}, "source_16_9_sha256": sha(concepts[0]), "layout_operations": ["subject_reposition"], "subject_not_occluded": "pass", "aspect_ratio_preserved": "pass", "thumbnail_readable": "pass", "title_safe_area_pass": "pass", "independent_layout": "pass"},
                "3:4": {"artifact": {"path": str(ratio34), "sha256": sha(ratio34)}, "source_16_9_sha256": sha(concepts[0]), "layout_operations": ["title_reflow"], "subject_not_occluded": "pass", "aspect_ratio_preserved": "pass", "thumbnail_readable": "pass", "title_safe_area_pass": "pass", "independent_layout": "pass"},
            },
            "cover_review": {"status": "approved", "approved_sha256": sha(concepts[0])},
        }
        manifest = self.base / "cover.json"
        write_json(manifest, data)
        return [str(manifest)], manifest, data

    def test_cover_blocks_duplicate_concepts_and_mechanical_ratio_resize(self) -> None:
        script = ROOT / "zhangyanfa-cover-production/scripts/audit_cover_manifest.py"
        args, manifest, baseline = self.cover_fixture()
        self.assertPass(run(script, *args))
        duplicate = copy.deepcopy(baseline)
        duplicate["concepts_16_9"][1]["artifact"] = duplicate["concepts_16_9"][0]["artifact"]
        write_json(manifest, duplicate)
        self.assertFail(run(script, *args), "six unique visual SHAs")
        mechanical = self.base / "mechanical-43.png"
        subprocess.run(["ffmpeg", "-v", "error", "-i", baseline["approved_16_9"]["path"], "-vf", "scale=160:120", "-y", str(mechanical)], check=True)
        resized = copy.deepcopy(baseline)
        resized["ratio_reviews"]["4:3"]["artifact"] = {"path": str(mechanical), "sha256": sha(mechanical)}
        write_json(manifest, resized)
        self.assertFail(run(script, *args), "mechanical resize detected")

    def renderer_project(self, include_authorization: bool = True) -> Path:
        root = self.base / ("project-authorized" if include_authorization else "project-no-authorization")
        (root / "approvals").mkdir(parents=True)
        proxy = root / "integrated-720.mp4"
        proxy.write_bytes(b"integrated")
        authority = {"revision": 7}
        write_json(root / "authority_bundle.json", authority)
        deliverables = {"items": {"integrated_proxy_720": {
            "path": "integrated-720.mp4", "sha256": sha(proxy), "approval_id": "proxy-1",
        }}}
        write_json(root / "deliverables.json", deliverables)
        approvals = [{
            "id": "proxy-1", "decision": "approved", "role": "integrated_proxy_720",
            "artifact": {"path": "integrated-720.mp4", "sha256": sha(proxy)},
        }]
        if include_authorization:
            approvals.append({
                "id": "formal-1", "decision": "approved", "gate": "formal_render_authorization",
                "integrated_proxy_sha256": sha(proxy), "authority_revision": 7,
                "user_quote": "批准当前整合代理进入正式渲染",
            })
        write_jsonl(root / "approvals/approval_ledger.jsonl", approvals)
        current = {
            "status": "active", "current_stage": "10_formal_render", "stage_status": "pending",
            "authority": {"path": "authority_bundle.json", "sha256": sha(root / "authority_bundle.json")},
            "deliverables": {"path": "deliverables.json", "sha256": sha(root / "deliverables.json")},
            "approvals": {"path": "approvals/approval_ledger.jsonl", "last_id": approvals[-1]["id"]},
        }
        write_json(root / "CURRENT.json", current)
        return root

    def test_renderer_preflight_requires_proxy_approval_and_formal_authorization(self) -> None:
        script = ROOT / "zhangyanfa-track-renderer/scripts/formal_render_preflight.py"
        root = self.renderer_project(True)
        self.assertPass(run(script, "--project-root", root))
        root = self.renderer_project(False)
        self.assertFail(run(script, "--project-root", root), "formal_render_authorization")

    def test_final_audit_requires_manual_review(self) -> None:
        script = ROOT / "zhangyanfa-track-renderer/scripts/audit_final_master.py"
        result = run(script, self.base / "missing.mp4", "--width", 160, "--height", 90, "--fps", 60, "--frames", 60)
        self.assertFail(result, "--manual-review")


if __name__ == "__main__":
    unittest.main()
