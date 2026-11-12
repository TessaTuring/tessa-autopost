"""Refresh an expiring Instagram Login token (valid 60 days) and print the new one.

System-user tokens from Meta's Unified login never expire; for those this prints
nothing and the workflow leaves the secret alone.
"""
import os

import requests

token = os.environ["IG_ACCESS_TOKEN"].strip()
if token.startswith("IG"):
    r = requests.get(
        "https://graph.instagram.com/refresh_access_token",
        params={"grant_type": "ig_refresh_token", "access_token": token},
        timeout=60,
    )
    r.raise_for_status()
    print(r.json()["access_token"])
