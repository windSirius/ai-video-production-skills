#!/usr/bin/env python3
"""Pack exact canonical units into deterministic VoxCPM2 generation blocks.

Canonical units are evidence and source-coverage units.  Generation blocks are
the larger, contiguous groups sent to VoxCPM2 as Target Text.  This planner
never rewrites or splits a canonical unit: it only groups adjacent units whose
existing boundaries are valid semantic boundaries.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


DEFAULT_TARGET = 150
DEFAULT_PREFERRED_MIN = 120
DEFAULT_PREFERRED_MAX = 180
DEFAULT_SHORT_WARNING = 100
DEFAULT_VERY_SHORT = 60
DEFAULT_SOFT_MAX = 200

LEGAL_TERMINATORS = frozenset("。！？!?；;.…")
TRAILING_CLOSERS = frozenset("”’」』】）》）)]}")


class PlanningError(ValueError):
    """Raised when canonical coverage or a semantic boundary is invalid."""


@dataclass(frozen=True)
class LengthPolicy:
    target: int = DEFAULT_TARGET
    preferred_min: int = DEFAULT_PREFERRED_MIN
    preferred_max: int = DEFAULT_PREFERRED_MAX
    short_warning_below: int = DEFAULT_SHORT_WARNING
    very_short_below: int = DEFAULT_VERY_SHORT
    soft_max: int = DEFAULT_SOFT_MAX

    def validate(self) -> None:
        values = (
            self.very_short_below,
            self.short_warning_below,
            self.preferred_min,
            self.target,
            self.preferred_max,
            self.soft_max,
        )
        if not all(isinstance(value, int) and value > 0 for value in values):
            raise PlanningError("all length thresholds must be positive integers")
        if not (
            self.very_short_below
            <= self.short_warning_below
            <= self.preferred_min
            <= self.target
            <= self.preferred_max
            <= self.soft_max
        ):
            raise PlanningError(
                "thresholds must satisfy very_short <= short_warning <= "
                "preferred_min <= target <= preferred_max <= soft_max"
            )


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def spoken_char_count(value: str) -> int:
    """Count normalized letters and numbers in generation text."""

    normalized = unicodedata.normalize("NFKC", value)
    return sum(
        1
        for character in normalized
        if unicodedata.category(character)[:1] in {"L", "N"}
    )


def is_legal_semantic_boundary(value: str) -> bool:
    """Return whether a canonical unit ends at a permitted semantic boundary."""

    if not value:
        return False
    horizontal_trimmed = value.rstrip(" \t")
    if horizontal_trimmed.endswith(("\n", "\r")):
        return True
    stripped = value.rstrip()
    while stripped and stripped[-1] in TRAILING_CLOSERS:
        stripped = stripped[:-1].rstrip()
    return bool(stripped) and stripped[-1] in LEGAL_TERMINATORS


def _require_mapping(value: Any, index: int) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PlanningError(f"canonical unit {index} must be a JSON object")
    return value


def normalize_units(
    canonical_text: str,
    raw_units: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Bind units to source spans and preserve whitespace-only separator gaps."""

    units: list[dict[str, Any]] = []
    separator_gaps: list[dict[str, Any]] = []
    cursor = 0
    previous_unit_id: str | None = None
    seen_ids: set[str] = set()
    raw_list = list(raw_units)
    if not raw_list:
        raise PlanningError("at least one canonical unit is required")

    for index, raw_value in enumerate(raw_list, start=1):
        raw = _require_mapping(raw_value, index)
        unit_id_value = raw.get("unit_id", raw.get("segment_id"))
        if unit_id_value is None or not str(unit_id_value):
            raise PlanningError(f"canonical unit {index} is missing unit_id or segment_id")
        unit_id = str(unit_id_value)
        if unit_id in seen_ids:
            raise PlanningError(f"duplicate canonical unit id: {unit_id}")
        seen_ids.add(unit_id)

        canonical = raw.get("canonical_text")
        if not isinstance(canonical, str) or not canonical:
            raise PlanningError(f"canonical unit {unit_id} has empty canonical_text")
        if not any(not character.isspace() for character in canonical):
            raise PlanningError(
                f"canonical unit {unit_id} contains only whitespace; use separator gaps"
            )
        generation = raw.get("generation_text", canonical)
        if not isinstance(generation, str) or not generation:
            raise PlanningError(f"canonical unit {unit_id} has empty generation_text")

        supplied_span = raw.get("source_span")
        if supplied_span is not None:
            if (
                not isinstance(supplied_span, list)
                or len(supplied_span) != 2
                or not all(isinstance(item, int) for item in supplied_span)
            ):
                raise PlanningError(f"canonical unit {unit_id} has invalid source_span")
            start, end = supplied_span
        else:
            start = cursor
            if not canonical_text.startswith(canonical, start):
                while start < len(canonical_text) and canonical_text[start].isspace():
                    start += 1
            end = start + len(canonical)

        if start < cursor:
            raise PlanningError(
                f"canonical unit {unit_id} source_span overlaps earlier coverage"
            )
        if start < 0 or end < start or end > len(canonical_text):
            raise PlanningError(f"canonical unit {unit_id} source_span is outside the source")

        gap_text = canonical_text[cursor:start]
        if gap_text and not all(character.isspace() for character in gap_text):
            raise PlanningError(
                f"non-whitespace source gap before canonical unit {unit_id}: "
                f"span {[cursor, start]}"
            )
        separator_before_gap_id: str | None = None
        if gap_text:
            separator_before_gap_id = f"GAP{len(separator_gaps) + 1:03d}"
            separator_gaps.append(
                {
                    "gap_id": separator_before_gap_id,
                    "kind": "leading" if previous_unit_id is None else "between_units",
                    "after_unit_id": previous_unit_id,
                    "before_unit_id": unit_id,
                    "source_span": [cursor, start],
                    "separator_text": gap_text,
                    "separator_sha256": sha256_text(gap_text),
                    "code_point_count": len(gap_text),
                    "whitespace_only": True,
                }
            )

        source_span = [start, end]
        if canonical_text[start:end] != canonical:
            raise PlanningError(
                f"canonical unit {unit_id} does not match the approved source at "
                f"span {source_span}"
            )

        force_break_after = raw.get("force_break_after", False)
        if not isinstance(force_break_after, bool):
            raise PlanningError(f"canonical unit {unit_id} force_break_after must be boolean")
        short_reason = raw.get("short_segment_reason")
        if short_reason is not None and (
            not isinstance(short_reason, str) or not short_reason.strip()
        ):
            raise PlanningError(
                f"canonical unit {unit_id} short_segment_reason must be non-empty text"
            )

        units.append(
            {
                "unit_id": unit_id,
                "canonical_text": canonical,
                "generation_text": generation,
                "source_span": source_span,
                "separator_before_gap_id": separator_before_gap_id,
                "force_break_after": force_break_after,
                "short_segment_reason": short_reason.strip() if short_reason else None,
                "spoken_char_count": spoken_char_count(generation),
            }
        )
        cursor = end
        previous_unit_id = unit_id

    trailing_text = canonical_text[cursor:]
    if trailing_text and not all(character.isspace() for character in trailing_text):
        raise PlanningError(
            f"non-whitespace trailing source gap: span {[cursor, len(canonical_text)]}"
        )
    if trailing_text:
        separator_gaps.append(
            {
                "gap_id": f"GAP{len(separator_gaps) + 1:03d}",
                "kind": "trailing",
                "after_unit_id": previous_unit_id,
                "before_unit_id": None,
                "source_span": [cursor, len(canonical_text)],
                "separator_text": trailing_text,
                "separator_sha256": sha256_text(trailing_text),
                "code_point_count": len(trailing_text),
                "whitespace_only": True,
            }
        )

    source_non_whitespace = sum(
        1 for character in canonical_text if not character.isspace()
    )
    covered_non_whitespace = sum(
        1
        for unit in units
        for character in str(unit["canonical_text"])
        if not character.isspace()
    )
    if covered_non_whitespace != source_non_whitespace:
        raise PlanningError(
            "canonical units do not cover every non-whitespace source character exactly once"
        )

    for unit in units[:-1]:
        if not is_legal_semantic_boundary(unit["canonical_text"]):
            raise PlanningError(
                f"canonical unit {unit['unit_id']} does not end at a legal semantic boundary"
            )
    return units, separator_gaps


