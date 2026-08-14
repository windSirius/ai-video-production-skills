from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "build_candidate_review_sheets.py"
)


def load_builder():
    spec = importlib.util.spec_from_file_location(
        "build_candidate_review_sheets_under_test", SCRIPT
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.load_pillow()
    return module


class ReviewSheetDirectoryTests(unittest.TestCase):
    def test_sheet_builders_create_nested_output_directories(self) -> None:
        builder = load_builder()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            frames = []
            for index, sample in enumerate(("head", "mid", "tail")):
                frame = root / f"{sample}.jpg"
                builder.Image.new(
                    "RGB", (160, 90), (20 + index * 30, 40, 60)
                ).save(frame)
                frames.append(
                    {
                        "path": str(frame),
                        "sample": sample,
                        "timestamp": float(index),
                    }
                )

            row = {
                "line_id": "1",
                "text": "目录创建回归检查",
                "candidate_a_score": "1",
                "candidate_b_score": "1",
                "candidate_c_score": "1",
            }
            evidence = {
                (1, label): list(frames)
                for label in ("selected", "A", "B", "C")
            }

            selected_dir = root / "missing" / "selected"
            risk_dir = root / "missing" / "risk"
            builder.make_selected_sheets([row], evidence, selected_dir)
            builder.make_risk_sheets([row], evidence, risk_dir)

            self.assertTrue((selected_dir / "selected_001.jpg").is_file())
            self.assertTrue((risk_dir / "risk_0001.jpg").is_file())


if __name__ == "__main__":
    unittest.main()
