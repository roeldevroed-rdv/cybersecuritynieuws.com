"""Volledige run: nieuws ophalen -> artikelen + evergreen-gidsen schrijven -> site bouwen.

Gebruik:
  python -m pipeline.run            # ophalen, schrijven en bouwen
  python -m pipeline.run --build    # alleen de site opnieuw bouwen
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
ARTICLES = ROOT / "content" / "articles"
SEEN = ROOT / "content" / "seen.json"
STOP = set("de het een en of van in op voor met door uit aan als is zijn je jouw wat hoe waarom the a an and of to for on in with".split())


def load_config() -> dict:
    return yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))


def load_existing() -> list[dict]:
    out = []
    for p in ARTICLES.glob("*.json"):
        a = json.loads(p.read_text(encoding="utf-8"))
        out.append(a)
    return out


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9][a-z0-9\-]{2,}", text.lower()) if w not in STOP}


def internal_candidates(existing: list[dict], text: str, limit: int = 20) -> list[dict]:
    """Kies de bestaande artikelen die het best bij een nieuw stuk passen (voor interne links).
    Gidsen krijgen voorrang: dat zijn de pagina's die je wilt laten scoren."""
    words = _words(text)
    scored = []
    for a in existing:
        aw = _words(" ".join([a["title"], a.get("tldr", ""), " ".join(a.get("keywords", [])),
                              " ".join(l for v in a.get("labels", {}).values() for l in v)]))
        s = len(words & aw) + (2 if a.get("type") == "gids" else 0)
        if s > 0:
            scored.append((s, a["published"], a))
    scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return [{"title": a["title"], "url": f"/artikel/{a['slug']}/"} for _, _, a in scored[:limit]]


def save(art: dict, used_photos: set | None = None) -> None:
    from .images import find_photo
    if used_photos is not None and not art.get("image"):
        art["image"] = find_photo(art.get("image_query", ""), used_photos, alt_fallback=art["title"])
    (ARTICLES / f"{art['id']}.json").write_text(json.dumps(art, ensure_ascii=False, indent=2), encoding="utf-8")


def update_news(config: dict) -> int:
    import anthropic
    from .fetch import gather
    from .writer import write_article

    seen = set(json.loads(SEEN.read_text())) if SEEN.exists() else set()
    existing = load_existing()
    slugs = {a["slug"] for a in existing}
    used = {(a.get("image") or {}).get("id") for a in existing}
    client = anthropic.Anthropic()
    written = 0
    for story in gather(config, seen):
        if written >= config["ai"]["max_new_articles_per_run"]:
            break
        seen |= {i.link for i in story.items}
        text = " ".join(i.title + " " + i.summary for i in story.items)
        try:
            art = write_article(client, config, story, internal_candidates(existing, text))
        except Exception as exc:
            print(f"  ! schrijven mislukt voor '{story.lead.title}': {exc}")
            continue
        if not art or art["slug"] in slugs:
            print(f"  - overgeslagen: {story.lead.title}")
            continue
        save(art, used)
        existing.append(art)
        slugs.add(art["slug"])
        written += 1
        print(f"  + {art['title']}")
    # Bewaar alleen de laatste 5000 links om het bestand klein te houden
    SEEN.write_text(json.dumps(sorted(seen)[-5000:], indent=0))
    print(f"{written} nieuwe nieuwsartikelen.")
    return written


def update_evergreen(config: dict) -> int:
    """Schrijft het volgende onderwerp uit de contentkalender, tot 'per_day' gidsen per dag."""
    import anthropic
    from .writer import write_evergreen

    ev = config.get("evergreen") or {}
    existing = load_existing()
    done = {a.get("topic_id") for a in existing} | {a["slug"] for a in existing}
    today = datetime.now(timezone.utc).date().isoformat()
    room = ev.get("per_day", 1) - sum(1 for a in existing if a.get("type") == "gids" and a["published"].startswith(today))
    todo = [t for t in ev.get("topics", []) if t["id"] not in done]
    if room <= 0 or not todo:
        print("Evergreen: niets te doen" + (" (kalender is leeg – voeg onderwerpen toe in config.yaml)" if not todo else "."))
        return 0
    client = anthropic.Anthropic()
    used = {(a.get("image") or {}).get("id") for a in existing}
    written = 0
    for topic in todo[:room]:
        try:
            art = write_evergreen(client, config, topic,
                                  internal_candidates(existing, topic["title"] + " " + topic["keyword"]))
        except Exception as exc:
            print(f"  ! gids mislukt voor '{topic['title']}': {exc}")
            continue
        if art:
            save(art, used)
            existing.append(art)
            written += 1
            print(f"  + gids: {art['title']}")
    return written


def add_missing_photos() -> None:
    """Zoekt foto's bij bestaande artikelen die er nog geen hebben (python -m pipeline.run --fotos)."""
    from .images import find_photo
    arts = load_existing()
    used = {(a.get("image") or {}).get("id") for a in arts}
    n = 0
    for a in arts:
        if not a.get("image"):
            a["image"] = find_photo(a.get("image_query") or " ".join(a.get("keywords", [])[:2]), used, a["title"])
            if a["image"]:
                (ARTICLES / f"{a['id']}.json").write_text(json.dumps(a, ensure_ascii=False, indent=2), encoding="utf-8")
                n += 1
    print(f"{n} foto's toegevoegd.")


def main() -> None:
    config = load_config()
    ARTICLES.mkdir(parents=True, exist_ok=True)
    if "--fotos" in sys.argv:
        add_missing_photos()
    if "--build" not in sys.argv and "--fotos" not in sys.argv:
        if os.environ.get("ANTHROPIC_API_KEY"):
            update_news(config)
            update_evergreen(config)
        else:
            print("ANTHROPIC_API_KEY ontbreekt: geen nieuwe artikelen geschreven.")
    from .build import build
    build(config)


if __name__ == "__main__":
    main()
