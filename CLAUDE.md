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
- Ticker bovenaan = laatste 10 nieuwsberichten (met tijd + rood label bij actief misbruikt), Nederland/België-blok op de voorpagina, weekoverzicht, client-side zoeken, RSS, sitemap, dark mode.
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
tools/nieuwsronde.py     # kandidaten zoeken + concepten valideren/opslaan voor de dagelijkse ronde
tools/indexnow.py        # meldt recente pagina's aan bij IndexNow (workflow-job na deploy)
```

## Status
- **LIVE** sinds 25 nov 2026 op https://cybersecuritynieuws.com (GitHub Pages, repo roeldevroed-rdv/cybersecuritynieuws.com, DNS bij TransIP: 4 A-records 185.199.108-111.153 + CNAME www → roeldevroed-rdv.github.io.).
- Google Search Console: domeinproperty geverifieerd via DNS-TXT bij TransIP (25 nov 2026). Sitemaps: sitemap.xml + news-sitemap.xml.
- E-mail (25 nov 2026): info@ (algemeen, privacy, JSON-LD, footer), redactie@ (tips/correcties), adverteren@. ImprovMX gratis (catch-all `*` → roeldevroed@gmail.com) voor ontvangen; versturen als redactie@ via Gmail 'Verzenden als' (smtp.gmail.com + app-wachtwoord). DNS bij TransIP: MX 10 mx1.improvmx.com. / 20 mx2.improvmx.com., SPF `v=spf1 include:spf.improvmx.com include:_spf.google.com ~all`, _dmarc p=none. Zoho bleek niet meer gratis.
- Mediakit (PDF): merk/mediakit/mediakit.html → Mediakit-CyberSecurityNieuws.pdf (playwright pdf). Tarieven zijn voorstel van Claude, eigenaar moet bevestigen.
- Weekbrief: `python -m tools.nieuwsbrief concept` zet concept-campagne in Brevo (nooit automatisch verzenden); `systeemmails` zet Brevo-sjablonen 1-4 in NL.
- Nieuwsbrief (25 nov 2026): **Brevo**, formulier "Website" gekoppeld via site.newsletter_action (templates/_nb_form.html: veld EMAIL, honeypot, locale nl; op home, /nieuwsbrief/ en onder elk artikel; bevestigingspagina's /nieuwsbrief/bijna-klaar/ en /nieuwsbrief/welkom/). gratis (300 mails/dag). API-sleutel als netwerksecret op omgeving `cybersecuritynieuws.com` voor api.brevo.com (header api-key, proxy injecteert; curl met `-H 'api-key: proxy-injected'`). Lijst id 2 "Nieuwsbrief CyberSecurityNieuws" (map 1), afzender info@ (id 1), domein geauthenticeerd (DKIM brevo1/brevo2 CNAME, brevo-code TXT, _dmarc met rua Brevo). Aanmeldformulier maakt eigenaar in Brevo-UI → action-URL in `site.newsletter_action`.
- 24 nov 2026: 8 nieuwsberichten + 6 startgidsen handmatig door Claude geschreven.
- Artikeltypes: "nieuws", "gids", "partner". run.py: `--build` (alleen bouwen), `--fotos` (foto's bij bestaande artikelen).

## Dagelijkse nieuwsronde (Claude-sessie, zonder API-kosten)
Geplande taak trig_01QzkdN6SJZcFzLiYDtdkmFa: elke 2 uur 07:23–23:23 (Europe/Amsterdam), 2–4 artikelen per ronde.
Nederlandse bronnen (NU.nl, NOS, Tweakers, NCSC, Computable; AG Connect en Data News gaven 404/405) staan in config met `snapshot: true` + `filter: security`; hun hosts zijn in de Claude-omgeving geblokkeerd (update_environment werd geweigerd), dus fetch.py valt terug op branch `bronnen` (elk uur gevuld door .github/workflows/bronnen.yml via tools/bronnen_ophalen.py). Workflow gepusht met akkoord eigenaar (25 nov 2026).
1. `python -m tools.nieuwsronde kandidaten` → top-verhalen (nog niet behandeld) + KEV-status; details in /tmp/nieuwsronde-kandidaten.json.
2. Alleen IT-/cybersecuritynieuws (geen algemeen nieuws, ook niet uit NU.nl/NOS; fetch.is_security filtert al, maar kies kritisch). Kies 2–4 verhalen: actief misbruikt / kritiek, Nederland & België, veel bronnen, relevant voor thuisgebruiker of mkb. Geen dubbelingen met recente artikelen.
3. Lees de bronnen (RSS-hosts zijn toegestaan in de omgeving; aanvullen met WebSearch). Gebruik alleen bevestigde feiten; benoem tegenstrijdigheden.
4. Schrijf concepten (JSON-lijst, velden: zie docstring van tools/nieuwsronde.py) in de stijl van bestaande artikelen: antwoord-eerst, 280–450 woorden, 2–3 vraaggerichte ##-kopjes, links naar bron(nen) + 1–3 interne links (/artikel/<slug>/ van gidsen of eerdere berichten), "Wat moet je doen?" 3–5 stappen, FAQ 2–3, meta 140–160 tekens. Geen AI-vermelding in de tekst.
5. `python -m tools.nieuwsronde opslaan /tmp/concepten.json` (controleert en voegt KEV toe), dan `python -m pipeline.run --build` en check "0 ongeldig verwijderd".
6. Commit (`content/`) en push naar main → GitHub bouwt, publiceert en meldt via IndexNow aan.

### Markt & bedrijven (sinds 25 nov 2026)
- Rubrieken (25 nov 2026 samengevoegd, 8 stuks): kwetsbaarheden, ransomware, datalekken, aanvallen (Aanvallen & malware), phishing, overheid (Overheid & wetgeving), ai, markt. Oude slugs → config `category_redirects` (redirectpagina's). Menu: 7 hoofdrubrieken (Kwetsbaarheden, Cyberaanvallen, Ransomware, Datalekken, Phishing, AI & security, Markt) + Gidsen + "Meer" (vanaf 1181px; 901-1180px: scrollbalk; t/m 900px: hamburgermenu #menuToggle, uitklaplijst).
- Rubriek `markt`. Vendorfeeds (Arctic Wolf, CrowdStrike, SentinelOne, Palo Alto, Check Point, ESET, Fortinet, Microsoft Security, Rapid7, HPE) + SecurityWeek M&A. Max. 1 marktbericht per ronde; alleen echt nieuws (overnames, investeringen, grote lanceringen, partnerships, ontslagen/leiderschap), geen reclame. Neutraal, ook als vendor adverteert.
- Bedrijfsprofielen "<Vendor>: wie zijn ze en wat doen ze?" (type gids, categorie markt, slug `<vendor>-wie-zijn-ze-en-wat-doen-ze`). Gedaan: Arctic Wolf (25 nov), CrowdStrike (26 nov). Nog te doen (max. 1 per dag, in een ronde zonder marktnieuws): SentinelOne, Palo Alto Networks, Fortinet, Check Point, Sophos, ESET, HPE (Aruba), Microsoft Security, Rapid7. Alleen gecontroleerde feiten (WebSearch), bronnen = persberichten/vakmedia. Later: vergelijkingen (bijv. MDR-aanbieders).
- Interviews met mensen bij vendoren: alleen echte interviews door de eigenaar; nooit verzinnen of citaten fabriceren.

## Pagina's & verdienmodel (24 nov 2026)
- Eigenaar/hoofdredacteur: Roel de Vroed (config `redactie`; foto nog toevoegen als static/img/… en `redactie.foto`).
- AI-vermelding (25 nov 2026, akkoord eigenaar): artikelen gaan zonder menselijke controle vooraf online, dus EU AI-verordening art. 50 vereist vermelding. Onder elk artikel (behalve type partner) staat `.ai-line` "Dit artikel is met behulp van AI geschreven op basis van de genoemde bronnen." /over/ en /redactie/ beschrijven dit eerlijk. Bronnen klein (één regel `.sources-line`). In de artikeltekst zelf geen AI-vermelding.
- Afbeeldingen: pipeline/covers.py maakt per artikel /og/<slug>.png (met titel, voor delen) en /beeld/<slug>.png (zonder titel, op de site). Pexels-foto heeft voorrang als `image` gezet is. Fonts in assets/fonts (OFL).
- Nieuwe pagina's: /redactie/ /contact/ (tipformulier via forms.tip_action) /adverteren/ (mediakit) /nieuwsbrief/ /privacy/ /cookies/ /colofon/ /producten/ + /product/<slug>/ (config `products`) /ransomware-tracker/ /patch-tuesday/ + news-sitemap.xml.
- Dreigingsniveau op voorpagina (build.threat_level). Advertenties via config `ads` (slots sidebar/artikel; met van/tot), anders huisadvertentie naar /adverteren/. Partnerartikel: type "partner" + `sponsor: {name,url}` → label Gesponsord, links rel=sponsored.
- Artikel-velden: `updated` (ISO) + `update_note` tonen "Bijgewerkt"/update-blok.
- Techniek (25 nov 2026): fonts zelf gehost in static/fonts (IBM Plex Sans/Mono, Newsreader; OFL), robots-meta via `{% block robots %}` (standaard max-image-preview:large), sitebeelden /beeld/*.webp, og-beelden PNG, alt = titel.
- SEO: WebSite+NewsMediaOrganization JSON-LD op home; verificatiecodes Google/Bing via config `zoekmachines`; IndexNow-sleutelbestand in dist/; standaard og-afbeelding static/og-default.png (block `ogimage`).
- Huisstijl (25 nov 2026): ORIGINEEL logo van eigenaar (assets/logo-origineel.png, transparant, witte tekst). Site-header: static/img/logo-licht.png (tekst donker, slot blauw; afgeleid van origineel) en logo-donker.png (dark mode). Favicon static/img/icon-32.png, apple-touch icon-180.png, static/logo-512.png (JSON-LD). covers.draw_logo gebruikt het origineel. static/logo.svg = oude natekening, niet meer in gebruik. Merkkleur blauw `--accent #0a8dff` (verloop #00a8ff→#005bff); rood `--danger` alleen voor badges actief misbruikt/kritiek en dreigingsniveau; alle rubrieken één kleur: merkblauw #0a7ee8 (geen kleur per rubriek, op verzoek eigenaar). og-default via covers.make_default_og. Redactiefoto met blauwe achtergrond.
- Thema-attribuut heet `data-mode` (niet data-theme: botst met de Claude-artifactviewer).

## Eventueel later
- Patch Tuesday-overzicht, OG-afbeeldingen per artikel.
- RSS-URL's in `config.yaml` zijn op 24 nov 2026 getest en werken allemaal (net als de CISA KEV-feed).
- Optioneel: `output_config.effort` in writer.py verlagen (bijv. "medium") om API-kosten te drukken.
