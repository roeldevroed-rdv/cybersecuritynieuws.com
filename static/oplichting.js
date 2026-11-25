/* "Is dit oplichting?" – eenvoudige, lokale controle op bekende kenmerken van oplichting. */
(function () {
  "use strict";
  var text = document.getElementById("scamText");
  var out = document.getElementById("scamResult");
  if (!text || !out) return;

  var RULES = [
    { id: "haast", w: 2, title: "Er wordt haast gemaakt",
      re: /\b(direct|meteen|onmiddellijk|binnen \d+ (uur|minuten|dagen)|vandaag nog|laatste (kans|herinnering|waarschuwing)|dringend|spoed|zo snel mogelijk|verloopt|wordt (geblokkeerd|afgesloten|opgeheven)|geblokkeerd|deactiveer)/i,
      why: "Oplichters willen dat je handelt voordat je nadenkt. Echte organisaties geven je tijd." },
    { id: "betalen", w: 3, title: "Er wordt om een betaling gevraagd",
      re: /(betaal|betaling|betaalverzoek|tikkie|overmak|overboek|openstaand bedrag|achterstallig|verzendkosten|inklaringskosten|€\s?\d|\d+[,.]\d{2}\s?(euro|eur)|iban|cadeaukaart|giftcard)/i,
      why: "Een onverwacht betaalverzoek, zeker via een link of naar een onbekend rekeningnummer, is een van de sterkste signalen." },
    { id: "inloggen", w: 3, title: "Je moet inloggen of gegevens bevestigen",
      re: /(log (hier )?in|inloggen|bevestig (uw|je) gegevens|verifi[eë]er|verificatie|update (uw|je) gegevens|wachtwoord|pincode|inlogcode|beveiligingscode|verificatiecode|digid)/i,
      why: "Banken, de overheid en webwinkels vragen nooit via een link in een bericht om in te loggen of codes door te geven." },
    { id: "link", w: 2, title: "Het bericht bevat een link",
      re: /(https?:\/\/|www\.|\b[a-z0-9-]+\.(xyz|top|click|info|online|site|live|shop|icu|buzz|link)\b|bit\.ly|tinyurl|t\.co\/|cutt\.ly|is\.gd|rebrand\.ly)/i,
      why: "Klik niet op links in onverwachte berichten. Ga zelf naar de website of open de officiële app." },
    { id: "kortelink", w: 2, title: "Er staat een verkorte of vreemde link in",
      re: /(bit\.ly|tinyurl|cutt\.ly|is\.gd|rebrand\.ly|t\.co\/|\.(xyz|top|click|icu|buzz)\b)/i,
      why: "Verkorte links en ongebruikelijke domeinen verbergen waar je echt naartoe gaat." },
    { id: "nieuwnummer", w: 4, title: "Iemand heeft 'een nieuw nummer'",
      re: /(nieuw(e)? nummer|mijn telefoon is (kapot|stuk|gevallen)|hoi (mam|pap|ma|pa)\b|dit is mijn nieuwe|oude nummer)/i,
      why: "Dit is de bekende 'vriend-in-nood'-fraude via WhatsApp. Bel de persoon op het nummer dat je al had." },
    { id: "instantie", w: 1, title: "Er wordt een bekende organisatie genoemd",
      re: /\b(belastingdienst|politie|cjib|digid|rijksoverheid|ing|rabobank|abn ?amro|sns|asn|knab|bunq|postnl|dhl|dpd|ups|bol(\.com)?|microsoft|apple|netflix|kpn|ziggo|odido|vodafone|marktplaats|paypal|fluxys|itsme|kbc|belfius|bpost)\b/i,
      why: "Oplichters doen zich vaak voor als een bekende organisatie. Controleer altijd via het officiële kanaal." },
    { id: "veiligerekening", w: 5, title: "Je moet geld naar een 'veilige rekening' overmaken",
      re: /(veilige rekening|kluisrekening|geld (in )?veiligheid|tijdelijke rekening)/i,
      why: "Een bank vraagt nooit om je geld naar een 'veilige rekening' over te maken. Dit is altijd oplichting." },
    { id: "meekijken", w: 5, title: "Er wordt gevraagd een app te installeren of mee te laten kijken",
      re: /(anydesk|teamviewer|quick ?support|rustdesk|scherm delen|meekijken|app installeren|download de app)/i,
      why: "Met zulke apps kan een oplichter je telefoon of computer overnemen en je bankzaken regelen." },
    { id: "prijs", w: 2, title: "Je hebt iets 'gewonnen' of krijgt iets gratis",
      re: /(gewonnen|winnaar|prijs|cadeau|gratis|beloning|terugbetaling|teruggave|restitutie|geselecteerd)/i,
      why: "Onverwachte prijzen en terugbetalingen zijn lokkertjes om je gegevens of geld te krijgen." },
    { id: "crypto", w: 3, title: "Het gaat over crypto of beleggen",
      re: /(bitcoin|crypto|investering|beleggen|rendement|trading|winst gegarandeerd)/i,
      why: "Beleggingsfraude belooft hoge, zekere winsten. Die bestaan niet." },
    { id: "aanhef", w: 1, title: "Onpersoonlijke aanhef",
      re: /(beste klant|geachte klant|beste gebruiker|dear customer|beste heer\/mevrouw)/i,
      why: "Een echte organisatie kent meestal je naam." }
  ];

  var EXAMPLE = "Hoi mam, mijn telefoon is kapot en dit is mijn nieuwe nummer. Kun je me snel helpen? Ik moet vandaag nog een rekening van 489,50 euro betalen, maar mijn bankapp werkt niet. Kun je het overmaken? Ik betaal je morgen terug!";

  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }

  function check() {
    var t = text.value.trim();
    if (!t) { out.hidden = true; return; }
    var hits = RULES.filter(function (r) { return r.re.test(t); });
    // 'link' en 'kortelink' niet dubbel tellen voor de score als beide raken
    var score = hits.reduce(function (s, r) { return s + r.w; }, 0);
    var level = score >= 7 ? "hoog" : score >= 3 ? "middel" : "laag";
    var head = {
      hoog: ["Grote kans op oplichting", "Dit bericht heeft meerdere sterke kenmerken van oplichting. Reageer niet, klik niet op links en betaal niets."],
      middel: ["Wees voorzichtig", "Dit bericht heeft kenmerken die vaak bij oplichting voorkomen. Controleer het via een kanaal dat je zelf opzoekt."],
      laag: ["Weinig bekende kenmerken gevonden", "We zien weinig typische kenmerken van oplichting. Twijfel je toch? Neem zelf contact op met de afzender."]
    }[level];
    var html = '<div class="scam-result__head scam-result--' + level + '"><strong>' + head[0] + "</strong><p>" + head[1] + "</p></div>";
    if (hits.length) {
      html += "<h2>Wat ons opviel</h2><ul class=\"scam-result__list\">" + hits.map(function (r) {
        return "<li><strong>" + esc(r.title) + "</strong><span>" + esc(r.why) + "</span></li>";
      }).join("") + "</ul>";
    }
    html += '<p class="small muted">Deze check is een hulpmiddel en geen garantie. Bij twijfel: niet doen.</p>';
    out.innerHTML = html;
    out.hidden = false;
    out.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  document.getElementById("scamCheck").addEventListener("click", check);
  document.getElementById("scamExample").addEventListener("click", function () { text.value = EXAMPLE; check(); });
})();
