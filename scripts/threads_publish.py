"""Publish a drafted text-only post to Threads.

Usage: python scripts/threads_publish.py YYYY-MM-DD
Env:   THREADS_USER_ID, THREADS_ACCESS_TOKEN
Prints the permalink of the published post.
"""
from __future__ import annotations

import json
import os
import sys
import time

import requests

from common import ROOT

BASE = "https://graph.threads.net/v1.0"


def call(method: str, path: str, **params) -> dict:
    token = os.environ["THREADS_ACCESS_TOKEN"].strip()
    url = f"{BASE}/{path}"
    if method == "POST":
        r = requests.post(url, data={**params, "access_token": token}, timeout=60)
    else:
        r = requests.get(url, params={**params, "access_token": token}, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f"Threads API {method} {path} failed ({r.status_code}): {r.text}")
    return r.json()


def publish(day: str) -> str:
    post = json.loads((ROOT / "threads" / f"{day}.json").read_text())
    user = os.environ["THREADS_USER_ID"].strip()

    container = call("POST", f"{user}/threads", media_type="TEXT", text=post["text"])["id"]
    time.sleep(5)  # Meta suggests a short wait between creating and publishing
    last = None
    for _ in range(4):
        try:
            media_id = call("POST", f"{user}/threads_publish", creation_id=container)["id"]
            break
        except RuntimeError as e:
            last = e
            time.sleep(15)
    else:
        raise last
    try:
        return call("GET", media_id, fields="permalink").get("permalink", media_id)
    except RuntimeError:
        return media_id  # posted fine; only the link lookup failed


if __name__ == "__main__":
    print(publish(sys.argv[1]))
