#!/usr/bin/env python3
"""Audit HyperFrames HTML clip boundaries using an integer-frame clock."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING, InvalidOperation
from html.parser import HTMLParser
from pathlib import Path


@dataclass(frozen=True)
class Clip:
    clip_id: str
    track: str
    start: Decimal
    duration: Decimal

    @property
    def end(self) -> Decimal:
        return self.start + self.duration


class ClipParser(HTMLParser):
    def __init__(self, track_attribute: str) -> None:
        super().__init__()
        self.track_attribute = track_attribute
        self.clips: list[Clip] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value for key, value in attrs}
        classes = set((values.get("class") or "").split())
        if "clip" not in classes or values.get("data-start") is None:
            return
        try:
            start = Decimal(values["data-start"] or "")
            duration = Decimal(values.get("data-duration") or "")
        except InvalidOperation as exc:
            raise ValueError(f"invalid clip timing on {values.get('id', '<unnamed>')}") from exc
        if duration <= 0:
            raise ValueError(f"non-positive duration on {values.get('id', '<unnamed>')}")
        track = values.get(self.track_attribute) or values.get("data-track") or "default"
        clip_id = values.get("id") or values.get("data-hf-id") or f"clip-{len(self.clips) + 1}"
        self.clips.append(Clip(clip_id, track, start, duration))


def first_sample_in_gap(end: Decimal, next_start: Decimal, fps: Decimal) -> int | None:
    candidate = int((end * fps).to_integral_value(rounding=ROUND_CEILING))
    sample = Decimal(candidate) / fps
    return candidate if end <= sample < next_start else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html", type=Path)
    parser.add_argument("--fps", type=Decimal, default=Decimal("60"))
    parser.add_argument("--track-attribute", default="data-track-index")
    parser.add_argument("--allow-overlap", action="store_true")
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()

    html = args.html.read_text(encoding="utf-8")
    clip_parser = ClipParser(args.track_attribute)
    clip_parser.feed(html)
    tracks: dict[str, list[Clip]] = {}
    for clip in clip_parser.clips:
        tracks.setdefault(clip.track, []).append(clip)

    gaps: list[dict[str, object]] = []
    overlaps: list[dict[str, object]] = []
    for track, clips in sorted(tracks.items()):
        ordered = sorted(clips, key=lambda item: (item.start, item.end, item.clip_id))
        for previous, current in zip(ordered, ordered[1:]):
            delta = current.start - previous.end
            record = {
                "track": track,
                "previous": previous.clip_id,
                "current": current.clip_id,
                "previous_end": str(previous.end),
                "current_start": str(current.start),
                "delta_seconds": str(delta),
            }
            if delta > 0:
                record["sample_frame_in_gap"] = first_sample_in_gap(previous.end, current.start, args.fps)
                gaps.append(record)
            elif delta < 0:
                overlaps.append(record)

    failures = bool(gaps or (overlaps and not args.allow_overlap))
    report = {
        "status": "fail" if failures else "pass",
        "html": str(args.html.resolve()),
        "fps": str(args.fps),
        "clip_count": len(clip_parser.clips),
        "track_count": len(tracks),
        "gaps": gaps,
        "overlaps": overlaps,
        "overlap_policy": "allowed" if args.allow_overlap else "forbidden",
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
