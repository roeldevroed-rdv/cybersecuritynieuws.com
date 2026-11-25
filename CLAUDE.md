# CyberSecurityNieuws.com – projectcontext voor Claude Code

Volledig geautomatiseerde Nederlandstalige cybersecuritynieuwssite (zoals thehackernews.com, maar beter).
Communiceer met de eigenaar in het **Nederlands**.

## Gekozen aanpak
- **Statische site** (Python + Jinja2) → map `dist/`, gehost op **GitHub Pages** (openbare repo, gratis), gekoppeld aan domein cybersecuritynieuws.com. Netlify is afgevallen: gratis plan ≈ 20 deploys/maand.
- **GitHub Actions** (`update.yml`): bij elke push bouwen + deployen naar Pages; elke 2 uur (met `ANTHROPIC_API_KEY`) eerst nieuws schrijven + `content/` committen.
- **Gratis alternatief voor de API**: de eigenaar laat Claude (Claude Code-sessie / geplande taak) zelf nieuws schrijven: `pipeline.fetch.gather` voor bronnen, `load_kev` voor KEV-check, artikel-JSON in `content/articles/` (type "nieuws", model "redactie (Claude)"), pushen naar main.
- **Content**: eigen Nederlandstalige artikelen *in eigen woorden* op basis van RSS-bronnen, altijd met bronvermelding. Nooit teksten of afbeeldingen van bronnen kopiëren.
- **Volledig automatisch publiceren** (geen goedkeuringsstap).
- **AI**: Anthropic API (`ANTHROPIC_API_KEY` als GitHub-secret), model instelbaar in `config.yaml` (standaard `claude-sonnet-5-5`).
  Let op: `claude-sonnet-5-5` accepteert geen geforceerde `tool_choice` (400) → writer gebruikt `auto` + `strict` schema + `fallbacks: "default"` (beta `server-side-fallback-2026-07-01`) en slaat `refusal` over.

## Onderscheidende features (t.o.v. The Hacker News)
- Elk artikel: **TL;DR** bovenaan + blok **"Wat moet je doen?"** met concrete stappen.
- Label **"Actief misbruikt"**: CVE's worden automatisch gecontroleerd tegen de CISA KEV-lijst.
- Dubbele berichten uit verschillende bronnen worden samengevoegd tot één artikel (clustering).
- **Twee-lagen indeling**: één hoofdthema per artikel + labels (regio, doelgroep, sector, technologie) — zie `config.yaml`.
- Ticker "Actief misbruikt", Nederland/België-blok op de voorpagina, weekoverzicht, client-side zoeken, RSS, sitemap, dark mode.
- Geen afbeeldingen van bronnen; kaarten zijn typografisch met een kleuraccent per thema.

## Structuur
```
config.yaml              # site-instellingen, bronnen, thema's, labels
netlify.toml             # ongebruikt (Netlify-config, bewaard voor als)
pipeline/fetch.py        # RSS ophalen, clusteren, scoren, KEV-check
pipeline/writer.py       # Claude schrijft nieuws (write_article) en evergreen-gidsen (write_evergreen); GEO/SEO-regels, FAQ, image_query
pipeline/images.py       # gratis stockfoto via Pexels (PEXELS_API_KEY, optioneel)
pipeline/run.py          # orkestratie: `python -m pipeline.run` (of `--build` voor alleen bouwen)
pipeline/build.py        # statische sitegenerator → dist/; valideert links (intern bestaand, extern alleen bronnen/trusted_domains), /gidsen/, llms.txt, FAQPage/Breadcrumb JSON-LD
templates/               # base, _macros, home, list, article, week, search, about, 404
static/                  # style.css (standaard licht, donker alleen via toggle, kleur per thema), app.js (thema, ticker, zoeken, relatieve tijden), favicon.svg
.github/workflows/update.yml  # push → build+deploy GitHub Pages; cron 2 uur → schrijven (met API-sleutel) + commit + deploy
content/articles/*.json  # gegenereerde artikelen (1 JSON per artikel)
content/voorbeelden/     # fictieve voorbeeldartikelen (example: true, offset_hours)
content/seen.json        # al verwerkte bron-URL's
README.md                # installatie: GitHub, secret, GitHub Pages, domein (DNS), kosten
```

## Status
- Live gaan wacht op GitHub: account van eigenaar was door GitHub 'flagged' (support aangeschreven); daarna repo (openbaar) koppelen via claude.ai/connect-github, pushen, Pages → Source: GitHub Actions, DNS instellen (zie README).
- 24 nov 2026: 8 nieuwsberichten handmatig door Claude geschreven op basis van RSS + webzoekopdrachten.
- 6 startgidsen zijn handmatig door Claude geschreven (content/articles/*-wat-is-phishing.json enz., type "gids"); de contentkalender slaat die onderwerpen over.
- Artikeltypes: "nieuws" en "gids". run.py: `--build` (alleen bouwen), `--fotos` (foto's bij bestaande artikelen).
- Alles van de oorspronkelijke takenlijst is af. Hosting: Cloudflare Pages → Netlify → nu GitHub Pages.

## Pagina's & verdienmodel (24 nov 2026)
- Eigenaar/hoofdredacteur: Roel de Vroed (config `redactie`; foto nog toevoegen als static/img/… en `redactie.foto`).
- Eigenaar wil GEEN AI-vermelding per artikel en bronnen klein (één regel `.sources-line`). AI wordt alleen algemeen genoemd op /over/; hoofdredacteur is redactioneel verantwoordelijk (EU AI-verordening art. 50: dan geen label nodig mits menselijke controle).
- Afbeeldingen: pipeline/covers.py maakt per artikel /og/<slug>.png (met titel, voor delen) en /beeld/<slug>.png (zonder titel, op de site). Pexels-foto heeft voorrang als `image` gezet is. Fonts in assets/fonts (OFL).
- Nieuwe pagina's: /redactie/ /contact/ (tipformulier via forms.tip_action) /adverteren/ (mediakit) /nieuwsbrief/ /privacy/ /cookies/ /colofon/ /is-dit-oplichting/ (lokale JS-check) /producten/ + /product/<slug>/ (config `products`) /ransomware-tracker/ /patch-tuesday/ + news-sitemap.xml.
- Dreigingsniveau op voorpagina (build.threat_level). Advertenties via config `ads` (slots sidebar/artikel; met van/tot), anders huisadvertentie naar /adverteren/. Partnerartikel: type "partner" + `sponsor: {name,url}` → label Gesponsord, links rel=sponsored.
- Artikel-velden: `updated` (ISO) + `update_note` tonen "Bijgewerkt"/update-blok.
- Thema-attribuut heet `data-mode` (niet data-theme: botst met de Claude-artifactviewer).

## Eventueel later
- Nieuwsbrief (Buttondown) – formulier staat klaar via `site.newsletter_action`.
- Patch Tuesday-overzicht, OG-afbeeldingen per artikel.
- RSS-URL's in `config.yaml` zijn op 24 nov 2026 getest en werken allemaal (net als de CISA KEV-feed).
- Optioneel: `output_config.effort` in writer.py verlagen (bijv. "medium") om API-kosten te drukken.
