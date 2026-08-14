#!/usr/bin/env python3
"""Select a coverage-oriented review queue from normalized Bilibili seasons."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from datetime import datetime
from pathlib import Path


NARRATIVE_TERMS = (
    "剧情",
    "叙事",
    "解析",
    "考据",
    "细节",
    "伏笔",
    "隐喻",
    "原型",
    "世界观",
    "角色",
    "故事",
    "神话",
    "主义",
    "文学",
    "哲学",
    "悲剧",
    "真相",
    "为什么",
    "究竟",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("seasons", type=Path, nargs="+")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--per-season", type=int, default=8)
    return parser.parse_args()


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("episodes"), list):
        raise ValueError(f"{path}: not a normalized season file")
    if value.get("integrity", {}).get("matches_reported_total") is not True:
        raise ValueError(f"{path}: season integrity check failed")
    return value


def safe_number(value: object) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return 0.0


def narrative_term_count(title: object) -> int:
    if not isinstance(title, str):
        return 0
    return sum(1 for term in NARRATIVE_TERMS if term in title)


def published_timestamp(episode: dict) -> float:
    value = episode.get("published_at")
    if not isinstance(value, str):
        return 0.0
    return datetime.fromisoformat(value).timestamp()


def closest_to_typical(episodes: list[dict]) -> dict:
    median_duration = statistics.median(
        safe_number(episode.get("duration_seconds")) for episode in episodes
    )
    median_log_views = statistics.median(
        math.log1p(safe_number(episode.get("view_count_snapshot")))
        for episode in episodes
    )

    def distance(episode: dict) -> float:
        duration = safe_number(episode.get("duration_seconds"))
        log_views = math.log1p(safe_number(episode.get("view_count_snapshot")))
        duration_scale = max(median_duration, 1.0)
        view_scale = max(median_log_views, 1.0)
        return abs(duration - median_duration) / duration_scale + abs(
            log_views - median_log_views
        ) / view_scale

    return min(episodes, key=distance)


def add_candidate(
    selected: dict[str, dict],
    episode: dict,
    role: str,
    reason: str,
) -> None:
    bvid = episode.get("bvid")
    if not isinstance(bvid, str):
        return
    item = selected.setdefault(
        bvid,
        {
            **episode,
            "sampling_roles": [],
            "sampling_reasons": [],
        },
    )
    if role not in item["sampling_roles"]:
        item["sampling_roles"].append(role)
        item["sampling_reasons"].append(reason)


def select(season: dict, limit: int) -> list[dict]:
    episodes = season["episodes"]
    if not episodes:
        return []
    selected: dict[str, dict] = {}

    choices = [
        (
            max(episodes, key=lambda item: safe_number(item.get("view_count_snapshot"))),
            "view-snapshot-peak",
            "Highest retrieval-time view count; inspect for reach mechanisms, not assumed quality.",
        ),
        (
            max(episodes, key=lambda item: safe_number(item.get("danmaku_count_snapshot"))),
            "discussion-snapshot-peak",
            "Highest retrieval-time danmaku count; inspect audience response points.",
        ),
        (
            max(episodes, key=lambda item: safe_number(item.get("duration_seconds"))),
            "long-form-extreme",
            "Longest item; inspect long-range structure, chaptering, and fatigue control.",
        ),
        (
            closest_to_typical(episodes),
            "typical-profile",
            "Closest to the season's median duration and view profile.",
        ),
        (
            max(episodes, key=published_timestamp),
            "recent",
            "Most recently published item; inspect current production conventions.",
        ),
        (
            min(episodes, key=published_timestamp),
            "archive",
            "Oldest item; inspect how the creator's editing grammar changed.",
        ),
        (
            max(
                episodes,
                key=lambda item: (
                    narrative_term_count(item.get("title")),
                    safe_number(item.get("view_count_snapshot")),
                ),
            ),
            "narrative-language",
            "Dense narrative-analysis language in the title; inspect claim and proof structure.",
        ),
        (
            max(
                episodes,
                key=lambda item: (
                    safe_number(item.get("view_count_snapshot"))
                    / max(safe_number(item.get("duration_seconds")), 60.0),
                    narrative_term_count(item.get("title")),
                ),
            ),
            "compact-reach",
            "High view snapshot relative to duration; inspect compression and opening contract.",
        ),
    ]
    for episode, role, reason in choices:
        add_candidate(selected, episode, role, reason)

    if len(selected) < limit:
        remaining = sorted(
            episodes,
            key=lambda item: (
                narrative_term_count(item.get("title")),
                safe_number(item.get("view_count_snapshot")),
            ),
            reverse=True,
        )
        for episode in remaining:
            add_candidate(
                selected,
                episode,
                "coverage-fill",
                "Added to reach the requested review-queue size with narrative relevance.",
            )
            if len(selected) >= limit:
                break

    role_priority = {
        "view-snapshot-peak": 0,
        "discussion-snapshot-peak": 1,
        "long-form-extreme": 2,
        "typical-profile": 3,
        "recent": 4,
        "archive": 5,
        "narrative-language": 6,
        "compact-reach": 7,
        "coverage-fill": 8,
    }
    output = list(selected.values())
    output.sort(
        key=lambda item: min(
            role_priority.get(role, 99) for role in item["sampling_roles"]
        )
    )
    return output[:limit]


def main() -> None:
    args = parse_args()
    if args.per_season < 1:
        raise SystemExit("--per-season must be positive")

    season_outputs: list[dict] = []
    for path in args.seasons:
        season = load(path)
        chosen = select(season, args.per_season)
        season_outputs.append(
            {
                "season_id": season["meta"]["season_id"],
                "title": season["meta"]["title"],
                "source": season["source"],
                "episode_count": len(season["episodes"]),
                "selected_count": len(chosen),
                "selected": chosen,
            }
        )

    output = {
        "schema_version": "1.0",
        "purpose": "Coverage-oriented manual review queue; not a quality ranking.",
        "seasons": season_outputs,
        "warnings": [
            "Views and danmaku are retrieval-time snapshots.",
            "Popularity and title wording do not prove editing quality.",
            "Promote rules only after audiovisual annotation and cross-work comparison.",
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.out.resolve()),
                "season_count": len(season_outputs),
                "selected_total": sum(
                    item["selected_count"] for item in season_outputs
                ),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
