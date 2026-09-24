#!/usr/bin/env python3
"""Index explicitly named music files/folders without copying or relocating them."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import unicodedata

from audit_bgm_diversity import sha256_file

EXTENSIONS = {".mp3", ".m4a", ".wav", ".flac", ".ogg", ".aac", ".aiff"}


def audio_metadata(probe: dict, path: Path) -> dict:
    """Read container AND audio-stream tags; neither is a verified artist credit."""
    fmt = probe["format"]
    stream = next(s for s in probe["streams"] if s.get("codec_type") == "audio")
    format_tags = {k.lower(): v for k, v in fmt.get("tags", {}).items() if str(v).strip()}
    stream_tags = {k.lower(): v for k, v in stream.get("tags", {}).items() if str(v).strip()}
    tags = {**format_tags, **stream_tags}
    variant = re.search(r"\(([^()]*\bver(?:sion)?\.?[^()]*)\)", path.stem, re.I)
    codec = stream.get("codec_name", "unknown")
    return {
        "title": tags.get("title") or path.stem,
        "artist": tags.get("artist") or "unknown",
        "album": tags.get("album", ""),
        "raw_tags": {"format": format_tags, "audio_stream": stream_tags},
        "tag_conflicts": {k: {"format": format_tags[k], "audio_stream": stream_tags[k]}
                          for k in format_tags.keys() & stream_tags.keys()
                          if format_tags[k] != stream_tags[k]},
        "version_hint_from_filename": variant.group(1).strip() if variant else "",
        "metadata_basis": "unverified_audio_tags_and_filename",
        "duration_s": float(fmt["duration"]), "codec": codec,
        "container": fmt.get("format_name", "unknown"),
        "extension_mismatch": (path.suffix.lower() == ".mp3" and codec != "mp3"),
        "sample_rate": int(stream["sample_rate"]) if stream.get("sample_rate") else None,
        "channels": stream.get("channels"),
    }


def apply_supplied_metadata(row: dict, supplied: dict) -> dict:
    """Retain curation, but old placeholder values must not erase newly read tags."""
    merged = {**row, **supplied}
    placeholders = {"", "unknown", "unclassified", "未核实", "未知"}
    for key in ("title", "artist", "album"):
        if str(supplied.get(key, "")).strip().casefold() in placeholders:
            merged[key] = row[key]
    # These fields describe the file just inspected, not a prior catalog snapshot.
    for key in ("raw_tags", "tag_conflicts", "version_hint_from_filename", "duration_s",
                "codec", "container", "extension_mismatch", "sample_rate", "channels", "bytes"):
        merged[key] = row[key]
    return merged


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, action="append", default=[])
    parser.add_argument("--file", type=Path, action="append", default=[])
    parser.add_argument("--metadata", type=Path, action="append", default=[],
                        help="JSON with tracks list; verified metadata overrides raw audio tags")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    supplied = {}
    for path in args.metadata:
        for row in json.loads(path.read_text(encoding="utf-8")).get("tracks", []):
            supplied[row["sha256"]] = row
    paths = list(args.file)
    for directory in args.directory:
        paths.extend(p for p in directory.rglob("*") if p.is_file() and p.suffix.lower() in EXTENSIONS)
    # Only inspect the explicit directories. Do not recursively scan home/private media.
    paths.extend(Path(row["path"]) for row in supplied.values())
    tracks = {}
    errors = []
    for path in sorted(set(p.expanduser().resolve() for p in paths)):
        try:
            digest = sha256_file(path)
            if digest in tracks:
                tracks[digest]["locations"].append(str(path))
                continue
            probe = json.loads(subprocess.check_output([
                "ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)
            ], stderr=subprocess.PIPE))
            metadata = audio_metadata(probe, path)
            identity = unicodedata.normalize("NFKC", metadata["artist"] + "|" + metadata["title"]).casefold().strip()
            row = {
                "track_id": "local_" + digest[:16],
                "composition_id": "tag_" + hashlib.sha256(identity.encode()).hexdigest()[:16],
                "composition_identity_basis": "provisional_tags_requires_review_before_shortlisting",
                "path": str(path), "sha256": digest, "bytes": path.stat().st_size,
                **metadata, "source_mode": "local_library",
                "license": {"status": "not_assessed"}, "suggested_roles": [],
                "palette": "unclassified", "vocal_content": "unclassified",
                "audition_status": "not_human_approved", "technical_qa": "probe_only",
                "inventory_status": "metadata_only",
            }
            if digest in supplied:
                row = apply_supplied_metadata(row, supplied[digest])
                row["composition_identity_basis"] = supplied[digest].get(
                    "composition_identity_basis", "supplied_metadata_requires_review")
            row.update(path=str(path), sha256=digest, locations=[str(path)])
            tracks[digest] = row
        except (OSError, ValueError, subprocess.CalledProcessError) as exc:
            errors.append({"path": str(path), "error": str(exc)})
    report = {
        "schema": "bgm_catalog_v1", "updated_at": datetime.now(timezone.utc).isoformat(),
        "scan_directories": [str(p.expanduser().resolve()) for p in args.directory],
        "explicit_files": [str(p.expanduser().resolve()) for p in args.file],
        "deduplication": "actual SHA for files; composition aliases require source/manual review",
        "track_count": len(tracks), "tracks": list(tracks.values()), "errors": errors,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS" if not errors else "FAIL", "track_count": len(tracks),
                      "total_bytes": sum(t["bytes"] for t in tracks.values()), "errors": errors,
                      "output": str(args.output)}, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
