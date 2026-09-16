#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_lexical_exactness import audit, validate_alias_bundle


exact = audit("他仿佛一位真正锻出来的神", "他仿佛一位真正锻出来的神")
assert exact["exact"] is True
assert exact["insertions"] == exact["deletions"] == exact["substitutions"] == 0

alias_row = {
    "asr_surface": "那拉延",
    "canonical_surface": "那菈延",
    "evidence_type": "targeted_human_audition",
    "evidence_ref": "audition-hotspot-001",
    "reviewer": "tester",
    "reviewed_at": "2026-08-30T00:00:00Z",
    "decision": "recognition_ambiguity",
}
alias = audit("那菈延", "那拉延", [alias_row])
assert alias["exact"] is True
assert alias["alias_evidence_count"] == 1

extra = audit("他仿佛一位真正锻出来的神", "他仿佛一位真正断出来的神之塔")
assert extra["exact"] is False
assert extra["insertions"] > 0
assert extra["substitutions"] > 0

wrong = audit("身体可以替换，关系也会变化", "身体可以替换，关系也未变化")
assert wrong["exact"] is False
assert wrong["substitutions"] > 0

missing = audit("我们继续往下看", "我们继续看")
assert missing["exact"] is False
assert missing["deletions"] > 0

punctuation = audit("爱若抵达永恒，还能允许改变吗？", "爱若抵达永恒还能允许改变吗")
assert punctuation["exact"] is True

try:
    audit("这是正确答案", "这是完全错误", {"完全错误": "正确答案"})  # type: ignore[arg-type]
except ValueError as exc:
    assert "not a replacement map" in str(exc)
else:
    raise AssertionError("free-form alias maps must be rejected")

try:
    audit("那菈延", "那拉延", [{**alias_row, "evidence_ref": ""}])
except ValueError as exc:
    assert "evidence_ref" in str(exc)
else:
    raise AssertionError("alias rows without evidence must be rejected")

bundle = {
    "schema_version": "asr_alias_evidence_v1",
    "canonical_sha256": "c" * 64,
    "asr_sha256": "a" * 64,
    "aliases": [alias_row],
}
mapping, rows = validate_alias_bundle(bundle, "c" * 64, "a" * 64)
assert mapping == {"那拉延": "那菈延"}
assert rows == [alias_row]

try:
    validate_alias_bundle(bundle, "d" * 64, "a" * 64)
except ValueError as exc:
    assert "canonical SHA" in str(exc)
else:
    raise AssertionError("alias bundle must bind the current canonical")

print("PASS")
