"""Nieuws ophalen uit RSS-bronnen, dubbele verhalen samenvoegen en rangschikken."""
from __future__ import annotations

import html
import json
import re
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

import feedparser

USER_AGENT = "CyberSecurityNieuwsBot/1.0 (+https://cybersecuritynieuws.com/over)"
CVE_RE = re.compile(r"CVE-\d{4}-\d{4,7}", re.I)
STOPWORDS = set("""
a an the and or of to in on for with by from at as is are was were be been it its this that these those
new over after into via how why what who your you we our their not now more than about says said
de het een en of van in op voor met door uit aan als is zijn was waren wordt worden dit dat deze die
nieuwe na over hoe waarom wat wie je jouw we ons hun niet nu meer dan zegt
""".split())
# Voor algemene nieuwsbronnen (NU.nl, NOS, Tweakers): alleen berichten over beveiliging doorlaten.
SECURITY_TERMS = (
    "cyber", "hack", "hacker", "gehackt", "datalek", "data breach", "ransomware", "malware", "phishing", "oplichting",
    "fraude", "beveiliging", "kwetsbaarheid", "lek ", "lekken", "zero-day", "ddos", "storing door aanval", "spyware",
    "wachtwoord", "inlog", "ncsc", "privacy", "persoonsgegevens", "spoofing", "helpdeskfraude", "trojan", "botnet",
    "afpersing", "cybercrim", "security", "vulnerability", "exploit", "patch", "update tegen", "gestolen gegevens",
)


def is_security(text: str) -> bool:
    t = " " + text.lower() + " "
    return any(term in t for term in SECURITY_TERMS)


NL_TERMS = ("nederland", "dutch", "netherlands", "belgi", "belgium", "europe", "eu ", "ncsc", "rijksoverheid")


@dataclass
class Item:
    source: str
    weight: float
    title: str
    link: str
    summary: str
    published: datetime
    cves: set[str] = field(default_factory=set)

    @property
    def tokens(self) -> set[str]:
        words = re.findall(r"[a-z0-9\-]{3,}", self.title.lower())
        return {w for w in words if w not in STOPWORDS}


@dataclass
class Story:
    items: list[Item]
    score: float = 0.0
    kev: list[dict] = field(default_factory=list)

    @property
    def cves(self) -> set[str]:
        out: set[str] = set()
        for it in self.items:
            out |= it.cves
        return out

    @property
    def lead(self) -> Item:
        return max(self.items, key=lambda i: (i.weight, len(i.summary)))

    def key(self) -> str:
        return self.lead.link


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _get(url: str, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


_FETCHED = False


def _snapshot(src: dict) -> bytes | None:
    """Feed uit de branch 'bronnen' (elk uur door GitHub Actions opgehaald), voor hosts die hier geblokkeerd zijn."""
    import subprocess
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    name = snapshot_name(src)
    global _FETCHED
    try:
        if not _FETCHED:
            _FETCHED = True
            subprocess.run(["git", "fetch", "-q", "origin", "bronnen"], cwd=root, timeout=60, check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        out = subprocess.run(["git", "show", f"origin/bronnen:{name}"], cwd=root, capture_output=True, timeout=30)
        return out.stdout if out.returncode == 0 and out.stdout else None
    except Exception:
        return None


def snapshot_name(src: dict) -> str:
    return re.sub(r"[^a-z0-9]+", "-", src["name"].lower()).strip("-") + ".xml"


def fetch_source(src: dict, max_age_hours: int) -> list[Item]:
    raw = None
    try:
        raw = _get(src["url"])
    except Exception as exc:  # een kapotte bron mag de rest niet stoppen
        if src.get("snapshot"):
            raw = _snapshot(src)
        if raw is None:
            print(f"  ! {src['name']}: {exc}")
            return []
    feed = feedparser.parse(raw)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    items = []
    for e in feed.entries:
        t = e.get("published_parsed") or e.get("updated_parsed")
        published = datetime.fromtimestamp(time.mktime(t), timezone.utc) if t else datetime.now(timezone.utc)
        if published < cutoff:
            continue
        title = _clean(e.get("title", ""))
        summary = _clean(e.get("summary", "") or e.get("description", ""))[:1500]
        link = e.get("link", "")
        if not title or not link:
            continue
        if src.get("filter") == "security" and not is_security(title + " " + summary):
            continue
        items.append(Item(src["name"], float(src.get("weight", 1.0)), title, link, summary, published,
                          {c.upper() for c in CVE_RE.findall(title + " " + summary)}))
    print(f"  {src['name']}: {len(items)} recente berichten")
    return items


def _similar(a: Item, b: Item) -> bool:
    if a.cves & b.cves:
        return True
    ta, tb = a.tokens, b.tokens
    if not ta or not tb:
        return False
    return len(ta & tb) / len(ta | tb) >= 0.34


def cluster(items: list[Item]) -> list[Story]:
    """Groepeer berichten over hetzelfde onderwerp uit verschillende bronnen."""
    stories: list[Story] = []
    for it in sorted(items, key=lambda i: i.published):
        for s in stories:
            if any(_similar(it, other) for other in s.items):
                if all(o.link != it.link for o in s.items):
                    s.items.append(it)
                break
        else:
            stories.append(Story([it]))
    return stories


def load_kev(url: str) -> dict[str, dict]:
    try:
        data = json.loads(_get(url, timeout=30))
        return {v["cveID"].upper(): v for v in data.get("vulnerabilities", [])}
    except Exception as exc:
        print(f"  ! KEV-lijst niet geladen: {exc}")
        return {}


def score(story: Story) -> float:
    n_sources = len({i.source for i in story.items})
    newest = max(i.published for i in story.items)
    age_h = (datetime.now(timezone.utc) - newest).total_seconds() / 3600
    text = " ".join(i.title + " " + i.summary for i in story.items).lower()
    s = sum(i.weight for i in story.items) + 1.5 * (n_sources - 1)
    s += 1.0 if story.cves else 0
    s += 2.0 if story.kev else 0
    s += 1.0 if any(t in text for t in NL_TERMS) else 0
    s += 0.5 if any(w in text for w in ("zero-day", "0-day", "actively exploited", "ransomware", "breach", "datalek")) else 0
    return s - age_h / 24


def gather(config: dict, seen: set[str]) -> list[Story]:
    print("Bronnen ophalen...")
    items: list[Item] = []
    for src in config["sources"]:
        items += fetch_source(src, config["ai"]["max_age_hours"])
    items = [i for i in items if i.link not in seen]
    stories = cluster(items)
    kev = load_kev(config["kev_url"]) if config.get("kev_url") else {}
    for s in stories:
        s.kev = [kev[c] for c in sorted(s.cves) if c in kev]
        s.score = score(s)
    stories.sort(key=lambda s: s.score, reverse=True)
    print(f"{len(items)} nieuwe berichten -> {len(stories)} unieke verhalen")
    return stories
