"""Schrijft met Claude Nederlandstalige artikelen: nieuws (op basis van bronberichten) en
evergreen-blogs (tijdloze uitleg op basis van een onderwerp uit de contentkalender)."""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone

import anthropic

from .fetch import Story

BASE_RULES = """Je bent hoofdredacteur van {name}, een Nederlandstalige site over cybersecurity voor
thuisgebruikers, het mkb en IT-beheerders. Je schrijft in helder, correct Nederlands.

Algemene regels:
- Schrijf in eigen woorden. Neem NOOIT zinnen letterlijk over uit bronnen.
- Verzin geen feiten, cijfers, namen, data, CVE-nummers of URL's. Als iets onzeker is, zeg dat.
- Toon: zakelijk, feitelijk, toegankelijk. Leg vaktermen kort uit bij het eerste gebruik. Geen sensatie, geen clickbait.
- Korte alinea's (2–4 zinnen). Gebruik opsommingen waar dat de leesbaarheid helpt.

GEO en SEO (zodat Google én AI-zoekmachines als ChatGPT en Perplexity de tekst goed begrijpen en citeren):
- Begin de body met een alinea die de kernvraag direct en volledig beantwoordt (het 'antwoord eerst').
- Gebruik tussenkopjes (##) die vragen of duidelijke onderwerpen zijn, zoals mensen ze zouden zoeken.
- Geef heldere definities in één zin ("X is ...") die los te citeren zijn.
- Verwerk het hoofdzoekwoord natuurlijk in de kop, de eerste alinea en minstens één tussenkop. Geen keyword-stuffing.
- meta_description: 140–160 tekens, wervend maar feitelijk, met het hoofdzoekwoord.
- faq: 3–5 vragen die lezers echt zoeken, elk met een kort, zelfstandig antwoord (1–3 zinnen).

Links (Markdown-syntax [tekst](url)):
- Interne links: link 2–4 keer naar passende artikelen uit de lijst 'Bestaande artikelen', met de exacte URL uit die lijst
  en een beschrijvende linktekst (nooit 'klik hier'). Alleen als het echt past; liever minder dan geforceerd.
- Externe links: alleen naar de bron-URL's die je krijgt en naar deze betrouwbare sites: {trusted}.
  Link naar de hoofdpagina van zo'n site als je niet zeker weet dat een diepere URL bestaat.
- Andere links worden automatisch verwijderd, dus verzin geen URL's.

Kies precies één hoofdthema en alleen labels uit de gegeven lijsten."""

NEWS_RULES = """
Dit is een NIEUWSARTIKEL op basis van de aangeleverde bronberichten:
- Gebruik alleen feiten uit de bronnen. Citeer hooguit een kort zinsdeel tussen aanhalingstekens, met naam van de bron.
- Kop: maximaal ~90 tekens, informatief. TL;DR: 1–2 zinnen met de kern.
- Body: 300–550 woorden, 2–3 tussenkopjes. Begin niet met een kopje. Noem de bron(nen) in de tekst ('meldt BleepingComputer').
- 'Wat moet je doen?': 2–5 concrete, uitvoerbare stappen.
- Zet newsworthy op false bij reclame, webinars, sponsored content, vacatures, podcasts zonder nieuws of te weinig informatie."""

EVERGREEN_RULES = """
Dit is een EVERGREEN-GIDS: een tijdloos, diepgaand uitlegartikel dat maanden relevant blijft.
- Schrijf vanuit algemeen geaccepteerde, stabiele kennis. Noem geen actuele incidenten, specifieke recente cijfers of
  wetsdata waarvan je niet zeker bent. Bij wetgeving: beschrijf de hoofdlijnen en verwijs naar de officiële bron.
- Kop: maximaal ~70 tekens, met het zoekwoord. TL;DR: 1–2 zinnen die de vraag beantwoorden.
- Body: 900–1400 woorden, 4–6 tussenkopjes, met praktische voorbeelden uit Nederland/België waar passend.
- 'Wat moet je doen?': 4–7 concrete stappen (een checklist die lezers direct kunnen afwerken).
- Zet newsworthy op true, severity op 'info' (of hoger als het onderwerp dat echt rechtvaardigt), zero_day en patch_available op false."""


def slugify(text: str, max_len: int = 70) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:max_len].rsplit("-", 1)[0] if len(text) > max_len else text


def _tool(config: dict) -> dict:
    labels = config["labels"]
    arr = lambda opts: {"type": "array", "items": {"type": "string", "enum": opts}}
    props = {
        "newsworthy": {"type": "boolean"},
        "title": {"type": "string"},
        "tldr": {"type": "string"},
        "meta_description": {"type": "string"},
        "body_markdown": {"type": "string"},
        "actions": {"type": "array", "items": {"type": "string"}},
        "faq": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "properties": {"q": {"type": "string"}, "a": {"type": "string"}}, "required": ["q", "a"]}},
        "category": {"type": "string", "enum": list(config["categories"].keys())},
        "regio": arr(labels["regio"]),
        "doelgroep": arr(labels["doelgroep"]),
        "sector": arr(labels["sector"]),
        "technologie": arr(labels["technologie"]),
        "severity": {"type": "string", "enum": ["kritiek", "hoog", "middel", "laag", "info"]},
        "zero_day": {"type": "boolean"},
        "patch_available": {"type": "boolean"},
        "keywords": {"type": "array", "items": {"type": "string"}, "description": "3-6 zoekwoorden"},
        "image_query": {"type": "string", "description": "Engelse zoekterm van 2-4 woorden voor een passende, sfeervolle stockfoto. "
                        "Generiek en visueel (bijv. 'hacker laptop dark', 'hospital corridor', 'smartphone sms'); geen merknamen of logo's."},
    }
    return {
        "name": "publiceer_artikel",
        "description": "Lever het afgeronde artikel aan voor publicatie. Roep deze tool altijd precies één keer aan.",
        "strict": True,
        "input_schema": {"type": "object", "additionalProperties": False,
                         "properties": props, "required": list(props)},
    }


