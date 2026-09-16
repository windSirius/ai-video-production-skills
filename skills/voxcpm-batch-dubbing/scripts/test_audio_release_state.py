#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
import tempfile
import unittest
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audio_release_state import machine_verified, release, sha256, transition_to_audition, validate


class AudioReleaseStateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.canonical = self.root / "canonical.txt"
        self.master = self.root / "master.wav"
        self.qa = self.root / "audio_qa.json"
        self.audition = self.root / "human_audition.json"
        self.canonical.write_text("这是正典文字", encoding="utf-8")
        with wave.open(str(self.master), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(16000)
            handle.writeframes(b"\0\0" * 3200)
        self.write_machine_qa()
        self.write_audition_receipt()

    def write_machine_qa(self, **overrides: object) -> None:
        value = {
            "status": "pass",
            "canonical_sha256": sha256(self.canonical),
            "master_sha256": sha256(self.master),
            "machine_checks": {
                "lexical": "pass",
                "signal": "pass",
                "joins": "pass",
                "pronunciation": "pass",
                "full_decode": "pass",
            },
        }
        value.update(overrides)
        self.qa.write_text(
            json.dumps(value),
            encoding="utf-8",
        )

    def write_audition_receipt(self, **overrides: object) -> None:
        value = {
            "schema_version": "human_audition_v1",
            "status": "approved",
            "master_path": str(self.master),
            "master_sha256": sha256(self.master),
            "canonical_sha256": sha256(self.canonical),
            "full_speed_1x_audition": True,
            "complete_master_audition": True,
            "reviewer": "user",
            "approval_ref": "audition-approval-1",
            "approved_at": "2026-08-30T00:00:00Z",
        }
        value.update(overrides)
        self.audition.write_text(json.dumps(value), encoding="utf-8")

    def test_release_requires_audition_state_and_matching_sha(self) -> None:
        machine = machine_verified(self.canonical, self.master, self.qa)
        self.assertEqual(machine["state"], "machine_verified")
        self.assertFalse(machine["release_ready"])
        with self.assertRaises(ValueError):
            release(machine, self.master, self.audition)

        awaiting = transition_to_audition(machine)
        self.assertEqual(awaiting["state"], "awaiting_human_audition")
        released, receipt = release(awaiting, self.master, self.audition)
        self.assertEqual(released["state"], "released")
        self.assertTrue(released["release_ready"])
        self.assertEqual(receipt["master_sha256"], released["master_sha256"])
        self.assertEqual(receipt["audition_receipt_sha256"], sha256(self.audition))
        self.assertEqual(validate(released)["status"], "pass")

    def test_master_mutation_invalidates_release(self) -> None:
        awaiting = transition_to_audition(machine_verified(self.canonical, self.master, self.qa))
        released, _ = release(awaiting, self.master, self.audition)
        self.master.write_bytes(b"RIFF-mutated")
        self.assertEqual(validate(released)["status"], "fail")

    def test_status_pass_cannot_hide_missing_required_checks(self) -> None:
        self.write_machine_qa(machine_checks={"lexical": "pass"})
        with self.assertRaisesRegex(ValueError, "missing required checks"):
            machine_verified(self.canonical, self.master, self.qa)

    def test_machine_qa_must_bind_canonical_and_master(self) -> None:
        self.write_machine_qa(master_sha256="0" * 64)
        with self.assertRaisesRegex(ValueError, "does not bind the actual narration master"):
            machine_verified(self.canonical, self.master, self.qa)

    def test_machine_verify_actually_probes_audio(self) -> None:
        self.master.write_bytes(b"not-audio")
        self.write_machine_qa()
        with self.assertRaisesRegex(ValueError, "failed audio probe/decode"):
            machine_verified(self.canonical, self.master, self.qa)

    def test_unknown_state_fails_validation(self) -> None:
        manifest = machine_verified(self.canonical, self.master, self.qa)
        manifest["state"] = "banana"
        self.assertEqual(validate(manifest)["status"], "fail")
        self.assertTrue(any("unknown audio release state" in error for error in validate(manifest)["errors"]))

    def test_mutated_machine_qa_receipt_invalidates_manifest(self) -> None:
        awaiting = transition_to_audition(machine_verified(self.canonical, self.master, self.qa))
        self.write_machine_qa(status="fail")
        result = validate(awaiting)
        self.assertEqual(result["status"], "fail")
        self.assertIn("machine QA path/SHA binding is invalid", result["errors"])

    def test_release_requires_independent_complete_1x_receipt(self) -> None:
        awaiting = transition_to_audition(machine_verified(self.canonical, self.master, self.qa))
        self.write_audition_receipt(full_speed_1x_audition=False)
        with self.assertRaisesRegex(ValueError, "full_speed_1x_audition"):
            release(awaiting, self.master, self.audition)


if __name__ == "__main__":
    unittest.main()
