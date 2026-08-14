#!/usr/bin/env python3
"""Fetch and normalize a public Bilibili season/archive list."""

from __future__ import annotations

import argparse
import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path


API = "https://api.bilibili.com/x/polymer/web-space/seasons_archives_list"

try:
    import certifi
except ImportError:
    SSL_CONTEXT = ssl.create_default_context()
else:
    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mid", type=int, required=True)
    parser.add_argument("--season-id", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--page-size", type=int, default=30)
    return parser.parse_args()


def fetch_json(mid: int, season_id: int, page_num: int, page_size: int) -> dict:
    query = urllib.parse.urlencode(
        {
            "mid": mid,
            "season_id": season_id,
            "sort_reverse": "false",
            "page_num": page_num,
            "page_size": page_size,
        }
    )
    request = urllib.request.Request(
        f"{API}?{query}",
        headers={
            "Accept": "application/json",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
            "Referer": f"https://space.bilibili.com/{mid}/",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 Chrome/126.0 Safari/537.36"
            ),
        },
    )
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(
                request,
                timeout=30,
                context=SSL_CONTEXT,
            ) as response:
                payload = json.load(response)
            if payload.get("code") != 0:
                raise RuntimeError(
                    f"Bilibili API error {payload.get('code')}: {payload.get('message')}"
                )
            return payload
        except (urllib.error.URLError, TimeoutError, RuntimeError) as error:
            last_error = error
            if attempt < 2:
                time.sleep(1.0 + attempt)
    raise RuntimeError(f"Failed after retries: {last_error}")


def iso_timestamp(value: object) -> str | None:
    if not isinstance(value, int):
        return None
    return datetime.fromtimestamp(value, tz=UTC).isoformat()


def normalize_archive(index: int, archive: dict) -> dict:
    stat = archive.get("stat") if isinstance(archive.get("stat"), dict) else {}
    return {
        "order": index,
        "aid": archive.get("aid"),
        "bvid": archive.get("bvid"),
        "title": archive.get("title"),
        "duration_seconds": archive.get("duration"),
        "published_at": iso_timestamp(archive.get("pubdate")),
        "view_count_snapshot": stat.get("view"),
        "danmaku_count_snapshot": stat.get("danmaku"),
        "cover": archive.get("pic"),
        "url": (
            f"https://www.bilibili.com/video/{archive.get('bvid')}/"
            if archive.get("bvid")
            else None
        ),
    }


def main() -> None:
    args = parse_args()
    if not 1 <= args.page_size <= 100:
        raise SystemExit("--page-size must be between 1 and 100")

    first = fetch_json(args.mid, args.season_id, 1, args.page_size)
    data = first["data"]
    meta = data["meta"]
    total = int(meta["total"])
    archives = list(data.get("archives", []))
    page_num = 2
    while len(archives) < total:
        page = fetch_json(args.mid, args.season_id, page_num, args.page_size)
        batch = page["data"].get("archives", [])
        if not batch:
            break
        archives.extend(batch)
        page_num += 1

    deduplicated: list[dict] = []
    seen: set[str] = set()
    for archive in archives:
        bvid = archive.get("bvid")
        if not isinstance(bvid, str) or bvid in seen:
            continue
        seen.add(bvid)
        deduplicated.append(archive)

    normalized = {
        "schema_version": "1.0",
        "fetched_at": datetime.now(tz=UTC).isoformat(),
        "source": (
            f"https://space.bilibili.com/{args.mid}/lists/"
            f"{args.season_id}?type=season"
        ),
        "meta": {
            "mid": meta.get("mid"),
            "season_id": meta.get("season_id"),
            "title": meta.get("title"),
            "name": meta.get("name"),
            "description": meta.get("description"),
            "cover": meta.get("cover"),
            "reported_total": total,
        },
        "episodes": [
            normalize_archive(index, archive)
            for index, archive in enumerate(deduplicated, start=1)
        ],
        "integrity": {
            "unique_episode_count": len(deduplicated),
            "matches_reported_total": len(deduplicated) == total,
        },
        "metric_warning": (
            "View and danmaku counts are retrieval-time snapshots and must not be "
            "treated as proof of editing quality."
        ),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.out.resolve()),
                "title": normalized["meta"]["title"],
                "episodes": len(deduplicated),
                "matches_reported_total": normalized["integrity"]["matches_reported_total"],
            },
            ensure_ascii=False,
        )
    )
    if len(deduplicated) != total:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
