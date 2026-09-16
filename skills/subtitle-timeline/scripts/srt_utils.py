#!/usr/bin/env python3
"""Shared, dependency-free SRT utilities."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path


TIMING_RE = re.compile(r"^(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})$")


@dataclass
class Caption:
    start_ms: int
    end_ms: int
    text: str


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def to_ms(value: str) -> int:
    hours, minutes, rest = value.split(":")
    seconds, millis = rest.split(",")
    return (((int(hours) * 60 + int(minutes)) * 60) + int(seconds)) * 1000 + int(millis)


def from_ms(value: int) -> str:
    if value < 0:
        raise ValueError("timestamp cannot be negative")
    seconds, millis = divmod(value, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def parse_srt(path: Path) -> list[Caption]:
    raw = path.read_text(encoding="utf-8-sig").strip()
    if not raw:
        return []
    captions: list[Caption] = []
    for block_no, block in enumerate(re.split(r"\r?\n\s*\r?\n+", raw), start=1):
        lines = block.splitlines()
        timing_index = next((i for i, line in enumerate(lines[:2]) if TIMING_RE.match(line.strip())), None)
        if timing_index is None:
            raise ValueError(f"block {block_no} has no valid timing line")
        match = TIMING_RE.match(lines[timing_index].strip())
        assert match is not None
        text = "\n".join(lines[timing_index + 1 :]).strip()
        captions.append(Caption(to_ms(match.group(1)), to_ms(match.group(2)), text))
    return captions


def render_srt(captions: list[Caption]) -> str:
    blocks = [
        f"{index}\n{from_ms(caption.start_ms)} --> {from_ms(caption.end_ms)}\n{caption.text}"
        for index, caption in enumerate(captions, start=1)
    ]
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def normalized_lexical(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    return "".join(
        char.lower()
        for char in text
        if not char.isspace() and not unicodedata.category(char).startswith("P")
    )


def visible_chars(text: str) -> int:
    return sum(not char.isspace() for char in text)
