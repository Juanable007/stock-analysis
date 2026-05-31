#!/usr/bin/env python3
"""Track, attach, and OCR Whop image assets for the private archive."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable


BASE_DIR = Path("data/whop_archive")
PARSED_DIR = BASE_DIR / "parsed"
IMAGES_DIR = BASE_DIR / "images"
ORIGINAL_DIR = IMAGES_DIR / "original"
OCR_DIR = IMAGES_DIR / "ocr"
ANALYSIS_DIR = IMAGES_DIR / "analysis"
KNOWLEDGE_DIR = BASE_DIR / "knowledge"
RAW_CAPTURE_DIR = BASE_DIR / "raw_captures"

IMAGES_TODO_PATH = PARSED_DIR / "images_todo.jsonl"
MESSAGES_PATH = PARSED_DIR / "messages.jsonl"
MANIFEST_PATH = IMAGES_DIR / "image_manifest.jsonl"
VERIFICATION_PATH = KNOWLEDGE_DIR / "image_verification_status.md"


@dataclass
class ImageAsset:
    asset_key: str
    message_id: str
    channel_slug: str
    channel_name: str
    local_datetime: str | None
    local_date: str | None
    local_weekday: str | None
    et_datetime: str | None
    market_session: str | None
    attachment_id: str | None
    placeholder_index: int
    context_summary: str
    inferred_meaning: str
    required_checks: list[str]
    local_path: str | None = None
    remote_url: str | None = None
    source_snapshot: str | None = None
    downloaded_status: str = "pending_download"
    ocr_status: str = "pending_image"
    ocr_text_path: str | None = None
    visual_review_status: str = "pending_image"
    evidence_status: str = "inferred_from_context"
    notes: str = ""


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


def write_jsonl(path: Path, records: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


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


def summarize(content: str, limit: int = 220) -> str:
    text = compact_content(content)
    if not text:
        return "仅图片/附件，等待下载后 OCR 与视觉解析。"
    text = re.sub(r"\s+", " ", text)
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "..."


def infer_trade_meaning(content: str) -> str:
    text = compact_content(content)
    if not text:
        return "暂无相邻文字，必须下载真图后 OCR/视觉解析。"
    if "几种回调中错误情绪" in text or "过于恐慌" in text or "后视镜看盘" in text:
        return "回调情绪校准：把低位恐慌、冲高后悔、踏空和死拿叙事转成交易计划复盘。"
    if "慢跑式减持" in text or "-0.88" in text:
        return "慢速减持/程序化波动：用重复跌幅和固定时间窗估算当日低点区域。"
    if "底部几大要素" in text or "缺口连续补掉" in text:
        return "底部结构：缺口回补、整数位恐慌低点、次日低点抬高。"
    if "模型都可以套用" in text:
        return "通用走势模型：需要确认图中价位、时间窗和可迁移条件。"
    if "港股A股" in text or "港A" in text or "回流本土" in text:
        return "资金轮动：解释港股/A股休息与美股硬件链回流。"
    if "霍尔木兹" in text or "伊朗" in text or "封锁" in text:
        return "地缘政治消息：评估战争/航道风险对日内风险偏好和高 beta 仓位的影响。"
    if "访华" in text or "Jensen" in text or "空军一号" in text:
        return "政策/名单事件链：用商界访华名单识别 AI 硬件、加密和高 beta 主题。"
    if "养老金" in text or "平衡调仓" in text or "再平衡" in text:
        return "月末再平衡：跟踪基金/养老金调仓导致的单边走势和尾盘加回窗口。"
    if "量子" in text or re.search(r"\b(wqtm|quts|rgti|ibm)\b", text, re.I):
        return "量子主题：区分 IBM、大盘/小盘量子标的和 WQTM 篮子。"
    if "10:30" in text or "10点" in text or "11:30" in text or "12:30" in text or "3:30" in text:
        return "盘中时间窗：验证开盘回踩和每小时程序化急跌急涨。"
    return "上下文显示该图是观点证据；需确认标的、价格、时间轴和图上标注。"


def asset_keys_for_message(item: dict) -> list[tuple[str, str | None, int]]:
    attachments = item.get("attachment_ids") or []
    if attachments:
        return [(attachment_id, attachment_id, index) for index, attachment_id in enumerate(attachments, start=1)]
    count = max(1, int(item.get("image_placeholders") or 1))
    return [(f"{item['id']}_image{index:02d}", None, index) for index in range(1, count + 1)]


def build_manifest_records(todo_records: list[dict], existing: dict[str, dict]) -> list[ImageAsset]:
    assets = []
    checks = ["OCR 文本", "标的/价格", "日期/时间轴", "K线或分时结构", "箭头/框线/手写标注", "与相邻发言一致性"]
    for item in todo_records:
        for asset_key, attachment_id, placeholder_index in asset_keys_for_message(item):
            old = existing.get(asset_key, {})
            assets.append(
                ImageAsset(
                    asset_key=asset_key,
                    message_id=item["id"],
                    channel_slug=item["channel_slug"],
                    channel_name=item["channel_name"],
                    local_datetime=item.get("local_datetime"),
                    local_date=item.get("local_date"),
                    local_weekday=item.get("local_weekday"),
                    et_datetime=item.get("et_datetime"),
                    market_session=item.get("market_session"),
                    attachment_id=attachment_id,
                    placeholder_index=placeholder_index,
                    context_summary=summarize(item.get("content", "")),
                    inferred_meaning=infer_trade_meaning(item.get("content", "")),
                    required_checks=checks,
                    local_path=old.get("local_path"),
                    remote_url=old.get("remote_url"),
                    source_snapshot=old.get("source_snapshot"),
                    downloaded_status=old.get("downloaded_status", "pending_download"),
                    ocr_status=old.get("ocr_status", "pending_image"),
                    ocr_text_path=old.get("ocr_text_path"),
                    visual_review_status=old.get("visual_review_status", "pending_image"),
                    evidence_status=old.get("evidence_status", "inferred_from_context"),
                    notes=old.get("notes", ""),
                )
            )
    assets.sort(key=lambda asset: (asset.local_datetime or "", asset.message_id, asset.placeholder_index, asset.asset_key))
    return assets


def load_existing_manifest() -> dict[str, dict]:
    return {record["asset_key"]: record for record in load_jsonl(MANIFEST_PATH)}


def init_manifest(_: argparse.Namespace) -> None:
    for path in [ORIGINAL_DIR, OCR_DIR, ANALYSIS_DIR, KNOWLEDGE_DIR]:
        path.mkdir(parents=True, exist_ok=True)
    assets = build_manifest_records(load_jsonl(IMAGES_TODO_PATH), load_existing_manifest())
    write_jsonl(MANIFEST_PATH, [asdict(asset) for asset in assets])
    write_report(assets)
    print(json.dumps({"manifest": str(MANIFEST_PATH), "assets": len(assets)}, ensure_ascii=False, indent=2))


def match_original_file(asset: dict, candidates: list[Path]) -> str | None:
    tokens = [asset["asset_key"], asset["message_id"]]
    if asset.get("attachment_id"):
        tokens.append(asset["attachment_id"])
    lowered = [(path, path.name.lower()) for path in candidates]
    for token in tokens:
        token_lower = token.lower()
        for path, name in lowered:
            if token_lower in name:
                return str(path)
    return None


def scan_originals(_: argparse.Namespace) -> None:
    ORIGINAL_DIR.mkdir(parents=True, exist_ok=True)
    image_exts = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
    candidates = [path for path in ORIGINAL_DIR.rglob("*") if path.is_file() and path.suffix.lower() in image_exts]
    records = load_jsonl(MANIFEST_PATH)
    for record in records:
        if record.get("local_path") and Path(record["local_path"]).exists():
            record["downloaded_status"] = "downloaded"
            continue
        match = match_original_file(record, candidates)
        if match:
            record["local_path"] = match
            record["downloaded_status"] = "downloaded"
            if record.get("ocr_status") == "pending_image":
                record["ocr_status"] = "pending_ocr"
            if record.get("visual_review_status") == "pending_image":
                record["visual_review_status"] = "pending_review"
    write_jsonl(MANIFEST_PATH, records)
    write_report([ImageAsset(**record) for record in records])
    print(json.dumps({"candidates": len(candidates), "matched": sum(1 for r in records if r.get("local_path"))}, ensure_ascii=False, indent=2))


def normalized_remote_url(url: str) -> str:
    if not url:
        return url
    parsed = urllib.parse.urlparse(url)
    if "/plain/" not in parsed.path:
        return url
    encoded = parsed.path.split("/plain/", 1)[1]
    encoded = encoded.split("@", 1)[0]
    candidate = urllib.parse.unquote(encoded)
    return candidate if candidate.startswith("http") else url


def infer_file_suffix(remote_url: str, attachment_filename: str | None = None, content_type: str | None = None) -> str:
    if attachment_filename:
        suffix = Path(attachment_filename).suffix
        if suffix:
            return suffix
    cleaned = normalized_remote_url(remote_url or "")
    parsed = urllib.parse.urlparse(cleaned)
    path = urllib.parse.unquote(parsed.path or "")
    if "%3F" in path:
        path = path.split("%3F", 1)[0]
    if "?" in path:
        path = path.split("?", 1)[0]
    suffix = Path(path).suffix
    if suffix:
        return suffix
    if content_type:
        mapping = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg",
            "image/webp": ".webp",
            "image/gif": ".gif",
        }
        if content_type.lower() in mapping:
            return mapping[content_type.lower()]
    return ".img"


def slugify_stem(text: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", text.strip())
    return cleaned.strip("._") or "asset"


def download_to_path(url: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=30) as response, path.open("wb") as handle:
        shutil.copyfileobj(response, handle)


def image_message_occurrence_index() -> dict[tuple[str, str, int], dict]:
    index: dict[tuple[str, str, int], dict] = {}
    per_key: dict[tuple[str, str], int] = {}
    for message in load_jsonl(MESSAGES_PATH):
        if not message.get("has_image"):
            continue
        key = (message["channel_slug"], message.get("raw_time") or "")
        per_key[key] = per_key.get(key, 0) + 1
        index[(message["channel_slug"], message.get("raw_time") or "", per_key[key])] = message
    return index


def message_occurrence_index(include_all_messages: bool = False) -> dict[tuple[str, str, int], dict]:
    index: dict[tuple[str, str, int], dict] = {}
    per_key: dict[tuple[str, str], int] = {}
    for message in load_jsonl(MESSAGES_PATH):
        if not include_all_messages and not message.get("has_image"):
            continue
        key = (message["channel_slug"], message.get("raw_time") or "")
        per_key[key] = per_key.get(key, 0) + 1
        index[(message["channel_slug"], message.get("raw_time") or "", per_key[key])] = message
    return index


def build_dom_asset_record(message: dict, existing: dict | None, placeholder_index: int = 1) -> dict:
    checks = ["OCR 文本", "标的/价格", "日期/时间轴", "K线或分时结构", "箭头/框线/手写标注", "与相邻发言一致性"]
    asset_key = f"{message['id']}_domimage{placeholder_index:02d}"
    return {
        "asset_key": asset_key,
        "message_id": message["id"],
        "channel_slug": message["channel_slug"],
        "channel_name": message["channel_name"],
        "local_datetime": message.get("local_datetime"),
        "local_date": message.get("local_date"),
        "local_weekday": message.get("local_weekday"),
        "et_datetime": message.get("et_datetime"),
        "market_session": message.get("market_session"),
        "attachment_id": None,
        "placeholder_index": placeholder_index,
        "context_summary": summarize(message.get("content", "")),
        "inferred_meaning": infer_trade_meaning(message.get("content", "")),
        "required_checks": checks,
        "local_path": existing.get("local_path") if existing else None,
        "remote_url": existing.get("remote_url") if existing else None,
        "source_snapshot": existing.get("source_snapshot") if existing else None,
        "downloaded_status": existing.get("downloaded_status", "pending_download") if existing else "pending_download",
        "ocr_status": existing.get("ocr_status", "pending_image") if existing else "pending_image",
        "ocr_text_path": existing.get("ocr_text_path") if existing else None,
        "visual_review_status": existing.get("visual_review_status", "pending_image") if existing else "pending_image",
        "evidence_status": existing.get("evidence_status", "inferred_from_context") if existing else "inferred_from_context",
        "notes": existing.get("notes", "") if existing else "",
    }


def looks_like_content_image(image: dict) -> bool:
    src = image.get("src") or ""
    alt = (image.get("alt") or "").strip().lower()
    rect_w = int(image.get("rectWidth") or 0)
    rect_h = int(image.get("rectHeight") or 0)
    natural_w = int(image.get("naturalWidth") or 0)
    natural_h = int(image.get("naturalHeight") or 0)
    if not src.startswith("http"):
        return False
    if alt in {"个人资料图片", "stock and option", "美股工具箱", "whop ai", "京津冀"}:
        return False
    if rect_w >= 120 or rect_h >= 120:
        return True
    if natural_w >= 200 or natural_h >= 200:
        return True
    return "assets-2-prod.whop.com" in src and ("uploads" in src)


def pick_message_image_urls(message: dict) -> list[str]:
    urls = []
    seen: set[str] = set()
    for image in message.get("images", []):
        if not looks_like_content_image(image):
            continue
        url = normalized_remote_url(image.get("src") or "")
        if url and url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def extract_channel_slug_from_url(url: str) -> str | None:
    if not url:
        return None
    parts = [part for part in urllib.parse.urlparse(url).path.split("/") if part]
    if "joined" in parts:
        idx = parts.index("joined")
        if idx + 2 < len(parts):
            return parts[idx + 2]
    if "chat" in parts:
        idx = parts.index("chat")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    return None


def import_dom_snapshots(args: argparse.Namespace) -> None:
    patterns = args.snapshots or ["*dom*_visible.json", "*dom*_top.json"]
    snapshot_paths: list[Path] = []
    for pattern in patterns:
        matches = sorted(RAW_CAPTURE_DIR.glob(pattern))
        if matches:
            snapshot_paths.extend(matches)
    unique_paths = []
    seen_paths: set[Path] = set()
    for path in snapshot_paths:
        if path not in seen_paths:
            unique_paths.append(path)
            seen_paths.add(path)

    manifest_records = load_jsonl(MANIFEST_PATH)
    manifest_by_message = {record["message_id"]: record for record in manifest_records}
    existing_by_asset_key = {record["asset_key"]: record for record in manifest_records}
    occurrence_index = message_occurrence_index(include_all_messages=False)
    all_message_index = message_occurrence_index(include_all_messages=True)
    linked = 0
    downloaded = 0
    missing = []

    for snapshot_path in unique_paths:
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        channel_slug = extract_channel_slug_from_url(snapshot.get("url") or "")
        if not channel_slug:
            continue
        seen_occurrence: dict[str, int] = {}
        for message in snapshot.get("visibleMessages", []):
            if message.get("type") != "main":
                continue
            raw_time = message.get("rawTime") or ""
            if not raw_time:
                continue
            urls = pick_message_image_urls(message)
            if not urls:
                continue
            seen_occurrence[raw_time] = seen_occurrence.get(raw_time, 0) + 1
            match = occurrence_index.get((channel_slug, raw_time, seen_occurrence[raw_time]))
            if not match:
                match = all_message_index.get((channel_slug, raw_time, seen_occurrence[raw_time]))
            if not match:
                continue
            manifest = manifest_by_message.get(match["id"])
            if not manifest:
                asset_key = f"{match['id']}_domimage01"
                manifest = build_dom_asset_record(match, existing_by_asset_key.get(asset_key), placeholder_index=1)
                manifest_records.append(manifest)
                manifest_by_message[match["id"]] = manifest
                existing_by_asset_key[asset_key] = manifest
                missing.append({"snapshot": snapshot_path.name, "channel_slug": channel_slug, "raw_time": raw_time, "message_id": match["id"], "created_dom_asset": asset_key})
            remote_url = urls[0]
            if manifest.get("remote_url") != remote_url:
                manifest["remote_url"] = remote_url
                manifest["source_snapshot"] = snapshot_path.name
                if manifest.get("downloaded_status") == "pending_download":
                    manifest["downloaded_status"] = "dom_url_found"
                linked += 1
            if args.download and not manifest.get("local_path"):
                suffix = infer_file_suffix(remote_url)
                filename = f"{manifest['asset_key']}{suffix}"
                local_path = ORIGINAL_DIR / filename
                try:
                    download_to_path(remote_url, local_path)
                    manifest["local_path"] = str(local_path)
                    manifest["downloaded_status"] = "downloaded"
                    if manifest.get("ocr_status") == "pending_image":
                        manifest["ocr_status"] = "pending_ocr"
                    if manifest.get("visual_review_status") == "pending_image":
                        manifest["visual_review_status"] = "pending_review"
                    downloaded += 1
                except Exception as exc:  # noqa: BLE001
                    note = f" DOM download failed from {snapshot_path.name}: {exc}"
                    manifest["notes"] = (manifest.get("notes") or "") + note
                    manifest["downloaded_status"] = "dom_download_failed"

        # History/forum views sometimes render attachment images at the page level
        # without exposing them inside visibleMessages. When alt text matches a
        # known file asset key, attach it directly to that manifest row.
        for image in snapshot.get("imgs", []):
            alt = (image.get("alt") or "").strip()
            if not alt.startswith("file_"):
                continue
            manifest = existing_by_asset_key.get(alt)
            if not manifest:
                continue
            remote_url = normalized_remote_url(image.get("src") or "")
            if not remote_url:
                continue
            if manifest.get("remote_url") != remote_url:
                manifest["remote_url"] = remote_url
                manifest["source_snapshot"] = snapshot_path.name
                if manifest.get("downloaded_status") == "pending_download":
                    manifest["downloaded_status"] = "dom_url_found"
                linked += 1
            if args.download and not manifest.get("local_path"):
                suffix = infer_file_suffix(remote_url)
                filename = f"{manifest['asset_key']}{suffix}"
                local_path = ORIGINAL_DIR / filename
                try:
                    download_to_path(remote_url, local_path)
                    manifest["local_path"] = str(local_path)
                    manifest["downloaded_status"] = "downloaded"
                    if manifest.get("ocr_status") == "pending_image":
                        manifest["ocr_status"] = "pending_ocr"
                    if manifest.get("visual_review_status") == "pending_image":
                        manifest["visual_review_status"] = "pending_review"
                    downloaded += 1
                except Exception as exc:  # noqa: BLE001
                    note = f" DOM rendered-image download failed from {snapshot_path.name}: {exc}"
                    manifest["notes"] = (manifest.get("notes") or "") + note
                    manifest["downloaded_status"] = "dom_download_failed"

    write_jsonl(MANIFEST_PATH, manifest_records)
    write_report([ImageAsset(**record) for record in manifest_records])
    print(json.dumps({
        "snapshots": [path.name for path in unique_paths],
        "linked_remote_urls": linked,
        "downloaded": downloaded,
        "missing_manifest_matches": missing[:20],
        "manifest": str(MANIFEST_PATH),
    }, ensure_ascii=False, indent=2))


def import_api_captures(args: argparse.Namespace) -> None:
    patterns = args.captures or ["*_api.json"]
    capture_paths: list[Path] = []
    for pattern in patterns:
        matches = sorted(RAW_CAPTURE_DIR.glob(pattern))
        if matches:
            capture_paths.extend(matches)
    unique_paths = []
    seen_paths: set[Path] = set()
    for path in capture_paths:
        if path not in seen_paths:
            unique_paths.append(path)
            seen_paths.add(path)

    manifest_records = load_jsonl(MANIFEST_PATH)
    manifest_by_attachment = {
        record["attachment_id"]: record
        for record in manifest_records
        if record.get("attachment_id")
    }
    linked = 0
    downloaded = 0

    for capture_path in unique_paths:
        payload = json.loads(capture_path.read_text(encoding="utf-8"))
        for post in payload.get("posts", []):
            for attachment in post.get("attachments") or []:
                attachment_id = attachment.get("id")
                source = attachment.get("source") or {}
                remote_url = source.get("url")
                attachment_filename = attachment.get("filename")
                content_type = attachment.get("contentType")
                if not attachment_id or not remote_url:
                    continue
                manifest = manifest_by_attachment.get(attachment_id)
                if not manifest:
                    continue
                if manifest.get("remote_url") != remote_url:
                    manifest["remote_url"] = remote_url
                    manifest["source_snapshot"] = capture_path.name
                    if manifest.get("downloaded_status") == "pending_download":
                        manifest["downloaded_status"] = "api_url_found"
                    linked += 1
                if args.download and not manifest.get("local_path"):
                    suffix = infer_file_suffix(remote_url, attachment_filename=attachment_filename, content_type=content_type)
                    filename = f"{manifest['asset_key']}{suffix}"
                    local_path = ORIGINAL_DIR / filename
                    try:
                        download_to_path(remote_url, local_path)
                        manifest["local_path"] = str(local_path)
                        manifest["downloaded_status"] = "downloaded"
                        if manifest.get("ocr_status") == "pending_image":
                            manifest["ocr_status"] = "pending_ocr"
                        if manifest.get("visual_review_status") == "pending_image":
                            manifest["visual_review_status"] = "pending_review"
                        downloaded += 1
                    except Exception as exc:  # noqa: BLE001
                        note = f" API download failed from {capture_path.name}: {exc}"
                        manifest["notes"] = (manifest.get("notes") or "") + note
                        manifest["downloaded_status"] = "api_download_failed"

    write_jsonl(MANIFEST_PATH, manifest_records)
    write_report([ImageAsset(**record) for record in manifest_records])
    print(json.dumps({
        "captures": [path.name for path in unique_paths],
        "linked_remote_urls": linked,
        "downloaded": downloaded,
        "manifest": str(MANIFEST_PATH),
    }, ensure_ascii=False, indent=2))


def run_ocr(_: argparse.Namespace) -> None:
    tesseract = shutil.which("tesseract")
    records = load_jsonl(MANIFEST_PATH)
    if not tesseract:
        for record in records:
            if record.get("local_path"):
                record["ocr_status"] = "ocr_tool_missing"
        write_jsonl(MANIFEST_PATH, records)
        write_report([ImageAsset(**record) for record in records])
        print(json.dumps({"ocr_status": "tesseract_missing", "assets_with_images": sum(1 for r in records if r.get("local_path"))}, ensure_ascii=False, indent=2))
        return

    OCR_DIR.mkdir(parents=True, exist_ok=True)
    completed = 0
    failed = 0
    for record in records:
        local_path = record.get("local_path")
        if not local_path or not Path(local_path).exists():
            continue
        out_base = OCR_DIR / record["asset_key"]
        try:
            subprocess.run([tesseract, local_path, str(out_base), "-l", "chi_sim+eng"], check=True, capture_output=True, text=True)
            text_path = out_base.with_suffix(".txt")
            record["ocr_text_path"] = str(text_path)
            record["ocr_status"] = "ocr_complete" if text_path.exists() else "ocr_no_output"
            completed += int(text_path.exists())
        except subprocess.CalledProcessError as exc:
            record["ocr_status"] = "ocr_failed"
            record["notes"] = (record.get("notes") or "") + f" OCR failed: {exc.stderr.strip()[:300]}"
            failed += 1
    write_jsonl(MANIFEST_PATH, records)
    write_report([ImageAsset(**record) for record in records])
    print(json.dumps({"ocr_complete": completed, "ocr_failed": failed}, ensure_ascii=False, indent=2))


def md_table(headers: list[str], rows: Iterable[Iterable[str]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        cells = [str(cell).replace("\n", "<br>").replace("|", "\\|") for cell in row]
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def write_report(assets: list[ImageAsset]) -> None:
    downloaded = sum(1 for asset in assets if asset.local_path)
    ocr_complete = sum(1 for asset in assets if asset.ocr_status == "ocr_complete")
    verified = sum(1 for asset in assets if asset.evidence_status in {"verified_from_image", "corrected_after_image_review"})
    rows = []
    for asset in assets:
        rows.append([
            asset.local_datetime or asset.local_date or "",
            asset.channel_name,
            asset.asset_key,
            asset.downloaded_status,
            asset.ocr_status,
            asset.visual_review_status,
            asset.evidence_status,
            asset.inferred_meaning,
        ])
    text = "\n".join([
        "# 图片验证状态",
        "",
        f"- 图片资产记录: {len(assets)}",
        f"- 已关联原图/截图: {downloaded}",
        f"- OCR 完成: {ocr_complete}",
        f"- 真图含义已验证/修正: {verified}",
        "",
        md_table(
            ["时间", "频道", "资产", "原图状态", "OCR", "视觉复核", "证据状态", "当前金融含义"],
            rows,
        ),
    ])
    write_text(VERIFICATION_PATH, text)


def report(_: argparse.Namespace) -> None:
    records = load_jsonl(MANIFEST_PATH)
    assets = [ImageAsset(**record) for record in records]
    write_report(assets)
    print(json.dumps({
        "assets": len(assets),
        "downloaded": sum(1 for asset in assets if asset.local_path),
        "ocr_complete": sum(1 for asset in assets if asset.ocr_status == "ocr_complete"),
        "report": str(VERIFICATION_PATH),
    }, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(required=True)
    init = sub.add_parser("init-manifest")
    init.set_defaults(func=init_manifest)
    scan = sub.add_parser("scan-originals")
    scan.set_defaults(func=scan_originals)
    api = sub.add_parser("import-api-captures")
    api.add_argument("captures", nargs="*")
    api.add_argument("--download", action="store_true")
    api.set_defaults(func=import_api_captures)
    imp = sub.add_parser("import-dom-snapshots")
    imp.add_argument("snapshots", nargs="*")
    imp.add_argument("--download", action="store_true")
    imp.set_defaults(func=import_dom_snapshots)
    ocr = sub.add_parser("run-ocr")
    ocr.set_defaults(func=run_ocr)
    rep = sub.add_parser("report")
    rep.set_defaults(func=report)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
