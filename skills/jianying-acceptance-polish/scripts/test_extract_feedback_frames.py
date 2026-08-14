#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("extract_feedback_frames.py")


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg/ffprobe required")
class ExtractFeedbackFramesTests(unittest.TestCase):
    def test_extracts_center_and_neighbors_at_60fps(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / "test.mp4"
            subprocess.run([
                shutil.which("ffmpeg") or "ffmpeg", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=60:duration=2",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video),
            ], check=True)
            output = root / "frames"
            result = subprocess.run([
                sys.executable, str(SCRIPT), str(video), "--time", "0.5",
                "--radius-frames", "1", "--output-dir", str(output),
            ], text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            manifest = json.loads((output / "feedback_frames_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual([item["frame"] for item in manifest["frames"]], [29, 30, 31])
            self.assertTrue(all(Path(item["path"]).is_file() for item in manifest["frames"]))


if __name__ == "__main__":
    unittest.main()
