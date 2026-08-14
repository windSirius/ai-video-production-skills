#!/usr/bin/env python3
from __future__ import annotations

import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "srt_to_match_sheet.py"


class MatchSheetTemplateTests(unittest.TestCase):
    def test_house_profile_review_fields_exist(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            srt = root / "final.srt"
            output = root / "match.tsv"
            srt.write_text("1\n00:00:00,000 --> 00:00:01,000\n开场\n", encoding="utf-8")
            result = subprocess.run([sys.executable, str(SCRIPT), str(srt), str(output)], text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            with output.open(encoding="utf-8", newline="") as handle:
                row = next(csv.DictReader(handle, delimiter="\t"))
            self.assertEqual(row["crop_mode"], "full_frame")
            self.assertEqual(row["uid_visible"], "pending")
            for field in ("selected_candidate_id", "source_id", "identity_review", "risk_flags"):
                self.assertIn(field, row)


if __name__ == "__main__":
    unittest.main()
