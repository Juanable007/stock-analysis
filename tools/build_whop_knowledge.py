#!/usr/bin/env python3
"""Build a private derived knowledge base from the Whop archive dataset."""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable


BASE_DIR = Path("data/whop_archive")
PARSED_DIR = BASE_DIR / "parsed"
KNOWLEDGE_DIR = BASE_DIR / "knowledge"
BOUNDARIES_PATH = BASE_DIR / "audit" / "channel_boundaries.json"
IMAGE_MANIFEST_PATH = BASE_DIR / "images" / "image_manifest.jsonl"

MESSAGES_PATH = PARSED_DIR / "messages.jsonl"
IMAGES_PATH = PARSED_DIR / "images_todo.jsonl"
CHANNELS_PATH = PARSED_DIR / "channels.json"
CANONICAL_MESSAGES_PATH = KNOWLEDGE_DIR / "messages_canonical.jsonl"

REFERENCE_DATE = "2026-05-31"
TARGET_START = "2026-02-01"
PRIMARY_SCOPE = {
    "100-50-B3kT9y4dyQGpgy": {
        "mode": "all",
        "label": "全量",
        "priority": 1,
    },
    "-GiWyN1ZTuUjwlG": {
        "mode": "from_date",
        "target_start": TARGET_START,
        "label": f"回溯到 {TARGET_START[:7]}",
        "priority": 2,
    },
    "-gZyq1MzOZAWO98": {
        "mode": "from_date",
        "target_start": TARGET_START,
        "label": f"回溯到 {TARGET_START[:7]}",
        "priority": 3,
    },
    "-JG1I58S5zTHbxs": {
        "mode": "from_date",
        "target_start": TARGET_START,
        "label": f"回溯到 {TARGET_START[:7]}",
        "priority": 4,
    },
    "-9vfxZgBNgXykNt": {
        "mode": "recent_days",
        "days": 31,
        "label": "近 1 个月",
        "priority": 5,
    },
}

NON_PRIMARY_VERIFIED_EMPTY = {
    "a-sNtx72qiyRNXem": {
        "state": "已核验当前无赵哥发言",
        "next_action": "已通过 chat feed API 全量核验，当前只有社区成员发言，没有 xiaozhaolucky 历史消息；后续仅需偶发复查。",
    },
    "discord-hugIsfN2FKmmyE": {
        "state": "已核验为外部入口",
        "next_action": "已确认该 experience 当前无 chat/forum/livestream feed，是 Discord 集成入口；无需按 Whop 消息频道继续抓取。",
    },
    "public-forum-3UF0FrckiKrvR3": {
        "state": "已核验当前空 forum",
        "next_action": "已通过 forum feed API 核验，当前返回 0 帖子；后续仅需偶发复查是否开始出现内容。",
    },
    "public-forum-JW27vkUfAY3dSh": {
        "state": "已核验当前空 forum",
        "next_action": "已通过 forum feed API 核验，当前返回 0 帖子；这是公司级 public forum 入口，后续仅需偶发复查。",
    },
    "public-forum-eWjjAKTB1V8P6C": {
        "state": "已核验当前空 forum",
        "next_action": "已通过 forum feed API 核验，当前返回 0 帖子；后续仅需偶发复查是否开始出现内容。",
    },
}

HOLIDAY_SOURCES = [
    {
        "name": "NYSE holiday calendar",
        "url": "https://www.nyse.com/markets/hours-calendars",
    },
    {
        "name": "Nasdaq trading hours and holiday calendar",
        "url": "https://www.nasdaq.com/market-activity/stock-market-holiday-schedule",
    },
]

MARKET_CALENDAR = {
    "2025": {
        "closed": [
            ("2025-01-01", "New Year's Day"),
            ("2025-01-20", "Martin Luther King, Jr. Day"),
            ("2025-02-17", "Washington's Birthday"),
            ("2025-04-18", "Good Friday"),
            ("2025-05-26", "Memorial Day"),
            ("2025-06-19", "Juneteenth"),
            ("2025-07-04", "Independence Day"),
            ("2025-09-01", "Labor Day"),
            ("2025-11-27", "Thanksgiving Day"),
            ("2025-12-25", "Christmas Day"),
        ],
        "early_close": [
            ("2025-07-03", "Day before Independence Day", "1:00 p.m. ET"),
            ("2025-11-28", "Day after Thanksgiving", "1:00 p.m. ET"),
            ("2025-12-24", "Christmas Eve", "1:00 p.m. ET"),
        ],
    },
    "2026": {
        "closed": [
            ("2026-01-01", "New Year's Day"),
            ("2026-01-19", "Martin Luther King, Jr. Day"),
            ("2026-02-16", "Washington's Birthday"),
            ("2026-04-03", "Good Friday"),
            ("2026-05-25", "Memorial Day"),
            ("2026-06-19", "Juneteenth"),
            ("2026-07-03", "Independence Day observed"),
            ("2026-09-07", "Labor Day"),
            ("2026-11-26", "Thanksgiving Day"),
            ("2026-12-25", "Christmas Day"),
        ],
        "early_close": [
            ("2026-11-27", "Day after Thanksgiving", "1:00 p.m. ET"),
            ("2026-12-24", "Christmas Eve", "1:00 p.m. ET"),
        ],
    },
}

TICKER_ALIASES = {
    "SPY": ["spy"],
    "BTC": ["btc", "bitcoin", "比特币"],
    "TSLL": ["tsll", "特斯拉双倍"],
    "TSLA": ["tsla", "特斯拉"],
    "NVDL": ["nvdl"],
    "NVDA": ["nvda", "英伟达", "nvidia"],
    "MSFT": ["msft", "微软"],
    "MSFL": ["msfl"],
    "AMD": ["amd"],
    "AMZN": ["amzn", "亚马逊"],
    "AMZU": ["amzu"],
    "IREN": ["iren"],
    "CIFR": ["cifr"],
    "BMNR": ["bmnr"],
    "CONL": ["conl"],
    "COIN": ["coin"],
    "HOOD": ["hood"],
    "SOFI": ["sofi"],
    "CRWV": ["crwv"],
    "LITE": ["lite"],
    "COHR": ["cohr"],
    "GLW": ["glw", "康宁", "corning"],
    "MU": ["mu", "美光"],
    "SOXL": ["soxl"],
    "INTC": ["intc"],
    "IBM": ["ibm"],
    "WQTM": ["wqtm"],
    "QUTS": ["quts"],
    "RGTI": ["rgti"],
}

