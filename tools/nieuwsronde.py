"""Hulpmiddel voor de dagelijkse nieuwsronde door de redactie (Claude-sessie, zonder API-kosten).

  python -m tools.nieuwsronde kandidaten [--uren 36] [--aantal 25]
      Haalt de RSS-bronnen op, voegt dubbele berichten samen, controleert CVE's tegen de CISA KEV-lijst
      en toont de best scorende verhalen die nog niet zijn behandeld. Schrijft details naar
      /tmp/nieuwsronde-kandidaten.json (met samenvattingen en bron-URL's).

  python -m tools.nieuwsronde opslaan concepten.json
      Leest een JSON-lijst met artikelconcepten, controleert ze (verplichte velden, thema's, labels,
      lengte van metabeschrijving en tekst), voegt de KEV-status toe op basis van de CVE's en schrijft
      ze naar content/articles/. Bron-URL's worden toegevoegd aan content/seen.json.

Velden per concept: slug, title, tldr, meta_description, body (Markdown), actions [..], faq [{q,a}],
category, labels {regio, doelgroep, sector, technologie}, keywords [..], severity, zero_day,
patch_available, cves [..], sources [{name,title,url}], image_query (Engelse zoekterm voor Pixabay-foto,
zonder personen, bijv. "server room"), optioneel hours_ago, ig_title (korte Instagram-kop) en ig_highlight
(max. 3 woorden uit die kop die blauw gemarkeerd worden).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
ARTICLES = ROOT / "content" / "articles"
SEEN = ROOT / "content" / "seen.json"
CANDIDATES = Path("/tmp/nieuwsronde-kandidaten.json")
SEVERITIES = {"kritiek", "hoog", "middel", "laag", "info"}


def _config() -> dict:
    return yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))


def _seen() -> set[str]:
    return set(json.loads(SEEN.read_text())) if SEEN.exists() else set()


def _existing() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in ARTICLES.glob("*.json")]


def kandidaten(uren: int, aantal: int) -> None:
    sys.path.insert(0, str(ROOT))
    from pipeline.fetch import gather

    config = _config()
    config["ai"]["max_age_hours"] = uren
    existing = _existing()
    covered = {s["url"] for a in existing for s in a.get("sources", [])} | _seen()
    stories = gather(config, covered)
    out = []
    for i, s in enumerate(stories[:aantal]):
        out.append({
            "nr": i, "score": round(s.score, 1), "cves": sorted(s.cves),
            "kev": [f"{k['cveID']} ({k.get('vendorProject','')} {k.get('product','')}, toegevoegd {k.get('dateAdded','')})" for k in s.kev],
            "bronnen": [{"name": it.source, "title": it.title, "url": it.link, "datum": it.published.isoformat(),
                         "samenvatting": it.summary} for it in s.items],
        })
    CANDIDATES.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nTop {len(out)} kandidaten (details in {CANDIDATES}):")
    for c in out:
        b = c["bronnen"][0]
        flag = " [KEV]" if c["kev"] else ""
        print(f"{c['nr']:>3}  {c['score']:>5}  {len(c['bronnen'])}x  {b['name']}: {b['title']}{flag}")
    print("\nAl behandelde titels (laatste 15):")
    for a in sorted(existing, key=lambda a: a["published"], reverse=True)[:15]:
        print("   -", a["title"])


def _slug(text: str) -> str:
    import unicodedata
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:80].rstrip("-")


def opslaan(path: str) -> None:
    sys.path.insert(0, str(ROOT))
    from pipeline.fetch import load_kev

    config = _config()
    drafts = json.loads(Path(path).read_text(encoding="utf-8"))
    labels_ok = config["labels"]
    kev = load_kev(config["kev_url"])
    slugs = {a["slug"] for a in _existing()}
    seen = _seen()
    now = datetime.now(timezone.utc)
    problems, saved = [], []
    for d in drafts:
        name = d.get("title", "?")[:60]
        for f in ("title", "tldr", "meta_description", "body", "actions", "category", "labels", "keywords", "severity", "sources"):
            if not d.get(f):
                problems.append(f"{name}: veld '{f}' ontbreekt")
        if d.get("category") not in config["categories"]:
            problems.append(f"{name}: onbekend thema '{d.get('category')}'")
        if d.get("severity") not in SEVERITIES:
            problems.append(f"{name}: onbekende ernst '{d.get('severity')}'")
        for group, vals in (d.get("labels") or {}).items():
            for v in vals:
                if v not in labels_ok.get(group, []):
                    problems.append(f"{name}: label '{v}' bestaat niet in groep '{group}'")
        if not 120 <= len(d.get("meta_description", "")) <= 165:
            problems.append(f"{name}: metabeschrijving is {len(d.get('meta_description',''))} tekens (doel 140–160)")
        if len(d.get("body", "").split()) < 220:
            problems.append(f"{name}: tekst is kort ({len(d.get('body','').split())} woorden; doel 280+)")
        slug = d.get("slug") or _slug(d.get("title", ""))
        if slug in slugs:
            problems.append(f"{name}: slug '{slug}' bestaat al")
    if problems:
        print("Niet opgeslagen. Los eerst dit op:\n- " + "\n- ".join(problems))
        sys.exit(1)
    for d in drafts:
        slug = d.get("slug") or _slug(d["title"])
        pub = (now - timedelta(hours=float(d.get("hours_ago", 0)))).replace(microsecond=0)
        cves = sorted({c.upper() for c in d.get("cves", [])})
        k = [kev[c] for c in cves if c in kev]
        art = {
            "id": f"{pub:%Y%m%d}-{slug}", "slug": slug, "type": d.get("type", "nieuws"), "topic_id": None,
            "title": d["title"].strip(), "tldr": d["tldr"].strip(), "meta_description": d["meta_description"].strip(),
            "body": d["body"].strip(), "actions": d["actions"], "faq": d.get("faq", []), "category": d["category"],
            "labels": {g: d["labels"].get(g, []) for g in ("regio", "doelgroep", "sector", "technologie")},
            "keywords": d["keywords"], "image_query": d.get("image_query", ""), "image": None,
            "severity": d["severity"], "zero_day": bool(d.get("zero_day")), "patch_available": bool(d.get("patch_available")),
            "exploited": bool(k), "cves": cves,
            "kev": [{"cve": x["cveID"], "product": f"{x.get('vendorProject','')} {x.get('product','')}".strip()} for x in k],
            "sources": d["sources"], "published": pub.isoformat(), "model": "redactie",
        }
        (ARTICLES / f"{art['id']}.json").write_text(json.dumps(art, ensure_ascii=False, indent=2), encoding="utf-8")
        seen |= {s["url"] for s in d["sources"]}
        saved.append(f"{'[KEV] ' if k else ''}{art['title']}")
    SEEN.write_text(json.dumps(sorted(seen)[-5000:], indent=0))
    print(f"{len(saved)} artikelen opgeslagen:\n- " + "\n- ".join(saved))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    k = sub.add_parser("kandidaten")
    k.add_argument("--uren", type=int, default=36)
    k.add_argument("--aantal", type=int, default=25)
    o = sub.add_parser("opslaan")
    o.add_argument("bestand")
    a = p.parse_args()
    kandidaten(a.uren, a.aantal) if a.cmd == "kandidaten" else opslaan(a.bestand)


if __name__ == "__main__":
    main()
