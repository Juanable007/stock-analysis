#!/usr/bin/env python3
"""Fetch Whop chat-feed posts through the user's authenticated Chrome tab.

This uses Chrome's AppleScript `execute javascript` bridge to issue GraphQL
requests from the active Whop page, so the requests automatically reuse the
user's logged-in browser session.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


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
    script = (
        'tell application "Google Chrome" '
        f'to execute active tab of front window javascript "{escaped}"'
    )
    return run_osascript(script)


def gql_request(endpoint_name: str, query: str, variables: dict) -> dict:
    payload = {
        "query": query,
        "variables": variables,
        "operationName": endpoint_name,
    }
    js = f"""
(() => {{
  const xhr = new XMLHttpRequest();
  xhr.open('POST', '/api/graphql/{endpoint_name}/', false);
  xhr.setRequestHeader('content-type', 'application/json');
  xhr.send({json.dumps(json.dumps(payload), ensure_ascii=False)});
  return xhr.responseText;
}})()
""".strip()
    raw = chrome_js(js)
    return json.loads(raw)


MESSAGES_PUBLIC_EXPERIENCE = """
query MessagesPublicExperience($experienceId: ID!) {
  publicExperience(id: $experienceId) {
    id
    name
    company {
      id
    }
    chatFeeds {
      id
      experienceId
    }
  }
}
""".strip()


MESSAGES_FETCH_FEED_POSTS = """
query MessagesFetchFeedPosts(
  $feedType: FeedTypes!,
  $feedId: ID!,
  $limit: Int,
  $includeDeleted: Boolean,
  $includeReactions: Boolean,
  $before: BigInt
) {
  feedPosts(
    feedType: $feedType
    feedId: $feedId
    limit: $limit
    includeDeleted: $includeDeleted
    includeReactions: $includeReactions
    before: $before
  ) {
    posts {
      __typename
      id
      createdAt
      updatedAt
      sortKey
      ... on DmsPost {
        content
        userId
        messageType
        attachments {
          __typename
          id
          filename
          contentType
          source(variant: original) {
            url
          }
        }
        richContent
        viewCount
      }
    }
    users {
      id
      name
      username
    }
    reactions {
      id
    }
  }
}
""".strip()


def resolve_feed_id(experience_id: str) -> tuple[str, dict]:
    resp = gql_request(
        "MessagesPublicExperience",
        MESSAGES_PUBLIC_EXPERIENCE,
        {"experienceId": experience_id},
    )
    experience = resp["data"]["publicExperience"]
    feeds = experience.get("chatFeeds") or []
    if not feeds:
        raise SystemExit(f"no chat feed found for {experience_id}")
    return feeds[0]["id"], resp


def fetch_posts(feed_id: str, limit: int, before: str | None) -> dict:
    vars_ = {
        "feedType": "chat_feed",
        "feedId": feed_id,
        "limit": limit,
        "includeDeleted": False,
        "includeReactions": False,
        "before": before,
    }
    return gql_request("MessagesFetchFeedPosts", MESSAGES_FETCH_FEED_POSTS, vars_)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--experience-id", required=True)
    parser.add_argument("--feed-id")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--pages", type=int, default=20)
    parser.add_argument("--before")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    feed_id = args.feed_id
    meta = {}
    if not feed_id:
        feed_id, meta = resolve_feed_id(args.experience_id)

    before = args.before
    seen_ids: set[str] = set()
    rows: list[dict] = []

    for page in range(args.pages):
        resp = fetch_posts(feed_id, args.limit, before)
        posts = resp.get("data", {}).get("feedPosts", {}).get("posts", [])
        if not posts:
            break
        fresh = [post for post in posts if post["id"] not in seen_ids]
        if not fresh:
            break
        for post in fresh:
            seen_ids.add(post["id"])
            rows.append(post)
        before = min(post["createdAt"] for post in fresh)
        print(
            json.dumps(
                {
                    "page": page + 1,
                    "posts": len(fresh),
                    "oldest_createdAt": before,
                    "oldest_id": fresh[-1]["id"],
                },
                ensure_ascii=False,
            )
        )

    payload = {
        "experience_id": args.experience_id,
        "feed_id": feed_id,
        "resolved_meta": meta,
        "posts": rows,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(out_path), "count": len(rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
