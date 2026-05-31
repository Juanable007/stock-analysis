#!/usr/bin/env python3
"""Capture the active Chrome tab's visible Whop content via page JavaScript.

This helper uses Chrome's AppleScript `execute javascript` bridge, so it works
against the user's authenticated Whop session without needing a separate browser
automation stack. It can:

- inspect the active tab and visible scroll container
- navigate the active tab to a URL
- move the primary vertical scroll container
- dump the current visible text/image state to JSON and text files
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


LOCAL_TZ = ZoneInfo("Asia/Shanghai")
BASE_DIR = Path("/Users/juanable/Documents/code/stock-analysis/data/whop_archive/raw_captures")


def run_osascript(script: str) -> str:
    result = subprocess.run(
        ["osascript", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def chrome_js(js: str) -> str:
    escaped = js.replace("\\", "\\\\").replace('"', '\\"')
    script = f'tell application "Google Chrome" to execute active tab of front window javascript "{escaped}"'
    return run_osascript(script)


def chrome_url() -> str:
    return run_osascript('tell application "Google Chrome" to get URL of active tab of front window')


def chrome_title() -> str:
    return run_osascript('tell application "Google Chrome" to execute active tab of front window javascript "document.title"')


def set_url(url: str) -> None:
    escaped = url.replace("\\", "\\\\").replace('"', '\\"')
    run_osascript(f'tell application "Google Chrome" to set URL of active tab of front window to "{escaped}"')


def build_snapshot_js() -> str:
    return r"""
(() => {
  const reactionSet = new Set(['❤️', '👍️', '😍️', '🤣️', '☠️', '🥹']);
  const seenMessageKeys = new Set();
  const imageData = (root) => Array.from(root.querySelectorAll('img')).map((img) => {
    const rect = img.getBoundingClientRect();
    return {
      alt: img.alt || '',
      src: img.currentSrc || img.src || '',
      naturalWidth: img.naturalWidth || 0,
      naturalHeight: img.naturalHeight || 0,
      rectWidth: Math.round(rect.width || 0),
      rectHeight: Math.round(rect.height || 0),
    };
  });
  const parseMessageLines = (lines, images, typeLabel) => {
    const authorIndex = lines.indexOf('xiaozhaolucky');
    let bulletIndex = lines.indexOf('•', authorIndex + 1);
    if (bulletIndex === -1) bulletIndex = lines.indexOf('·', authorIndex + 1);
    const hasHandleLine = !!lines[authorIndex + 1] && lines[authorIndex + 1].startsWith('@');
    const expectedBulletIndex = hasHandleLine ? authorIndex + 2 : authorIndex + 1;
    if (authorIndex === -1 || bulletIndex !== expectedBulletIndex || !lines[bulletIndex + 1]) return null;
    const rawTime = lines[bulletIndex + 1];
    const content = [];
    for (let i = bulletIndex + 2; i < lines.length; i++) {
      const line = lines[i];
      if (line.startsWith('被') && line.endsWith('阅读')) break;
      if (reactionSet.has(line)) continue;
      if (/^[0-9]+$/.test(line) && i > 0 && reactionSet.has(lines[i - 1])) continue;
      if (line === 'Edited' || line === '已钉帖子') continue;
      content.push(line);
    }
    const key = `${typeLabel}|${rawTime}|${content.join('\n').slice(0, 120)}`;
    if (seenMessageKeys.has(key)) return null;
    seenMessageKeys.add(key);
    return {
      type: 'main',
      author: 'xiaozhaolucky',
      rawTime,
      content,
      images,
      source: typeLabel,
    };
  };
  const visibleMessages = [];
  const messageContainers = Array.from(document.querySelectorAll('div'))
    .filter((el) => typeof el.className === 'string' && el.className.includes('@container/message-container'));
  for (const node of messageContainers) {
    const replyNodes = Array.from(node.querySelectorAll('div'))
      .filter((el) => typeof el.className === 'string' && el.className.includes('peer/reply'));
    for (const reply of replyNodes) {
      const lines = (reply.innerText || '')
        .split(/\n+/)
        .map((s) => s.trim())
        .filter(Boolean);
      if (lines[0] === 'xiaozhaolucky') {
        visibleMessages.push({
          type: 'reply',
          author: 'xiaozhaolucky',
          rawTime: null,
          lines,
          images: imageData(reply),
        });
      }
    }
    const lines = (node.innerText || '')
      .split(/\n+/)
      .map((s) => s.trim())
      .filter(Boolean);
    const parsed = parseMessageLines(lines, imageData(node), 'message_container');
    if (parsed) visibleMessages.push(parsed);
  }
  const postHeaders = Array.from(document.querySelectorAll('div'))
    .filter((el) => typeof el.className === 'string' && el.className.includes('group/post-header'));
  for (const header of postHeaders) {
    const root = header.parentElement || header;
    const lines = (root.innerText || '')
      .split(/\n+/)
      .map((s) => s.trim())
      .filter(Boolean);
    const parsed = parseMessageLines(lines, imageData(root), 'post_header');
    if (parsed) visibleMessages.push(parsed);
  }
  const scrollables = Array.from(document.querySelectorAll('*'))
    .map((el, i) => ({
      index: i,
      tag: el.tagName,
      role: el.getAttribute('role'),
      className: typeof el.className === 'string' ? el.className : '',
      scrollHeight: el.scrollHeight || 0,
      clientHeight: el.clientHeight || 0,
      scrollTop: el.scrollTop || 0,
    }))
    .filter((x) => x.scrollHeight > x.clientHeight + 50)
    .sort((a, b) => (b.scrollHeight - b.clientHeight) - (a.scrollHeight - a.clientHeight));
  return JSON.stringify({
    ts: new Date().toISOString(),
    title: document.title,
    url: location.href,
    innerTextLen: document.body.innerText.length,
    textContentLen: document.body.textContent.length,
    text: document.body.innerText,
    visibleMessages,
    scrolls: scrollables.slice(0, 20),
    imgs: Array.from(document.images).map((img, i) => ({
      i,
      alt: img.alt,
      src: img.currentSrc || img.src,
      w: img.naturalWidth,
      h: img.naturalHeight,
    })),
  });
})()
""".strip()


def build_scroll_js(position: str | None, delta: int | None) -> str:
    if position not in {"top", "bottom", None}:
        raise ValueError(f"unsupported position: {position}")
    if position is None and delta is None:
        raise ValueError("either position or delta must be provided")
    action = "el.scrollTop = 0;"
    if position == "bottom":
        action = "el.scrollTop = el.scrollHeight;"
    elif delta is not None:
        action = f"el.scrollTop = Math.max(0, Math.min(el.scrollHeight, el.scrollTop + ({delta})));"
    return f"""
