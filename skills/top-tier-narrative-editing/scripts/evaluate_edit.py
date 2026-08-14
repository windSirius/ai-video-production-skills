#!/usr/bin/env python3
"""Aggregate a narrative-editing rubric JSON and enforce hard gates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


MAXIMA = {
    "narrative_contract_and_hook": 15,
    "visual_reasoning": 20,
    "rhythm_and_attention": 15,
    "emotional_architecture": 15,
    "evidence_and_comprehension": 10,
    "sound_and_narration": 10,
    "continuity_and_payoff": 10,
    "technical_finish": 5,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("evaluation", type=Path)
    return parser.parse_args()


def load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("evaluation must be a JSON object")
    return data


def validate_scores(data: dict) -> tuple[dict[str, float], list[str]]:
    raw_scores = data.get("scores")
    if not isinstance(raw_scores, dict):
        raise ValueError("scores must be a JSON object")

    scores: dict[str, float] = {}
    errors: list[str] = []
    for key, maximum in MAXIMA.items():
        value = raw_scores.get(key)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            errors.append(f"{key}: missing or non-numeric")
            continue
        numeric = float(value)
        if numeric < 0 or numeric > maximum:
            errors.append(f"{key}: {numeric} outside 0..{maximum}")
            continue
        scores[key] = numeric
    return scores, errors


def rating(total: float) -> str:
    if total >= 90:
        return "exceptional_internal_benchmark"
    if total >= 80:
        return "strong_publishable"
    if total >= 70:
        return "competent_needs_revision"
    return "structural_revision_required"


def main() -> None:
    args = parse_args()
    data = load(args.evaluation)
    scores, errors = validate_scores(data)

    hard_gates = data.get("hard_gates", {})
    if not isinstance(hard_gates, dict):
        errors.append("hard_gates must be a JSON object")
        hard_gates = {}
    failed_gates = sorted(key for key, passed in hard_gates.items() if passed is not True)

    total = sum(scores.values())
    result = {
        "total": total,
        "maximum": sum(MAXIMA.values()),
        "rating": rating(total),
        "hard_gate_failures": failed_gates,
        "accepted": not errors and not failed_gates and total >= 80,
        "validation_errors": errors,
        "quality_claim": (
            "Internal revision proxy only; external and repeated-project evidence "
            "is required for a top-tier claim."
        ),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(2)
    if failed_gates:
        raise SystemExit(3)


if __name__ == "__main__":
    main()
