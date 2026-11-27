"""Zoekt een passende, gratis te gebruiken stockfoto bij een artikel (Pixabay).

Pixabay-licentie: gratis, ook commercieel, naamsvermelding niet verplicht (we vermelden de fotograaf
wel). Pixabay vraagt om foto's zelf te hosten: het origineel wordt opgeslagen in content/fotos/<slug>.jpg;
build.py maakt daar de sitebeelden in huisstijl van (pipeline/covers.brand_photo).
Foto's met herkenbare personen slaan we over (die mogen niet in een negatief daglicht komen, en bij
nieuws over hackers of fraude zou dat wel gebeuren).
Zonder PIXABAY_API_KEY gebeurt er niets: het artikel houdt het typografische beeld."""
from __future__ import annotations

import io
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FOTOS = ROOT / "content" / "fotos"
API = "https://pixabay.com/api/"
UA = {"User-Agent": "CyberSecurityNieuwsBot/1.0 (+https://cybersecuritynieuws.com)"}
FALLBACK_QUERIES = ["cyber security", "computer security", "laptop code", "server room", "data network"]
PEOPLE = {"woman", "man", "women", "men", "girl", "boy", "people", "person", "face", "child", "kid",
          "businessman", "businesswoman", "model", "portrait", "lady", "guy", "female", "male", "hacker"}


def _get(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.read()


def _search(query: str, key: str) -> list[dict]:
    params = {"key": key, "q": query[:100], "image_type": "photo", "orientation": "horizontal",
              "safesearch": "true", "min_width": 1280, "per_page": 30, "order": "popular"}
    return json.loads(_get(f"{API}?{urllib.parse.urlencode(params)}")).get("hits", [])


def _has_people(hit: dict) -> bool:
    tags = {t.strip().lower() for t in hit.get("tags", "").split(",")}
    return bool(tags & PEOPLE)


def find_photo(query: str, used_ids: set, alt_fallback: str = "", slug: str | None = None) -> dict | None:
    key = os.environ.get("PIXABAY_API_KEY")
    if not key or not slug:
        return None
    from PIL import Image
    for q in [query] + FALLBACK_QUERIES:
        if not q:
            continue
        try:
            hits = _search(q, key)
        except Exception as exc:
            print(f"  ! foto zoeken mislukt ({q}): {exc}")
            return None
        for h in hits:
            if h["id"] in used_ids or _has_people(h):
                continue
            try:
                im = Image.open(io.BytesIO(_get(h["largeImageURL"]))).convert("RGB")
            except Exception as exc:
                print(f"  ! foto downloaden mislukt ({h['id']}): {exc}")
                continue
            im.thumbnail((1600, 1600))
            FOTOS.mkdir(parents=True, exist_ok=True)
            im.save(FOTOS / f"{slug}.jpg", quality=86, optimize=True)
            used_ids.add(h["id"])
            return {
                "id": h["id"],
                "file": f"{slug}.jpg",
                "alt": alt_fallback,
                "credit": h.get("user") or "Pixabay",
                "credit_url": f"https://pixabay.com/users/{h.get('user')}-{h.get('user_id')}/",
                "page_url": h.get("pageURL", "https://pixabay.com"),
                "provider": "Pixabay",
            }
    return None