def _length_penalty(count: int, policy: LengthPolicy) -> int:
    distance = abs(count - policy.target)
    if policy.preferred_min <= count <= policy.preferred_max:
        return distance
    if policy.short_warning_below <= count <= policy.soft_max:
        return 10_000 + distance
    if policy.very_short_below <= count < policy.short_warning_below:
        return 100_000 + distance
    if count < policy.very_short_below:
        return 1_000_000 + distance
    return 10_000_000 + distance


def _partition_chunk(
    units: list[dict[str, Any]],
    policy: LengthPolicy,
) -> list[list[dict[str, Any]]]:
    """Find a deterministic minimum-penalty contiguous partition."""

    prefix = [0]
    for unit in units:
        prefix.append(prefix[-1] + int(unit["spoken_char_count"]))

    # Each state is total penalty plus the tuple of exclusive end boundaries.
    best: list[tuple[int, tuple[int, ...]] | None] = [None] * (len(units) + 1)
    best[0] = (0, ())
    for end in range(1, len(units) + 1):
        for start in range(0, end):
            previous = best[start]
            if previous is None:
                continue
            count = prefix[end] - prefix[start]
            # soft_max may be exceeded only by one indivisible canonical unit.
            if count > policy.soft_max and end - start > 1:
                continue
            boundaries = previous[1] + (end,)
            candidate = (
                previous[0] + _length_penalty(count, policy),
                boundaries,
            )
            current = best[end]
            candidate_key = (candidate[0], len(boundaries), boundaries)
            if current is None:
                best[end] = candidate
                continue
            current_key = (current[0], len(current[1]), current[1])
            if candidate_key < current_key:
                best[end] = candidate

    result = best[-1]
    if result is None:
        raise PlanningError("no legal generation-block partition could be constructed")
    groups: list[list[dict[str, Any]]] = []
    start = 0
    for end in result[1]:
        groups.append(units[start:end])
        start = end
    return groups


