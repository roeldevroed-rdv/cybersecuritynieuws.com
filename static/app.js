/* CyberSecurityNieuws – thema-toggle, ticker en zoeken */
(function () {
  "use strict";
  var root = document.documentElement;

  // ---- Thema (licht/donker) ----
  function currentTheme() {
    return root.dataset.mode === "dark" ? "dark" : "light";
  }
  var toggle = document.getElementById("themeToggle");
  if (toggle) {
    var sync = function () { toggle.setAttribute("aria-pressed", currentTheme() === "dark" ? "true" : "false"); };
    sync();
    toggle.addEventListener("click", function () {
      var next = currentTheme() === "dark" ? "light" : "dark";
      root.dataset.mode = next;
      try { localStorage.setItem("theme", next); } catch (e) { /* opslag geblokkeerd: alleen voor deze pagina */ }
      sync();
    });
  }

  // ---- Ticker: inhoud verdubbelen voor een naadloze lus ----
  var track = document.querySelector(".ticker__track");
  if (track && track.children.length) {
    var move = document.createElement("div");
    while (track.firstChild) move.appendChild(track.firstChild);
    var copy = move.cloneNode(true);
    Array.prototype.forEach.call(copy.querySelectorAll("a"), function (a) { a.setAttribute("tabindex", "-1"); });
    var wrapper = document.createElement("div");
    wrapper.className = "ticker__move";
    // Twee identieke helften; animatie schuift precies één helft op
    var half1 = document.createElement("span"); half1.style.display = "inline-flex"; half1.style.gap = "40px"; half1.style.paddingRight = "40px";
    var half2 = half1.cloneNode(); half2.setAttribute("aria-hidden", "true");
    while (move.firstChild) half1.appendChild(move.firstChild);
    while (copy.firstChild) half2.appendChild(copy.firstChild);
    wrapper.appendChild(half1); wrapper.appendChild(half2);
    var speed = Math.max(30, track.textContent.length / 6); // langere tekst = langzamer
    wrapper.style.animationDuration = speed + "s";
    track.appendChild(wrapper);
  }

  // ---- Relatieve tijden ("3 uur geleden") actueel houden; de site wordt alleen bij nieuwe content gebouwd ----
  var MONTHS = ["januari","februari","maart","april","mei","juni","juli","augustus","september","oktober","november","december"];
  function ago(d) {
    var mins = Math.floor((Date.now() - d.getTime()) / 60000);
    if (mins < 60) return Math.max(mins, 1) + " min geleden";
    if (mins < 1440) return Math.floor(mins / 60) + " uur geleden";
    var days = Math.floor(mins / 1440);
    if (days === 1) return "gisteren";
    if (days < 7) return days + " dagen geleden";
    return d.getDate() + " " + MONTHS[d.getMonth()] + " " + d.getFullYear();
  }
  function refreshTimes() {
    Array.prototype.forEach.call(document.querySelectorAll("time[data-ago]"), function (el) {
      var d = new Date(el.getAttribute("datetime"));
      if (!isNaN(d)) el.textContent = ago(d);
    });
  }
  refreshTimes();
  setInterval(refreshTimes, 60000);

  // ---- Zoeken ----
  var input = document.getElementById("q");
  var results = document.getElementById("searchResults");
  if (!input || !results) return;
  var status = document.getElementById("searchStatus");
  var index = null;

  function norm(s) {
    return (s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
  }
  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function highlight(text, terms) {
    var out = esc(text);
    terms.forEach(function (t) {
      if (t.length < 2) return;
      var re = new RegExp("(" + t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ")", "gi");
      out = out.replace(re, "<mark>$1</mark>");
    });
    return out;
  }
  function run() {
    var q = input.value.trim();
    try { history.replaceState(null, "", q ? "?q=" + encodeURIComponent(q) : location.pathname); } catch (e) {}
    results.innerHTML = "";
    if (!q) { status.textContent = ""; return; }
    if (!index) { status.textContent = "Zoekindex laden…"; return; }
    var terms = norm(q).split(/\s+/).filter(Boolean);
    var hits = [];
    index.forEach(function (d) {
      var title = norm(d.t), body = norm(d.d), meta = norm((d.l || []).join(" ") + " " + d.c);
      var score = 0;
      for (var i = 0; i < terms.length; i++) {
        var t = terms[i], s = 0;
        if (title.indexOf(t) > -1) s += 5;
        if (meta.indexOf(t) > -1) s += 3;
        if (body.indexOf(t) > -1) s += 1;
        if (!s) return; // alle termen moeten voorkomen
        score += s;
      }
      hits.push({ d: d, s: score });
    });
    hits.sort(function (a, b) { return b.s - a.s || (a.d.p < b.d.p ? 1 : -1); });
    status.textContent = hits.length ? hits.length + (hits.length === 1 ? " resultaat" : " resultaten") : "Geen resultaten voor “" + q + "”.";
    var raw = q.split(/\s+/);
    results.innerHTML = hits.slice(0, 50).map(function (h) {
      var d = h.d;
      return '<li><a href="' + esc(d.u) + '">' + highlight(d.t, raw) + "</a>" +
        "<p>" + highlight(d.d, raw) + "</p>" +
        '<span class="small muted">' + esc(d.c) + " · " + esc(d.p.split("-").reverse().join("-")) + "</span></li>";
    }).join("");
  }

  var timer;
  input.addEventListener("input", function () { clearTimeout(timer); timer = setTimeout(run, 120); });
  try { input.value = new URLSearchParams(location.search).get("q") || ""; } catch (e) {}
  fetch("/search.json")
    .then(function (r) { return r.json(); })
    .then(function (data) { index = data; run(); })
    .catch(function () { status.textContent = "De zoekindex kon niet worden geladen."; });
})();

// Hamburgermenu (mobiel)
(function () {
  var btn = document.getElementById("menuToggle");
  var head = document.querySelector(".masthead");
  if (!btn || !head) return;
  btn.addEventListener("click", function () {
    var open = head.classList.toggle("menu-open");
    btn.setAttribute("aria-expanded", open ? "true" : "false");
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && head.classList.contains("menu-open")) { head.classList.remove("menu-open"); btn.setAttribute("aria-expanded", "false"); btn.focus(); }
  });
})();
