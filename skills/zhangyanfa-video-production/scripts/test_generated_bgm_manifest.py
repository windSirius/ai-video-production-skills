#!/usr/bin/env python3
"""Regression test for generated-score provenance validation."""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


CHECKER = Path(__file__).with_name("run_objective_checks.py")


class GeneratedBgmTests(unittest.TestCase):
    def test_generated_source_and_hash_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "audio/generated_sources").mkdir(parents=True)
            source = root / "audio/generated_sources/chapter01.wav"
            source.write_bytes(b"generated-audio-fixture")
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            generation = {
                "status": "pass",
                "generations": [{
                    "service": "fixture",
                    "model": "fixture-v1",
                    "prompt_sha256": "a" * 64,
                    "source": str(source),
                    "sha256": digest,
                    "duration": 12.0,
                }],
            }
            bgm = {
                "source_mode": "generated_score",
                "generation_manifest": "audio/generation_manifest.json",
                "sections": [{"chapter": "hook", "source": str(source)}],
            }
            (root / "audio/generation_manifest.json").write_text(json.dumps(generation), encoding="utf-8")
            (root / "audio/bgm_manifest.json").write_text(json.dumps(bgm), encoding="utf-8")
            plan = {
                "checks": [{
                    "id": "bgm_provenance_current",
                    "type": "generated_bgm_manifest_integrity",
                    "path": "audio/bgm_manifest.json",
                }]
            }
            (root / "verification_plan.json").write_text(json.dumps(plan), encoding="utf-8")
            result = subprocess.run(
                ["python3", str(CHECKER), str(root)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
