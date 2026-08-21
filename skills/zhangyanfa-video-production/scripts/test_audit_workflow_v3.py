#!/usr/bin/env python3

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
import wave
from datetime import datetime, timedelta, timezone
from pathlib import Path

from audit_workflow_v3 import run_audit, sha256_file


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class WorkflowV3AuditTests(unittest.TestCase):
    def setUp(self) -> None:
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            self.skipTest("ffmpeg/ffprobe are required")
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.build_valid_run()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def build_valid_run(self) -> None:
        root = self.root
        write_json(
            root / "request_contract.json",
            {
                "workflow_profiles": {"production_control": "artifact_bound_release_v3"},
                "approval_policy": {
                    "work_authorization_cannot_release_unseen_artifacts": True,
                    "require_artifact_sha256": True,
                    "require_artifact_created_before_showing": True,
                    "require_showing_before_approval": True,
                    "require_exact_user_quote": True,
                },
                "creative_release_policy": {
                    "require_research_counterevidence": True,
                    "require_whole_document_script_qa": True,
                    "require_voice_lexical_and_prosody_gates": True,
                    "minimum_a_direct_plus_strong_ratio": 0.80,
                    "minimum_a_plus_b_ratio": 0.90,
                    "maximum_consecutive_visual_family": 3,
                    "require_cross_episode_reuse_ledger": True,
                    "require_full_length_720p_proxy": True,
                    "full_length_proxy_requires_frozen_narration": True,
                    "require_bgm_human_audition": True,
                    "require_artifact_bound_bgm_review": True,
                    "require_deterministic_exact_subject_cover_assets": True,
                    "require_artifact_bound_cover_review": True,
                },
            },
        )
        (root / "script.md").write_text("这是测试口播。\n", encoding="utf-8")
        narration = root / "narration/final.wav"
        narration.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(narration), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(48000)
            handle.writeframes(b"\0\0" * 48000)
        subtitle = root / "captions/final.srt"
        subtitle.parent.mkdir(parents=True, exist_ok=True)
        subtitle.write_text("1\n00:00:00,000 --> 00:00:01,000\n这是测试口播\n", encoding="utf-8")

        authority = {
            "schema_version": 1,
            "revision": 1,
            "status": "frozen",
            "delivery_spec": {"width": 2560, "height": 1440, "fps": 10, "target_frame_count": 10},
            "authorities": {
                "script": {
                    "path": "script.md",
                    "sha256": sha256_file(root / "script.md"),
                    "status": "frozen",
                },
                "narration": {
                    "path": "narration/final.wav",
                    "sha256": sha256_file(narration),
                    "status": "frozen",
                    "duration_frame_count": 10,
                    "lexical_status": "pass",
                    "human_audition_status": "pass",
                    "pronunciation_hotspots_status": "pass_with_minor_warnings",
                    "prosody_status": "pass",
                    "full_length_audition_status": "pass",
                },
                "subtitle": {
                    "path": "captions/final.srt",
                    "sha256": sha256_file(subtitle),
                    "status": "frozen",
                    "cue_count": 1,
                    "final_end_frame": 10,
                    "caption_tail_hold_frames": 0,
                    "human_approval_status": "pass",
                },
            },
            "downstream": [],
        }
        write_json(root / "authority_bundle.json", authority)
        write_json(
            root / "run_manifest.json",
            {"workflow_profiles": {"production_control": "artifact_bound_release_v3"}, "artifacts": {}},
        )
        research = root / "research/evidence_matrix.tsv"
        research.parent.mkdir(parents=True, exist_ok=True)
        research.write_text(
            "claim_id\tclaim_level\tclaim_text\tgame_evidence\treal_prototype\t"
            "narrative_function\tinternal_cross_validation\tcounterevidence\tconfidence\tsource_refs\tstatus\n"
            "C01\tcore\t测试命题\t游戏原文\tnot_applicable\t叙事功能\tnone_found\t缺少第二例\tstrong_inference\tscript.md\treviewed\n",
            encoding="utf-8",
        )
        write_json(
            root / "script/script_qa.json",
            {
                "script_sha256": authority["authorities"]["script"]["sha256"],
                "structure_pass": True,
                "evidence_pass": True,
                "chinese_oral_pass": True,
                "anti_calque_pass": True,
                "persona_pass": True,
                "entity_pronoun_pass": True,
                "read_aloud_pass": True,
                "human_status": "pass",
            },
        )
        write_json(
            root / "narration/voice_release.json",
            {
                "narration_sha256": authority["authorities"]["narration"]["sha256"],
                "lexical_status": "pass",
                "pronunciation_status": "pass_with_minor_warnings",
                "prosody_status": "pass",
                "punctuation_topology": "preserved",
                "micro_splice_used": False,
                "full_length_audition_status": "pass",
                "approval_ledger_id": "APR-VOICE",
            },
        )
        write_json(
            root / "visuals/semantic_coverage_qa.json",
            {
                "status": "PASS",
                "unresolved_units": 0,
                "opening_gate": {"cg_like_only": True},
                "a_track_semantic_rubric": {"direct_plus_strong_ratio": 0.86},
                "composite_a_plus_b_rubric": {"ratio": 0.93},
                "failures": [],
            },
        )
        write_json(
            root / "visuals/reuse_qa.json",
            {
                "status": "PASS",
                "visual_family_ids_complete": True,
                "max_consecutive_same_visual_family": 3,
                "unresolved_overlap_count": 0,
                "cross_episode_cooldown_violations": 0,
            },
        )

        match_sheet = root / "visuals/match_sheet.tsv"
        match_sheet.write_text(
            "visual_unit_id\tstart_frame\tend_frame\tsemantic_grade\n"
            "VU001\t0\t10\tdirect\n",
            encoding="utf-8",
        )
        a_review = root / "visuals/review_manifest.json"
        write_json(
            a_review,
            {
                "status": "PASS",
                "human_status": "approved_by_user",
                "render_authorized": True,
                "visual_unit_count": 1,
            },
        )
        b_review = root / "tracks/review_manifest.json"
        write_json(
            b_review,
            {
                "status": "PASS",
                "human_status": "approved_by_user",
                "render_authorized": True,
                "asset_count": 1,
            },
        )
        static_bundle = root / "visuals/static_asset_review_bundle.json"
        write_json(
            static_bundle,
            {
                "status": "PASS",
                "human_status": "approved_by_user",
                "a_visual_review_manifest_sha256": sha256_file(a_review),
                "b_review_manifest_sha256": sha256_file(b_review),
                "approval_ledger_id": "APR-STATIC",
            },
        )
        composition = root / "hyperframes/composition.json"
        render_plan = root / "hyperframes/render_plan.json"
        stress_manifest = root / "hyperframes/stress/stress_manifest.json"
        write_json(composition, {"status": "PASS", "target_frame_count": 10})
        write_json(render_plan, {"status": "PASS", "target_frame_count": 10})
        write_json(stress_manifest, {"status": "PASS", "target_frame_count": 10})

        proxy = root / "hyperframes/proxy/aesthetic_proxy_720p.mp4"
        proxy.parent.mkdir(parents=True, exist_ok=True)
        completed = subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-f",
                "lavfi",
                "-i",
                "color=c=blue:s=1280x720:r=10:d=1",
                "-f",
                "lavfi",
                "-i",
                "anullsrc=r=48000:cl=mono:d=1",
                "-shortest",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-y",
                str(proxy),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        approved = datetime.now(timezone.utc)
        shown = approved - timedelta(seconds=1)
        created = approved - timedelta(seconds=2)
        approval_id = "APR-0001"
        approval = {
            "status": "PASS",
            "human_status": "approved_by_user",
            "render_authorized": True,
            "full_timeline_reviewed": True,
            "review_start_frame": 0,
            "review_end_frame": 10,
            "proxy_sha256": sha256_file(proxy),
            "authority_bundle_sha256": sha256_file(root / "authority_bundle.json"),
            "semantic_coverage_sha256": sha256_file(root / "visuals/semantic_coverage_qa.json"),
            "visual_reuse_qa_sha256": sha256_file(root / "visuals/reuse_qa.json"),
            "match_sheet_sha256": sha256_file(match_sheet),
            "visual_review_manifest_sha256": sha256_file(a_review),
            "b_review_manifest_sha256": sha256_file(b_review),
            "static_asset_review_bundle_sha256": sha256_file(static_bundle),
            "composition_sha256": sha256_file(composition),
            "render_plan_sha256": sha256_file(render_plan),
            "stress_manifest_sha256": sha256_file(stress_manifest),
            "narration_authority_sha256": authority["authorities"]["narration"]["sha256"],
            "approval_ledger_id": approval_id,
        }
        write_json(root / "visuals/aesthetic_review/approval.json", approval)
        for name in ("picture.mp4", "bgm.wav", "cover.png"):
            (root / name).write_bytes((name + "\n").encode())
        ledger = root / "approvals/approval_ledger.jsonl"
        ledger.parent.mkdir(parents=True, exist_ok=True)
        approval_rows = [
            {
                "schema_version": 1,
                "approval_id": "APR-VOICE",
                "kind": "script_audio_freeze",
                "status": "approved",
                "artifact_path": "authority_bundle.json",
                "artifact_sha256": sha256_file(root / "authority_bundle.json"),
                "exact_user_quote": "这版稿件、配音和字幕可以冻结",
                "user_verdict": "pass",
                "scope": "freeze script, narration and subtitle authorities",
            },
            {
                "schema_version": 1,
                "approval_id": "APR-STATIC",
                "kind": "static_asset_review",
                "status": "approved",
                "artifact_path": "visuals/static_asset_review_bundle.json",
                "artifact_sha256": sha256_file(static_bundle),
                "exact_user_quote": "可以，就这一版",
                "user_verdict": "pass",
                "scope": "freeze reviewed A/B static assets",
            },
            {
                "schema_version": 1,
                "approval_id": approval_id,
                "kind": "full_proxy_render_authorization",
                "status": "approved",
                "artifact_path": "hyperframes/proxy/aesthetic_proxy_720p.mp4",
                "artifact_sha256": sha256_file(proxy),
                "exact_user_quote": "通过，开始渲染A和B的2k60fps版本",
                "user_verdict": "pass",
                "scope": "render the same hash-bound master",
            },
            {
                "schema_version": 1,
                "approval_id": "APR-BGM",
                "kind": "bgm_mix_review",
                "status": "approved",
                "artifact_path": "bgm.wav",
                "artifact_sha256": sha256_file(root / "bgm.wav"),
                "exact_user_quote": "这版BGM可以",
                "user_verdict": "pass",
                "scope": "freeze BGM audition mix and master",
            },
            {
                "schema_version": 1,
                "approval_id": "APR-COVER",
                "kind": "cover_review",
                "status": "approved",
                "artifact_path": "cover.png",
                "artifact_sha256": sha256_file(root / "cover.png"),
                "exact_user_quote": "封面就用这一版",
                "user_verdict": "pass",
                "scope": "freeze the approved 16:9 cover",
            },
        ]
        for row in approval_rows:
            row.update(
                {
                    "artifact_created_at": created.isoformat(),
                    "shown_at": shown.isoformat(),
                    "approved_at": approved.isoformat(),
                }
            )
        write_json(
            root / "audio/bgm_manifest.json",
            {
                "human_audition_performed": True,
                "human_status": "pass",
                "bgm_master_path": "bgm.wav",
                "bgm_master_sha256": sha256_file(root / "bgm.wav"),
                "audition_mix_path": "bgm.wav",
                "audition_mix_sha256": sha256_file(root / "bgm.wav"),
                "approval_ledger_id": "APR-BGM",
                "audition_checkpoints": {
                    "hook": "pass",
                    "densest_evidence": "pass",
                    "emotional_turn": "pass",
                    "ending": "pass",
                },
            },
        )
        write_json(
            root / "cover/review_manifest.json",
            {
                "identity_pass": True,
                "shot_pass": True,
                "same_space_pass": True,
                "text_pass": True,
                "thumbnail_pass": True,
                "edge_artifact_pass": True,
                "exact_subject_route": "deterministic_official_foreground",
                "contains_exact_official_weapon_or_ui": True,
                "human_status": "pass",
                "approved_artifact_path": "cover.png",
                "approved_artifact_sha256": sha256_file(root / "cover.png"),
                "approval_ledger_id": "APR-COVER",
            },
        )
        ledger.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in approval_rows),
            encoding="utf-8",
        )
        current_artifacts = {
            "script": root / "script.md",
            "narration": narration,
            "subtitle": subtitle,
            "picture_master": root / "picture.mp4",
            "bgm_master": root / "bgm.wav",
            "cover_16_9": root / "cover.png",
        }
        write_json(
            root / "CURRENT.json",
            {
                "schema_version": 1,
                "workflow_profile": "artifact_bound_release_v3",
                "revision": 1,
                "status": "current",
                "updated_at": approved.isoformat(),
                "artifacts": {
                    key: {"path": str(path.relative_to(root)), "sha256": sha256_file(path)}
                    for key, path in current_artifacts.items()
                },
            },
        )

    def test_valid_pre_render_passes(self) -> None:
        result = run_audit(self.root, "pre-render")
        self.assertTrue(result["ok"], json.dumps(result, ensure_ascii=False, indent=2))

    def test_work_authorization_cannot_approve_unseen_proxy(self) -> None:
        ledger = self.root / "approvals/approval_ledger.jsonl"
        ledger.write_text(
            json.dumps(
                {
                    "approval_id": "APR-0001",
                    "kind": "work_authorization",
                    "status": "approved",
                    "exact_user_quote": "睡醒前做完",
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        result = run_audit(self.root, "pre-render")
        self.assertFalse(result["ok"])
        failed = {row["id"] for row in result["checks"] if not row["pass"]}
        self.assertIn("full_proxy_render_authorization", failed)

    def test_low_semantic_coverage_blocks_release(self) -> None:
        path = self.root / "visuals/semantic_coverage_qa.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["a_track_semantic_rubric"]["direct_plus_strong_ratio"] = 0.79
        write_json(path, data)
        result = run_audit(self.root, "pre-render")
        self.assertFalse(result["ok"])
        failed = {row["id"] for row in result["checks"] if not row["pass"]}
        self.assertIn("semantic_coverage_gate", failed)
        self.assertIn("full_timeline_dynamic_proxy", failed)

    def test_missing_reuse_metric_blocks_release(self) -> None:
        path = self.root / "visuals/reuse_qa.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["unresolved_overlap_count"] = None
        write_json(path, data)
        result = run_audit(self.root, "pre-render")
        self.assertFalse(result["ok"])
        failed = {row["id"] for row in result["checks"] if not row["pass"]}
        self.assertIn("visual_family_reuse_gate", failed)
        self.assertIn("full_timeline_dynamic_proxy", failed)

    def test_post_approval_composition_drift_blocks_release(self) -> None:
        composition = self.root / "hyperframes/composition.json"
        write_json(composition, {"status": "PASS", "target_frame_count": 10, "drift": True})
        result = run_audit(self.root, "pre-render")
        self.assertFalse(result["ok"])
        failed = {row["id"] for row in result["checks"] if not row["pass"]}
        self.assertIn("full_timeline_dynamic_proxy", failed)

    def test_valid_seal_passes(self) -> None:
        result = run_audit(self.root, "seal")
        self.assertTrue(result["ok"], json.dumps(result, ensure_ascii=False, indent=2))

    def test_unapproved_bgm_change_blocks_seal(self) -> None:
        (self.root / "bgm.wav").write_bytes(b"changed BGM\n")
        result = run_audit(self.root, "seal")
        self.assertFalse(result["ok"])
        failed = {row["id"] for row in result["checks"] if not row["pass"]}
        self.assertIn("bgm_human_audition", failed)
        self.assertIn("bgm_mix_user_approval", failed)

    def test_unapproved_cover_change_blocks_seal(self) -> None:
        (self.root / "cover.png").write_bytes(b"changed cover\n")
        result = run_audit(self.root, "seal")
        self.assertFalse(result["ok"])
        failed = {row["id"] for row in result["checks"] if not row["pass"]}
        self.assertIn("cover_identity_and_asset_route", failed)
        self.assertIn("cover_user_approval", failed)


if __name__ == "__main__":
    unittest.main()
