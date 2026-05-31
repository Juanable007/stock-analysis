#!/usr/bin/env python3
"""
Private Whop archive helper.

This script ingests text copied from the already-open Whop page, parses
xiaozhaolucky messages, standardizes time fields, and maintains an auditable
local dataset for a private research knowledge base.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo


AUTHOR = "xiaozhaolucky"
LOCAL_TZ = ZoneInfo("Asia/Shanghai")
ET_TZ = ZoneInfo("America/New_York")
BASE_DIR = Path("data/whop_archive")
RAW_DIR = BASE_DIR / "raw_captures"
PARSED_DIR = BASE_DIR / "parsed"
AUDIT_DIR = BASE_DIR / "audit"

CHANNELS = {
    "public-forum-eWjjAKTB1V8P6C": {
        "name": "Public forum",
        "url": "https://whop.com/joined/stock-and-option/public-forum-eWjjAKTB1V8P6C/app/",
        "purpose": "公开论坛之一，待采集后根据主题归类。",
    },
    "public-forum-3UF0FrckiKrvR3": {
        "name": "Public forum",
        "url": "https://whop.com/joined/stock-and-option/public-forum-3UF0FrckiKrvR3/app/",
        "purpose": "公开论坛之二，待采集后根据主题归类。",
    },
    "public-forum-JW27vkUfAY3dSh": {
        "name": "Public forum",
        "url": "https://whop.com/joined/stock-and-option/public-forum-JW27vkUfAY3dSh/app/",
        "purpose": "公司级公开论坛入口，当前需核实是否为空 forum 或公共占位区。",
    },
    "100-50-B3kT9y4dyQGpgy": {
        "name": "市值理论100跌50 公式记录",
        "url": "https://whop.com/joined/stock-and-option/100-50-B3kT9y4dyQGpgy/app/",
        "purpose": "记录市值理论、100跌50公式和框架型规则。",
    },
    "-YaUGmSLziDBKaw": {
        "name": "讨论区股票记录",
        "url": "https://whop.com/joined/stock-and-option/-YaUGmSLziDBKaw/app/",
        "purpose": "股票讨论和交易记录沉淀区。",
    },
    "-RCmV4WDjEOJcFF": {
        "name": "新闻",
        "url": "https://whop.com/joined/stock-and-option/-RCmV4WDjEOJcFF/app/",
        "purpose": "新闻、宏观事件、政策和消息面记录。",
    },
    "a-sNtx72qiyRNXem": {
        "name": "A股",
        "url": "https://whop.com/joined/stock-and-option/a-sNtx72qiyRNXem/app/",
        "purpose": "A股、港股与外资回流/流出相关讨论。",
    },
    "-GiWyN1ZTuUjwlG": {
        "name": "不用翻墙美股发布",
        "url": "https://whop.com/joined/stock-and-option/-GiWyN1ZTuUjwlG/app/",
        "purpose": "美股交易发布、仓位、止损、止盈、事件驱动提示。",
    },
    "-JG1I58S5zTHbxs": {
        "name": "历史股票期权记录区",
        "url": "https://whop.com/joined/stock-and-option/-JG1I58S5zTHbxs/app/",
        "purpose": "历史股票和期权案例复盘记录。",
    },
    "-gZyq1MzOZAWO98": {
        "name": "不用翻墙期权",
        "url": "https://whop.com/joined/stock-and-option/-gZyq1MzOZAWO98/app/",
        "purpose": "期权交易发布、结构、风控和执行记录。",
    },
    "-9vfxZgBNgXykNt": {
        "name": "不用翻墙美股讨论区",
        "url": "https://whop.com/joined/stock-and-option/-9vfxZgBNgXykNt/app/",
        "purpose": "美股讨论、问答、补充解释和盘中观点。",
    },
    "discord-hugIsfN2FKmmyE": {
        "name": "Discord",
        "url": "https://whop.com/joined/stock-and-option/discord-hugIsfN2FKmmyE/app/",
        "purpose": "Discord 入口或跨平台信息说明。",
    },
}

US_MARKET_HOLIDAYS = {
    date(2025, 1, 1): "New Year's Day",
    date(2025, 1, 20): "Martin Luther King Jr. Day",
    date(2025, 2, 17): "Washington's Birthday",
    date(2025, 4, 18): "Good Friday",
    date(2025, 5, 26): "Memorial Day",
    date(2025, 6, 19): "Juneteenth National Independence Day",
    date(2025, 7, 4): "Independence Day",
    date(2025, 9, 1): "Labor Day",
    date(2025, 11, 27): "Thanksgiving Day",
    date(2025, 12, 25): "Christmas Day",
    date(2026, 1, 1): "New Year's Day",
    date(2026, 1, 19): "Martin Luther King Jr. Day",
    date(2026, 2, 16): "Washington's Birthday",
    date(2026, 4, 3): "Good Friday",
    date(2026, 5, 25): "Memorial Day",
    date(2026, 6, 19): "Juneteenth National Independence Day",
    date(2026, 7, 3): "Independence Day observed",
    date(2026, 9, 7): "Labor Day",
    date(2026, 11, 26): "Thanksgiving Day",
    date(2026, 12, 25): "Christmas Day",
}

US_MARKET_EARLY_CLOSES = {
    date(2025, 7, 3): "Day before Independence Day",
    date(2025, 11, 28): "Day after Thanksgiving",
    date(2025, 12, 24): "Christmas Eve",
    date(2026, 11, 27): "Day after Thanksgiving",
    date(2026, 12, 24): "Christmas Eve",
}

NOISE_LINES = {
    "",
    "•",
    "❤️",
    "👍️",
    "😍️",
    "🤣️",
    "Only admins can send messages",
    "US$0.00",
    "加入",
    "查看更多",
    "资源",
    "首页",
    "支持聊天",
    "在 Whop 中搜索",
    "已钉帖子",
    "查看所有活动",
    "分享",
    "喜欢",
    "回复",
    "通知偏好",
    "全部",
    "获取全部通知",
    "提及",
    "收到提及时获取通知",
    "无",
    "不接收任何通知",
}


@dataclass
class ParsedMessage:
    id: str
    channel_slug: str
    channel_name: str
    author: str
    raw_time: str
    local_datetime: str | None
    local_date: str | None
    local_time: str | None
    local_weekday: str | None
    et_datetime: str | None
    et_date: str | None
    et_time: str | None
    et_weekday: str | None
    time_source: str
    date_precision: str
    market_session: str | None
    calendar_tags: list[str]
    content: str
    content_hash: str
    has_image: bool
    image_placeholders: int
    attachment_ids: list[str]
    signal_tags: list[str]
    read_count: int | None
    capture_id: str


def ensure_dirs() -> None:
    for path in (RAW_DIR, PARSED_DIR, AUDIT_DIR):
        path.mkdir(parents=True, exist_ok=True)


def read_clipboard() -> str:
    return subprocess.check_output(["pbpaste"]).decode("utf-8", errors="replace")


def stable_hash(*parts: str, length: int = 16) -> str:
    payload = "\n---\n".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:length]


def clean_line(line: str) -> str:
    return line.replace("\ufffc", "").strip()


def normalize_text(text: str) -> list[str]:
    feed_time = r"(\d{1,2}月\d{1,2}日|\d+\s*[mhdw])"
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").replace("\ufffc", "\n")
    normalized = re.sub(r"([A-Za-z0-9_]{3,})(@[A-Za-z0-9_]+)\s*·\s*" + feed_time, r"\1\n\2\n·\n\3\n", normalized)
    normalized = re.sub(r"(@[A-Za-z0-9_]+)\s*·\s*" + feed_time, r"\1\n·\n\2\n", normalized)
    normalized = normalized.replace(AUTHOR + AUTHOR, AUTHOR + "\n" + AUTHOR)
    return [clean_line(line) for line in normalized.split("\n")]


def parse_read_count(lines: list[str]) -> int | None:
    for line in reversed(lines):
        match = re.search(r"被\s*(\d+)\s*阅读", line)
        if match:
            return int(match.group(1))
    return None


def strip_message_noise(lines: list[str]) -> list[str]:
    cleaned: list[str] = []
    skip_next_numeric_reaction = False
    for line in lines:
        if not line:
            continue
        if re.fullmatch(r"被\s*\d+\s*阅读", line):
            continue
        if is_time_line(line):
            continue
        if line in {"❤️", "👍️", "😍️", "🤣️"}:
            skip_next_numeric_reaction = True
            continue
        if skip_next_numeric_reaction and re.fullmatch(r"\d+", line):
            skip_next_numeric_reaction = False
            continue
        skip_next_numeric_reaction = False
        if line in NOISE_LINES:
            continue
        if line.endswith(" | stock and option | Whop"):
            continue
        cleaned.append(line)
    return cleaned


def is_time_line(line: str) -> bool:
    if re.fullmatch(r"[A-Z][a-z]+ \d{1,2}, 20\d{2} \d{1,2}:\d{2} [AP]M", line):
        return True
    if re.fullmatch(r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday) \d{1,2}:\d{2} [AP]M", line):
        return True
    if re.fullmatch(r"(Yesterday|Today) at \d{1,2}:\d{2} [AP]M", line):
        return True
    return False


def is_zh_date_line(line: str) -> bool:
    return bool(re.fullmatch(r"\d{1,2}月\d{1,2}日", line))


def is_relative_age_line(line: str) -> bool:
    return bool(re.fullmatch(r"\d+\s*(m|h|d|w)", line, flags=re.IGNORECASE))


def is_feed_time_line(line: str) -> bool:
    return is_zh_date_line(line) or is_relative_age_line(line)


def previous_weekday(ref: date, weekday: int) -> date:
    delta = (ref.weekday() - weekday) % 7
    return ref - timedelta(days=delta)


def parse_ampm(value: str) -> time:
    return datetime.strptime(value, "%I:%M %p").time()


def parse_time(raw: str, reference_date: date, reference_now: datetime) -> tuple[datetime | None, str, str]:
    raw = raw.strip()
    exact = re.fullmatch(r"([A-Z][a-z]+ \d{1,2}, 20\d{2}) (\d{1,2}:\d{2} [AP]M)", raw)
    if exact:
        dt = None
        for fmt in ("%B %d, %Y %I:%M %p", "%b %d, %Y %I:%M %p"):
            try:
                dt = datetime.strptime(raw, fmt).replace(tzinfo=LOCAL_TZ)
                break
            except ValueError:
                continue
        if dt is None:
            raise ValueError(f"Unsupported exact timestamp: {raw}")
        return dt, "exact", "minute"

    rel_day = re.fullmatch(r"(Yesterday|Today) at (\d{1,2}:\d{2} [AP]M)", raw)
    if rel_day:
        day = reference_date if rel_day.group(1) == "Today" else reference_date - timedelta(days=1)
        return datetime.combine(day, parse_ampm(rel_day.group(2)), LOCAL_TZ), "relative_day", "minute"

    weekday_match = re.fullmatch(
        r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday) (\d{1,2}:\d{2} [AP]M)",
        raw,
    )
    if weekday_match:
        weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        day = previous_weekday(reference_date, weekday_names.index(weekday_match.group(1)))
        return datetime.combine(day, parse_ampm(weekday_match.group(2)), LOCAL_TZ), "relative_weekday", "minute"

    zh_date = re.fullmatch(r"(\d{1,2})月(\d{1,2})日", raw)
    if zh_date:
        month = int(zh_date.group(1))
        day = int(zh_date.group(2))
        candidate = date(reference_date.year, month, day)
        if candidate > reference_date + timedelta(days=1):
            candidate = date(reference_date.year - 1, month, day)
        return datetime.combine(candidate, time(12, 0), LOCAL_TZ), "zh_date_only", "date"

    age = re.fullmatch(r"(\d+)\s*(m|h|d|w)", raw, flags=re.IGNORECASE)
    if age:
        amount = int(age.group(1))
        unit = age.group(2).lower()
        delta_by_unit = {
            "m": timedelta(minutes=amount),
            "h": timedelta(hours=amount),
            "d": timedelta(days=amount),
            "w": timedelta(weeks=amount),
        }
        return reference_now - delta_by_unit[unit], "relative_age", "approximate"

    return None, "unparsed", "unknown"


def classify_market_session(local_dt: datetime | None) -> tuple[str | None, list[str], datetime | None]:
    if local_dt is None:
        return None, [], None
    et_dt = local_dt.astimezone(ET_TZ)
    tags: list[str] = []
    et_day = et_dt.date()
    et_t = et_dt.time()

    if local_dt.date().day >= 27:
        tags.append("month_end_window")
    if et_day in US_MARKET_HOLIDAYS:
        tags.append(f"us_market_holiday:{US_MARKET_HOLIDAYS[et_day]}")
    if et_day in US_MARKET_EARLY_CLOSES:
        tags.append(f"us_market_early_close:{US_MARKET_EARLY_CLOSES[et_day]}")
    for holiday, name in US_MARKET_HOLIDAYS.items():
        delta = (et_day - holiday).days
        if -2 <= delta <= 2 and delta != 0:
            tags.append(f"near_us_market_holiday:{name}:{delta:+d}d")

    if et_dt.weekday() >= 5:
        return "weekend_or_closed", tags + ["weekend"], et_dt
    if et_day in US_MARKET_HOLIDAYS:
        return "market_holiday", tags, et_dt
    if et_day in US_MARKET_EARLY_CLOSES and time(13, 0) <= et_t < time(20, 0):
        return "after_early_close", tags, et_dt
    if time(4, 0) <= et_t < time(9, 30):
        return "premarket", tags, et_dt
    if time(9, 30) <= et_t < time(16, 0):
        return "regular_hours", tags, et_dt
    if time(16, 0) <= et_t < time(20, 0):
        return "after_hours", tags, et_dt
    return "overnight", tags, et_dt


def signal_tags(content: str) -> list[str]:
    rules = {
        "entry": ["开了", "加了", "加回", "加仓", "买"],
        "exit": ["出", "止盈", "撤"],
        "stop_loss": ["止损"],
        "position_sizing": ["三分之一", "一半", "常规仓", "长线仓位"],
        "intraday": ["日内", "做个T", "大T", "第一波"],
        "gap": ["缺口"],
        "policy": ["政府", "政策", "入股", "讲话", "养老金"],
        "holiday_event": ["节日", "劳动节", "过节", "假期"],
        "fund_flow": ["回流", "减持", "外资", "资金"],
        "retail_flow": ["散户", "追高", "止损"],
        "geopolitics": ["伊朗", "特朗普", "霍尔木兹", "战争", "封锁"],
        "rebalancing": ["再平衡", "调仓", "月末"],
        "hardware_ai": ["硬件", "soxl", "mu", "nvdl", "lite", "英伟达"],
        "quantum": ["量子", "wqtm", "quts", "rgti", "ibm"],
        "crypto_related": ["coin", "conl"],
    }
    tags = []
    lower = content.lower()
    for tag, keywords in rules.items():
        if any(keyword.lower() in lower for keyword in keywords):
            tags.append(tag)
    return tags


def iter_message_blocks(lines: list[str]) -> Iterable[tuple[str, list[str]]]:
    i = 0
    while i < len(lines):
        if lines[i] != AUTHOR:
            i += 1
            continue
        j = i + 1
        while j < len(lines) and lines[j] in {"", "•"}:
            j += 1
        if j >= len(lines) or not is_time_line(lines[j]):
            i += 1
            continue
        raw_time = lines[j]
        j += 1
        body: list[str] = []
        while j < len(lines):
            if lines[j] == AUTHOR:
                break
            if lines[j] in {"Only admins can send messages"}:
                break
            body.append(lines[j])
            j += 1
        yield raw_time, body
        i = j


def is_feed_header_at(lines: list[str], index: int) -> bool:
    return (
        index + 3 < len(lines)
        and bool(lines[index])
        and lines[index + 1].startswith("@")
        and lines[index + 2] == "·"
        and is_feed_time_line(lines[index + 3])
    )


def iter_feed_blocks(lines: list[str]) -> Iterable[tuple[str, list[str]]]:
    i = 0
    while i < len(lines):
        if not is_feed_header_at(lines, i):
            i += 1
            continue
        author = lines[i]
        raw_time = lines[i + 3]
        j = i + 4
        body: list[str] = []
        while j < len(lines) and not is_feed_header_at(lines, j):
            body.append(lines[j])
            j += 1
        if author == AUTHOR:
            yield raw_time, body
        i = j


def attachment_ids(content: str) -> list[str]:
    return sorted(set(re.findall(r"\bfile_[A-Za-z0-9]+\b", content)))


def parse_messages(
    text: str,
    channel_slug: str,
    capture_id: str,
    reference_date: date,
    reference_now: datetime,
) -> list[ParsedMessage]:
    channel = CHANNELS[channel_slug]
    lines = normalize_text(text)
    compact_lines = [line for line in lines if line]
    blocks = list(iter_message_blocks(lines)) + list(iter_feed_blocks(compact_lines))
    messages: list[ParsedMessage] = []
    seen_ids: set[str] = set()
    for raw_time, body_lines in blocks:
        read_count = parse_read_count(body_lines)
        body = strip_message_noise(body_lines)
        content = "\n".join(body).strip()
        if not content:
            content = "[empty_or_image_only]"
        local_dt, time_source, date_precision = parse_time(raw_time, reference_date, reference_now)
        market_session, calendar_tags, et_dt = classify_market_session(local_dt)
        if date_precision == "date":
            market_session = "date_only"
        content_hash = stable_hash(content, length=24)
        message_id = stable_hash(channel_slug, raw_time, content, length=20)
        if message_id in seen_ids:
            continue
        seen_ids.add(message_id)
        attachments = attachment_ids(content)
        image_placeholder_count = content.count("image.png") + len(attachments)
        has_image = image_placeholder_count > 0
        local_date = local_dt.date().isoformat() if local_dt else None
        et_date = et_dt.date().isoformat() if et_dt else None
        messages.append(
            ParsedMessage(
                id=message_id,
                channel_slug=channel_slug,
                channel_name=channel["name"],
                author=AUTHOR,
                raw_time=raw_time,
                local_datetime=local_dt.isoformat() if local_dt else None,
                local_date=local_date,
                local_time=local_dt.strftime("%H:%M:%S") if local_dt and date_precision != "date" else None,
                local_weekday=local_dt.strftime("%A") if local_dt else None,
                et_datetime=et_dt.isoformat() if et_dt else None,
                et_date=et_date,
                et_time=et_dt.strftime("%H:%M:%S") if et_dt and date_precision != "date" else None,
                et_weekday=et_dt.strftime("%A") if et_dt else None,
                time_source=time_source,
                date_precision=date_precision,
                market_session=market_session,
                calendar_tags=calendar_tags,
                content=content,
                content_hash=content_hash,
                has_image=has_image,
                image_placeholders=image_placeholder_count,
                attachment_ids=attachments,
                signal_tags=signal_tags(content),
                read_count=read_count,
                capture_id=capture_id,
            )
        )
    return messages


def load_existing_messages(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    records: dict[str, dict] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            records[item["id"]] = item
    return records


def write_jsonl(path: Path, records: Iterable[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def append_jsonl(path: Path, record: dict) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def load_audit_entries() -> list[dict]:
    path = AUDIT_DIR / "capture_log.jsonl"
    if not path.exists():
        return []
    entries: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def ingest(args: argparse.Namespace) -> None:
    ensure_dirs()
    channel_slug = args.channel
    if channel_slug not in CHANNELS:
        raise SystemExit(f"unknown channel slug: {channel_slug}")
    reference_date = date.fromisoformat(args.reference_date)
    text = Path(args.from_file).read_text(encoding="utf-8") if args.from_file else read_clipboard()
    now = datetime.now(LOCAL_TZ)
    capture_id = f"{now.strftime('%Y%m%d_%H%M%S')}_{channel_slug}_{stable_hash(text, length=8)}"

    raw_path = RAW_DIR / f"{capture_id}.txt"
    raw_path.write_text(text, encoding="utf-8")

    parsed = parse_messages(text, channel_slug, capture_id, reference_date, now)
    parsed_path = PARSED_DIR / "messages.jsonl"
    existing = load_existing_messages(parsed_path)
    before_count = len(existing)
    for message in parsed:
        existing[message.id] = asdict(message)
    ordered = sorted(
        existing.values(),
        key=lambda item: (
            item.get("local_datetime") or "",
            item.get("channel_slug") or "",
            item.get("id") or "",
        ),
    )
    write_jsonl(parsed_path, ordered)

    image_todos = [asdict(message) for message in parsed if message.has_image]
    if image_todos:
        image_path = PARSED_DIR / "images_todo.jsonl"
        existing_images = load_existing_messages(image_path)
        for item in image_todos:
            existing_images[item["id"]] = item
        write_jsonl(image_path, sorted(existing_images.values(), key=lambda item: item["id"]))

    audit = {
        "capture_id": capture_id,
        "captured_at": now.isoformat(),
        "channel_slug": channel_slug,
        "channel_name": CHANNELS[channel_slug]["name"],
        "raw_path": str(raw_path),
        "clipboard_chars": len(text),
        "parsed_messages_in_capture": len(parsed),
        "new_or_updated_messages": len(existing) - before_count,
        "total_unique_messages": len(existing),
        "image_placeholder_messages_in_capture": sum(1 for message in parsed if message.has_image),
        "earliest_local_datetime_in_capture": min(
            (message.local_datetime for message in parsed if message.local_datetime),
            default=None,
        ),
        "latest_local_datetime_in_capture": max(
            (message.local_datetime for message in parsed if message.local_datetime),
            default=None,
        ),
    }
    append_jsonl(AUDIT_DIR / "capture_log.jsonl", audit)
    print(json.dumps(audit, ensure_ascii=False, indent=2))


def rebuild(args: argparse.Namespace) -> None:
    ensure_dirs()
    reference_date = date.fromisoformat(args.reference_date)
    records: dict[str, dict] = {}
    image_records: dict[str, dict] = {}
    captures = 0
    for entry in load_audit_entries():
        channel_slug = entry.get("channel_slug")
        raw_path = Path(entry.get("raw_path", ""))
        capture_id = entry.get("capture_id") or raw_path.stem
        captured_at = datetime.fromisoformat(entry["captured_at"])
        if channel_slug not in CHANNELS or not raw_path.exists():
            continue
        text = raw_path.read_text(encoding="utf-8")
        parsed = parse_messages(text, channel_slug, capture_id, reference_date, captured_at)
        captures += 1
        for message in parsed:
            item = asdict(message)
            records[message.id] = item
            if message.has_image:
                image_records[message.id] = item
    ordered = sorted(
        records.values(),
        key=lambda item: (
            item.get("local_datetime") or "",
            item.get("channel_slug") or "",
            item.get("id") or "",
        ),
    )
    write_jsonl(PARSED_DIR / "messages.jsonl", ordered)
    write_jsonl(PARSED_DIR / "images_todo.jsonl", sorted(image_records.values(), key=lambda item: item["id"]))
    print(
        json.dumps(
            {
                "rebuilt_captures": captures,
                "total_unique_messages": len(records),
                "image_placeholder_messages": len(image_records),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def write_channels(_: argparse.Namespace) -> None:
    ensure_dirs()
    path = PARSED_DIR / "channels.json"
    path.write_text(json.dumps(CHANNELS, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(path)


def report(_: argparse.Namespace) -> None:
    ensure_dirs()
    records = list(load_existing_messages(PARSED_DIR / "messages.jsonl").values())
    by_channel: dict[str, dict] = {}
    for item in records:
        bucket = by_channel.setdefault(
            item["channel_slug"],
            {
                "channel_name": item["channel_name"],
                "messages": 0,
                "images": 0,
                "earliest": None,
                "latest": None,
                "sessions": {},
                "signal_tags": {},
            },
        )
        bucket["messages"] += 1
        bucket["images"] += item["image_placeholders"]
        dt = item.get("local_datetime")
        if dt:
            bucket["earliest"] = dt if bucket["earliest"] is None else min(bucket["earliest"], dt)
            bucket["latest"] = dt if bucket["latest"] is None else max(bucket["latest"], dt)
        session = item.get("market_session") or "unknown"
        bucket["sessions"][session] = bucket["sessions"].get(session, 0) + 1
        for tag in item.get("signal_tags", []):
            bucket["signal_tags"][tag] = bucket["signal_tags"].get(tag, 0) + 1
    print(json.dumps(by_channel, ensure_ascii=False, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(required=True)

    ingest_parser = sub.add_parser("ingest-clipboard")
    ingest_parser.add_argument("--channel", required=True)
    ingest_parser.add_argument("--from-file")
    ingest_parser.add_argument("--reference-date", default="2026-05-31")
    ingest_parser.set_defaults(func=ingest)

    rebuild_parser = sub.add_parser("rebuild")
    rebuild_parser.add_argument("--reference-date", default="2026-05-31")
    rebuild_parser.set_defaults(func=rebuild)

    channels_parser = sub.add_parser("write-channels")
    channels_parser.set_defaults(func=write_channels)

    report_parser = sub.add_parser("report")
    report_parser.set_defaults(func=report)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
