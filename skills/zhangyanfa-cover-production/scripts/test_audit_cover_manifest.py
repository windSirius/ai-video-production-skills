"""Check actual image geometry when macOS tools are unavailable."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from audit_cover_manifest import aspect_ok, image_size


class CoverImageGeometryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.no_native_tools = patch(
            "audit_cover_manifest.subprocess.run", side_effect=FileNotFoundError
        )
        self.no_native_tools.start()

    def tearDown(self):
        self.no_native_tools.stop()
        self.temp.cleanup()

    def test_png_ratios_without_native_image_tools(self):
        for ratio, size in (("16:9", (160, 90)), ("4:3", (160, 120)), ("3:4", (90, 120))):
            with self.subTest(ratio=ratio):
                path = self.root / (ratio.replace(":", "-") + ".png")
                Image.new("RGB", size, "blue").save(path)
                self.assertEqual(image_size(path), size)
                self.assertTrue(aspect_ok(path, ratio))
                for wrong_ratio in {"16:9", "4:3", "3:4"} - {ratio}:
                    self.assertFalse(aspect_ok(path, wrong_ratio))

    def test_jpeg_dimensions_without_native_image_tools(self):
        path = self.root / "cover.jpg"
        Image.new("RGB", (320, 180), "red").save(path)
        self.assertEqual(image_size(path), (320, 180))
        self.assertTrue(aspect_ok(path, "16:9"))

    def test_missing_and_invalid_images_fail_closed(self):
        invalid = self.root / "invalid.png"
        invalid.write_bytes(b"not an image")
        for path in (self.root / "missing.png", invalid):
            self.assertIsNone(image_size(path))
            self.assertFalse(aspect_ok(path, "16:9"))


if __name__ == "__main__":
    unittest.main()
