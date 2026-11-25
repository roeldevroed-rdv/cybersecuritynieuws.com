"""Wekelijkse nieuwsbrief en Brevo-mails in de huisstijl.

  python -m tools.nieuwsbrief voorbeeld            # schrijft /tmp/nieuwsbrief.html (laatste 7 dagen)
  python -m tools.nieuwsbrief concept              # zet de nieuwsbrief als CONCEPT-campagne klaar in Brevo
  python -m tools.nieuwsbrief systeemmails         # zet de Brevo-standaardmails (bevestigen, afmelden) in het Nederlands

De Brevo-sleutel wordt door de netwerkproxy van de omgeving toegevoegd (header api-key);
er wordt nooit automatisch verstuurd: de eigenaar drukt zelf op Verzenden in Brevo."""
from __future__ import annotations

import html
import json
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
SITE = CONFIG["site"]["url"].rstrip("/")
LIST_ID = 2
SENDER = {"name": "CyberSecurityNieuws", "email": "info@cybersecuritynieuws.com"}
BLUE, INK, MUTED, RED, LINE, BG = "#0a7ee8", "#16171a", "#5b606a", "#dc2626", "#e4e1db", "#f4f6f9"
FONT = "-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"


def brevo(method: str, path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(f"https://api.brevo.com/v3{path}", method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"api-key": "proxy-injected", "content-type": "application/json", "accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
    return json.loads(raw) if raw else {}


def shell(inner: str, preheader: str = "", footer: str = "") -> str:
    """Mail-omhulsel: tabellen + inline stijlen (werkt in Outlook, Gmail, Apple Mail)."""
    e = html.escape
    return f"""<!doctype html><html lang="nl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CyberSecurityNieuws</title></head>
<body style="margin:0;padding:0;background:{BG};">
<div style="display:none;max-height:0;overflow:hidden;opacity:0">{e(preheader)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{BG};"><tr><td align="center" style="padding:24px 12px;">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="width:100%;max-width:600px;background:#ffffff;border-radius:12px;border:1px solid {LINE};">
<tr><td style="padding:24px 32px 18px;border-bottom:3px solid {BLUE};">
<a href="{SITE}/"><img src="{SITE}/static/img/mail-logo.png" width="220" alt="CyberSecurityNieuws.com" style="display:block;border:0;width:220px;height:auto;"></a>
</td></tr>
{inner}
<tr><td style="padding:20px 32px 28px;border-top:1px solid {LINE};font:13px/1.6 {FONT};color:{MUTED};">
{footer}CyberSecurityNieuws.com · Het belangrijkste cybersecuritynieuws in helder Nederlands<br>
<a href="{SITE}/" style="color:{BLUE};">Website</a> · <a href="{SITE}/privacy/" style="color:{BLUE};">Privacy</a>
</td></tr></table></td></tr></table></body></html>"""


def p(text: str, size: int = 16, color: str = INK) -> str:
    return f'<p style="margin:0 0 14px;font:{size}px/1.6 {FONT};color:{color};">{text}</p>'


def button(url: str, label: str) -> str:
    return (f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin:8px 0 18px;"><tr>'
            f'<td style="background:{BLUE};border-radius:8px;"><a href="{url}" style="display:inline-block;padding:13px 22px;'
            f'font:700 16px {FONT};color:#ffffff;text-decoration:none;">{label}</a></td></tr></table>')


# ---------------------------------------------------------------- systeemmails

def systeemmails() -> None:
    optin = shell(f"""<tr><td style="padding:28px 32px 8px;">
<h1 style="margin:0 0 14px;font:700 24px/1.3 {FONT};color:{INK};">Bevestig je aanmelding</h1>
{p("Bedankt voor je aanmelding voor de nieuwsbrief van CyberSecurityNieuws. Klik op de knop hieronder om te bevestigen dat dit jouw e-mailadres is.")}
{button("{{ doubleoptin }}", "Ja, ik wil de nieuwsbrief ontvangen")}
{p("Elke week krijg je de lekken die je moet patchen, de grootste incidenten en één praktische tip. Afmelden kan altijd met één klik.", 15, MUTED)}
{p("Heb je je niet zelf aangemeld? Dan kun je deze mail negeren; je ontvangt dan niets van ons.", 14, MUTED)}
</td></tr>""", "Nog één klik: bevestig je aanmelding")
    afmeld = shell(f"""<tr><td style="padding:28px 32px 8px;">
<h1 style="margin:0 0 14px;font:700 24px/1.3 {FONT};color:{INK};">Je bent afgemeld</h1>
{p("Je ontvangt de nieuwsbrief van CyberSecurityNieuws niet meer. Jammer dat je gaat!")}
{p(f'Het nieuws blijft natuurlijk gewoon te lezen op <a href="{SITE}/" style="color:{BLUE};">cybersecuritynieuws.com</a>. Per ongeluk afgemeld? <a href="{SITE}/nieuwsbrief/" style="color:{BLUE};">Meld je opnieuw aan</a>.', 15, MUTED)}
</td></tr>""", "Je bent afgemeld voor de nieuwsbrief")
    welkom = shell(f"""<tr><td style="padding:28px 32px 8px;">
<h1 style="margin:0 0 14px;font:700 24px/1.3 {FONT};color:{INK};">Welkom bij de nieuwsbrief!</h1>
{p("Je aanmelding is bevestigd. Elke week krijg je van ons de kwetsbaarheden die je moet patchen, de grootste incidenten en één praktische tip.")}
{p("Tip: zet info@cybersecuritynieuws.com in je contacten, dan komt de nieuwsbrief niet in je spam terecht.", 15, MUTED)}
{button(SITE + "/", "Lees het laatste nieuws")}
</td></tr>""", "Je aanmelding is bevestigd")
    sender = {"id": 1}
    for tid, name, subject, body in [
        (1, "Bevestiging aanmelding (dubbele opt-in, NL)", "Bevestig je aanmelding voor de nieuwsbrief", optin),
        (3, "Welkom na bevestiging (NL)", "Welkom bij de nieuwsbrief van CyberSecurityNieuws", welkom),
        (2, "Eenvoudige bevestiging (NL)", "Welkom bij de nieuwsbrief van CyberSecurityNieuws", welkom),
        (4, "Afgemeld (NL)", "Je bent afgemeld voor de nieuwsbrief", afmeld),
    ]:
        brevo("PUT", f"/smtp/templates/{tid}", {"templateName": name, "subject": subject, "htmlContent": body,
                                                "sender": sender, "isActive": True})
        print(f"sjabloon {tid} bijgewerkt: {name}")


# ---------------------------------------------------------------- weekbrief

def recent_articles(days: int = 7) -> list[dict]:
    arts = []
    for f in (ROOT / "content" / "articles").glob("*.json"):
        a = json.loads(f.read_text(encoding="utf-8"))
        a["dt"] = datetime.fromisoformat(a["published"].replace("Z", "+00:00"))
        arts.append(a)
    arts.sort(key=lambda a: a["dt"], reverse=True)
    since = datetime.now(timezone.utc) - timedelta(days=days)
    news = [a for a in arts if a.get("type", "nieuws") == "nieuws" and a["dt"] >= since]
    guides = [a for a in arts if a.get("type") == "gids"]
    return news, guides


SEV = {"kritiek": 0, "hoog": 1, "middel": 2, "laag": 3, "info": 4}


def item(a: dict, urgent: bool = False) -> str:
    e = html.escape
    url = f"{SITE}/artikel/{a['slug']}/?utm_source=nieuwsbrief&utm_medium=email"
    tags = []
    if a.get("exploited"):
        tags.append(f'<span style="background:{RED};color:#fff;border-radius:10px;padding:2px 8px;font:700 11px {FONT};">ACTIEF MISBRUIKT</span>')
    if a.get("cves"):
        tags.append(f'<span style="font:12px Menlo,Consolas,monospace;color:{BLUE};">{e(a["cves"][0])}</span>')
    todo = ""
    if urgent and a.get("actions"):
        todo = f'<p style="margin:6px 0 0;font:14px/1.5 {FONT};color:{INK};"><strong style="color:{BLUE};">Wat moet je doen?</strong> {e(a["actions"][0])}</p>'
    return f"""<tr><td style="padding:14px 32px;border-top:1px solid {LINE};">
{('<div style="margin-bottom:6px;">' + ' &nbsp;'.join(tags) + '</div>') if tags else ''}
<a href="{url}" style="font:700 17px/1.35 {FONT};color:{INK};text-decoration:none;">{e(a['title'])}</a>
<p style="margin:6px 0 0;font:15px/1.55 {FONT};color:{MUTED};">{e(a.get('tldr', ''))}</p>{todo}
</td></tr>"""


def section(title: str, color: str = INK) -> str:
    return (f'<tr><td style="padding:22px 32px 6px;font:700 13px {FONT};letter-spacing:.08em;'
            f'text-transform:uppercase;color:{color};">{title}</td></tr>')


def weekbrief() -> tuple[str, str, str]:
    news, guides = recent_articles()
    urgent = sorted([a for a in news if a.get("exploited") or a.get("severity") == "kritiek"],
                    key=lambda a: (not a.get("exploited"), SEV.get(a.get("severity"), 9)))[:5]
    rest = [a for a in news if a not in urgent][:6]
    nl = [a for a in news if any(l in ("Nederland", "België") for l in a.get("labels", []))]
    week = datetime.now().isocalendar().week
    top = urgent[0] if urgent else (news[0] if news else None)
    subject = f"Week {week}: {top['title']}" if top else f"Cybersecuritynieuws week {week}"
    if len(subject) > 90:
        subject = subject[:87].rstrip() + "…"
    intro = (f'<tr><td style="padding:26px 32px 4px;">'
             f'<h1 style="margin:0 0 10px;font:700 24px/1.3 {FONT};color:{INK};">Het cybersecuritynieuws van week {week}</h1>'
             + p(f"Deze week {len(news)} berichten, waarvan {sum(1 for a in news if a.get('exploited'))} over lekken die al actief "
                 f"worden misbruikt. Hieronder het belangrijkste, met wat je moet doen.", 16, MUTED) + "</td></tr>")
    parts = [intro]
    if urgent:
        parts += [section("Eerst patchen", RED)] + [item(a, urgent=True) for a in urgent]
    if rest:
        parts += [section("Ook belangrijk")] + [item(a) for a in rest]
    if nl:
        parts += [section("Nederland &amp; België")] + [item(a) for a in nl if a not in urgent and a not in rest][:3]
    if guides:
        g = guides[(week) % len(guides)]
        parts.append(section("Tip van de week", BLUE))
        parts.append(f'<tr><td style="padding:6px 32px 18px;">'
                     + p(f'<strong>{html.escape(g["title"])}</strong><br>{html.escape(g.get("tldr", ""))}', 15)
                     + button(f"{SITE}/artikel/{g['slug']}/?utm_source=nieuwsbrief&utm_medium=email", "Lees de gids") + "</td></tr>")
    parts.append(f'<tr><td style="padding:8px 32px 20px;">'
                 + button(f"{SITE}/?utm_source=nieuwsbrief&utm_medium=email", "Al het nieuws op de site") + "</td></tr>")
    footer = ('Je ontvangt deze mail omdat je je hebt aangemeld op cybersecuritynieuws.com. '
              f'<a href="{{{{ unsubscribe }}}}" style="color:{BLUE};">Afmelden</a><br><br>')
    pre = top["tldr"][:140] if top else "Het belangrijkste cybersecuritynieuws van deze week"
    return subject, shell("\n".join(parts), pre, footer), pre


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "voorbeeld"
    if cmd == "systeemmails":
        systeemmails()
        return
    subject, body, pre = weekbrief()
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("/tmp/nieuwsbrief.html")
    out.write_text(body, encoding="utf-8")
    print(f"Onderwerp: {subject}\nVoorbeeld: {out}")
    if cmd == "concept":
        week = datetime.now().isocalendar().week
        r = brevo("POST", "/emailCampaigns", {
            "name": f"Nieuwsbrief week {week} ({datetime.now():%Y})", "subject": subject, "previewText": pre,
            "sender": SENDER, "replyTo": SENDER["email"], "htmlContent": body, "recipients": {"listIds": [LIST_ID]},
            "inlineImageActivation": False})
        print(f"Concept-campagne aangemaakt in Brevo (id {r.get('id')}); niet verzonden.")


if __name__ == "__main__":
    main()
