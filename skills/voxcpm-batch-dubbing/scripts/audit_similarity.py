#!/usr/bin/env python3
"""Compare canonical narration text with ASR output using a frozen threshold."""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path


def normalize(text: str, aliases: dict[str, str]) -> str:
    text = unicodedata.normalize("NFKC", text)
    for source, target in aliases.items():
        text = text.replace(source, target)
    return re.sub(r"[^\w\u3400-\u9fff]+", "", text, flags=re.UNICODE).lower()


def score(canonical: str, asr: str, aliases: dict[str, str]) -> float:
    left = normalize(canonical, aliases)
    right = normalize(asr, aliases)
    return SequenceMatcher(None, left, right, autojunk=False).ratio() if left or right else 1.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("canonical", type=Path)
    parser.add_argument("asr", type=Path)
    parser.add_argument("--threshold", type=float, default=0.90)
    parser.add_argument("--aliases", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if not 0 < args.threshold <= 1:
        parser.error("threshold must be in (0, 1]")
    aliases = json.loads(args.aliases.read_text(encoding="utf-8")) if args.aliases else {}
    value = score(
        args.canonical.read_text(encoding="utf-8"),
        args.asr.read_text(encoding="utf-8"),
        aliases,
    )
    result = {"status": "pass" if value >= args.threshold else "fail", "similarity": value, "threshold": args.threshold}
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else f"{result['status'].upper()} similarity={value:.4f} threshold={args.threshold:.4f}")
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
