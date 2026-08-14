#!/usr/bin/env python3
"""Regression tests for audit_hyperframes_boundaries.py."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("audit_hyperframes_boundaries.py")


class BoundaryAuditTests(unittest.TestCase):
    def run_case(self, body: str) -> tuple[int, dict]:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "index.html"
            path.write_text(body, encoding="utf-8")
            result = subprocess.run(
                ["python3", str(SCRIPT), str(path), "--fps", "60"],
                text=True,
                capture_output=True,
                check=False,
            )
            return result.returncode, json.loads(result.stdout)

    def test_contiguous_boundary_passes(self) -> None:
        code, report = self.run_case(
            '<div class="clip" id="a" data-track-index="1" data-start="0" data-duration="8.516666666"></div>'
            '<div class="clip" id="b" data-track-index="1" data-start="8.516666666" data-duration="1"></div>'
        )
        self.assertEqual(code, 0)
        self.assertEqual(report["status"], "pass")

    def test_one_nanosecond_gap_fails(self) -> None:
        code, report = self.run_case(
            '<div class="clip" id="a" data-track-index="1" data-start="0" data-duration="8.516666666"></div>'
            '<div class="clip" id="b" data-track-index="1" data-start="8.516666667" data-duration="1"></div>'
        )
        self.assertEqual(code, 1)
        self.assertEqual(report["gaps"][0]["sample_frame_in_gap"], 511)


if __name__ == "__main__":
    unittest.main()