(() => {{
  const els = Array.from(document.querySelectorAll('*'))
    .filter((el) => (el.scrollHeight || 0) > (el.clientHeight || 0) + 50)
    .sort((a, b) => ((b.scrollHeight - b.clientHeight) - (a.scrollHeight - a.clientHeight)));
  const el = els[0];
  if (!el) return JSON.stringify({{ok:false, reason:'no-scrollable'}});
  {action}
  el.dispatchEvent(new Event('scroll', {{ bubbles: true }}));
  return JSON.stringify({{
    ok: true,
    className: typeof el.className === 'string' ? el.className : '',
    scrollTop: el.scrollTop,
    scrollHeight: el.scrollHeight,
    clientHeight: el.clientHeight
  }});
}})()
""".strip()


def write_snapshot_files(snapshot: dict, stem: str) -> tuple[Path, Path]:
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    json_path = BASE_DIR / f"{stem}.json"
    txt_path = BASE_DIR / f"{stem}_clean.txt"
    json_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    txt_path.write_text(snapshot["text"], encoding="utf-8")
    return json_path, txt_path


def visible_messages_to_text(snapshot: dict) -> str:
    blocks = []
    for item in snapshot.get("visibleMessages", []):
        if item.get("type") == "main":
            blocks.extend(
                [
                    "xiaozhaolucky",
                    "@xiaozhaolucky",
                    "·",
                    item.get("rawTime") or "[unknown_time]",
                    "",
                    *item.get("content", []),
                    "",
                ]
            )
        elif item.get("type") == "reply":
            lines = item.get("lines", [])
            content = lines[1:] if len(lines) > 1 else []
            blocks.extend(
                [
                    "xiaozhaolucky",
                    "@xiaozhaolucky",
                    "·",
                    "[reply_fragment]",
                    "",
                    *content,
                    "",
                ]
            )
    return "\n".join(blocks).strip() + ("\n" if blocks else "")


def cmd_info(_: argparse.Namespace) -> None:
    print(json.dumps({"title": chrome_title(), "url": chrome_url()}, ensure_ascii=False, indent=2))


def cmd_navigate(args: argparse.Namespace) -> None:
    set_url(args.url)
    print(json.dumps({"ok": True, "url": args.url}, ensure_ascii=False))


def cmd_scroll(args: argparse.Namespace) -> None:
    payload = json.loads(chrome_js(build_scroll_js(args.position, args.delta)))
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def cmd_snapshot(args: argparse.Namespace) -> None:
    snapshot = json.loads(chrome_js(build_snapshot_js()))
    stem = args.stem
    if not stem:
        ts = datetime.now(LOCAL_TZ).strftime("%Y%m%d_%H%M%S")
        stem = f"chrome_visible_{ts}"
    json_path, txt_path = write_snapshot_files(snapshot, stem)
    visible_path = BASE_DIR / f"{stem}_visible_messages.txt"
    visible_path.write_text(visible_messages_to_text(snapshot), encoding="utf-8")
    print(
        json.dumps(
            {
                "json_path": str(json_path),
                "txt_path": str(txt_path),
                "visible_messages_path": str(visible_path),
                "title": snapshot["title"],
                "url": snapshot["url"],
                "innerTextLen": snapshot["innerTextLen"],
                "visibleMessages": len(snapshot.get("visibleMessages", [])),
                "images": len(snapshot["imgs"]),
                "scrolls": snapshot["scrolls"][:3],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(required=True)

    info_parser = sub.add_parser("info")
    info_parser.set_defaults(func=cmd_info)

    nav_parser = sub.add_parser("navigate")
    nav_parser.add_argument("url")
    nav_parser.set_defaults(func=cmd_navigate)

    scroll_parser = sub.add_parser("scroll")
    scroll_group = scroll_parser.add_mutually_exclusive_group(required=True)
    scroll_group.add_argument("--position", choices=["top", "bottom"])
    scroll_group.add_argument("--delta", type=int)
    scroll_parser.set_defaults(func=cmd_scroll)

    snap_parser = sub.add_parser("snapshot")
    snap_parser.add_argument("--stem")
    snap_parser.set_defaults(func=cmd_snapshot)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