THEORY_BUCKETS = {
    "position_sizing": {
        "title": "仓位分层与利润垫",
        "principle": "先用三分之一或一半常规仓建立试错仓，确认低点、急跌或回踩后再分批补；盈利后先卖一半锁定利润，再用回落买回降低成本。",
    },
    "stop_loss": {
        "title": "止损与失效条件",
        "principle": "每次开仓需要绑定明确止损位；跌破结构低点或计划内价位时不扩大亏损。",
    },
    "gap": {
        "title": "缺口与底部结构",
        "principle": "连续回补上轮起涨缺口、整数低点、次日低点高于前日低点，是判断恐慌后修复结构的重要线索。",
    },
    "intraday": {
        "title": "日内节奏与程序化时间窗",
        "principle": "反复关注 10:20/10:30、11:30、12:30、15:30 等时间窗，把急跌急涨当作程序流动性和大资金吸筹/派发的执行点观察。",
    },
    "fund_flow": {
        "title": "资金回流、外资减持与月末调仓",
        "principle": "港股/A股回流或外资减持会影响美股硬件链；月末养老金/基金再平衡可能造成尾盘和单边走势。",
    },
    "policy": {
        "title": "政策、节日与讲话事件驱动",
        "principle": "节假日、政府入股、法案投票、总统讲话和地缘政治消息会改变板块预期，尤其影响硬件、加密和高 beta 标的。",
    },
    "holiday_event": {
        "title": "节假日交易节奏",
        "principle": "节日前后流动性、讲话和消息披露会改变日内空间；靠近假期时更重视急跌机会、夜盘/盘后信息和节后回流。",
    },
    "hardware_ai": {
        "title": "AI 硬件链与英伟达投资链",
        "principle": "围绕英伟达、光通信、硬件 ETF 和访华名单识别资金关注方向；LITE、COHR、MU、IREN 等被归入硬件/算力扩散链。",
    },
    "crypto_related": {
        "title": "加密链与 BTC/COIN/CONL 传导",
        "principle": "BTC 整数位、政府资金、加密法案和 COIN/CONL 结构被用来判断加密链风险偏好。",
    },
    "quantum": {
        "title": "量子主题",
        "principle": "大盘用 IBM 观察，小盘关注 QUTS/RGTI，WQTM 作为量子 ETF 载体；政府投资预期是主题催化。",
    },
    "retail_flow": {
        "title": "散户情绪与反身性",
        "principle": "散户追高止损后容易成为大资金吸筹来源；过度恐慌、后视镜乐观、踏空焦虑都被视为错误情绪。",
    },
    "geopolitics": {
        "title": "地缘政治风险",
        "principle": "伊朗、霍尔木兹、战争/封锁等消息会改变日内风险偏好，适合先做第一波并降低隔夜暴露。",
    },
    "rebalancing": {
        "title": "再平衡与尾盘交换",
        "principle": "尾盘再平衡会在相关标的间形成相对强弱互换，适合结合目标价和尾盘资金流观察。",
    },
}


CONTENT_SANITIZE_OVERRIDES = {
    "da374909ee6e7fac3a2a": "7月3日那个节日的周一周二也是六月\n六月会有2次被动减和一个月末周五",
    "c7c6c789a7b412d74865": "可以用ai追踪下\n都是资讯里面会披露",
}


@dataclass
class MessageSummary:
    id: str
    channel: str
    local_datetime: str | None
    local_date: str | None
    local_weekday: str | None
    et_time: str | None
    market_session: str | None
    tags: list[str]
    tickers: list[str]
    summary: str


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def apply_content_sanitizers(messages: list[dict]) -> list[dict]:
    sanitized = []
    for item in messages:
        cloned = item.copy()
        override = CONTENT_SANITIZE_OVERRIDES.get(cloned.get("id"))
        if override is not None:
            cloned["content"] = override
            cloned["content_hash"] = normalized_content(override)[:24]
        sanitized.append(cloned)
    return sanitized


def load_image_manifest_by_message() -> dict[str, dict]:
    preferred_statuses = {"verified_from_image", "corrected_after_image_review"}
    mapping: dict[str, dict] = {}
    for record in load_jsonl(IMAGE_MANIFEST_PATH):
        message_id = record.get("message_id")
        if not message_id:
            continue
        current = mapping.get(message_id)
        if not current:
            mapping[message_id] = record
            continue
        if current.get("evidence_status") not in preferred_statuses and record.get("evidence_status") in preferred_statuses:
            mapping[message_id] = record
    return mapping


def load_boundaries() -> dict:
    if not BOUNDARIES_PATH.exists():
        return {}
    return json.loads(BOUNDARIES_PATH.read_text(encoding="utf-8"))


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def compact_content(content: str) -> str:
    lines = []
    for line in content.splitlines():
        line = line.strip()
        if not line or re.fullmatch(r"file_[A-Za-z0-9]+", line) or line == "image.png":
            continue
        lines.append(line)
    return " / ".join(lines)


def normalized_content(content: str) -> str:
    text = compact_content(content).lower()
    text = re.sub(r"\s+", "", text)
    text = text.replace("。", ".").replace("，", ",")
    return text


def summarize(content: str, limit: int = 150) -> str:
    text = compact_content(content)
    if not text:
        return "仅图片/附件，等待下载后 OCR 与视觉解析。"
    text = re.sub(r"\s+", " ", text)
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "..."


def extract_tickers(content: str) -> list[str]:
    lower = content.lower()
    tickers = []
    for ticker, aliases in TICKER_ALIASES.items():
        for alias in aliases:
            if re.search(rf"(?<![a-z0-9]){re.escape(alias.lower())}(?![a-z0-9])", lower):
                tickers.append(ticker)
                break
    return sorted(set(tickers))


def make_summaries(messages: Iterable[dict]) -> list[MessageSummary]:
    summaries = []
    for item in messages:
        tickers = extract_tickers(item.get("content", ""))
        summaries.append(
            MessageSummary(
                id=item["id"],
                channel=item["channel_name"],
                local_datetime=item.get("local_datetime"),
                local_date=item.get("local_date"),
                local_weekday=item.get("local_weekday"),
                et_time=item.get("et_time"),
                market_session=item.get("market_session"),
                tags=item.get("signal_tags", []),
                tickers=tickers,
                summary=summarize(item.get("content", "")),
            )
        )
    return summaries


def canonical_key(item: dict) -> tuple[str, str, str]:
    content = item.get("content", "")
    attachments = ",".join(sorted(item.get("attachment_ids", [])))
    summary_text = compact_content(content)
    image_only = not summary_text and (content.strip() in {"image.png", "[empty_or_image_only]"} or attachments)
    if image_only:
        return (item["channel_slug"], "image-only", item["id"])
    return (item["channel_slug"], item.get("content_hash") or "", attachments)


def precision_rank(item: dict) -> tuple[int, int, str]:
    source_rank = {
        "exact": 5,
        "relative_weekday": 4,
        "relative_day": 4,
        "zh_date_only": 3,
        "relative_age": 2,
        "unparsed": 0,
    }
    precision = item.get("date_precision")
    precision_bonus = {"minute": 2, "date": 1, "approximate": 0}.get(precision, 0)
    return (
        source_rank.get(item.get("time_source"), 0),
        precision_bonus,
        item.get("local_datetime") or "",
    )


def canonicalize_messages(messages: list[dict]) -> tuple[list[dict], list[dict]]:
    grouped: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for item in messages:
        grouped[canonical_key(item)].append(item)

    canonical = []
    duplicate_report = []
    for key, items in grouped.items():
        chosen = max(items, key=precision_rank).copy()
        duplicate_ids = sorted({item["id"] for item in items if item["id"] != chosen["id"]})
        if duplicate_ids:
            chosen["duplicate_ids"] = duplicate_ids
            chosen["duplicate_count"] = len(duplicate_ids)
            duplicate_report.append({
                "canonical_id": chosen["id"],
                "duplicate_ids": duplicate_ids,
                "channel_slug": chosen["channel_slug"],
                "content_hash": chosen.get("content_hash"),
                "summary": summarize(chosen.get("content", "")),
            })
        else:
            chosen["duplicate_ids"] = []
            chosen["duplicate_count"] = 0
        canonical.append(chosen)

    canonical.sort(key=lambda item: (item.get("local_datetime") or "", item.get("channel_slug") or "", item["id"]))
    duplicate_report.sort(key=lambda item: (item["channel_slug"], item["canonical_id"]))
    return canonical, duplicate_report