def partition_units(
    units: list[dict[str, Any]],
    policy: LengthPolicy,
) -> list[list[dict[str, Any]]]:
    """Partition units without crossing an explicit force_break_after marker."""

    groups: list[list[dict[str, Any]]] = []
    chunk_start = 0
    for index, unit in enumerate(units):
        if unit["force_break_after"] or index == len(units) - 1:
            groups.extend(_partition_chunk(units[chunk_start : index + 1], policy))
            chunk_start = index + 1
    return groups


def classify_length(count: int, policy: LengthPolicy) -> str:
    if count < policy.very_short_below:
        return "very_short"
    if count < policy.short_warning_below:
        return "short"
    if count < policy.preferred_min:
        return "below_preferred"
    if count <= policy.preferred_max:
        return "preferred"
    if count <= policy.soft_max:
        return "above_preferred"
    return "over_soft_max"


def build_plan(
    canonical_text: str,
    raw_units: Iterable[dict[str, Any]],
    policy: LengthPolicy | None = None,
) -> dict[str, Any]:
    policy = policy or LengthPolicy()
    policy.validate()
    units, separator_gaps = normalize_units(canonical_text, raw_units)
    groups = partition_units(units, policy)
    gaps_by_id = {
        str(gap["gap_id"]): gap
        for gap in separator_gaps
    }

    blocks: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for index, group in enumerate(groups, start=1):
        canonical_parts = [str(group[0]["canonical_text"])]
        generation_parts = [str(group[0]["generation_text"])]
        internal_gap_ids: list[str] = []
        for unit in group[1:]:
            gap_id = unit.get("separator_before_gap_id")
            if gap_id:
                gap = gaps_by_id[str(gap_id)]
                separator = str(gap["separator_text"])
                canonical_parts.append(separator)
                generation_parts.append(separator)
                internal_gap_ids.append(str(gap_id))
            canonical_parts.append(str(unit["canonical_text"]))
            generation_parts.append(str(unit["generation_text"]))
        canonical = "".join(canonical_parts)
        generation = "".join(generation_parts)
        count = spoken_char_count(generation)
        block_id = f"GB{index:03d}"
        status = classify_length(count, policy)
        reasons = list(
            dict.fromkeys(
                str(unit["short_segment_reason"])
                for unit in group
                if unit.get("short_segment_reason")
            )
        )
        block = {
            "generation_block_id": block_id,
            "canonical_unit_ids": [unit["unit_id"] for unit in group],
            "canonical_text": canonical,
            "generation_text": generation,
            "source_span": [
                int(group[0]["source_span"][0]),
                int(group[-1]["source_span"][1]),
            ],
            "covered_source_spans": [
                list(unit["source_span"])
                for unit in group
            ],
            "separator_gap_ids": internal_gap_ids,
            "spoken_char_count": count,
            "length_status": status,
            "short_segment_reasons": reasons,
            "canonical_sha256": sha256_text(canonical),
            "generation_sha256": sha256_text(generation),
            "force_break_after": bool(group[-1]["force_break_after"]),
        }
        source_slice = canonical_text[block["source_span"][0] : block["source_span"][1]]
        if source_slice != canonical:
            raise PlanningError(
                f"generation block {block_id} does not preserve its source separators"
            )
        blocks.append(block)

        if status == "very_short":
            warnings.append(
                {
                    "code": "very_short_generation_block",
                    "generation_block_id": block_id,
                    "spoken_char_count": count,
                    "threshold": policy.very_short_below,
                    "short_segment_reasons": reasons,
                }
            )
        elif status == "short":
            warnings.append(
                {
                    "code": "short_generation_block",
                    "generation_block_id": block_id,
                    "spoken_char_count": count,
                    "threshold": policy.short_warning_below,
                    "short_segment_reasons": reasons,
                }
            )
        elif status == "over_soft_max":
            warnings.append(
                {
                    "code": "generation_block_over_soft_max",
                    "generation_block_id": block_id,
                    "spoken_char_count": count,
                    "threshold": policy.soft_max,
                }
            )

    source_non_whitespace = sum(
        1 for character in canonical_text if not character.isspace()
    )
    covered_non_whitespace = sum(
        1
        for unit in units
        for character in str(unit["canonical_text"])
        if not character.isspace()
    )

    return {
        "schema_version": "voxcpm_generation_block_plan_v1",
        "policy": asdict(policy),
        "canonical_sha256": sha256_text(canonical_text),
        "canonical_length_code_points": len(canonical_text),
        "source_span_unit": "unicode_code_points",
        "coverage": {
            "exact": True,
            "policy": "canonical_units_plus_whitespace_gaps_cover_source_exactly_once",
            "source_exactly_partitioned_by_units_and_gaps": True,
            "all_non_whitespace_covered_once": True,
            "no_non_whitespace_gaps": True,
            "source_non_whitespace_code_points": source_non_whitespace,
            "covered_non_whitespace_code_points": covered_non_whitespace,
            "separator_gap_count": len(separator_gaps),
            "separator_code_points": sum(
                int(gap["code_point_count"])
                for gap in separator_gaps
            ),
            "canonical_unit_count": len(units),
            "generation_block_count": len(blocks),
        },
        "canonical_units": units,
        "separator_gaps": separator_gaps,
        "generation_blocks": blocks,
        "warnings": warnings,
    }


