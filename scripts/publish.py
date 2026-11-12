"""Publish a drafted carousel to Instagram.

Works with either kind of Meta token:
  - Instagram Login tokens (start with "IG")  -> graph.instagram.com
  - Unified / Facebook Login and system-user tokens (start with "EA") -> graph.facebook.com

Usage: python scripts/publish.py YYYY-MM-DD
Env:   IG_USER_ID, IG_ACCESS_TOKEN, GITHUB_REPOSITORY
Prints the permalink of the published post.
"""
from __future__ import annotations

import json
import os
import sys
import time

import requests

from common import DRAFTS, raw_url

VERSION = "v27.0"


def api_base() -> str:
    token = os.environ["IG_ACCESS_TOKEN"].strip()
    host = "graph.instagram.com" if token.startswith("IG") else "graph.facebook.com"
    return f"https://{host}/{VERSION}"


def call(method: str, path: str, **payload) -> dict:
    headers = {"Authorization": f"Bearer {os.environ['IG_ACCESS_TOKEN'].strip()}"}
    url = f"{api_base()}/{path}"
    r = requests.request(method, url, headers=headers, json=payload or None, timeout=60) if method == "POST" \
        else requests.get(url, headers=headers, params=payload, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f"Instagram API {method} {path} failed ({r.status_code}): {r.text}")
    return r.json()


def wait_ready(container_id: str, minutes: int = 5) -> None:
    for _ in range(minutes * 4):
        status = call("GET", container_id, fields="status_code")["status_code"]
        if status == "FINISHED":
            return
        if status in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Container {container_id} status {status}")
        time.sleep(15)
    raise RuntimeError(f"Container {container_id} not ready after {minutes} minutes")


def publish(day: str) -> str:
    post = json.loads((DRAFTS / day / "post.json").read_text())
    ig = os.environ["IG_USER_ID"].strip()

    children = []
    for rel in post["images"]:
        cid = call("POST", f"{ig}/media", image_url=raw_url(rel), is_carousel_item=True)["id"]
        children.append(cid)
    for cid in children:
        wait_ready(cid)

    carousel = call(
        "POST", f"{ig}/media",
        media_type="CAROUSEL",
        children=",".join(children),
        caption=post["caption"],
        is_ai_generated=True,  # Instagram's own "AI info" label on the post
    )["id"]
    wait_ready(carousel)
    media_id = call("POST", f"{ig}/media_publish", creation_id=carousel)["id"]
    return call("GET", media_id, fields="permalink").get("permalink", media_id)


if __name__ == "__main__":
    print(publish(sys.argv[1]))
