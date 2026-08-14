#!/usr/bin/env python3
from pathlib import Path
from tempfile import TemporaryDirectory

from audit_lore_script import audit


with TemporaryDirectory() as directory:
    root = Path(directory)
    manuscript = root / "稿件.md"
    canonical = root / "口播纯文本.md"
    manuscript.write_text("## 三、口播稿正文\n我们先看原文\n## 四、标题池\n标题", encoding="utf-8")
    canonical.write_text("我们先看原文", encoding="utf-8")
    assert audit(manuscript, canonical)["status"] == "pass"
    canonical.write_text("另一份文字", encoding="utf-8")
    assert audit(manuscript, canonical)["status"] == "fail"

print("PASS")
