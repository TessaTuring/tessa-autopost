"""Publish drafts/<date>/reel.mp4 to Instagram as a Reel (Reels tab only, so the grid isn't doubled).

Usage: python scripts/publish_reel.py YYYY-MM-DD
Env:   IG_USER_ID, IG_ACCESS_TOKEN, GITHUB_REPOSITORY
"""
from __future__ import annotations

import json
import os
import sys

from common import DRAFTS, raw_url
from publish import call, wait_ready


def publish_reel(day: str) -> str:
    post = json.loads((DRAFTS / day / "post.json").read_text())
    ig = os.environ["IG_USER_ID"].strip()
    container = call(
        "POST", f"{ig}/media",
        media_type="REELS",
        video_url=raw_url(f"drafts/{day}/reel.mp4"),
        caption=post["caption"],
        share_to_feed=False,
        is_ai_generated=True,
    )["id"]
    wait_ready(container, minutes=10)
    media_id = call("POST", f"{ig}/media_publish", creation_id=container)["id"]
    return call("GET", media_id, fields="permalink").get("permalink", media_id)


if __name__ == "__main__":
    print(publish_reel(sys.argv[1]))
