#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import unittest
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_srt import audit
from freeze_timing import freeze
from repair_srt import merge_duplicates
from srt_utils import Caption, sha256


class SubtitleTimelineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.canonical = self.root / "canonical.txt"
        self.srt = self.root / "candidate.srt"
        self.master = self.root / "master.wav"
        self.script_manifest = self.root / "script_manifest.json"
        self.audio_manifest = self.root / "audio_manifest.json"
        self.voice_release = self.root / "voice_release.json"
        self.machine_qa = self.root / "audio_qa.json"
        self.audition_receipt = self.root / "human_audition.json"
        self.style = self.root / "style.json"
        self.canonical.write_text("第一句第二句", encoding="utf-8")
        self.srt.write_text(
            "1\n00:00:00,000 --> 00:00:01,000\n第一句\n\n"
            "2\n00:00:01,000 --> 00:00:02,000\n第二句\n",
            encoding="utf-8",
        )
        with wave.open(str(self.master), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(16000)
            handle.writeframes(b"\0\0" * 32000)
        self.style.write_text(
            json.dumps(
                {
                    "forbidden_terminal_punctuation": "，。；：,.;:",
                    "trailing_closing_marks": "」』”’）》〉）】",
                    "max_visible_chars_warning": 24,
                    "max_cps_warning": 12.0,
                }
            ),
            encoding="utf-8",
        )
        self.script_manifest.write_text(
            json.dumps(
                {
                    "schema_version": "script_manifest_v1",
                    "state": "approved",
                    "canonical_path": str(self.canonical),
                    "canonical_sha256": sha256(self.canonical),
                    "approved_by": "user",
                    "approval_ref": "script-approval-1",
                    "approved_at": "2026-08-30T00:00:00Z",
                }
            ),
            encoding="utf-8",
        )

    def write_audio_state(self, state: str, release_ready: bool) -> None:
        master_sha = sha256(self.master)
        canonical_sha = sha256(self.canonical)
        machine_checks = {
            "lexical": "pass",
            "signal": "pass",
            "joins": "pass",
            "pronunciation": "pass",
            "full_decode": "pass",
        }
        self.machine_qa.write_text(
            json.dumps(
                {
                    "status": "pass",
                    "canonical_sha256": canonical_sha,
                    "master_sha256": master_sha,
                    "machine_checks": machine_checks,
                }
            ),
            encoding="utf-8",
        )
        self.audition_receipt.write_text(
            json.dumps(
                {
                    "schema_version": "human_audition_v1",
                    "status": "approved",
                    "master_path": str(self.master),
                    "master_sha256": master_sha,
                    "canonical_sha256": canonical_sha,
                    "full_speed_1x_audition": True,
                    "complete_master_audition": True,
                    "reviewer": "user",
                    "approval_ref": "audio-approval-1",
                    "approved_at": "2026-08-30T00:00:00Z",
                }
            ),
            encoding="utf-8",
        )
        audition_sha = sha256(self.audition_receipt)
        audition = (
            {
                "status": "approved",
                "reviewer": "user",
                "approval_ref": "audio-approval-1",
                "approved_at": "2026-08-30T00:00:00Z",
                "approved_master_sha256": master_sha,
                "full_speed_1x_audition": True,
                "complete_master_audition": True,
                "receipt_path": str(self.audition_receipt),
                "receipt_sha256": audition_sha,
            }
            if release_ready
            else {"status": "pending"}
        )
        self.audio_manifest.write_text(
            json.dumps(
                {
                    "schema_version": "audio_release_v2",
                    "state": state,
                    "release_ready": release_ready,
                    "canonical_path": str(self.canonical),
                    "canonical_sha256": canonical_sha,
                    "master_path": str(self.master),
                    "master_sha256": master_sha,
                    "machine_qa_path": str(self.machine_qa),
                    "machine_qa_sha256": sha256(self.machine_qa),
                    "machine_checks": machine_checks,
                    "audio_probe": {"status": "pass", "master_sha256": master_sha},
                    "human_audition": audition,
                    "history": [{"state": state, "at": "2026-08-30T00:00:00Z"}],
                }
            ),
            encoding="utf-8",
        )
        self.voice_release.write_text(
            json.dumps(
                {
                    "schema_version": "voice_release_v2",
                    "status": "approved" if release_ready else "pending",
                    "release_ready": release_ready,
                    "master_sha256": master_sha,
                    "canonical_sha256": canonical_sha,
                    "full_speed_1x_audition": release_ready,
                    "complete_master_audition": release_ready,
                    "audition_receipt_path": str(self.audition_receipt),
                    "audition_receipt_sha256": audition_sha if release_ready else None,
                    "reviewer": "user" if release_ready else None,
                    "approval_ref": "audio-approval-1" if release_ready else None,
                    "approved_at": "2026-08-30T00:00:00Z" if release_ready else None,
                }
            ),
            encoding="utf-8",
        )

    def audit_args(self, state: str, include_voice: bool = True) -> argparse.Namespace:
        return argparse.Namespace(
            srt=self.srt,
            canonical=self.canonical,
            script_manifest=self.script_manifest,
            audio_manifest=self.audio_manifest,
            voice_release=self.voice_release if include_voice else None,
            raw_srt=None,
            style=self.style,
            requested_state=state,
        )

    def test_provisional_allowed_before_audio_release_but_not_downstream(self) -> None:
        self.write_audio_state("awaiting_human_audition", False)
        result = audit(self.audit_args("provisional", include_voice=False))
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["state"], "provisional")
        self.assertFalse(result["downstream_allowed"])
        self.assertFalse(result["audio_released"])

    def test_candidate_final_requires_released_audio(self) -> None:
        self.write_audio_state("awaiting_human_audition", False)
        result = audit(self.audit_args("candidate_final"))
        self.assertEqual(result["status"], "fail")
        self.write_audio_state("released", True)
        result = audit(self.audit_args("candidate_final"))
        self.assertEqual(result["status"], "pass")
        self.assertFalse(result["downstream_allowed"])

    def test_large_negative_overlap_is_not_merged(self) -> None:
        captions = [Caption(0, 5000, "重复"), Caption(1000, 2000, "重复")]
        merged, changes, rejected = merge_duplicates(captions, max_gap_ms=100, max_overlap_ms=50)
        self.assertEqual(len(merged), 2)
        self.assertEqual(changes, [])
        self.assertEqual(rejected[0]["overlap_ms"], 4000)

    def test_small_bounded_gap_is_merged(self) -> None:
        captions = [Caption(0, 1000, "重复"), Caption(1050, 2000, "重复")]
        merged, changes, rejected = merge_duplicates(captions, max_gap_ms=100, max_overlap_ms=0)
        self.assertEqual(len(merged), 1)
        self.assertEqual(len(changes), 1)
        self.assertEqual(rejected, [])

    def test_freeze_produces_integer_frame_contract(self) -> None:
        self.write_audio_state("released", True)
        qa = audit(self.audit_args("candidate_final"))
        qa_path = self.root / "subtitle_qa.json"
        qa_path.write_text(json.dumps(qa), encoding="utf-8")
        args = argparse.Namespace(
            audit=qa_path,
            srt=self.srt,
            canonical=self.canonical,
            script_manifest=self.script_manifest,
            audio_manifest=self.audio_manifest,
            voice_release=self.voice_release,
            style=self.style,
            fps_num=60,
            fps_den=1,
            tail_tolerance_ms=100,
            out_seconds=None,
            rounding="nearest",
            reviewer="user",
            approval_ref="subtitle-approval-1",
            approved_at="2026-08-30T00:00:00Z",
        )
        contract, cues, manifest = freeze(args)
        self.assertEqual(contract["total_frames"], 120)
        self.assertTrue(all(isinstance(row["start_frame"], int) for row in cues["cues"]))
        self.assertEqual(manifest["state"], "final_frozen")
        self.assertTrue(manifest["downstream_allowed"])

    def test_candidate_rejects_shallow_forged_release_files(self) -> None:
        master_sha = sha256(self.master)
        self.audio_manifest.write_text(
            json.dumps(
                {
                    "state": "released",
                    "release_ready": True,
                    "canonical_sha256": sha256(self.canonical),
                    "master_path": str(self.master),
                    "master_sha256": master_sha,
                }
            ),
            encoding="utf-8",
        )
        self.voice_release.write_text(
            json.dumps({"status": "approved", "release_ready": True, "master_sha256": master_sha}),
            encoding="utf-8",
        )
        result = audit(self.audit_args("candidate_final"))
        self.assertEqual(result["status"], "fail")
        self.assertIn("audio_release", result["failures"])

    def test_candidate_requires_current_approved_script_manifest(self) -> None:
        self.write_audio_state("released", True)
        value = json.loads(self.script_manifest.read_text(encoding="utf-8"))
        value["state"] = "draft"
        self.script_manifest.write_text(json.dumps(value), encoding="utf-8")
        result = audit(self.audit_args("candidate_final"))
        self.assertEqual(result["status"], "fail")
        self.assertIn("script_manifest", result["failures"])


if __name__ == "__main__":
    unittest.main()
