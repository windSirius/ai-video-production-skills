#!/usr/bin/env python3
"""Build hash-bound selected-shot and risk-row A/B/C review sheets.

The generated manifest is an evidence bundle, not an approval.  A reviewer may
copy it to ``review_manifest.json``, set ``status`` to ``PASS``, and populate
the review fields after inspecting only the files recorded in ``files``.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any

STILL_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}
TRUE_VALUES = {"1", "true", "yes", "y", "是", "required"}
Image = None
ImageDraw = None
ImageFont = None


def load_pillow() -> None:
    global Image, ImageDraw, ImageFont
    if Image is not None:
        return
    try:
        from PIL import Image as pil_image
        from PIL import ImageDraw as pil_image_draw
        from PIL import ImageFont as pil_image_font
    except ImportError as exc:
        raise SystemExit(
            "Pillow is required to render review sheets; install it in the "
            "selected workspace Python environment"
        ) from exc
    Image = pil_image
    ImageDraw = pil_image_draw
    ImageFont = pil_image_font


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def atomic_tsv(
    path: Path, fieldnames: list[str], rows: list[dict[str, object]]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(
            descriptor, "w", encoding="utf-8", newline=""
        ) as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=fieldnames,
                delimiter="\t",
                lineterminator="\n",
                extrasaction="ignore",
            )
            writer.writeheader()
            writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def source_paths_from_manifest(path: Path | None) -> dict[str, Path]:
    if path is None:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    result: dict[str, Path] = {}
    for key in ("primary_sources", "auxiliary_assets", "sources", "assets"):
        for item in data.get(key, []):
            source_id = str(
                item.get("source_id")
                or item.get("asset_id")
                or item.get("id")
                or ""
            )
            source_path = (
                item.get("real_path")
                or item.get("path")
                or item.get("local_path")
                or item.get("source_file")
            )
            if source_id and source_path:
                result[source_id] = Path(str(source_path)).expanduser().resolve()
    return result


def parse_ids(value: str) -> set[int]:
    return {
        int(item)
        for item in re.split(r"[\s,;]+", value.strip())
        if item.strip()
    }


def ids_from_file(path: Path | None) -> set[int]:
    if path is None:
        return set()
    text = path.read_text(encoding="utf-8-sig").strip()
    if not text:
        return set()
    if path.suffix.lower() == ".json":
        data = json.loads(text)
        if isinstance(data, dict):
            data = (
                data.get("risk_row_ids")
                or data.get("cue_ids")
                or data.get("line_ids")
                or []
            )
        return {int(item) for item in data}
    return parse_ids(text)


def is_true(value: str) -> bool:
    return value.strip().casefold() in TRUE_VALUES


def is_risk_row(row: dict[str, str]) -> bool:
    explicit = " ".join(
        row.get(key, "")
        for key in (
            "risk_flags",
            "risk_reason",
            "review_risk",
            "identity_review",
        )
    ).strip()
    if explicit:
        return True
    if is_true(row.get("identity_required", "")):
        return True
    if row.get("named_entities_expected", "").strip():
        return True
    if row.get("narrative_job", "").strip().casefold() in {
        "hook",
        "ending",
        "resolution",
        "climax",
        "quote",
        "quote_or_evidence",
    }:
        return True
    if row.get("confidence", "").strip().casefold() in {"low", "medium", "低", "中"}:
        return True
    try:
        if float(row.get("retry_round") or 0) > 0:
            return True
    except ValueError:
        return True
    if row.get("ocr_collision_risk", "").strip().casefold() in {"high", "medium"}:
        return True
    if row.get("rights_status", "").strip() not in {
        "",
        "user_recording",
        "original",
        "public-domain",
    }:
        return True
    if Path(row.get("source_file", "")).suffix.casefold() in STILL_SUFFIXES:
        return True
    subject = row.get("subject", "").strip()
    if subject and subject not in {"主题概念", "叙述者", "无"}:
        return True
    return False


@dataclass(frozen=True)
class MediaChoice:
    label: str
    candidate_id: str
    source_id: str
    source_file: Path
    segments: tuple[tuple[float, float], ...]
    kind: str
    descriptor: str

    @property
    def source_in(self) -> float:
        return self.segments[0][0]

    @property
    def source_out(self) -> float:
        return self.segments[-1][1]


def parse_segments(value: str) -> tuple[tuple[float, float], ...]:
    matches = re.findall(r"(-?\d+(?:\.\d+)?)-(-?\d+(?:\.\d+)?)", value)
    segments = tuple((float(start), float(end)) for start, end in matches)
    if not segments or any(end <= start for start, end in segments):
        raise ValueError(f"invalid candidate span: {value!r}")
    return segments


def resolve_candidate_path(
    source_id: str,
    filename: str,
    row: dict[str, str],
    source_paths: dict[str, Path],
) -> Path:
    if source_id in source_paths:
        return source_paths[source_id]
    candidate = Path(filename).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    selected = Path(row.get("source_file", "")).expanduser()
    if selected.name == candidate.name and selected.is_absolute():
        return selected.resolve()
    raise ValueError(
        f"cannot resolve source {source_id!r}/{filename!r}; "
        "provide --source-manifest"
    )


def selected_choice(row: dict[str, str]) -> MediaChoice:
    source = Path(row["source_file"]).expanduser().resolve()
    source_in = float(row.get("source_in") or 0)
    source_out = float(row.get("source_out") or row.get("duration") or 0)
    if source.suffix.casefold() in STILL_SUFFIXES:
        source_in = 0.0
        source_out = max(source_out, float(row.get("duration") or 0.001))
        kind = "still"
    else:
        kind = "video"
    if source_out <= source_in:
        raise ValueError("selected source_out must be after source_in")
    return MediaChoice(
        label="selected",
        candidate_id=row.get("selected_candidate_id", "") or "selected",
        source_id=(
            row.get("selected_source_id", "")
            or row.get("source_id", "")
            or "selected"
        ),
        source_file=source,
        segments=((source_in, source_out),),
        kind=kind,
        descriptor="selected match-sheet range",
    )


def candidate_choice(
    row: dict[str, str],
    suffix: str,
    source_paths: dict[str, Path],
) -> MediaChoice:
    descriptor = row[f"candidate_{suffix.lower()}"].strip()
    candidate_id = row.get(
        f"candidate_{suffix.lower()}_id", ""
    ).strip()
    if not candidate_id:
        raise ValueError(
            f"candidate_{suffix.lower()}_id is required"
        )
    parts = descriptor.split("|")
    if len(parts) >= 5:
        source_id, filename, span, _step_id, kind = parts[:5]
        source = resolve_candidate_path(source_id, filename, row, source_paths)
        return MediaChoice(
            label=suffix.upper(),
            candidate_id=candidate_id,
            source_id=source_id,
            source_file=source,
            segments=parse_segments(span),
            kind=kind,
            descriptor=descriptor,
        )
    if parts and "@" in parts[0]:
        filename, span = parts[0].rsplit("@", 1)
        source_id = f"candidate_{suffix.lower()}"
        source = resolve_candidate_path(source_id, filename, row, source_paths)
        return MediaChoice(
            label=suffix.upper(),
            candidate_id=candidate_id,
            source_id=source_id,
            source_file=source,
            segments=parse_segments(span),
            kind="video",
            descriptor=descriptor,
        )
    raise ValueError(f"unrecognized candidate descriptor: {descriptor!r}")


def sample_points(choice: MediaChoice) -> list[tuple[str, float]]:
    if choice.kind == "still" or choice.source_file.suffix.casefold() in STILL_SUFFIXES:
        return [("head", 0.0), ("mid", 0.0), ("tail", 0.0)]
    durations = [end - start for start, end in choice.segments]
    total = sum(durations)
    margin = min(0.08, max(0.001, total * 0.03))

    def at_offset(offset: float) -> float:
        remaining = max(0.0, min(offset, total))
        for (start, end), duration in zip(choice.segments, durations):
            if remaining <= duration:
                return min(end - 0.001, start + remaining)
            remaining -= duration
        return choice.segments[-1][1] - 0.001

    return [
        ("head", at_offset(margin)),
        ("mid", at_offset(total / 2)),
        ("tail", at_offset(max(0.0, total - margin))),
    ]


def render_sample(
    choice: MediaChoice,
    sample_name: str,
    timestamp: float,
    destination: Path,
    ffmpeg: str,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.stem}.tmp.jpg")
    temporary.unlink(missing_ok=True)
    if choice.kind == "still" or choice.source_file.suffix.casefold() in STILL_SUFFIXES:
        with Image.open(choice.source_file) as raw:
            raw.convert("RGB").save(temporary, quality=92)
    else:
        completed = subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                f"{timestamp:.6f}",
                "-i",
                str(choice.source_file),
                "-frames:v",
                "1",
                "-vf",
                "scale=960:-2",
                "-q:v",
                "2",
                "-y",
                str(temporary),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0 or not temporary.is_file():
            temporary.unlink(missing_ok=True)
            raise RuntimeError(
                f"{sample_name}: ffmpeg failed for {choice.source_file}"
                f"@{timestamp:.3f}: {completed.stderr.strip()}"
            )
    os.replace(temporary, destination)


def load_font(size: int) -> ImageFont.ImageFont:
    for path in (
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def fit_image(path: Path, size: tuple[int, int]) -> Image.Image:
    with Image.open(path) as raw:
        image = raw.convert("RGB")
    image.thumbnail(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, (12, 12, 12))
    canvas.paste(
        image,
        ((size[0] - image.width) // 2, (size[1] - image.height) // 2),
    )
    return canvas


def image_is_black(path: Path, threshold: float = 0.02) -> bool:
    with Image.open(path) as raw:
        grayscale = raw.convert("L")
        grayscale.thumbnail((64, 64))
        histogram = grayscale.histogram()
    pixel_count = sum(histogram)
    if pixel_count <= 0:
        return True
    mean = sum(value * count for value, count in enumerate(histogram)) / (
        255 * pixel_count
    )
    return mean <= threshold


def draw_text_lines(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    *,
    font: ImageFont.ImageFont,
    fill: str,
    width: int,
    max_lines: int,
) -> None:
    lines = textwrap.wrap(text, width=max(8, width), replace_whitespace=False)
    for index, line in enumerate(lines[:max_lines]):
        draw.text((xy[0], xy[1] + index * 23), line, font=font, fill=fill)


def make_selected_sheets(
    rows: list[dict[str, str]],
    evidence: dict[tuple[int, str], list[dict[str, Any]]],
    output_dir: Path,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    title_font = load_font(19)
    label_font = load_font(15)
    for sheet_number, offset in enumerate(range(0, len(rows), 4), start=1):
        subset = rows[offset : offset + 4]
        sheet = Image.new("RGB", (1200, 1120), (5, 5, 5))
        draw = ImageDraw.Draw(sheet)
        cue_ids = []
        for row_number, row in enumerate(subset):
            line_id = int(row["line_id"])
            cue_ids.append(line_id)
            y0 = row_number * 280
            draw.rectangle((0, y0, 1200, y0 + 58), fill=(20, 20, 20))
            draw_text_lines(
                draw,
                (10, y0 + 7),
                f"{line_id:04d}  {row['text']}",
                font=title_font,
                fill="#f4f4f4",
                width=72,
                max_lines=2,
            )
            for column, sample in enumerate(evidence[(line_id, "selected")]):
                x0 = column * 400
                tile = fit_image(Path(sample["path"]), (400, 190))
                sheet.paste(tile, (x0, y0 + 58))
                draw.rectangle((x0, y0 + 248, x0 + 400, y0 + 280), fill=(8, 8, 8))
                draw.text(
                    (x0 + 8, y0 + 253),
                    f"{sample['sample'].upper()}  {sample['timestamp']:.3f}s",
                    font=label_font,
                    fill="#61dada",
                )
        output = output_dir / f"selected_{sheet_number:03d}.jpg"
        sheet.save(output, quality=92, subsampling=0)
        records.append(
            {
                "kind": "selected_sheet",
                "path": str(output.resolve()),
                "sha256": sha256_file(output),
                "size_bytes": output.stat().st_size,
                "cue_ids": cue_ids,
            }
        )
    return records


def make_risk_sheets(
    rows: list[dict[str, str]],
    evidence: dict[tuple[int, str], list[dict[str, Any]]],
    output_dir: Path,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    title_font = load_font(20)
    label_font = load_font(15)
    for row in rows:
        line_id = int(row["line_id"])
        sheet = Image.new("RGB", (1200, 1000), (5, 5, 5))
        draw = ImageDraw.Draw(sheet)
        draw.rectangle((0, 0, 1200, 82), fill=(20, 20, 20))
        draw_text_lines(
            draw,
            (10, 8),
            f"{line_id:04d}  {row['text']}",
            font=title_font,
            fill="#f4f4f4",
            width=72,
            max_lines=3,
        )
        for column, choice_label in enumerate(("A", "B", "C")):
            x0 = column * 400
            score = row.get(f"candidate_{choice_label.lower()}_score", "")
            draw.rectangle((x0, 82, x0 + 400, 122), fill=(10, 10, 10))
            draw.text(
                (x0 + 9, 91),
                f"{choice_label}  score={score}",
                font=title_font,
                fill="#61dada" if choice_label == "A" else "#eeeeee",
            )
            for sample_index, sample in enumerate(
                evidence[(line_id, choice_label)]
            ):
                y0 = 122 + sample_index * 286
                tile = fit_image(Path(sample["path"]), (400, 248))
                sheet.paste(tile, (x0, y0))
                draw.rectangle((x0, y0 + 248, x0 + 400, y0 + 286), fill=(8, 8, 8))
                draw.text(
                    (x0 + 8, y0 + 257),
                    f"{sample['sample'].upper()}  {sample['timestamp']:.3f}s",
                    font=label_font,
                    fill="#dddddd",
                )
        output = output_dir / f"risk_{line_id:04d}.jpg"
        sheet.save(output, quality=92, subsampling=0)
        records.append(
            {
                "kind": "risk_abc_sheet",
                "path": str(output.resolve()),
                "sha256": sha256_file(output),
                "size_bytes": output.stat().st_size,
                "cue_ids": [line_id],
            }
        )
    return records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("match_sheet", nargs="?", type=Path)
    parser.add_argument("--match-sheet", dest="match_sheet_flag", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--candidate-pool", type=Path, required=True)
    parser.add_argument(
        "--mode",
        choices=("selected", "risk", "both"),
        default="both",
    )
    parser.add_argument("--risk-ids", default="")
    parser.add_argument("--risk-ids-file", type=Path)
    parser.add_argument("--ffmpeg", default=shutil.which("ffmpeg") or "ffmpeg")
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    load_pillow()

    match_sheet = args.match_sheet_flag or args.match_sheet
    if match_sheet is None:
        parser.error("provide MATCH_SHEET or --match-sheet")
    match_sheet = match_sheet.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    source_manifest = args.source_manifest.expanduser().resolve()
    if not source_manifest.is_file():
        raise SystemExit(f"source manifest is missing: {source_manifest}")
    candidate_pool = args.candidate_pool.expanduser().resolve()
    if not candidate_pool.is_file():
        raise SystemExit(f"candidate pool is missing: {candidate_pool}")
    source_paths = source_paths_from_manifest(source_manifest)
    rows = read_tsv(match_sheet)
    row_ids = [int(row["line_id"]) for row in rows]
    if len(row_ids) != len(set(row_ids)):
        raise SystemExit("duplicate line_id values in match sheet")

    explicit_risk = parse_ids(args.risk_ids) | ids_from_file(args.risk_ids_file)
    unknown_risk = explicit_risk - set(row_ids)
    if unknown_risk:
        raise SystemExit(f"unknown --risk-ids: {sorted(unknown_risk)}")
    risk_ids = {
        int(row["line_id"]) for row in rows if is_risk_row(row)
    } | explicit_risk
    risk_rows = [row for row in rows if int(row["line_id"]) in risk_ids]

    evidence_dir = output_dir / "evidence"
    selected_dir = output_dir / "selected"
    risk_dir = output_dir / "risk"
    evidence: dict[tuple[int, str], list[dict[str, Any]]] = {}
    errors: list[dict[str, Any]] = []

    requested: list[tuple[dict[str, str], MediaChoice]] = []
    if args.mode in {"selected", "both"}:
        for row in rows:
            try:
                requested.append((row, selected_choice(row)))
            except (KeyError, OSError, ValueError) as error:
                errors.append(
                    {
                        "line_id": int(row.get("line_id") or 0),
                        "view": "selected",
                        "error": str(error),
                    }
                )
    if args.mode in {"risk", "both"}:
        for row in risk_rows:
            for suffix in ("A", "B", "C"):
                try:
                    requested.append(
                        (row, candidate_choice(row, suffix, source_paths))
                    )
                except (KeyError, OSError, ValueError) as error:
                    errors.append(
                        {
                            "line_id": int(row.get("line_id") or 0),
                            "view": suffix,
                            "error": str(error),
                        }
                    )

    file_records: list[dict[str, Any]] = []
    for row, choice in requested:
        line_id = int(row["line_id"])
        samples = []
        if not choice.source_file.is_file():
            errors.append(
                {
                    "line_id": line_id,
                    "view": choice.label,
                    "error": f"source missing: {choice.source_file}",
                }
            )
            continue
        for sample_name, timestamp in sample_points(choice):
            destination = (
                evidence_dir
                / f"cue_{line_id:04d}_{choice.label.lower()}_{sample_name}.jpg"
            )
            try:
                render_sample(
                    choice,
                    f"cue {line_id} {choice.label} {sample_name}",
                    timestamp,
                    destination,
                    args.ffmpeg,
                )
            except (OSError, RuntimeError) as error:
                errors.append(
                    {
                        "line_id": line_id,
                        "view": choice.label,
                        "sample": sample_name,
                        "error": str(error),
                    }
                )
                continue
            record = {
                "kind": "evidence_frame",
                "path": str(destination.resolve()),
                "sha256": sha256_file(destination),
                "size_bytes": destination.stat().st_size,
                "cue_ids": [line_id],
                "view": choice.label,
                "sample": sample_name,
                "candidate_id": choice.candidate_id,
                "source_id": choice.source_id,
                "source_file": str(choice.source_file),
                "source_in": choice.source_in,
                "source_out": choice.source_out,
                "timestamp": timestamp,
            }
            file_records.append(record)
            samples.append(
                {
                    "sample": sample_name,
                    "timestamp": timestamp,
                    "path": record["path"],
                    "sha256": record["sha256"],
                }
            )
        if len(samples) == 3:
            evidence[(line_id, choice.label)] = samples

    if not errors and args.mode in {"selected", "both"}:
        file_records.extend(
            make_selected_sheets(rows, evidence, selected_dir)
        )
    if not errors and args.mode in {"risk", "both"}:
        file_records.extend(
            make_risk_sheets(risk_rows, evidence, risk_dir)
        )

    evidence_manifest_path = output_dir / "selected_evidence_manifest.tsv"
    if not errors and args.mode in {"selected", "both"}:
        evidence_rows: list[dict[str, object]] = []
        for row in rows:
            line_id = int(row["line_id"])
            samples = evidence[(line_id, "selected")]
            sample_by_name = {sample["sample"]: sample for sample in samples}
            evidence_rows.append(
                {
                    "line_id": line_id,
                    "caption": row["text"],
                    "source_id": (
                        row.get("selected_source_id", "")
                        or row.get("source_id", "")
                    ),
                    "source_file": str(
                        Path(row["source_file"]).expanduser().resolve()
                    ),
                    "source_in": row.get("source_in", ""),
                    "source_out": row.get("source_out", ""),
                    "evidence_image": sample_by_name["mid"]["path"],
                    "evidence_head": sample_by_name["head"]["path"],
                    "evidence_mid": sample_by_name["mid"]["path"],
                    "evidence_tail": sample_by_name["tail"]["path"],
                    "black_midpoint": str(
                        image_is_black(Path(sample_by_name["mid"]["path"]))
                    ),
                    "visual_review": "PENDING",
                }
            )
        atomic_tsv(
            evidence_manifest_path,
            [
                "line_id",
                "caption",
                "source_id",
                "source_file",
                "source_in",
                "source_out",
                "evidence_image",
                "evidence_head",
                "evidence_mid",
                "evidence_tail",
                "black_midpoint",
                "visual_review",
            ],
            evidence_rows,
        )
        file_records.append(
            {
                "kind": "selected_evidence_manifest",
                "path": str(evidence_manifest_path.resolve()),
                "sha256": sha256_file(evidence_manifest_path),
                "size_bytes": evidence_manifest_path.stat().st_size,
                "cue_ids": row_ids,
            }
        )

    manifest_path = (
        args.manifest.expanduser().resolve()
        if args.manifest
        else output_dir / "candidate_review_manifest.json"
    )
    selected_evidence_ids = (
        row_ids if args.mode in {"selected", "both"} and not errors else []
    )
    candidate_evidence_ids = (
        sorted(risk_ids)
        if args.mode in {"risk", "both"} and not errors
        else []
    )
    identity_required_ids = sorted(
        int(row["line_id"])
        for row in rows
        if is_true(row.get("identity_required", ""))
        or row.get("named_entities_expected", "").strip()
        or (
            row.get("subject", "").strip()
            and row.get("subject", "").strip() not in {"主题概念", "叙述者", "无"}
        )
    )
    selected_sheet_records = [
        record
        for record in file_records
        if record.get("kind") == "selected_sheet"
    ]
    range_reviews = [
        {
            "range": (
                f"{record['cue_ids'][0]}-{record['cue_ids'][-1]}"
            ),
            "status": "PENDING",
            "sheet_path": record["path"],
            "sheet_sha256": record["sha256"],
        }
        for record in selected_sheet_records
        if record.get("cue_ids")
    ]
    manifest = {
        "schema_version": 2,
        "status": "FAIL" if errors else "READY_FOR_REVIEW",
        "artifact_status": "FAIL" if errors else "PASS",
        "match_sheet": str(match_sheet),
        "match_sheet_sha256": sha256_file(match_sheet),
        "source_manifest": str(source_manifest) if source_manifest else "",
        "source_manifest_sha256": (
            sha256_file(source_manifest) if source_manifest else ""
        ),
        "candidate_pool_path": str(candidate_pool),
        "candidate_pool_sha256": sha256_file(candidate_pool),
        "mode": args.mode,
        "row_count": len(rows),
        "selected_evidence_manifest_path": (
            str(evidence_manifest_path.resolve())
            if evidence_manifest_path.is_file()
            else ""
        ),
        "selected_evidence_manifest_sha256": (
            sha256_file(evidence_manifest_path)
            if evidence_manifest_path.is_file()
            else ""
        ),
        "contact_sheets": [
            record["path"] for record in selected_sheet_records
        ],
        "range_reviews": range_reviews,
        "selected_evidence_ids": selected_evidence_ids,
        "risk_row_ids": sorted(risk_ids),
        "candidate_evidence_ids": candidate_evidence_ids,
        "identity_required_ids": identity_required_ids,
        "selected_reviewed_ids": [],
        "candidate_reviewed_ids": [],
        "identity_verified": {},
        "opening_review": {"status": "PENDING"},
        "ending_review": {"status": "PENDING"},
        "unresolved_ids": sorted(
            {
                int(error["line_id"])
                for error in errors
                if int(error.get("line_id") or 0) > 0
            }
        ),
        "files": file_records,
        "errors": errors,
        "review_instructions": [
            "Review only files listed in this manifest and verify their SHA-256 values.",
            "Set status=PASS only after selected_reviewed_ids covers every cue.",
            "candidate_reviewed_ids must cover every risk_row_id.",
            "Set every range_reviews[].status to PASS after reviewing that selected sheet.",
            "Set every selected_evidence_manifest.tsv visual_review cell to approved_manual, then refresh selected_evidence_manifest_sha256.",
            "After changing the evidence TSV, also refresh the matching files[] record SHA-256 and size.",
            "identity_verified, opening_review, ending_review, and unresolved_ids must be completed before render-ready audit.",
        ],
    }
    atomic_json(manifest_path, manifest)
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "row_count": len(rows),
                "risk_row_count": len(risk_ids),
                "file_count": len(file_records),
                "manifest": str(manifest_path),
            },
            ensure_ascii=False,
        )
    )
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
