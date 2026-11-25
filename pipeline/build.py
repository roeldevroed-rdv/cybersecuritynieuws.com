"""Bouwt de statische website in de map dist/ op basis van content/articles/*.json."""
from __future__ import annotations

import json
import math
import re
import shutil
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape

import markdown
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"


def _asset_version() -> str:
    """Korte hash van stijl, scripts en beeldgenerator: verandert iets, dan laden browsers meteen de nieuwe versie."""
    import hashlib
    h = hashlib.sha1()
    for f in sorted([*(ROOT / "static").rglob("*"), ROOT / "pipeline" / "covers.py", *(ROOT / "assets").glob("*.png")]):
        if f.is_file():
            h.update(f.read_bytes())
    return h.hexdigest()[:8]


ASSET_V = _asset_version()
MONTHS = ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus",
          "september", "oktober", "november", "december"]
SEVERITY = {"kritiek": "Kritiek", "hoog": "Hoog", "middel": "Middel", "laag": "Laag", "info": "Info"}


def label_slug(text: str) -> str:
    text = text.lower().replace("ë", "e").replace("&", "en")
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def nl_date(dt: datetime, with_time: bool = False) -> str:
    local = dt.astimezone(timezone(timedelta(hours=1)))  # CET; prima voor weergave
    s = f"{local.day} {MONTHS[local.month - 1]} {local.year}"
    return s + f", {local:%H:%M}" if with_time else s


