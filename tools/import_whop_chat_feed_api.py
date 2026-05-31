#!/usr/bin/env python3
"""Import Chrome GraphQL Whop chat-feed captures into parsed archive JSONL."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from whop_archive import (
    AUTHOR,
    CHANNELS,
    ET_TZ,
    LOCAL_TZ,
    PARSED_DIR,
    classify_market_session,
    load_existing_messages,
    signal_tags,
    stable_hash,
    write_jsonl,
)


UTC = ZoneInfo("UTC")


def normalize_channel_slug(experience_id: str) -> str:
    if not experience_id.startswith("exp_"):
        raise SystemExit(f"missing experience_id prefix: {experience_id}")
    base = experience_id.removeprefix("exp_")
    candidates = [base, f"-{base}", f"a-{base}", f"public-forum-{base}", f"discord-{base}"]
    for candidate in candidates:
        if candidate in CHANNELS:
            return candidate
    for key in CHANNELS:
        if key.endswith(base):
            return key
    raise SystemExit(f"unknown channel slug for experience_id={experience_id}: tried {candidates}")


def to_local_iso(created_at_ms: str) -> tuple[datetime, datetime]:
    utc_dt = datetime.fromtimestamp(int(created_at_ms) / 1000, tz=UTC)
    return utc_dt.astimezone(LOCAL_TZ), utc_dt.astimezone(ET_TZ)


def format_raw_time(local_dt: datetime) -> str:
    return local_dt.strftime("%b %d, %Y %I:%M:%S %p")


def build_existing_lookups(existing: dict[str, dict]) -> tuple[dict[tuple[str, str, str], str], dict[tuple[str, str], str]]:
    exact: dict[tuple[str, str, str], str] = {}
    image_only: dict[tuple[str, str], str] = {}
    for item_id, item in existing.items():
        exact_key = (
            item.get("channel_slug") or "",
            item.get("local_datetime") or "",
            item.get("content_hash") or "",
        )
        exact[exact_key] = item_id
        if item.get("has_image"):
            dt = item.get("local_datetime") or ""
            image_key = (item.get("channel_slug") or "", dt[:16])
            image_only.setdefault(image_key, item_id)
    return exact, image_only


def choose_message_id(
    channel_slug: str,
    local_dt: datetime,
    content_hash: str,
    content: str,
    attachments: list[dict],
    exact_lookup: dict[tuple[str, str, str], str],
    image_lookup: dict[tuple[str, str], str],
    post_id: str,
) -> str:
    exact_key = (channel_slug, local_dt.isoformat(), content_hash)
    if exact_key in exact_lookup:
        return exact_lookup[exact_key]
    if attachments and content == "[empty_or_image_only]":
        minute_key = (channel_slug, local_dt.isoformat()[:16])
        if minute_key in image_lookup:
            return image_lookup[minute_key]
    return stable_hash(channel_slug, format_raw_time(local_dt), content, length=20) + "_" + post_id[-6:]


def import_capture(path: Path, existing: dict[str, dict]) -> tuple[int, int]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    posts = payload.get("posts", [])
    if not posts:
        return 0, 0

    feed_id = payload.get("feed_id")
    experience_id = payload.get("experience_id")
    if not experience_id:
        raise SystemExit(f"missing experience_id in {path}")
    channel_slug = normalize_channel_slug(experience_id)

    capture_id = path.stem
    exact_lookup, image_lookup = build_existing_lookups(existing)
    imported = 0

    for post in posts:
        if post.get("__typename") != "DmsPost":
            continue
        if post.get("userId") != "user_4yeplXgbguTu4":
            continue

        local_dt, et_dt = to_local_iso(post["createdAt"])
        attachments = post.get("attachments") or []
        attachment_ids = [att.get("id") for att in attachments if att.get("id")]
        content = (post.get("content") or "").strip() or "[empty_or_image_only]"
        content_hash = stable_hash(content, length=24)
        message_id = choose_message_id(
            channel_slug,
            local_dt,
            content_hash,
            content,
            attachments,
            exact_lookup,
            image_lookup,
            post["id"],
        )
        market_session, calendar_tags, _ = classify_market_session(local_dt)
        record = {
            "id": message_id,
            "channel_slug": channel_slug,
            "channel_name": CHANNELS[channel_slug]["name"],
            "author": AUTHOR,
            "raw_time": format_raw_time(local_dt),
            "local_datetime": local_dt.isoformat(),
            "local_date": local_dt.date().isoformat(),
            "local_time": local_dt.strftime("%H:%M:%S"),
            "local_weekday": local_dt.strftime("%A"),
            "et_datetime": et_dt.isoformat(),
            "et_date": et_dt.date().isoformat(),
            "et_time": et_dt.strftime("%H:%M:%S"),
            "et_weekday": et_dt.strftime("%A"),
            "time_source": "exact",
            "date_precision": "minute",
            "market_session": market_session,
            "calendar_tags": calendar_tags,
            "content": content,
            "content_hash": content_hash,
            "has_image": bool(attachments),
            "image_placeholders": len(attachments),
            "attachment_ids": attachment_ids,
            "signal_tags": signal_tags(content),
            "read_count": post.get("viewCount"),
            "capture_id": capture_id,
            "source_post_id": post.get("id"),
            "source_feed_id": feed_id,
        }
        imported += 1
        existing[message_id] = record
        exact_lookup[(channel_slug, record["local_datetime"], record["content_hash"])] = message_id
        if record["has_image"]:
            image_lookup.setdefault((channel_slug, record["local_datetime"][:16]), message_id)

    return imported, len(posts)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+")
    args = parser.parse_args()

    messages_path = PARSED_DIR / "messages.jsonl"
    images_path = PARSED_DIR / "images_todo.jsonl"
    existing = load_existing_messages(messages_path)
    before = len(existing)
    totals = []

    for raw in args.inputs:
        path = Path(raw)
        imported, scanned = import_capture(path, existing)
        totals.append({"path": str(path), "scanned_posts": scanned, "imported_records": imported})

    ordered = sorted(
        existing.values(),
        key=lambda item: (
            item.get("local_datetime") or "",
            item.get("channel_slug") or "",
            item.get("id") or "",
        ),
    )
    write_jsonl(messages_path, ordered)
    write_jsonl(images_path, sorted((item for item in ordered if item.get("has_image")), key=lambda item: item["id"]))

    print(
        json.dumps(
            {
                "inputs": totals,
                "total_before": before,
                "total_after": len(existing),
                "net_new": len(existing) - before,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