def _internal_block(internal: list[dict]) -> str:
    if not internal:
        return "### Bestaande artikelen\n(nog geen – sla interne links over)"
    lines = [f"- {a['title']} – {a['url']}" for a in internal]
    return "### Bestaande artikelen (voor interne links)\n" + "\n".join(lines)


def _story_prompt(story: Story, internal: list[dict]) -> str:
    parts = []
    for i, it in enumerate(story.items, 1):
        parts.append(f"### Bron {i}: {it.source} ({it.published:%Y-%m-%d %H:%M} UTC)\nTitel: {it.title}\nURL: {it.link}\nSamenvatting: {it.summary}")
    if story.kev:
        kev = "\n".join(f"- {k['cveID']}: {k.get('vendorProject','')} {k.get('product','')} – {k.get('vulnerabilityName','')}"
                        f" (toegevoegd {k.get('dateAdded','')}, deadline federale instanties {k.get('dueDate','')})" for k in story.kev)
        parts.append("### Officiële bevestiging\nDeze CVE's staan op de CISA-lijst van actief misbruikte kwetsbaarheden (KEV):\n" + kev)
    parts.append(_internal_block(internal))
    return "Schrijf een nieuwsartikel over dit nieuws:\n\n" + "\n\n".join(parts)


def _call(client: anthropic.Anthropic, config: dict, system: str, prompt: str) -> dict | None:
    tool = _tool(config)
    # Nieuwere modellen (o.a. claude-sonnet-5-5) ondersteunen geen geforceerde tool_choice meer.
    # Daarom 'auto' + strict schema + expliciete opdracht. 'fallbacks' laat de API bij een
    # (onterechte) weigering automatisch een ander model proberen.
    msg = client.beta.messages.create(
        model=config["ai"]["model"],
        max_tokens=16000,
        system=system,
        tools=[tool],
        tool_choice={"type": "auto"},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{"role": "user", "content": prompt + f"\n\nLever het resultaat uitsluitend aan via de tool '{tool['name']}'."}],
    )
    if msg.stop_reason == "refusal":
        print(f"  ! model weigerde dit onderwerp ({getattr(msg.stop_details, 'category', None)})")
        return None
    return next((b.input for b in msg.content if b.type == "tool_use"), None)


def _system(config: dict, extra: str) -> str:
    return BASE_RULES.format(name=config["site"]["name"], trusted=", ".join(config.get("trusted_domains", []))) + extra


def _article(config: dict, data: dict, *, kind: str, sources: list[dict], cves: list[str] | None = None,
             kev: list[dict] | None = None, topic: dict | None = None) -> dict:
    now = datetime.now(timezone.utc)
    slug = topic["id"] if topic else slugify(data["title"])
    return {
        "id": f"{now:%Y%m%d}-{slug}",
        "slug": slug,
        "type": kind,
        "topic_id": topic["id"] if topic else None,
        "title": data["title"].strip(),
        "tldr": data["tldr"].strip(),
        "meta_description": data.get("meta_description", "").strip(),
        "body": data["body_markdown"].strip(),
        "actions": data.get("actions", []),
        "faq": [f for f in data.get("faq", []) if f.get("q") and f.get("a")],
        "category": topic["category"] if topic else data["category"],
        "labels": {k: data.get(k, []) for k in ("regio", "doelgroep", "sector", "technologie")},
        "keywords": data.get("keywords", []),
        "image_query": data.get("image_query", ""),
        "image": None,
        "severity": data["severity"],
        "zero_day": bool(data.get("zero_day")) and kind == "nieuws",
        "patch_available": bool(data.get("patch_available")) and kind == "nieuws",
        "exploited": bool(kev),
        "cves": cves or [],
        "kev": [{"cve": k["cveID"], "product": f"{k.get('vendorProject','')} {k.get('product','')}".strip()} for k in (kev or [])],
        "sources": sources,
        "published": now.isoformat(timespec="seconds"),
        "model": config["ai"]["model"],
    }


def write_article(client: anthropic.Anthropic, config: dict, story: Story, internal: list[dict] | None = None) -> dict | None:
    data = _call(client, config, _system(config, NEWS_RULES), _story_prompt(story, internal or []))
    if not data or not data.get("newsworthy"):
        return None
    if len(data.get("body_markdown", "").split()) < 150:
        return None  # te dun, niet publiceren
    return _article(config, data, kind="nieuws",
                    sources=[{"name": i.source, "title": i.title, "url": i.link} for i in story.items],
                    cves=sorted(story.cves), kev=story.kev)


def write_evergreen(client: anthropic.Anthropic, config: dict, topic: dict, internal: list[dict] | None = None) -> dict | None:
    prompt = (f"Schrijf een evergreen-gids.\n\nWerktitel: {topic['title']}\nHoofdzoekwoord: {topic['keyword']}\n"
              f"Hoofdthema: {topic['category']}\n\n" + _internal_block(internal or []))
    data = _call(client, config, _system(config, EVERGREEN_RULES), prompt)
    if not data or len(data.get("body_markdown", "").split()) < 600:
        return None
    return _article(config, data, kind="gids", sources=[], topic=topic)