def ago(dt: datetime) -> str:
    mins = int((datetime.now(timezone.utc) - dt).total_seconds() // 60)
    if mins < 60:
        return f"{max(mins, 1)} min geleden"
    if mins < 60 * 24:
        return f"{mins // 60} uur geleden"
    days = mins // 1440
    return "gisteren" if days == 1 else (f"{days} dagen geleden" if days < 7 else nl_date(dt))


def load_articles() -> list[dict]:
    """Laadt alle artikelen. Zolang er nog geen echte artikelen zijn, worden de
    (als fictief gemarkeerde) voorbeeldartikelen uit content/voorbeelden/ gebruikt."""
    files = list((ROOT / "content" / "articles").glob("*.json"))
    if not files:
        files = list((ROOT / "content" / "voorbeelden").glob("*.json"))
        if files:
            print("Nog geen echte artikelen: voorbeeldartikelen worden gebruikt.")
    arts = []
    for p in files:
        a = json.loads(p.read_text(encoding="utf-8"))
        if "offset_hours" in a:  # voorbeeldartikelen: datum relatief aan het bouwmoment
            dt = datetime.now(timezone.utc) - timedelta(hours=a["offset_hours"])
            a["published"] = dt.isoformat(timespec="seconds")
        a["dt"] = datetime.fromisoformat(a["published"])
        a["url"] = f"/artikel/{a['slug']}/"
        a.setdefault("example", False)
        a.setdefault("type", "nieuws")
        a.setdefault("faq", [])
        a.setdefault("image", None)
        a.setdefault("meta_description", "")
        a.setdefault("updated", None)
        a["updated_dt"] = datetime.fromisoformat(a["updated"]) if a.get("updated") else None
        # Ruwe HTML in door AI geschreven tekst wordt niet uitgevoerd (alleen Markdown).
        a["html"] = markdown.markdown(a["body"].replace("<", "&lt;"), extensions=["extra", "sane_lists"])
        a["reading_min"] = max(1, round(len(a["body"].split()) / 200))
        a["all_labels"] = [l for vals in a["labels"].values() for l in vals]
        arts.append(a)
    return sorted(arts, key=lambda a: a["dt"], reverse=True)


LINK_RE = re.compile(r'<a href="([^"]*)"([^>]*)>(.*?)</a>', re.S)


def _domain_ok(host: str, allowed: set[str]) -> bool:
    host = host.lower().split(":")[0]
    host = host[4:] if host.startswith("www.") else host
    return any(host == d or host.endswith("." + d) for d in allowed)


def clean_links(a: dict, valid_urls: set[str], trusted: set[str]) -> None:
    """Houdt alleen links over die kloppen: interne links naar bestaande pagina's, externe links naar
    de bronnen van het artikel of naar betrouwbare domeinen. Andere links worden gewone tekst."""
    from urllib.parse import urlparse
    allowed = set(trusted) | {urlparse(s["url"]).netloc.lower().removeprefix("www.") for s in a.get("sources", [])}
    if a.get("sponsor", {}).get("url"):
        allowed.add(urlparse(a["sponsor"]["url"]).netloc.lower().removeprefix("www."))
    ext_rel = "sponsored noopener" if a.get("type") == "partner" else "noopener"
    stats = {"intern": 0, "extern": 0, "verwijderd": 0}

    def fix(m: re.Match) -> str:
        href, text = m.group(1), m.group(3)
        if href.startswith("/"):
            path = href.split("#")[0]
            path = path if path.endswith("/") else path + "/"
            if path in valid_urls and path != a["url"]:
                stats["intern"] += 1
                return f'<a href="{path}">{text}</a>'
        elif href.startswith("https://") and _domain_ok(urlparse(href).netloc, allowed):
            stats["extern"] += 1
            return f'<a href="{href}" rel="{ext_rel}" target="_blank">{text}</a>'
        stats["verwijderd"] += 1
        return text

    a["html"] = LINK_RE.sub(fix, a["html"])
    a["link_stats"] = stats


def relatedness(a: dict, b: dict) -> float:
    s = 3.0 if a["category"] == b["category"] else 0.0
    s += 2.0 * len(set(a["cves"]) & set(b["cves"]))
    s += len(set(a["all_labels"]) & set(b["all_labels"])) * 0.7
    s += len({k.lower() for k in a.get("keywords", [])} & {k.lower() for k in b.get("keywords", [])})
    s += 1.0 if b.get("type") == "gids" else 0.0
    return s


def threat_level(arts: list[dict]) -> dict:
    """Dreigingsniveau op basis van de afgelopen 7 dagen: actief misbruikte en kritieke kwetsbaarheden."""
    week = [a for a in arts if a["dt"] > datetime.now(timezone.utc) - timedelta(days=7) and a.get("type") != "gids"]
    exploited = sum(1 for a in week if a["exploited"] or a["zero_day"])
    critical = sum(1 for a in week if a["severity"] == "kritiek")
    score = exploited * 2 + critical
    levels = [(0, "laag", "Laag", "Geen bijzondere dreigingen. Houd je normale updateritme aan."),
              (3, "verhoogd", "Verhoogd", "Er worden kwetsbaarheden actief misbruikt. Controleer of je de genoemde updates hebt."),
              (7, "hoog", "Hoog", "Meerdere kritieke lekken worden actief misbruikt. Geef updates deze week voorrang."),
              (12, "kritiek", "Kritiek", "Grootschalig misbruik van kritieke lekken. Patch direct en controleer op inbraak.")]
    level = [l for l in levels if score >= l[0]][-1]
    return {"key": level[1], "name": level[2], "advice": level[3], "exploited": exploited, "critical": critical, "index": levels.index(level)}


def active_ads(config: dict) -> dict[str, list[dict]]:
    today = datetime.now(timezone.utc).date().isoformat()
    out: dict[str, list[dict]] = defaultdict(list)
    for ad in config.get("ads") or []:
        if str(ad.get("van", "0000")) <= today <= str(ad.get("tot", "9999")):
            out[ad.get("slot", "sidebar")].append(ad)
    return out


def product_matches(a: dict, terms: list[str]) -> bool:
    text = " ".join([a["title"], a["tldr"], " ".join(a.get("keywords", [])), " ".join(k.get("product", "") for k in a.get("kev", []))]).lower()
    return any(t in text for t in terms)


class Site:
    def __init__(self, config: dict):
        self.c = config
        self.env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=select_autoescape(["html"]))
        self.env.filters.update(nl_date=nl_date, ago=ago, label_slug=label_slug,
                                faq_entity=lambda f: {"@type": "Question", "name": f["q"],
                                                      "acceptedAnswer": {"@type": "Answer", "text": f["a"]}})
        self.env.globals.update(asset_v=ASSET_V, site=config["site"], categories=config["categories"], severity_names=SEVERITY,
                                year=datetime.now().year, now=datetime.now(timezone.utc))
        self.urls: list[str] = []

    def page(self, path: str, template: str, **ctx) -> None:
        out = DIST / path.strip("/") / "index.html" if not path.endswith(".html") else DIST / path.strip("/")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(self.env.get_template(template).render(path=path, **ctx), encoding="utf-8")
        if path.endswith("/"):
            self.urls.append(path)

    def listing(self, base: str, title: str, items: list[dict], intro: str = "", **ctx) -> None:
        per = self.c["site"]["articles_per_page"]
        pages = max(1, math.ceil(len(items) / per))
        for n in range(1, pages + 1):
            path = base if n == 1 else f"{base}pagina/{n}/"
            self.page(path, "list.html", title=title, intro=intro, items=items[(n - 1) * per:n * per],
                      page_num=n, pages=pages, base=base, **ctx)


