#!/usr/bin/env python3
"""Fetch Whop forum-feed posts through the user's authenticated Chrome tab."""

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


FETCH_FORUM_FEED = """
query FetchForumFeed($publicExperienceId: ID!) {
  publicExperience(id: $publicExperienceId) {
    forumFeed {
      id
      whoCanPost
      isDeleted
    }
  }
}
""".strip()


FETCH_FORUM_POSTS = """
query FetchForumPosts($feedId: ID!, $limit: Int, $before: BigInt) {
  feedPosts(
    feedId: $feedId
    feedType: forum_feed
    limit: $limit
    before: $before
    includeReactions: false
    includeChildren: false
    includeDeleted: false
  ) {
    posts {
      __typename
      id
      createdAt
      sortKey
      ... on ForumPost {
        pinned
        title
        content
        richContent
        feedId
        experienceId
        viewCount
        commentCount
        attachments {
          id
          filename
          contentType
          source(variant: original) {
            url
          }
        }
        user {
          id
          name
          username
        }
      }
    }
  }
}
""".strip()


def resolve_forum_feed_id(experience_id: str) -> tuple[str, dict]:
    resp = gql_request(
        "FetchForumFeed",
        FETCH_FORUM_FEED,
        {"publicExperienceId": experience_id},
    )
    forum_feed = resp["data"]["publicExperience"]["forumFeed"]
    if not forum_feed:
        raise SystemExit(f"no forum feed found for {experience_id}")
    return forum_feed["id"], resp


def fetch_posts(feed_id: str, limit: int, before: str | None) -> dict:
    vars_ = {
        "feedId": feed_id,
        "limit": limit,
        "before": before,
    }
    return gql_request("FetchForumPosts", FETCH_FORUM_POSTS, vars_)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--experience-id", required=True)
    parser.add_argument("--feed-id")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--pages", type=int, default=40)
    parser.add_argument("--before")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    feed_id = args.feed_id
    meta = {}
    if not feed_id:
        feed_id, meta = resolve_forum_feed_id(args.experience_id)

    before = args.before
    seen_ids: set[str] = set()
    rows: list[dict] = []

    for page in range(args.pages):
        resp = fetch_posts(feed_id, args.limit, before)
        posts = resp.get("data", {}).get("feedPosts", {}).get("posts", [])
        if not posts:
            break
        fresh = [post for post in posts if post.get("id") not in seen_ids]
        if not fresh:
            break
        for post in fresh:
            seen_ids.add(post["id"])
            rows.append(post)
        regular = [post for post in fresh if post.get("__typename") == "ForumPost" and not post.get("pinned")]
        if not regular:
            break
        before = str(min(int(post["createdAt"]) for post in regular))
        print(
            json.dumps(
                {
                    "page": page + 1,
                    "posts": len(fresh),
                    "regular_posts": len(regular),
                    "oldest_regular_createdAt": before,
                    "oldest_regular_id": min(regular, key=lambda post: int(post["createdAt"]))["id"],
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
