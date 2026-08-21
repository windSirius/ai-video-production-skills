#!/usr/bin/env python3

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("init_run.py")
VALIDATOR = Path(__file__).with_name("validate_run.py")


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_init(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--root",
            str(root),
            "--title",
            "测试项目",
            "--objective",
            "生成一个可验证的测试项目",
            "--deliverable",
            "测试产物",
            "--in-scope",
            "测试",
            "--out-of-scope",
            "外部发布",
            "--success-criterion",
            "run manifest exists::run_manifest_exists",
        ],
        check=False,
        capture_output=True,
        text=True,
    )


class InitRunV3Tests(unittest.TestCase):
    def test_new_run_uses_v3_and_writes_v3_skeletons(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "new"
            completed = run_init(root)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            manifest = json.loads((root / "run_manifest.json").read_text(encoding="utf-8"))
            plan = json.loads((root / "verification_plan.json").read_text(encoding="utf-8"))
            self.assertEqual(
                manifest["workflow_profiles"]["production_control"],
                "artifact_bound_release_v3",
            )
            self.assertTrue((root / "approvals/approval_ledger.jsonl").is_file())
            self.assertTrue((root / "CURRENT.json").is_file())
            self.assertTrue(
                any(check.get("type") == "workflow_v3_release_integrity" for check in plan["checks"])
            )
            validation = subprocess.run(
                [sys.executable, str(VALIDATOR), str(root), "--contract-only"],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(validation.returncode, 0, validation.stdout + validation.stderr)

    def test_existing_legacy_run_is_not_silently_migrated(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "legacy"
            root.mkdir(parents=True)
            write_json(root / "request_contract.json", {"workflow_profiles": {}})
            write_json(
                root / "run_manifest.json",
                {
                    "title": "旧项目",
                    "current_phase": "intake",
                    "status": "in_progress",
                    "artifacts": {},
                },
            )
            completed = run_init(root)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            manifest = json.loads((root / "run_manifest.json").read_text(encoding="utf-8"))
            plan = json.loads((root / "verification_plan.json").read_text(encoding="utf-8"))
            self.assertEqual(
                manifest["workflow_profiles"]["production_control"],
                "single_authority_bundle_v2_2",
            )
            self.assertFalse((root / "approvals/approval_ledger.jsonl").exists())
            self.assertFalse((root / "CURRENT.json").exists())
            self.assertFalse(
                any(check.get("type") == "workflow_v3_release_integrity" for check in plan["checks"])
            )


if __name__ == "__main__":
    unittest.main()
