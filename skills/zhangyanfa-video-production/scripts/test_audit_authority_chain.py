#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
import wave
from pathlib import Path

from audit_authority_chain import audit_authority_bundle
from run_objective_checks import run_check


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class AuthorityChainAuditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not shutil.which("ffprobe"):
            raise unittest.SkipTest("ffprobe is required")

    def make_run(self) -> tuple[Path, Path]:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        (root / "script.md").write_text("唯一文案\n", encoding="utf-8")
        with wave.open(str(root / "narration.wav"), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(48000)
            output.writeframes(b"\x00\x00" * 48000 * 2)
        (root / "final.srt").write_text(
            "1\n00:00:00,000 --> 00:00:02,000\n唯一字幕\n",
            encoding="utf-8",
        )
        (root / "a.mp4").write_bytes(b"picture-master")
        bundle = {
            "schema_version": 1,
            "revision": 1,
            "status": "frozen",
            "delivery_spec": {
                "width": 2560,
                "height": 1440,
                "fps": 60,
                "target_frame_count": 120,
            },
            "authorities": {
                "script": {
                    "path": "script.md",
                    "sha256": sha256(root / "script.md"),
                    "status": "frozen",
                },
                "narration": {
                    "path": "narration.wav",
                    "sha256": sha256(root / "narration.wav"),
                    "status": "frozen",
                    "duration_frame_count": 120,
                    "lexical_status": "pass",
                    "human_audition_status": "pass",
                },
                "subtitle": {
                    "path": "final.srt",
                    "sha256": sha256(root / "final.srt"),
                    "status": "frozen",
                    "cue_count": 1,
                    "final_end_frame": 120,
                    "caption_tail_hold_frames": 0,
                    "human_approval_status": "pass",
                },
            },
            "downstream": [
                {
                    "id": "a_track",
                    "kind": "a_track",
                    "path": "a.mp4",
                    "sha256": sha256(root / "a.mp4"),
                    "state": "accepted",
                    "objective_status": "pass",
                    "human_status": "pass",
                    "bindings": {
                        "script_sha256": sha256(root / "script.md"),
                        "narration_sha256": sha256(root / "narration.wav"),
                        "subtitle_sha256": sha256(root / "final.srt"),
                        "width": 2560,
                        "height": 1440,
                        "fps": 60,
                        "target_frame_count": 120,
                    },
                }
            ],
        }
        bundle_path = root / "authority_bundle.json"
        bundle_path.write_text(json.dumps(bundle), encoding="utf-8")
        return root, bundle_path

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_accepts_one_frozen_chain(self) -> None:
        root, bundle = self.make_run()
        result = audit_authority_bundle(root, bundle, require_descendants={"a_track"})
        self.assertTrue(result["ok"], result["errors"])

    def test_rejects_modified_subtitle(self) -> None:
        root, bundle = self.make_run()
        (root / "final.srt").write_text(
            "1\n00:00:00,000 --> 00:00:01,500\n被改过\n",
            encoding="utf-8",
        )
        result = audit_authority_bundle(root, bundle)
        self.assertFalse(result["ok"])
        self.assertTrue(any("subtitle.sha256 is stale" in error for error in result["errors"]))

    def test_rejects_pending_human_audition(self) -> None:
        root, bundle = self.make_run()
        data = json.loads(bundle.read_text(encoding="utf-8"))
        data["authorities"]["narration"]["human_audition_status"] = "pending"
        bundle.write_text(json.dumps(data), encoding="utf-8")
        result = audit_authority_bundle(root, bundle)
        self.assertFalse(result["ok"])
        self.assertIn(
            "authorities.narration.human_audition_status must be pass", result["errors"]
        )

    def test_rejects_descendant_bound_to_old_subtitle(self) -> None:
        root, bundle = self.make_run()
        data = json.loads(bundle.read_text(encoding="utf-8"))
        data["downstream"][0]["bindings"]["subtitle_sha256"] = "0" * 64
        bundle.write_text(json.dumps(data), encoding="utf-8")
        result = audit_authority_bundle(root, bundle, require_descendants={"a_track"})
        self.assertFalse(result["ok"])
        self.assertTrue(
            any("bindings.subtitle_sha256" in error for error in result["errors"])
        )

    def test_rejects_machine_only_acceptance(self) -> None:
        root, bundle = self.make_run()
        data = json.loads(bundle.read_text(encoding="utf-8"))
        data["downstream"][0]["human_status"] = "pending"
        bundle.write_text(json.dumps(data), encoding="utf-8")
        result = audit_authority_bundle(root, bundle, require_descendants={"a_track"})
        self.assertFalse(result["ok"])
        self.assertTrue(any("human_status must be pass" in error for error in result["errors"]))

    def test_rejects_target_frame_count_from_old_audio(self) -> None:
        root, bundle = self.make_run()
        data = json.loads(bundle.read_text(encoding="utf-8"))
        data["delivery_spec"]["target_frame_count"] = 119
        bundle.write_text(json.dumps(data), encoding="utf-8")
        result = audit_authority_bundle(root, bundle)
        self.assertFalse(result["ok"])
        self.assertTrue(
            any("actual narration duration frame count" in error for error in result["errors"])
        )

    def test_objective_check_dispatches_authority_audit(self) -> None:
        root, _bundle = self.make_run()
        passed, message, details = run_check(
            root,
            {
                "type": "authority_chain_integrity",
                "path": "authority_bundle.json",
                "require_descendants": ["a_track"],
            },
        )
        self.assertTrue(passed, message)
        self.assertTrue(details["ok"])


if __name__ == "__main__":
    unittest.main()
