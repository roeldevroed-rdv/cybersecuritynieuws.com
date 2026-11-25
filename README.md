# CyberSecurityNieuws.com

Een volledig automatische Nederlandstalige nieuwssite over cybersecurity. Elke twee uur:

1. **GitHub Actions** haalt nieuws op uit RSS-bronnen (`config.yaml`), voegt dubbele berichten samen en controleert CVE's tegen de CISA-lijst van actief misbruikte kwetsbaarheden.
2. **Claude** (Anthropic API) schrijft per verhaal een origineel Nederlands artikel met TL;DR, "Wat moet je doen?", thema en labels.
3. De nieuwe artikelen worden in `content/articles/` gecommit.
4. Dezelfde workflow bouwt de statische site en publiceert die gratis op **GitHub Pages**.

```
GitHub Actions (elke 2 uur of bij een push) ──► artikelen + dist/ ──► GitHub Pages ──► cybersecuritynieuws.com
```

## Lokaal testen

Nodig: Python 3.11 of nieuwer.

```bash
pip install -r requirements.txt
```

```bash
python -m pipeline.run --build
```

```bash
python -m http.server -d dist 8000
```

Open daarna <http://localhost:8000>. Zolang `content/articles/` leeg is, gebruikt de site de **fictieve voorbeeldartikelen** uit `content/voorbeelden/` (met een duidelijke "Voorbeeld"-melding). Zodra er één echt artikel is, verdwijnen ze vanzelf.

Echte artikelen lokaal laten schrijven (kost API-tegoed):

```bash
ANTHROPIC_API_KEY=sk-ant-... python -m pipeline.run
```

## Online zetten

### 1. GitHub-repository

1. Maak op GitHub een nieuwe repository, bijvoorbeeld `cybersecuritynieuws` (privé mag).
2. Upload deze map en push naar de branch `main`:

   ```bash
   git init -b main
   ```

   ```bash
   git add . && git commit -m "Eerste versie"
   ```

   ```bash
   git remote add origin https://github.com/JOUW-NAAM/cybersecuritynieuws.git
   ```

   ```bash
   git push -u origin main
   ```

### 2. Anthropic API-sleutel als secret

1. Maak een API-sleutel aan op <https://platform.claude.com> (en zet er tegoed op).
2. Ga in GitHub naar **Settings → Secrets and variables → Actions → New repository secret**.
3. Naam: `ANTHROPIC_API_KEY`, waarde: je sleutel.
4. Controleer onder **Settings → Actions → General → Workflow permissions** dat **Read and write permissions** aan staat (nodig om artikelen te committen).

### Optioneel: gratis foto's (Pexels)

1. Maak een gratis account op <https://www.pexels.com/api/> en vraag een API-sleutel aan.
2. Voeg hem in GitHub toe als secret `PEXELS_API_KEY`.
3. Vanaf dan krijgt elk nieuw artikel automatisch een passende stockfoto, met naamsvermelding van de fotograaf. Foto's bij bestaande artikelen voeg je toe met `python -m pipeline.run --fotos`.

Zonder sleutel werkt alles gewoon, maar dan zonder foto's.

### 3. GitHub Pages aanzetten

De repository moet **openbaar** (Public) zijn; dan is GitHub Pages gratis.

1. Ga in de repository naar **Settings → Pages**.
2. Kies bij **Source** voor **GitHub Actions**.
3. Ga naar **Actions → "Site bijwerken en publiceren" → Run workflow**. Na een paar minuten staat de site op `https://JOUW-NAAM.github.io/cybersecuritynieuws/`.

   Let op: op dat tijdelijke adres werken de links pas goed zodra je eigen domein is gekoppeld (de site verwacht in de hoofdmap van een domein te staan).

### 4. Domein koppelen

1. In GitHub: **Settings → Pages → Custom domain** → vul `cybersecuritynieuws.com` in en klik **Save**.
2. Maak bij je domeinregistrar deze DNS-records aan:
   - vier `A`-records voor `@` (het hoofddomein): `185.199.108.153`, `185.199.109.153`, `185.199.110.153` en `185.199.111.153`;
   - een `CNAME`-record voor `www` naar `JOUW-NAAM.github.io`.
3. Wacht tot GitHub het domein heeft gecontroleerd (minuten tot een paar uur) en vink dan **Enforce HTTPS** aan.

### 5. Hoe vaak wordt er gepubliceerd?

- Elke push naar `main` (bijvoorbeeld nieuwe artikelen) wordt direct gepubliceerd.
- Elke 2 uur draait de workflow vanzelf. Met een `ANTHROPIC_API_KEY` schrijft hij dan zelf nieuwe artikelen; zonder sleutel bouwt hij alleen de site opnieuw.
- GitHub Pages en Actions zijn gratis voor openbare repositories, dus je kunt de hele dag door publiceren.

