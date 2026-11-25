"""Meldt recent gepubliceerde pagina's aan via IndexNow (Bing, Yandex, Seznam, Naver …).

Draait in GitHub Actions na elke publicatie. Zonder indexnow_key in config.yaml doet het niets."""
from __future__ import annotations

import json
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    config = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    key = (config.get("zoekmachines") or {}).get("indexnow_key")
    if not key:
        print("Geen indexnow_key ingesteld; overgeslagen.")
        return
    site = config["site"]["url"].rstrip("/")
    host = site.split("://", 1)[1]
    cutoff = datetime.now(timezone.utc) - timedelta(days=3)
    urls = [f"{site}/", f"{site}/actief-misbruikt/", f"{site}/weekoverzicht/"]
    for p in (ROOT / "content" / "articles").glob("*.json"):
        a = json.loads(p.read_text(encoding="utf-8"))
        changed = datetime.fromisoformat(a.get("updated") or a["published"])
        if changed > cutoff:
            urls.append(f"{site}/artikel/{a['slug']}/")
    body = json.dumps({"host": host, "key": key, "keyLocation": f"{site}/{key}.txt", "urlList": urls}).encode()
    req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body,
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print(f"IndexNow: {len(urls)} URL's aangemeld (HTTP {r.status}).")
    except Exception as exc:  # nooit de publicatie laten mislukken
        print(f"IndexNow mislukt (niet erg): {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