def md_table(headers: list[str], rows: Iterable[Iterable[str]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        clean = [str(cell).replace("\n", "<br>").replace("|", "\\|") for cell in row]
        out.append("| " + " | ".join(clean) + " |")
    return "\n".join(out)


def parse_day(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def format_day(value: date | None) -> str:
    return value.isoformat() if value else ""


def channel_scope(slug: str) -> dict | None:
    return PRIMARY_SCOPE.get(slug)


def date_gaps(items: list[dict], min_gap_days: int = 4) -> list[dict]:
    days = sorted({parse_day(m.get("local_date")) for m in items if parse_day(m.get("local_date"))})
    gaps = []
    for left, right in zip(days, days[1:]):
        gap_days = (right - left).days - 1
        if gap_days >= min_gap_days:
            gaps.append({
                "from": left.isoformat(),
                "to": right.isoformat(),
                "missing_days": gap_days,
            })
    return gaps


def build_channel_audit(channels: dict, messages: list[dict], boundaries: dict) -> list[dict]:
    target = parse_day(TARGET_START)
    reference = parse_day(REFERENCE_DATE)
    by_channel = defaultdict(list)
    for msg in messages:
        by_channel[msg["channel_slug"]].append(msg)

    audit = []
    for slug, meta in sorted(channels.items(), key=lambda item: item[1]["name"]):
        scope = channel_scope(slug)
        boundary = boundaries.get(slug, {})
        items = by_channel.get(slug, [])
        days = sorted({parse_day(m.get("local_date")) for m in items if parse_day(m.get("local_date"))})
        earliest = days[0] if days else None
        latest = days[-1] if days else None
        verified_start = parse_day(boundary.get("verified_channel_start"))
        if scope and scope["mode"] == "all":
            if not items:
                state = "未开始采集"
                next_action = "打开该频道并持续滚动，直到页面无更早 xiaozhaolucky 消息，同时补齐图片解析。"
            elif verified_start and earliest and earliest >= verified_start:
                state = "已验证当前频道全量起点"
                next_action = f"已记录真实起点证据：{boundary.get('evidence_summary', '页面滚动到顶仍无更早消息')}。后续重点转向知识沉淀与抽样复核。"
            else:
                state = "已开始全量采集"
                next_action = "继续向上/向下验证页面无更早 xiaozhaolucky 消息，并补齐图片 OCR。"
        elif scope and scope["mode"] == "recent_days":
            threshold = reference - timedelta(days=scope["days"] - 1) if reference else None
            if not items:
                state = "未开始采集"
                next_action = f"打开该频道，从最新消息开始复制/滚动，至少覆盖近 {scope['days']} 天。"
            elif threshold and earliest and earliest <= threshold:
                state = "已覆盖近 1 个月目标"
                next_action = "补齐图片 OCR，并抽样复核是否存在漏页或查看更多未展开的消息。"
            else:
                state = "已开始但未覆盖近 1 个月"
                threshold_text = threshold.isoformat() if threshold else TARGET_START
                next_action = f"从当前最早 {format_day(earliest)} 继续向历史滚动到 {threshold_text}。"
        elif scope and scope["mode"] == "from_date":
            scope_target = parse_day(scope["target_start"])
            if not items:
                state = "未开始采集"
                next_action = f"打开该频道，从最新消息开始复制/滚动，直到 {scope['target_start']} 或频道真实起点。"
            elif verified_start and scope_target and verified_start > scope_target and earliest and earliest >= verified_start:
                state = f"已验证真实起点晚于 {scope['target_start'][:7]}"
                next_action = f"已记录真实起点证据：{boundary.get('evidence_summary', '页面滚动到顶仍无更早消息')}。后续重点转向图片 OCR 与知识沉淀。"
            elif scope_target and earliest and earliest <= scope_target:
                state = f"已覆盖 {scope['target_start'][:7]} 目标"
                next_action = "继续抽样复核滚动断层，并补齐图片 OCR。"
            else:
                state = f"已开始但未覆盖 {scope['target_start'][:7]}"
                next_action = f"从当前最早 {format_day(earliest)} 继续向历史滚动到 {scope['target_start']} 或频道真实起点。"
        elif not items:
            verified_empty = NON_PRIMARY_VERIFIED_EMPTY.get(slug)
            if verified_empty:
                state = verified_empty["state"]
                next_action = verified_empty["next_action"]
            else:
                state = "未开始采集"
                next_action = "非本轮重点频道；如需补采，再从最新消息开始滚动。"
        else:
            state = "非本轮重点频道"
            next_action = "当前先保留已采样本，不纳入主缺口统计。"

        leading_gap = ""
        if scope and scope["mode"] == "from_date":
            scope_target = parse_day(scope["target_start"])
            if verified_start and scope_target and verified_start > scope_target and earliest and earliest >= verified_start:
                leading_gap = "已验证真实起点"
            elif scope_target and earliest and earliest > scope_target:
                leading_gap = f"{(earliest - scope_target).days} 天"
            elif scope_target and not earliest and reference:
                leading_gap = f"{(reference - scope_target).days + 1} 天"
        elif scope and scope["mode"] == "recent_days":
            threshold = reference - timedelta(days=scope["days"] - 1) if reference else None
            if threshold and earliest and earliest > threshold:
                leading_gap = f"{(earliest - threshold).days} 天"
            elif threshold and not earliest and reference:
                leading_gap = f"{(reference - threshold).days + 1} 天"
        elif target and earliest and earliest > target:
            leading_gap = f"{(earliest - target).days} 天"
        elif target and not earliest and reference:
            leading_gap = f"{(reference - target).days + 1} 天"

        audit.append({
            "slug": slug,
            "name": meta["name"],
            "purpose": meta.get("purpose", ""),
            "messages": len(items),
            "images": sum(int(m.get("image_placeholders") or 0) for m in items),
            "earliest": format_day(earliest),
            "latest": format_day(latest),
            "state": state,
            "target_gap": leading_gap,
            "scope_label": scope["label"] if scope else "非本轮重点",
            "is_primary_scope": bool(scope),
            "boundary_note": boundary.get("evidence_summary", ""),
            "large_gaps": date_gaps(items),
            "next_action": next_action,
            "url": meta.get("url", ""),
        })
    return audit


def build_status(raw_messages: list[dict], messages: list[dict], images: list[dict], duplicate_report: list[dict], boundaries: dict) -> dict:
    dates = sorted({m.get("local_date") for m in messages if m.get("local_date")})
    by_channel = defaultdict(list)
    for msg in messages:
        by_channel[msg["channel_slug"]].append(msg)
    primary_slugs = set(PRIMARY_SCOPE.keys())
    missing_channels = sorted(primary_slugs - set(by_channel.keys()))
    earliest_by_channel = {
        slug: min((m.get("local_date") for m in items if m.get("local_date")), default=None)
        for slug, items in by_channel.items()
        if slug in primary_slugs
    }
    reference = parse_day(REFERENCE_DATE)
    before_target = []
    for slug in sorted(primary_slugs & set(by_channel.keys())):
        scope = channel_scope(slug)
        earliest = earliest_by_channel.get(slug)
        boundary = boundaries.get(slug, {})
        verified_start = boundary.get("verified_channel_start")
        if not scope:
            continue
        if scope["mode"] == "from_date":
            if verified_start and verified_start > scope["target_start"] and earliest is not None and earliest >= verified_start:
                continue
            if earliest is None or earliest > scope["target_start"]:
                before_target.append(slug)
        elif scope["mode"] == "all":
            if verified_start and earliest is not None and earliest >= verified_start:
                continue
            before_target.append(slug)
        elif scope["mode"] == "recent_days":
            threshold = (reference - timedelta(days=scope["days"] - 1)).isoformat() if reference else None
            if earliest is None or (threshold and earliest > threshold):
                before_target.append(slug)
    warning_bits = []
    if missing_channels:
        warning_bits.append(f"主任务仍有 {len(missing_channels)} 个频道未采：{', '.join(missing_channels)}")
    if before_target:
        warning_bits.append(f"部分主任务频道尚未达到各自目标：{', '.join(before_target)}")
    coverage_warning = "采集仍未完成：" + "；".join(warning_bits) if warning_bits else "当前已满足这轮五个重点频道的覆盖目标，剩余工作主要是继续补全量、图片解析与知识沉淀。"
    status = {
        "reference_date": REFERENCE_DATE,
        "target_start": TARGET_START,
        "primary_scope": PRIMARY_SCOPE,
        "raw_parsed_records": len(raw_messages),
        "total_messages": len(messages),
        "merged_duplicate_records": sum(len(item["duplicate_ids"]) for item in duplicate_report),
        "image_or_attachment_messages": len(images),
        "all_image_placeholders": sum(int(m.get("image_placeholders") or 0) for m in messages),
        "earliest_any_message_date": min(dates) if dates else None,
        "latest_any_message_date": max(dates) if dates else None,
        "coverage_warning": coverage_warning,
        "channels": {},
    }
    for slug, items in by_channel.items():
        ds = sorted({m.get("local_date") for m in items if m.get("local_date")})
        status["channels"][slug] = {
            "channel_name": items[0]["channel_name"],
            "messages": len(items),
            "earliest": min(ds) if ds else None,
            "latest": max(ds) if ds else None,
            "images": sum(int(m.get("image_placeholders") or 0) for m in items),
        }
    return status


def write_status(status: dict) -> None:
    write_text(KNOWLEDGE_DIR / "crawl_status.md", "\n".join([
        "# 采集状态",
        "",
        f"- 参考日期: {status['reference_date']}",
        f"- 当前回溯下限: {status['target_start']}",
        f"- 原始解析记录: {status['raw_parsed_records']}",
        f"- 规范化消息: {status['total_messages']}",
        f"- 已合并重复记录: {status['merged_duplicate_records']}",
        f"- 图片/附件消息: {status['image_or_attachment_messages']}",
        f"- 图片/附件占位总数: {status['all_image_placeholders']}",
        f"- 最早消息日期: {status['earliest_any_message_date']}",
        f"- 最新消息日期: {status['latest_any_message_date']}",
        f"- 状态判断: {status['coverage_warning']}",
        "",
        md_table(
            ["频道", "消息数", "最早", "最新", "图片占位"],
            (
                [ch["channel_name"], ch["messages"], ch["earliest"], ch["latest"], ch["images"]]
                for ch in status["channels"].values()
            ),
        ),
    ]))
    (KNOWLEDGE_DIR / "status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")


def write_coverage_audit(channel_audit: list[dict]) -> None:
    overview_rows = []
    for item in channel_audit:
        gap_text = "; ".join(f"{gap['from']} -> {gap['to']} 缺 {gap['missing_days']} 天" for gap in item["large_gaps"][:6])
        overview_rows.append([
            item["name"],
            item["scope_label"],
            item["messages"],
            item["earliest"],
            item["latest"],
            item["images"],
            item["state"],
            item["target_gap"],
            gap_text,
        ])

    lines = [
        "# 覆盖完整性审计",
        "",
        "这份文件只判断采集完整性，不把没有发言的自然日直接当作缺漏；日期断档表示已采样本之间存在大跨度空白，需要回到 Whop 滚动验证。",
        "",
        md_table(
            ["频道", "范围目标", "消息数", "最早", "最新", "图片占位", "状态", "距目标缺口", "大日期断档"],
            overview_rows,
        ),
        "",
        "## 逐频道续采动作",
        "",
    ]
    for item in channel_audit:
        lines.append(f"### {item['name']}")
        lines.append("")
        lines.append(f"- slug: `{item['slug']}`")
        lines.append(f"- URL: {item['url']}")
        lines.append(f"- 职责: {item['purpose']}")
        lines.append(f"- 下一步: {item['next_action']}")
        if item["large_gaps"]:
            lines.append("- 需要复核的日期断档:")
            for gap in item["large_gaps"][:10]:
                lines.append(f"  - {gap['from']} 到 {gap['to']} 中间缺 {gap['missing_days']} 天")
        lines.append("")
    write_text(KNOWLEDGE_DIR / "coverage_audit.md", "\n".join(lines))


def write_next_capture_plan(channel_audit: list[dict]) -> None:
    priority_order = sorted(
        [item for item in channel_audit if item["is_primary_scope"]],
        key=lambda item: (
            PRIMARY_SCOPE[item["slug"]]["priority"],
            0 if item["messages"] == 0 else 1,
            item["earliest"] or "9999-99-99",
        ),
    )
    rows = []
    for index, item in enumerate(priority_order, start=1):
        rows.append([
            index,
            item["name"],
            item["slug"],
            item["scope_label"],
            item["messages"],
            item["earliest"] or "未采",
            item["state"],
            item["next_action"],
        ])
    body = "\n".join([
        "# 下一轮采集计划",
        "",
        "目标：按当前任务边界续采。`市值理论100跌50 公式记录` 尽量全量；`不用翻墙美股发布`、`不用翻墙期权`、`历史股票期权记录区` 回溯到 2026-02；`不用翻墙美股讨论区` 覆盖近 1 个月。",
        "",
        md_table(["优先级", "频道", "slug", "范围目标", "现有消息", "当前最早", "状态", "动作"], rows),
        "",
        "## 执行规则",
        "",
        "- 每次滚动后先展开 `查看更多`，再复制选中区域入库。",
        "- 复制入库后立刻运行 `python3 tools/whop_archive.py report` 和 `python3 tools/build_whop_knowledge.py`，检查最早日期是否推进。",
        "- 图片只拿到占位不算完成；必须后续下载/截图并做 OCR、视觉含义和交易含义沉淀。",
        "- 若某频道滚动到底仍没有更早历史，需要在采集日志记录“页面无更早消息/频道真实起点”。",
    ])
    write_text(KNOWLEDGE_DIR / "next_capture_plan.md", body)


def write_canonical_messages(messages: list[dict], duplicate_report: list[dict]) -> None:
    with CANONICAL_MESSAGES_PATH.open("w", encoding="utf-8") as handle:
        for item in messages:
            handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
    write_text(KNOWLEDGE_DIR / "duplicates_merged.md", "# 重复合并报告\n\n" + md_table(
        ["规范ID", "重复ID", "频道", "摘要"],
        (
            [item["canonical_id"], ", ".join(item["duplicate_ids"]), item["channel_slug"], item["summary"]]
            for item in duplicate_report
        ),
    ))


def write_crosspost_report(messages: list[dict]) -> None:
    grouped = defaultdict(list)
    for item in messages:
        key = normalized_content(item.get("content", ""))
        if len(key) < 8:
            continue
        grouped[key].append(item)

    rows = []
    for items in grouped.values():
        channels = sorted({item["channel_name"] for item in items})
        if len(items) < 2 or len(channels) < 2:
            continue
        chosen = max(items, key=precision_rank)
        rows.append([
            summarize(chosen.get("content", ""), limit=110),
            ", ".join(channels),
            ", ".join(sorted(item["id"] for item in items)),
            chosen.get("local_datetime") or chosen.get("local_date") or "",
        ])
    rows.sort(key=lambda row: row[3])
    write_text(KNOWLEDGE_DIR / "crosspost_report.md", "# 跨频道重复/同步内容\n\n" + md_table(
        ["内容摘要", "出现频道", "消息ID", "代表时间"],
        rows,
    ))


def write_channel_map(channels: dict, messages: list[dict]) -> None:
    counts = Counter(m["channel_slug"] for m in messages)
    rows = []
    for slug, meta in channels.items():
        rows.append([meta["name"], slug, counts[slug], meta.get("purpose", ""), meta.get("url", "")])
    write_text(KNOWLEDGE_DIR / "channel_map.md", "# 频道职责\n\n" + md_table(
        ["频道", "slug", "已采消息", "职责判断", "URL"],
        rows,
    ))


def write_timeline(messages: list[dict]) -> None:
    by_date = defaultdict(list)
    for msg in messages:
        by_date[msg.get("local_date") or "unknown"].append(msg)
    rows = []
    for day in sorted(by_date):
        items = by_date[day]
        weekday = next((m.get("local_weekday") for m in items if m.get("local_weekday")), "")
        sessions = Counter(m.get("market_session") or "unknown" for m in items)
        tags = Counter(t for m in items for t in m.get("signal_tags", []))
        calendar = sorted({tag for m in items for tag in m.get("calendar_tags", [])})
        rows.append([
            day,
            weekday,
            len(items),
            ", ".join(f"{k}:{v}" for k, v in sessions.most_common()),
            ", ".join(k for k, _ in tags.most_common(6)),
            ", ".join(calendar[:4]),
        ])
    write_text(KNOWLEDGE_DIR / "timeline.md", "# 日期时间索引\n\n" + md_table(
        ["日期", "星期", "消息数", "交易时段", "高频标签", "日历/节日标签"],
        rows,
    ))


def write_message_index(summaries: list[MessageSummary]) -> None:
    csv_path = KNOWLEDGE_DIR / "message_index.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "id",
            "channel",
            "local_datetime",
            "local_date",
            "weekday",
            "et_time",
            "market_session",
            "tags",
            "tickers",
            "summary",
        ])
        for s in summaries:
            writer.writerow([
                s.id,
                s.channel,
                s.local_datetime or "",
                s.local_date or "",
                s.local_weekday or "",
                s.et_time or "",
                s.market_session or "",
                ",".join(s.tags),
                ",".join(s.tickers),
                s.summary,
            ])

    rows = []
    for s in summaries[-60:]:
        rows.append([
            s.local_datetime or s.local_date or "",
            s.channel,
            ",".join(s.tickers),
            ",".join(s.tags),
            s.summary,
            s.id,
        ])
    write_text(KNOWLEDGE_DIR / "message_index.md", "# 消息索引\n\n完整表见 `message_index.csv`。\n\n" + md_table(
        ["时间", "频道", "标的", "标签", "摘要", "ID"],
        rows,
    ))


def write_ticker_index(messages: list[dict], summaries: list[MessageSummary]) -> None:
    by_ticker = defaultdict(list)
    summary_by_id = {s.id: s for s in summaries}
    for msg in messages:
        for ticker in extract_tickers(msg.get("content", "")):
            by_ticker[ticker].append(msg)
    lines = ["# 标的索引", ""]
    for ticker in sorted(by_ticker, key=lambda k: (-len(by_ticker[k]), k)):
        items = by_ticker[ticker]
        dates = sorted({m.get("local_date") for m in items if m.get("local_date")})
        tags = Counter(t for m in items for t in m.get("signal_tags", []))
        lines.append(f"## {ticker}")
        lines.append("")
        lines.append(f"- 消息数: {len(items)}")
        lines.append(f"- 日期范围: {dates[0] if dates else ''} 至 {dates[-1] if dates else ''}")
        lines.append(f"- 常见主题: {', '.join(k for k, _ in tags.most_common(6))}")
        lines.append("")
        rows = []
        for msg in items[-8:]:
            s = summary_by_id[msg["id"]]
            rows.append([msg.get("local_datetime") or msg.get("local_date") or "", ",".join(msg.get("signal_tags", [])), s.summary, msg["id"]])
        lines.append(md_table(["时间", "标签", "摘要", "ID"], rows))
        lines.append("")
    write_text(KNOWLEDGE_DIR / "ticker_index.md", "\n".join(lines))


def write_theory(messages: list[dict], summaries: list[MessageSummary]) -> None:
    by_id = {s.id: s for s in summaries}
    image_by_message = load_image_manifest_by_message()
    lines = ["# 金融知识与理论沉淀", ""]
    lines.append("> 当前为已采集样本的结构化沉淀；历史未采完前，任何理论都先标记为阶段性。")
    lines.append("")
    for tag, meta in THEORY_BUCKETS.items():
        items = [m for m in messages if tag in m.get("signal_tags", [])]
        if not items:
            continue
        dates = sorted({m.get("local_date") for m in items if m.get("local_date")})
        tickers = Counter(t for m in items for t in extract_tickers(m.get("content", "")))
        lines.append(f"## {meta['title']}")
        lines.append("")
        lines.append(f"**核心规则**: {meta['principle']}")
        lines.append("")
        lines.append(f"- 样本数: {len(items)}")
        lines.append(f"- 日期范围: {dates[0] if dates else ''} 至 {dates[-1] if dates else ''}")
        lines.append(f"- 相关标的: {', '.join(k for k, _ in tickers.most_common(10)) or '待进一步采集'}")
        lines.append("")
        rows = []
        for msg in items[-10:]:
            s = by_id[msg["id"]]
            rows.append([msg.get("local_datetime") or msg.get("local_date") or "", ",".join(s.tickers), s.summary, msg["id"]])
        lines.append(md_table(["时间", "标的", "证据摘要", "ID"], rows))
        lines.append("")
        reviewed_images = []
        for msg in items:
            image = image_by_message.get(msg["id"])
            if not image:
                continue
            if image.get("visual_review_status") != "reviewed":
                continue
            if image.get("evidence_status") not in {"verified_from_image", "corrected_after_image_review"}:
                continue
            meaning = image.get("inferred_meaning", "").strip()
            if not meaning:
                continue
            reviewed_images.append({
                "time": msg.get("local_datetime") or msg.get("local_date") or "",
                "asset_key": image.get("asset_key", ""),
                "meaning": meaning,
            })
        if reviewed_images:
            lines.append("**图证补充**")
            lines.append("")
            seen = set()
            count = 0
            for image in sorted(reviewed_images, key=lambda item: item["time"]):
                marker = (image["asset_key"], image["meaning"])
                if marker in seen:
                    continue
                seen.add(marker)
                lines.append(f"- `{image['time']}` `{image['asset_key']}`: {image['meaning']}")
                count += 1
                if count >= 5:
                    break
            lines.append("")
    write_text(KNOWLEDGE_DIR / "trading_theory.md", "\n".join(lines))


IMAGE_CONTEXT_OVERRIDES = {
    "3ab37d1f825eac24c29b": {
        "queue": "根据同屏上下文，这张图大概率是首个期权大肉案例的盈亏/价格截图，配合“第一个大肉”与 RIVN 出场点，用来展示彩票仓快速止盈的样本。",
        "meaning": "期权首个大肉案例图：与“第一个大肉”“1.5出三分之一rivn”同时间出现，图的意义是确认彩票仓在指数转弯前分批兑现的样本，而不是继续贪恋波动。",
    },
    "6def76747ba1ce7e0045": {
        "queue": "根据同屏上下文，这张图大概率是指数‘心电图/锯齿过密’的检测界面或分时图，用来解释为什么当天模型不容易给出清晰的期权检测信号。",
        "meaning": "锯齿过密、难以检测的分时图：配合“今天开盘指数心电图了”“锯齿太密集就不容易检测到”，图的核心是说明当日微结构噪音太多，期权短线模型应降低出手频率。",
    },
    "65d2b9ac6a21e05cad29": {
        "queue": "根据同屏上下文，这张图大概率是大盘分时/转弯结构图，用来配合“打仗吸的点就是看大盘指数，转弯直线就都吸”这条，强调战争消息冲击下的指数转折买点。",
        "meaning": "战争冲击下的大盘转弯吸筹图：与“打仗吸的点就是看大盘指数 转弯直线就都吸”同时间出现，图应是指数分时或指标截图，功能是把地缘冲击下的低吸动作锚定到指数转弯而不是主观猜底。",
    },
    "bff15a9581682d2a8b82": {
        "queue": "根据同屏上下文，这张图大概率是当天指数转弯点与期权开仓点重合的证据图，可能展示分时、期权信号或关键拐点标记。",
        "meaning": "期权信号与指数转弯重合证据图：与“今天的转弯点正好是期权的开仓点”同时间出现，重点不是个股，而是用图确认期权大单/信号可以提前标记指数拐点。",
    },
    "48bb2ad7f7a39212b3cf": {
        "queue": "根据同屏上下文，这张图大概率是当日指数或个股分时图，用来展示‘转弯点就是期权开仓点’这条方法在盘中的具体落点。",
        "meaning": "盘中拐点识别图：服务于“转弯点=期权开仓点”的方法论，把抽象信号落到具体价格路径上，用于帮助以后复用同类日内判断。",
    },
    "3e4bcd41337744d5a058": {
        "queue": "根据同屏上下文，这张图大概率是 IREN 或类似双底形态的走势截图，用来支撑‘昨天iren也是双底，今天+12%’这条复盘。",
        "meaning": "双底命中案例图：对应 IREN 的双底后上冲样本，图的意义在于说明前一日底部识别并非口头判断，而是有可回看的形态证据。",
    },
    "cda225867058fd552bde": {
        "queue": "根据同屏上下文，这张图大概率是日内急拉后转弯的减仓示意图，用来配合‘日内的减仓点也是看转弯’这条。",
        "meaning": "日内减仓转弯图：强调减仓不是按固定涨幅机械卖，而是观察冲高后的转弯结构，图应是对应这种卖点的分时证据。",
    },
    "782f3897326a53827715": {
        "queue": "根据同屏上下文，这张图大概率是盘中分时/振幅结构图，用来配合“多轮次高点转弯就减振幅大的仓位”这条，可能显示急拉后转弯的卖点。",
        "meaning": "高点转弯减仓证据图：与“要注意转弯，多的轮次，高点转弯就注意减手里振幅多的”同时间出现，图更像分时或指标截图，用来确认振幅过大的标的在转弯点先减仓。",
    },
    "45ee39115631634532ef": {
        "queue": "根据同屏上下文，这张图大概率是韩国顶级玩家/Leo KoGuan 再度大手笔加仓英伟达的新闻截图，用来证明“死拿英伟达”的大资金案例。",
        "meaning": "英伟达死拿案例证据图：文字明确指向韩国顶级玩家在夜盘继续加 100 万股英伟达，图更像新闻报道或帖子截图，功能是给 AI 硬件链和死拿仓位提供行为样本，而不是单纯价格图。",
    },
    "0bfbb0d6204e8c85785b": {
        "queue": "根据同屏上下文，这张图大概率是“港股/A股回流维持指数、硬件股承接”的证据截图，可能展示分时、板块强弱或回流对象。",
        "meaning": "资金轮动证据图：位于“港股A股回流维持指数”之后，更像是用图证明回流方向和硬件链承接，而不是独立交易喊单。",
    },
    "0b0148f8fd89d66b6521": {
        "queue": "根据同屏上下文，这张图大概率对应散户追高/止损后的回落吸筹结构，可能是 HOOD、SOXL、MU 等分时或筹码图。",
        "meaning": "散户情绪与吸筹结构图：夹在“散户就是养料”这条后面，重点应是证明回调后大资金吸单、急拉急跌的节奏，而非单纯价格截图。",
    },
    "0d20d545c1cc7845285b": {
        "queue": "根据同屏上下文，这张图大概率是 WQTM 或量子成分股/ETF 结构图，用来解释政府投资链和量子篮子的组成。",
        "meaning": "量子主题证据图：位于 WQTM 建仓之后，图大概率在展示量子 ETF 成分、权重或相关个股映射，服务于主题归类而不是纯日内价格判断。",
    },
    "bde4214cbc4f4e651f0f": {
        "queue": "根据同屏上下文，这张图大概率继续补充量子板块结构，可能是 IBM/QUTS/RGTI/WQTM 之间的大盘小盘分层图。",
        "meaning": "量子板块分层图：紧跟“量子股票的话 大盘股是 IBM，小盘股主要在 QUTS、RGTI”之后，更像分类图或成分截图。",
    },
    "60fd9c13df969fcbfeac": {
        "queue": "根据同屏上下文，这张图大概率对应月末养老金再平衡、尾盘单边减持或高位先减仓的证据截图。",
        "meaning": "月末再平衡证据图：夹在“今天月末养老金在平衡调仓幅度大”之后，图的功能更像证明尾盘被动调仓而不是发新逻辑。",
    },
    "2c1dbbfb5fdafdb5e818": {
        "queue": "根据同屏上下文，这张图大概率是特朗普/伊朗/霍尔木兹相关消息源截图，用来佐证周末地缘风险判断。",
        "meaning": "地缘政治消息截图：位于伊朗封锁条件长文之后，几乎可以确定是新闻源或社交媒体原文截图，用来支撑周末风险判断。",
    },
}


def image_override(record: dict | None) -> dict | None:
    if not record:
        return None
    return IMAGE_CONTEXT_OVERRIDES.get(record.get("id"))


def image_inference(content: str, record: dict | None = None) -> str:
    text = compact_content(content)
    override = image_override(record)
    placeholder_only = text in {"", "image.png"} or bool(re.fullmatch(r"(file_[A-Za-z0-9]+\s*/?\s*)+", text))
    if placeholder_only and override:
        return override["queue"]
    if placeholder_only:
        return "仅有图片占位；需要回到 Whop 下载/截图后 OCR 与视觉解析。"
    tags = []
    if "回调" in text or "-0.88" in text:
        tags.append("可能是指数/个股回调模型图，用于解释错误情绪与正确复盘方式。")
    if "慢跑式减持" in text:
        tags.append("可能是分时或指数截图，用于解释慢速减持时低点幅度重复。")
    if "底部" in text or "缺口" in text:
        tags.append("可能是底部结构示意图，重点在缺口回补、整数低点和次日低点抬高。")
    if "模型都可以套用" in text:
        tags.append("可能是可复用走势模型图，需要确认图中关键价位和路径。")
    if "10点" in text or "11:30" in text:
        tags.append("可能是盘中时间节奏图，验证每隔约一小时的程序化波动。")
    if not tags:
        tags.append("根据相邻文字推断该图用于支撑本条交易观点，真图解析待补。")
    return " ".join(tags)


def image_trade_meaning(content: str, record: dict | None = None) -> str:
    text = compact_content(content)
    override = image_override(record)
    placeholder_only = text in {"", "image.png"} or bool(re.fullmatch(r"(file_[A-Za-z0-9]+\s*/?\s*)+", text))
    if placeholder_only and override:
        return override["meaning"]
    if placeholder_only:
        return "暂无相邻文字，不能负责任地推断图意；必须下载真图后 OCR/视觉解析。"
    if "几种回调中错误情绪" in text or "过于恐慌" in text or "后视镜看盘" in text:
        return "回调情绪校准图：用低位恐慌、冲高后悔和死拿叙事对比，提醒交易时用时间、价格、成交和计划判断，不被盘中极端情绪带走。"
    if "慢跑式减持" in text or "-0.88" in text:
        return "慢速减持/程序化波动图：观察 10:30、11:30 等时间点反复出现相近跌幅，估计当日低点区域和减持节奏。"
    if "底部几大要素" in text or "缺口连续补掉" in text:
        return "底部结构图：缺口完全回补、整数位恐慌低点、次日低点抬高，构成从恐慌到修复的确认链。"
    if "模型都可以套用" in text:
        return "通用模型图：很可能展示一套可迁移的走势/情绪/回踩模板，需要确认图中关键价位、时间窗和适用标的。"
    if "港股A股" in text or "港A" in text or "回流本土" in text:
        return "资金轮动图：用于解释港股/A股高位休息与资金回流美股硬件链的周期性关系。"
    if "霍尔木兹" in text or "伊朗" in text or "封锁" in text:
        return "地缘政治消息截图：用于判断战争/航道风险对日内风险偏好和加密/高 beta 仓位的影响。"
    if "访华" in text or "Jensen" in text or "空军一号" in text:
        return "事件链图：通过商界访华名单和特朗普表态识别硬件、AI、加密等政策关注方向，服务于中线主题筛选。"
    if "养老金" in text or "平衡调仓" in text or "再平衡" in text:
        return "月末再平衡图：用于说明基金/养老金调仓造成的单边下跌、尾盘互换和加回窗口。"
    if "量子" in text or "wqtm" in text.lower() or "quts" in text.lower() or "rgti" in text.lower():
        return "量子主题图：可能是 ETF/成分股或政府投资链截图，用来区分大盘 IBM、小盘 QUTS/RGTI 和 WQTM 篮子。"
    if "10:30" in text or "10点" in text or "11:30" in text or "12:30" in text or "3:30" in text:
        return "盘中时间窗图：验证开盘回踩和每小时程序化急跌急涨，为日内买卖点提供节奏锚。"
    return "上下文显示该图是本条观点的证据截图；需下载真图确认价格、时间、标的、K线/分时形态和文字注释。"


def resolved_image_meaning(item: dict, manifest_by_message: dict[str, dict]) -> tuple[str, str, str | None]:
    record = manifest_by_message.get(item["id"])
    if record and record.get("evidence_status") in {"verified_from_image", "corrected_after_image_review"}:
        return (
            record.get("inferred_meaning") or image_trade_meaning(item.get("content", ""), item),
            record["evidence_status"],
            record.get("local_path"),
        )
    return image_trade_meaning(item.get("content", ""), item), "inferred_from_context", record.get("local_path") if record else None


def write_image_queue(images: list[dict], manifest_by_message: dict[str, dict]) -> None:
    rows = []
    for item in sorted(images, key=lambda m: (m.get("local_datetime") or "", m["id"])):
        attachments = ",".join(item.get("attachment_ids", [])) or "image.png"
        meaning, evidence_status, _ = resolved_image_meaning(item, manifest_by_message)
        rows.append([
            item.get("local_datetime") or item.get("local_date") or "",
            item["channel_name"],
            attachments,
            summarize(item.get("content", ""), limit=110),
            f"{meaning} [{evidence_status}]",
            item["id"],
        ])
    write_text(KNOWLEDGE_DIR / "image_queue.md", "# 图片/附件解析队列\n\n" + md_table(
        ["时间", "频道", "附件", "相邻文字", "当前含义沉淀", "消息ID"],
        rows,
    ))


def write_image_meanings(images: list[dict], manifest_by_message: dict[str, dict]) -> None:
    lines = [
        "# 图片含义沉淀",
        "",
        "以下按消息沉淀图片含义。若已拿到真图并人工确认，会标成 `verified_from_image`；否则仍是基于相邻文字的临时判断。",
        "",
    ]
    for item in sorted(images, key=lambda m: (m.get("local_datetime") or "", m["id"])):
        attachments = ", ".join(item.get("attachment_ids", [])) or "image.png"
        content = item.get("content", "")
        meaning, evidence_status, local_path = resolved_image_meaning(item, manifest_by_message)
        lines.append(f"## {item.get('local_datetime') or item.get('local_date') or 'unknown'} | {item['channel_name']}")
        lines.append("")
        lines.append(f"- 消息ID: `{item['id']}`")
        lines.append(f"- 附件/占位: `{attachments}`")
        lines.append(f"- 相邻文字摘要: {summarize(content, limit=220)}")
        lines.append(f"- 当前图意推断: {meaning}")
        lines.append(f"- 证据状态: `{evidence_status}`")
        if local_path:
            lines.append(f"- 本地原图: `{local_path}`")
        if evidence_status == "inferred_from_context":
            lines.append("- 真图校验项: OCR 文本、标的/价格、时间轴、K线或分时结构、箭头/框线/手写标注、与相邻发言是否一致。")
        lines.append("")
    write_text(KNOWLEDGE_DIR / "image_meanings.md", "\n".join(lines))


def write_image_protocol() -> None:
    text = """# 图片下载与解析协议

目标：每张 Whop 图片都必须有原图/截图、OCR 文本、视觉结构说明和金融含义，不能只保留 `image.png` 或 `file_...` 占位。

## 页面资产抓取

- 页面解锁后，先滚动到含图消息可见区域。
- 使用 Chrome `pageAssets` 能力列出当前渲染页已观察到的 image/video 资产。
- 对可见图片执行 bundle 下载；若资产能力拿不到原图，则点开图片大图并截图保存。
- 每次下载后把本地路径、附件 ID、消息 ID 写回图片解析记录。

## 本地命令

- 初始化逐图清单: `python3 tools/whop_image_pipeline.py init-manifest`
- 扫描已下载原图: `python3 tools/whop_image_pipeline.py scan-originals`
- 尝试 OCR: `python3 tools/whop_image_pipeline.py run-ocr`
- 生成验证状态: `python3 tools/whop_image_pipeline.py report`

当前环境未检测到 `tesseract`、PIL 或 pytesseract；因此 OCR 会在原图下载后标记为 `ocr_tool_missing`，直到安装 OCR 工具或改用人工/视觉模型解析。

## OCR/视觉解析

- OCR: 提取图中文字、价格、标的、日期、时间、百分比和箭头标注。
- 视觉: 描述图片类型，是分时图、K线图、新闻截图、订单/持仓截图、名单/表格，还是纯文字截图。
- 金融含义: 把图片转化成可复用规则，例如底部确认、回调情绪、节日流动性、月末再平衡、政策主题链。
- 证据状态: `inferred_from_context` 只能作为临时解释；看到真图后改为 `verified_from_image` 或 `corrected_after_image_review`。

## 命名约定

- 原图目录: `data/whop_archive/images/original/`
- OCR 目录: `data/whop_archive/images/ocr/`
- 视觉解析目录: `data/whop_archive/images/analysis/`
- 文件名优先使用 `{local_date}_{message_id}_{attachment_id}`，没有附件 ID 时使用 `{local_date}_{message_id}_imageNN`。
"""
    write_text(KNOWLEDGE_DIR / "image_analysis_protocol.md", text)


def write_market_calendar() -> None:
    lines = [
        "# 市场日历校验",
        "",
        "用途：把每条消息的日期、星期、节假日、提前收盘和美股交易时段放到统一基准里。2025/2026 日期依据 NYSE/ICE 与 Nasdaq 官方日历整理。",
        "",
        "## 来源",
        "",
    ]
    for source in HOLIDAY_SOURCES:
        lines.append(f"- [{source['name']}]({source['url']})")
    lines.append("")
    for year, data in MARKET_CALENDAR.items():
        lines.append(f"## {year} 休市日")
        lines.append("")
        lines.append(md_table(["日期", "事件"], data["closed"]))
        lines.append("")
        lines.append(f"## {year} 提前收盘")
        lines.append("")
        lines.append(md_table(["日期", "事件", "收盘时间"], data["early_close"]))
        lines.append("")
    lines.append("## 使用规则")
    lines.append("")
    lines.append("- 中国时间消息统一保留原始北京时间，同时换算美东时间用于判断盘前、盘中、盘后。")
    lines.append("- 遇到提前收盘日，美东 13:00 后的发言按 `after_early_close` 理解，而不是普通盘中。")
    lines.append("- 节日前后样本要单独标注，因为流动性、讲话、政策消息和月末/节后回流会改变策略含义。")
    write_text(KNOWLEDGE_DIR / "market_calendar.md", "\n".join(lines))


def write_readme(status: dict) -> None:
    source_lines = "\n".join(f"- [{s['name']}]({s['url']})" for s in HOLIDAY_SOURCES)
    readme = f"""# Whop xiaozhaolucky 私有知识库

本目录由本地原始采集数据生成，目标是把 Whop 各频道中 xiaozhaolucky 的历史发言沉淀为可检索的交易知识库。

## 当前状态

- 原始解析记录: {status['raw_parsed_records']}
- 规范化消息: {status['total_messages']}
- 已合并重复记录: {status['merged_duplicate_records']}
- 图片/附件消息: {status['image_or_attachment_messages']}
- 当前最早消息: {status['earliest_any_message_date']}
- 当前回溯下限: {status['target_start']}
- 结论: {status['coverage_warning']}

## 文件

- `crawl_status.md`: 当前覆盖范围、缺口和频道统计。
- `coverage_audit.md`: 逐频道覆盖完整性、范围目标缺口和大日期断档。
- `next_capture_plan.md`: 下一轮滚动采集顺序、断点和执行规则。
- `channel_map.md`: 所有已知群组/频道职责。
- `timeline.md`: 日期、星期、交易时段、节假日/临近节假日标签。
- `market_calendar.md`: 2025/2026 美股休市与提前收盘校验基准。
- `message_index.csv`: 全量结构化消息索引，含 ID、时间、频道、标签、标的、摘要。
- `messages_canonical.jsonl`: 合并滚动重复后的规范化消息集。
- `duplicates_merged.md`: 被合并的重复解析记录。
- `crosspost_report.md`: 同一内容在不同频道同步出现的映射。
- `message_index.md`: 最近样本的便读索引。
- `ticker_index.md`: 标的维度索引。
- `trading_theory.md`: 金融知识、理论基础和证据摘要。
- `dom_snapshot_evidence.md`: 通过已登录 Chrome 直接抓取的当前可见 DOM 证据快照，包含结构化可见消息与图片 URL 线索。
- `image_queue.md`: 图片/附件 OCR 与视觉解析队列，以及基于相邻文字的临时含义沉淀。
- `image_meanings.md`: 每张/每组图片的临时图意和金融含义沉淀。
- `image_analysis_protocol.md`: 后续下载原图、OCR、视觉解析和命名规范。
- `image_verification_status.md`: 由 `tools/whop_image_pipeline.py` 生成的逐图原图/OCR/视觉复核状态。
- `status.json`: 机器可读采集状态。

## 日历来源

以下官方/主流市场日历用于后续校验美股节假日和提前收盘：

{source_lines}

## 重要说明

原始消息全文保存在 `../raw_captures/` 与 `../parsed/messages.jsonl` 中。当前知识库文件以摘要、索引和理论沉淀为主；图片资产已经全部落地到本地原图目录，当前主工作是继续做逐图视觉释义、提取图上的交易规则/时间轴/价格位，并把这些证据折叠进理论章节。对于讨论群/讨论区，只把 xiaozhaolucky 本人的发言当主证据，其他成员发言最多保留为理解上下文的触发背景，不单独沉淀为理论结论。
"""
    write_text(KNOWLEDGE_DIR / "README.md", readme)


def main() -> None:
    raw_messages = load_jsonl(MESSAGES_PATH)
    raw_messages = apply_content_sanitizers(raw_messages)
    images = load_jsonl(IMAGES_PATH)
    channels = json.loads(CHANNELS_PATH.read_text(encoding="utf-8")) if CHANNELS_PATH.exists() else {}
    boundaries = load_boundaries()
    image_manifest = load_image_manifest_by_message()
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)

    messages, duplicate_report = canonicalize_messages(raw_messages)
    summaries = make_summaries(messages)
    status = build_status(raw_messages, messages, images, duplicate_report, boundaries)
    channel_audit = build_channel_audit(channels, messages, boundaries)
    write_canonical_messages(messages, duplicate_report)
    write_crosspost_report(messages)
    write_status(status)
    write_coverage_audit(channel_audit)
    write_next_capture_plan(channel_audit)
    write_channel_map(channels, messages)
    write_timeline(messages)
    write_message_index(summaries)
    write_ticker_index(messages, summaries)
    write_theory(messages, summaries)
    write_image_queue(images, image_manifest)
    write_image_meanings(images, image_manifest)
    write_image_protocol()
    write_market_calendar()
    write_readme(status)

    print(json.dumps({
        "knowledge_dir": str(KNOWLEDGE_DIR),
        "raw_messages": len(raw_messages),
        "canonical_messages": len(messages),
        "merged_duplicates": sum(len(item["duplicate_ids"]) for item in duplicate_report),
        "images": len(images),
        "files": sorted(path.name for path in KNOWLEDGE_DIR.iterdir()),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
