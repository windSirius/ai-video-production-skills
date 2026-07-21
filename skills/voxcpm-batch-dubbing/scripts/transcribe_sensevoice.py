#!/usr/bin/env python3
"""Load a local SenseVoice model once and transcribe multiple audio files."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", nargs="+", type=Path)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--language", default="auto")
    args = parser.parse_args()

    try:
        from funasr import AutoModel
    except ImportError:
        print(json.dumps({"error": "funasr is not installed in this Python environment"}))
        return 2

    if not args.model.exists():
        print(json.dumps({"error": f"model not found: {args.model}"}, ensure_ascii=False))
        return 2

    model = AutoModel(
        model=str(args.model),
        disable_update=True,
        log_level="ERROR",
        device=args.device,
    )
    output = []
    failed = False
    for path in args.audio:
        try:
            if not path.is_file():
                raise FileNotFoundError(path)
            result = model.generate(
                input=str(path),
                language=args.language,
                use_itn=True,
            )
            raw_text = result[0]["text"]
            transcript = re.sub(r"<\|[^>]+\|>", "", raw_text).strip()
            output.append({"path": str(path.resolve()), "transcript": transcript})
        except Exception as exc:  # Continue to report remaining files.
            failed = True
            output.append({"path": str(path), "error": str(exc)})

    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
