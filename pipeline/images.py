"""Zoekt een passende, gratis te gebruiken stockfoto bij een artikel (Pexels).

Pexels-foto's mogen gratis (ook commercieel) worden gebruikt; we vermelden altijd de fotograaf.
Zonder PEXELS_API_KEY gebeurt er niets en blijft het artikel zonder foto (typografische kaart)."""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

API = "https://api.pexels.com/v1/search"
FALLBACK_QUERIES = ["cyber security", "computer security", "laptop code dark", "server room", "data network"]


def _search(query: str, key: str) -> list[dict]:
    url = f"{API}?{urllib.parse.urlencode({'query': query, 'per_page': 15, 'orientation': 'landscape'})}"
    req = urllib.request.Request(url, headers={"Authorization": key, "User-Agent": "CyberSecurityNieuwsBot/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read()).get("photos", [])


def find_photo(query: str, used_ids: set, alt_fallback: str = "") -> dict | None:
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        return None
    for q in [query] + FALLBACK_QUERIES:
        if not q:
            continue
        try:
            photos = _search(q, key)
        except Exception as exc:
            print(f"  ! foto zoeken mislukt ({q}): {exc}")
            return None
        for p in photos:
            if p["id"] in used_ids:
                continue  # dezelfde foto niet twee keer gebruiken
            used_ids.add(p["id"])
            return {
                "id": p["id"],
                "url": p["src"].get("landscape") or p["src"]["large"],
                "alt": p.get("alt") or alt_fallback,
                "credit": p.get("photographer", "Pexels"),
                "credit_url": p.get("photographer_url", "https://www.pexels.com"),
                "page_url": p.get("url", "https://www.pexels.com"),
                "provider": "Pexels",
            }
    return None