## Instellingen (`config.yaml`)

| Instelling | Betekenis |
|---|---|
| `ai.model` | `claude-sonnet-5-5` (beste kwaliteit/prijs) of `claude-haiku-5-5` (veel goedkoper, iets minder goed Nederlands) |
| `ai.max_new_articles_per_run` | Maximaal aantal nieuwe artikelen per run (elke 2 uur) |
| `ai.max_age_hours` | Hoe oud een bronbericht maximaal mag zijn |
| `sources` | RSS-bronnen met een gewicht voor de rangschikking |
| `categories` / `labels` | Thema's en labels waar de AI uit kiest |
| `site.newsletter_action` | Form-URL van bijv. Buttondown; leeg = geen aanmeldformulier |

Na een wijziging in templates, stijl of `config.yaml` wordt de site bij de push automatisch opnieuw gebouwd en gepubliceerd.

## Gidsen, links en SEO/GEO

- **Contentkalender**: onder `evergreen.topics` in `config.yaml` staan 30 onderwerpen voor tijdloze gidsen. Elke dag wordt er één geschreven (`evergreen.per_day`). Voeg gerust eigen onderwerpen toe.
- **Interne links**: bij het schrijven krijgt de AI de best passende bestaande artikelen mee om naar te linken. Bij het bouwen worden links naar niet-bestaande pagina's automatisch verwijderd.
- **Externe links**: alleen naar de bronnen van het artikel en naar de betrouwbare sites in `trusted_domains`. Andere externe links worden automatisch verwijderd.
- **SEO**: metabeschrijving, gestructureerde data (Article/NewsArticle, FAQPage, BreadcrumbList), sitemap met datums en een "Lees ook"-blok.
- **GEO** (vindbaar in ChatGPT, Perplexity en dergelijke): antwoord-eerst-teksten, vraaggerichte tussenkopjes, een FAQ per artikel en `/llms.txt` met een overzicht van alle gidsen.

## Kosten (indicatie)

Prijzen per november 2026; controleer de actuele tarieven bij Anthropic en GitHub.

**Anthropic API.** Een artikel kost ongeveer 2.500 invoertokens en tot ~4.000 uitvoertokens (inclusief het "denkwerk" van het model).

| Model | Prijs per 1M tokens (in/uit) | Per artikel | Bij 40 artikelen/dag |
|---|---|---|---|
| `claude-sonnet-5-5` | $2 / $10 | ± $0,04–0,05 | ± $50–60 per maand |
| `claude-haiku-5-5` | $0,10 / $0,50 | ± $0,002 | ± $3 per maand |

Met de standaard `max_new_articles_per_run: 8` kunnen het er in theorie 96 per dag zijn, al worden het er in de praktijk meestal minder (alleen echt nieuwe verhalen). Wil je de kosten begrenzen, verlaag dan dat getal naar 3–4, of stel in de Anthropic Console een maandlimiet in.

**GitHub Actions.** Gratis voor publieke repositories. Voor privé-repositories zit een maandbundel aan minuten in het gratis plan; een run duurt een paar minuten.

**Hosting.** GitHub Pages en GitHub Actions zijn gratis voor openbare repositories.

**Domein.** Ongeveer €10–15 per jaar bij je registrar.

## Mappen

```
config.yaml                    instellingen, bronnen, thema's, labels
netlify.toml                   alleen nodig als je ooit naar Netlify gaat (wordt niet gebruikt op GitHub Pages)
.github/workflows/update.yml   elke 2 uur en bij elke push: (artikelen schrijven en) publiceren op GitHub Pages
pipeline/fetch.py              RSS ophalen, clusteren, scoren, KEV-check
pipeline/writer.py             Claude schrijft het artikel (tool use, strikt JSON-schema)
pipeline/build.py              statische sitegenerator → dist/
pipeline/run.py                alles samen: python -m pipeline.run [--build]
templates/                     Jinja2-templates
static/                        style.css, app.js (thema, zoeken, ticker), favicon.svg
content/articles/              gegenereerde artikelen (JSON)
content/voorbeelden/           fictieve voorbeeldartikelen voor lokaal testen
content/seen.json              al verwerkte bron-URL's
```

## Goed om te weten

- Artikelen worden **zonder menselijke controle** gepubliceerd. Onder elk artikel staan de bronnen, en de pagina "Over" legt uit hoe de site werkt. Een fout artikel verwijder je door het JSON-bestand in `content/articles/` te verwijderen en te pushen.
- Weigert het model een onderwerp (dat kan bij cybersecurity af en toe gebeuren), dan probeert de API automatisch een ander model; lukt dat niet, dan wordt het verhaal overgeslagen.
- Bronnen die tijdelijk niet bereikbaar zijn, worden overgeslagen; de rest gaat gewoon door.