def load_unit_rows(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(value, dict):
        value = value.get("canonical_units", value.get("units"))
    if not isinstance(value, list):
        raise PlanningError(
            "units JSON must be an array or an object containing canonical_units or units"
        )
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("canonical", type=Path, help="approved canonical plain-text file")
    parser.add_argument("units", type=Path, help="JSON canonical-unit array or object")
    parser.add_argument("--output", type=Path, help="write the plan as JSON; otherwise print it")
    parser.add_argument("--target", type=int, default=DEFAULT_TARGET)
    parser.add_argument("--preferred-min", type=int, default=DEFAULT_PREFERRED_MIN)
    parser.add_argument("--preferred-max", type=int, default=DEFAULT_PREFERRED_MAX)
    parser.add_argument("--short-warning-below", type=int, default=DEFAULT_SHORT_WARNING)
    parser.add_argument("--very-short-below", type=int, default=DEFAULT_VERY_SHORT)
    parser.add_argument("--soft-max", type=int, default=DEFAULT_SOFT_MAX)
    parser.add_argument(
        "--fail-on-warnings",
        action="store_true",
        help="exit 2 after writing the plan when length warnings exist",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        policy = LengthPolicy(
            target=args.target,
            preferred_min=args.preferred_min,
            preferred_max=args.preferred_max,
            short_warning_below=args.short_warning_below,
            very_short_below=args.very_short_below,
            soft_max=args.soft_max,
        )
        canonical_text = args.canonical.read_text(encoding="utf-8")
        plan = build_plan(canonical_text, load_unit_rows(args.units), policy)
    except (OSError, json.JSONDecodeError, PlanningError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    if args.output:
        write_json(args.output, plan)
    else:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    if args.fail_on_warnings and plan["warnings"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