def build(config: dict) -> None:
    arts = load_articles()
    if DIST.exists():
        shutil.rmtree(DIST)
    shutil.copytree(ROOT / "static", DIST / "static")
    site = Site(config)
    from .covers import make_cover
    for a in arts:
        make_cover(a, config["categories"], DIST / "og" / f"{a['slug']}.png", config["site"]["name"])
        make_cover(a, config["categories"], DIST / "beeld" / f"{a['slug']}.webp", config["site"]["name"], with_title=False)
        a["cover"] = f"/og/{a['slug']}.png?v={ASSET_V}"           # met titel: voor delen op sociale media
        a["art"] = f"/beeld/{a['slug']}.webp?v={ASSET_V}"          # zonder titel: voor op de site
        a["thumb"] = a["image"]["url"] if a.get("image") else a["art"]
    red = config.get("redactie") or {}
    site.env.globals.update(
        redactie=red, editor=red.get("hoofdredacteur") or f"Redactie {config['site']['name']}",
        threat=threat_level(arts), ads=active_ads(config), forms=config.get("forms") or {},
        analytics=config.get("analytics") or {}, products=config.get("products") or [],
        zoekmachines=config.get("zoekmachines") or {})
    valid = {a["url"] for a in arts} | {f"/thema/{c}/" for c in config["categories"]} | {"/gidsen/", "/actief-misbruikt/", "/weekoverzicht/", "/over/", "/redactie/", "/contact/",
             "/adverteren/", "/nieuwsbrief/", "/ransomware-tracker/", "/patch-tuesday/", "/producten/",
             "/privacy/", "/cookies/", "/colofon/"} | {f"/product/{p['slug']}/" for p in config.get("products") or []}
    trusted = set(config.get("trusted_domains", []))
    totals = defaultdict(int)
    for a in arts:
        clean_links(a, valid, trusted)
        for k, v in a["link_stats"].items():
            totals[k] += v
    print(f"Links: {totals['intern']} intern, {totals['extern']} extern, {totals['verwijderd']} ongeldig verwijderd")
    exploited = [a for a in arts if a["exploited"] or a["zero_day"]]
    site.env.globals.update(ticker=exploited[:6], latest=[a for a in arts if a.get("type") != "gids"][:6],
                            guides=[a for a in arts if a.get("type") == "gids"][:6])

    by_cat, by_label = defaultdict(list), defaultdict(list)
    for a in arts:
        by_cat[a["category"]].append(a)
        for l in a["all_labels"]:
            by_label[l].append(a)
    site.env.globals["cat_counts"] = {k: len(v) for k, v in by_cat.items()}

    # Voorpagina: hoofdverhaal = meest urgente van de laatste 48 uur
    recent = [a for a in arts if a["dt"] > datetime.now(timezone.utc) - timedelta(hours=48)] or arts[:1]
    rank = {"kritiek": 4, "hoog": 3, "middel": 2, "laag": 1, "info": 0}
    hero = max(recent, key=lambda a: (a["exploited"], rank[a["severity"]], a["dt"])) if recent else None
    rest = [a for a in arts if a is not hero]
    nl = [a for a in arts if {"Nederland", "België"} & set(a["labels"].get("regio", []))]
    site.page("/", "home.html", hero=hero, items=rest[:12], nl_items=nl[:5], exploited=exploited[:5],
              by_cat={k: v[:3] for k, v in by_cat.items()}, more=len(rest) > 12)
    if len(rest) > 12:
        site.listing("/nieuws/", "Al het nieuws", arts)

    for a in arts:
        related = sorted((b for b in arts if b is not a), key=lambda b: (relatedness(a, b), b["dt"]), reverse=True)[:4]
        site.page(a["url"], "article.html", a=a, related=related)

    for slug, name in config["categories"].items():
        site.listing(f"/thema/{slug}/", name, by_cat.get(slug, []), kind="Thema")
    for label, items in by_label.items():
        site.listing(f"/label/{label_slug(label)}/", label, items, kind="Label")
    site.listing("/actief-misbruikt/", "Actief misbruikt", exploited, kind="Urgent",
                 intro="Kwetsbaarheden die aanvallers nu al misbruiken (bevestigd via de CISA KEV-lijst) en zero-days. Patch deze als eerste.")
    week = [a for a in arts if a["dt"] > datetime.now(timezone.utc) - timedelta(days=7)]
    week_by_cat = {k: [a for a in week if a["category"] == k] for k in config["categories"]}
    guides = [a for a in arts if a.get("type") == "gids"]
    site.listing("/gidsen/", "Gidsen", guides, kind="Uitgelegd",
                 intro="Tijdloze uitleg en stappenplannen: van phishing herkennen tot NIS2. Praktisch, in gewoon Nederlands.")
    site.page("/weekoverzicht/", "week.html", week=week, week_by_cat=week_by_cat)
    site.page("/zoeken/", "search.html")
    # Vertrouwen, contact, verdienmodel
    for path, tpl in [("/redactie/", "redactie.html"), ("/contact/", "contact.html"), ("/adverteren/", "adverteren.html"),
                      ("/nieuwsbrief/", "nieuwsbrief.html"), ("/privacy/", "privacy.html"), ("/cookies/", "cookies.html"),
                      ("/colofon/", "colofon.html")]:
        site.page(path, tpl, stats={"artikelen": len(arts), "gidsen": len(guides)})
    # Bevestigingspagina's nieuwsbrief (Brevo dubbele opt-in); niet in sitemap
    site.page("/nieuwsbrief/bijna-klaar/", "nieuwsbrief_status.html", stap="bijna", kop="Bijna klaar: bevestig je aanmelding",
              intro="We hebben je een mail gestuurd. Klik op de link daarin om je aanmelding te bevestigen.")
    site.page("/nieuwsbrief/welkom/", "nieuwsbrief_status.html", stap="welkom", kop="Welkom! Je bent aangemeld",
              intro="Bedankt voor het bevestigen. De eerstvolgende nieuwsbrief komt naar je toe.")
    site.urls = [u for u in site.urls if u not in ("/nieuwsbrief/bijna-klaar/", "/nieuwsbrief/welkom/")]
    # Productpagina's
    prod_items = []
    for p in config.get("products") or []:
        items = [a for a in arts if product_matches(a, p["match"])]
        prod_items.append((p, items))
        site.listing(f"/product/{p['slug']}/", f"Beveiligingsnieuws over {p['name']}", items, kind="Product",
                     intro=f"Alle kwetsbaarheden, updates en incidenten rond {p['name']}, met per bericht wat je moet doen.")
    site.page("/producten/", "producten.html", prod_items=prod_items)
    # Ransomware-tracker en Patch Tuesday
    rw = [a for a in arts if a["category"] == "ransomware" or "ransomware" in (a["title"] + " " + " ".join(a.get("keywords", []))).lower()]
    site.page("/ransomware-tracker/", "ransomware.html", rw=[a for a in rw if a.get("type") != "gids"], guides_rw=[a for a in rw if a.get("type") == "gids"])
    pt = [a for a in arts if "patch tuesday" in (a["title"] + " " + " ".join(a.get("keywords", []))).lower()]
    site.listing("/patch-tuesday/", "Patch Tuesday", pt, kind="Maandelijks",
                 intro="Elke tweede dinsdag van de maand brengen Microsoft, Adobe en anderen hun beveiligingsupdates uit. Hier vind je per maand wat je moet installeren en wat al wordt misbruikt.")
    site.page("/over/", "about.html", labels=config["labels"])
    site.page("/404.html", "404.html")

    # Zoekindex, RSS, sitemap, robots
    (DIST / "search.json").write_text(json.dumps([
        {"t": a["title"], "u": a["url"], "d": a["tldr"], "c": config["categories"].get(a["category"], ""),
         "l": a["all_labels"] + a["cves"], "p": a["published"][:10]} for a in arts], ensure_ascii=False))
    write_rss(config, arts[:40])
    url = config["site"]["url"].rstrip("/")
    lastmod = {a["url"]: a["published"][:10] for a in arts}
    (DIST / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                                      + "".join(f"  <url><loc>{url}{escape(u)}</loc>" + (f"<lastmod>{lastmod[u]}</lastmod>" if u in lastmod else "")
                                                + "</url>\n" for u in site.urls) + "</urlset>\n")
    write_llms_txt(config, arts)
    write_news_sitemap(config, arts)
    key = (config.get("zoekmachines") or {}).get("indexnow_key")
    if key:  # IndexNow-sleutelbestand in de hoofdmap
        (DIST / f"{key}.txt").write_text(key)
    (DIST / "CNAME").write_text(config["site"]["domain"] + "\n")  # eigen domein op GitHub Pages
    (DIST / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {url}/sitemap.xml\nSitemap: {url}/news-sitemap.xml\n")
    print(f"Site gebouwd: {len(arts)} artikelen, {len(site.urls)} pagina's -> dist/")


def write_news_sitemap(config: dict, arts: list[dict]) -> None:
    """Google Nieuws-sitemap: nieuwsartikelen van de laatste 48 uur."""
    url, name = config["site"]["url"].rstrip("/"), config["site"]["name"]
    recent = [a for a in arts if a.get("type") == "nieuws" and a["dt"] > datetime.now(timezone.utc) - timedelta(hours=48)]
    items = "".join(
        f"<url><loc>{url}{a['url']}</loc><news:news><news:publication><news:name>{escape(name)}</news:name>"
        f"<news:language>nl</news:language></news:publication><news:publication_date>{a['published']}</news:publication_date>"
        f"<news:title>{escape(a['title'])}</news:title></news:news></url>\n" for a in recent)
    (DIST / "news-sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
                                           'xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">\n' + items + "</urlset>\n", encoding="utf-8")


def write_llms_txt(config: dict, arts: list[dict]) -> None:
    """llms.txt: een overzicht voor AI-zoekmachines (GEO) van wat er op de site staat."""
    s, url = config["site"], config["site"]["url"].rstrip("/")
    lines = [f"# {s['name']}", "", f"> {s['description']}", "",
             "Nederlandstalige cybersecuritysite. Elk artikel heeft een TL;DR, concrete stappen ('Wat moet je doen?') en bronvermelding.", ""]
    guides = [a for a in arts if a.get("type") == "gids"]
    if guides:
        lines += ["## Gidsen", ""] + [f"- [{a['title']}]({url}{a['url']}): {a['tldr']}" for a in guides] + [""]
    lines += ["## Laatste nieuws", ""] + [f"- [{a['title']}]({url}{a['url']}): {a['tldr']}" for a in arts if a.get("type") != "gids"][:50]
    lines += ["", "## Over", "", f"- [Werkwijze en AI-transparantie]({url}/over/)", f"- [RSS-feed]({url}/rss.xml)", ""]
    (DIST / "llms.txt").write_text("\n".join(lines), encoding="utf-8")


def write_rss(config: dict, arts: list[dict]) -> None:
    s, url = config["site"], config["site"]["url"].rstrip("/")
    items = "".join(
        f"<item><title>{escape(a['title'])}</title><link>{url}{a['url']}</link><guid>{url}{a['url']}</guid>"
        f"<pubDate>{format_datetime(a['dt'])}</pubDate><category>{escape(config['categories'].get(a['category'], ''))}</category>"
        f"<description>{escape(a['tldr'])}</description></item>\n" for a in arts)
    (DIST / "rss.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel><title>{escape(s["name"])}</title>'
        f"<link>{url}/</link><description>{escape(s['description'])}</description><language>nl</language>\n{items}</channel></rss>\n",
        encoding="utf-8")
