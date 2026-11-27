"""Instagram-materiaal per artikel: carrousel-slides, een verticale explainer-video en een bijschrift.

  python -m tools.instagram <slug>            # carrousel + video + bijschrift
  python -m tools.instagram <slug> --geen-video
  python -m tools.instagram <slug> --geen-stem    # video zonder voice-over

Uitvoer in social/<slug>/ (niet in git):
  slide-1.png … slide-5.png   1080x1350 (Instagram-carrousel, staand 4:5)
  reel.mp4                    1080x1920, 30 fps, met Nederlandse voice-over (vrouwenstem, Piper TTS);
                              scèneduur past zich aan de gesproken tekst aan
  voiceover.txt               de uitgesproken tekst per scène (om na te lezen)
  bijschrift.txt              tekst + hashtags

Stem: Piper-stem nl-nathalie (gratis, offline). Wordt bij eerste gebruik gedownload van de
Piper-release op GitHub naar ~/.cache/cybersecuritynieuws/piper/. Lukt dat niet, dan wordt de video
zonder geluid gemaakt. Let op: label de reel in Instagram als AI-gegenereerd (synthetische stem).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import wave
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFilter

from pipeline.covers import BG, BLUE, DANGER, INK, MUTED, _font, _motif, _wrap, draw_logo

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "social"
SITE = "cybersecuritynieuws.com"
FPS = 30


# ---------- inhoud ----------

def _article(slug: str) -> dict:
    for p in sorted((ROOT / "content" / "articles").glob("*.json")):
        a = json.loads(p.read_text(encoding="utf-8"))
        if a.get("slug") == slug:
            return a
    sys.exit(f"Artikel '{slug}' niet gevonden in content/articles/")


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9'\"(])", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _short(text: str, max_chars: int) -> str:
    """Eerste zinnen tot max_chars (hele zinnen)."""
    out = ""
    for s in _sentences(text):
        if len(out) + len(s) + 1 > max_chars and out:
            break
        out = (out + " " + s).strip()
    return out


def scenes(a: dict, categories: dict) -> list[dict]:
    cat = categories.get(a.get("category"), "")
    badge = None
    if a.get("exploited"):
        badge = ("ACTIEF MISBRUIKT", DANGER)
    elif a.get("severity") == "kritiek":
        badge = ("KRITIEK", DANGER)
    faq = (a.get("faq") or [{}])[0]
    return [
        {"kind": "cover", "kicker": cat.upper(), "title": a["title"], "badge": badge},
        {"kind": "text", "kicker": "WAT IS ER AAN DE HAND?", "text": _short(a["tldr"], 230)},
        {"kind": "text", "kicker": "GOED OM TE WETEN", "heading": faq.get("q", ""), "text": _short(faq.get("a", ""), 200)},
        {"kind": "list", "kicker": "WAT MOET JE DOEN?", "items": [x.rstrip(".") for x in a.get("actions", [])[:4]]},
        {"kind": "cta"},
    ]


def caption(a: dict, categories: dict) -> str:
    tags = ["#cybersecurity", "#cyberveiligheid", "#onlineveiligheid"]
    extra = {"phishing": ["#phishing", "#oplichting", "#fraude"], "datalekken": ["#datalek", "#privacy"],
             "ransomware": ["#ransomware"], "kwetsbaarheden": ["#beveiligingsupdate", "#updaten"],
             "aanvallen": ["#hackers", "#malware"], "ai": ["#AI", "#kunstmatigeintelligentie"],
             "overheid": ["#overheid", "#NIS2"], "markt": ["#securitymarkt"]}
    tags += extra.get(a.get("category"), [])
    for k in a.get("keywords", [])[:3]:
        t = "#" + re.sub(r"[^0-9A-Za-zÀ-ÿ]", "", k)
        if len(t) > 2 and t.lower() not in {x.lower() for x in tags}:
            tags.append(t)
    regio = a.get("labels", {}).get("regio", [])
    if "Nederland" in regio:
        tags.append("#nederland")
    if "België" in regio:
        tags.append("#belgië")
    seen, uniek = set(), []
    for t in tags:
        if t.lower() not in seen:
            seen.add(t.lower()); uniek.append(t)
    tags = uniek
    acties = "\n".join(f"✅ {x}" for x in a.get("actions", [])[:3])
    return (f"{a['title']}\n\n{_short(a['tldr'], 300)}\n\nWat moet je doen?\n{acties}\n\n"
            f"👉 Lees het hele artikel via de link in onze bio ({SITE}).\n\n" + " ".join(tags))


# ---------- voice-over ----------

VOICE = "nl-nathalie-x-low"
VOICE_URL = f"https://github.com/rhasspy/piper/releases/download/v0.0.2/voice-{VOICE}.tar.gz"
VOICE_DIR = Path.home() / ".cache" / "cybersecuritynieuws" / "piper"

# uitspraak: woorden die de stem anders verkeerd zegt
SAY = [
    (r"cybersecuritynieuws\.com", "cybersecuritynieuws punt com"),
    (r"\bCVE-(\d+)-(\d+)", r"C V E \1 \2"),
    (r"\bAI\b", "A.I."), (r"\bAVG\b", "A.V.G."), (r"\bNCSC\b", "N.C.S.C."), (r"\bCISA\b", "Cisa"),
    (r"(?i)\bvpn\b", "V.P.N."), (r"\bIT\b", "I.T."), (r"\bmkb\b", "M.K.B."), (r"\bMKB\b", "M.K.B."),
    (r"\bwifi\b", "waaifaai"), (r"&", " en "), (r"→", ""), (r"\s*>\s*", ", "),
]


def _say(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # markdown-links
    text = re.sub(r"[*_#`]", "", text)
    for pat, rep in SAY:
        text = re.sub(pat, rep, text)
    return re.sub(r"\s+", " ", text).strip()


def narration(a: dict, sc: list[dict]) -> list[str]:
    out = []
    for s in sc:
        if s["kind"] == "cover":
            out.append(a["title"] + ".")
        elif s["kind"] == "text" and s.get("heading"):
            out.append(f"Goed om te weten. {s['heading']} {s['text']}")
        elif s["kind"] == "text":
            out.append(f"Wat is er aan de hand? {s['text']}")
        elif s["kind"] == "list":
            out.append("Wat moet je doen? " + " ".join(x.rstrip(".") + "." for x in s["items"]))
        else:
            out.append("Lees het hele artikel op cybersecuritynieuws.com. En volg ons voor meer.")
    return [_say(t) for t in out]


def _voice_model() -> Path | None:
    model = VOICE_DIR / f"{VOICE}.onnx"
    if model.exists():
        return model
    try:
        VOICE_DIR.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as tmp:
            tgz = Path(tmp) / "voice.tar.gz"
            urllib.request.urlretrieve(VOICE_URL, tgz)
            with tarfile.open(tgz) as tf:
                for m in tf.getmembers():
                    name = Path(m.name).name
                    if m.isfile() and name in (f"{VOICE}.onnx", f"{VOICE}.onnx.json"):
                        (VOICE_DIR / name).write_bytes(tf.extractfile(m).read())
        return model if model.exists() else None
    except Exception as e:  # geen netwerk e.d.
        print(f"  ! stem niet beschikbaar ({e}); video zonder geluid")
        return None


def _tts(model: Path, text: str, wav: Path) -> float:
    subprocess.run([sys.executable, "-m", "piper", "-m", str(model), "-f", str(wav),
                    "--length-scale", "1.05", "--sentence-silence", "0.25"],
                   input=text.encode("utf-8"), check=True, capture_output=True)
    with wave.open(str(wav)) as w:
        return w.getnframes() / w.getframerate()


def voiceover(a: dict, sc: list[dict], out: Path) -> tuple[list[float], Path] | None:
    """Spreekt elke scène in; geeft scèneduren en een audiobestand dat precies even lang is."""
    model = _voice_model()
    if not model:
        return None
    texts = narration(a, sc)
    (out / "voiceover.txt").write_text("\n\n".join(texts) + "\n", encoding="utf-8")
    lead, tail = 0.5, 0.9
    durations, chunks, params = [], [], None
    with tempfile.TemporaryDirectory() as tmp:
        for i, t in enumerate(texts):
            wav = Path(tmp) / f"s{i}.wav"
            secs = _tts(model, t, wav)
            with wave.open(str(wav)) as w:
                params = w.getparams()
                frames = w.readframes(w.getnframes())
            dur = max(4.0, lead + secs + tail)
            durations.append(dur)
            chunks.append((frames, dur))
    rate, width, ch = params.framerate, params.sampwidth, params.nchannels
    path = out / "voiceover.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(ch); w.setsampwidth(width); w.setframerate(rate)
        for frames, dur in chunks:
            total = int(round(int(dur * FPS) / FPS * rate)) * width * ch
            pre = int(lead * rate) * width * ch
            buf = (b"\0" * pre + frames)[:total]
            w.writeframes(buf + b"\0" * (total - len(buf)))
    return durations, path


# ---------- tekenen ----------

def _background(w: int, h: int, seed: str) -> Image.Image:
    img = Image.new("RGBA", (w, h), BG + (255,))
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for i in range(12):
        r = int(w * 0.55) - i * 34
        gd.ellipse([w - 120 - r, 180 - r, w - 120 + r, 180 + r], fill=BLUE + (8,))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(70)))
    # netwerkpatroon alleen in een band rechtsboven, naar onder uitgefaded (niet achter de tekst)
    motif = Image.new("RGBA", (1200, 640), (0, 0, 0, 0))
    _motif(motif, BLUE, seed, 700, 460)
    band_h = int(h * 0.16)
    motif = motif.crop((1200 - w, 0, 1200, 640)).resize((w, band_h), Image.LANCZOS)
    fade = Image.linear_gradient("L").rotate(180).resize((w, band_h))
    motif.putalpha(Image.composite(motif.getchannel("A"), Image.new("L", motif.size, 0), fade))
    img.alpha_composite(motif, (0, int(h * 0.02)))
    ImageDraw.Draw(img).rectangle([0, 0, 14, h], fill=BLUE)
    return img


def _text_block(lines: list[str], font, color, spacing: float = 1.25) -> Image.Image:
    lh = int(font.size * spacing)
    w = max(int(ImageDraw.Draw(Image.new("L", (1, 1))).textlength(l, font=font)) for l in lines) + 8
    im = Image.new("RGBA", (w, lh * len(lines) + 10), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for i, l in enumerate(lines):
        d.text((0, i * lh), l, font=font, fill=color)
    return im


def _pill(text: str, color, size: int) -> Image.Image:
    f = _font("Carlito-Bold.ttf", size)
    tw = int(ImageDraw.Draw(Image.new("L", (1, 1))).textlength(text, font=f))
    pad = size // 2
    im = Image.new("RGBA", (tw + pad * 2, size + pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, im.width - 1, im.height - 1], radius=im.height // 2, fill=color + (255,))
    d.text((pad, pad // 2 - 2), text, font=f, fill=(255, 255, 255))
    return im


def layout(scene: dict, w: int, h: int, scale: float) -> list[tuple[Image.Image, tuple[int, int]]]:
    """Lijst van (laag, positie) in leesvolgorde; de video laat ze één voor één verschijnen."""
    m = int(84 * scale)
    width = w - m * 2
    probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    els: list[tuple[Image.Image, tuple[int, int]]] = []
    y = int(h * 0.20)
    kind = scene["kind"]

    def add(im, x, yy):
        els.append((im, (x, yy)))

    if kind == "cover":
        if scene.get("badge"):
            p = _pill(scene["badge"][0], scene["badge"][1], int(30 * scale))
            add(p, m, y)
            y += p.height + int(28 * scale)
        k = _text_block([scene["kicker"]], _font("Carlito-Bold.ttf", int(30 * scale)), BLUE)
        add(k, m, y)
        y += k.height + int(18 * scale)
        for size in (96, 88, 80, 72, 64, 58):
            f = _font("Caladea-Bold.ttf", int(size * scale))
            lines = _wrap(probe, scene["title"], f, width)
            if len(lines) <= 6:
                break
        t = _text_block(lines, f, INK, 1.15)
        add(t, m, y)
        y += t.height + int(40 * scale)
        add(_text_block(["Swipe voor de uitleg  →"], _font("Carlito-Regular.ttf", int(32 * scale)), MUTED), m, y)
    elif kind in ("text", "list"):
        k = _text_block([scene["kicker"]], _font("Carlito-Bold.ttf", int(38 * scale)), BLUE)
        add(k, m, y)
        y += k.height + int(30 * scale)
        if scene.get("heading"):
            f = _font("Caladea-Bold.ttf", int(62 * scale))
            hb = _text_block(_wrap(probe, scene["heading"], f, width), f, INK, 1.15)
            add(hb, m, y)
            y += hb.height + int(26 * scale)
        if kind == "text":
            f = _font("Carlito-Regular.ttf", int(54 * scale))
            for s in _sentences(scene["text"]):
                b = _text_block(_wrap(probe, s, f, width), f, INK, 1.3)
                add(b, m, y)
                y += b.height + int(22 * scale)
        else:
            f = _font("Carlito-Regular.ttf", int(48 * scale))
            for i, item in enumerate(scene["items"], 1):
                lines = _wrap(probe, item, f, width - int(80 * scale))
                b = _text_block(lines, f, INK, 1.25)
                row = Image.new("RGBA", (width, max(b.height, int(64 * scale))), (0, 0, 0, 0))
                rd = ImageDraw.Draw(row)
                r = int(26 * scale)
                rd.ellipse([0, 0, r * 2, r * 2], fill=BLUE + (255,))
                nf = _font("Carlito-Bold.ttf", int(30 * scale))
                rd.text((r, r), str(i), font=nf, fill=(255, 255, 255), anchor="mm")
                row.alpha_composite(b, (int(80 * scale), 0))
                add(row, m, y)
                y += row.height + int(26 * scale)
    else:  # cta
        y = int(h * 0.30)
        logo = Image.new("RGBA", (w, int(220 * scale)), (0, 0, 0, 0))
        draw_logo(logo, 0, 0, 3.6 * scale)
        add(logo, m, y)
        y += int(250 * scale)
        f = _font("Caladea-Bold.ttf", int(62 * scale))
        t = _text_block(_wrap(probe, "Lees het hele artikel via de link in onze bio", f, width), f, INK, 1.15)
        add(t, m, y)
        y += t.height + int(36 * scale)
        f2 = _font("Carlito-Regular.ttf", int(38 * scale))
        add(_text_block(_wrap(probe, "Elke dag het belangrijkste cybersecuritynieuws op één plek.", f2, width), f2, MUTED), m, y)
        y += int(130 * scale)
        add(_pill("Volg ons voor meer", BLUE, int(36 * scale)), m, y)
    # blok verticaal centreren tussen logo (boven) en voettekst (onder)
    if els:
        top = min(p[1] for _, p in els)
        bottom = max(p[1] + im.height for im, p in els)
        area_top, area_bottom = int(h * 0.15), int(h * 0.90)
        shift = (area_top + (area_bottom - area_top - (bottom - top)) // 2) - top
        els = [(im, (x, yy + shift)) for im, (x, yy) in els]
    return els


def _chrome(img: Image.Image, idx: int, total: int, scale: float) -> None:
    """Logo boven, sitenaam en paginateller onder."""
    w, h = img.size
    m = int(84 * scale)
    if idx < total - 1:
        draw_logo(img, m, int(64 * scale), 1.5 * scale)
    d = ImageDraw.Draw(img)
    f = _font("Carlito-Regular.ttf", int(28 * scale))
    d.text((m, h - int(90 * scale)), SITE, font=f, fill=MUTED)
    d.text((w - m, h - int(90 * scale)), f"{idx + 1}/{total}", font=f, fill=MUTED, anchor="ra")


# ---------- carrousel ----------

def carrousel(a: dict, sc: list[dict], out: Path) -> None:
    W, H = 1080, 1350
    for i, s in enumerate(sc):
        img = _background(W, H, a["slug"])
        _chrome(img, i, len(sc), 1.0)
        for im, pos in layout(s, W, H, 1.0):
            img.alpha_composite(im, pos)
        img.convert("RGB").save(out / f"slide-{i + 1}.png", optimize=True)


# ---------- video ----------

def _ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def video(a: dict, sc: list[dict], out: Path, stem: bool = True) -> None:
    W, H = 1080, 1920
    scale = 1.32
    durations = [6.5, 11.0, 10.0, 15.0, 6.0]
    vo = voiceover(a, sc, out) if stem else None
    if vo:
        durations = vo[0]
    total = sum(int(d * FPS) for d in durations) / FPS
    target = out / ("reel-stil.mp4" if vo else "reel.mp4")
    bg = _background(W, H, a["slug"])
    proc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
         "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium",
         "-crf", "20", "-movflags", "+faststart", str(target)],
        stdin=subprocess.PIPE)
    t0 = 0.0
    for i, (s, dur) in enumerate(zip(sc, durations)):
        base = bg.copy()
        _chrome(base, i, len(sc), scale)
        els = layout(s, W, H, scale)
        n = len(els)
        step = min(0.9, (dur - 2.5) / max(n, 1))
        frames = int(dur * FPS)
        for fi in range(frames):
            t = fi / FPS
            frame = base.copy()
            for j, (im, (x, y)) in enumerate(els):
                p = _ease((t - 0.25 - j * step) / 0.6)
                if p <= 0:
                    continue
                layer = im if p >= 1 else im.copy()
                if p < 1:
                    alpha = layer.getchannel("A").point(lambda v, p=p: int(v * p))
                    layer.putalpha(alpha)
                frame.alpha_composite(layer, (x, int(y + (1 - p) * 40)))
            # uitfaden naar zwart aan het eind van elke scène
            fade = _ease((t - (dur - 0.45)) / 0.45)
            if fade > 0:
                frame = Image.blend(frame, Image.new("RGBA", (W, H), BG + (255,)), fade)
            # voortgangsbalk bovenaan
            d = ImageDraw.Draw(frame)
            prog = (t0 + t) / total
            d.rectangle([0, 0, W, 10], fill=(40, 44, 52))
            d.rectangle([0, 0, int(W * prog), 10], fill=BLUE)
            proc.stdin.write(frame.convert("RGB").tobytes())
        t0 += dur
    proc.stdin.close()
    proc.wait()
    if vo:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(target), "-i", str(vo[1]),
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-shortest",
                        "-movflags", "+faststart", str(out / "reel.mp4")], check=True)
        target.unlink()
        vo[1].unlink()


def main() -> None:
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    if not args:
        sys.exit(__doc__)
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    a = _article(args[0])
    # KEV-status zoals op de site
    a.setdefault("exploited", bool(a.get("kev")))
    sc = scenes(a, cfg["categories"])
    out = OUT / a["slug"]
    out.mkdir(parents=True, exist_ok=True)
    carrousel(a, sc, out)
    (out / "bijschrift.txt").write_text(caption(a, cfg["categories"]), encoding="utf-8")
    if "--geen-video" not in sys.argv:
        video(a, sc, out, stem="--geen-stem" not in sys.argv)
    print(f"Klaar: {out.relative_to(ROOT)}/")
    for p in sorted(out.iterdir()):
        print(f"  {p.name}  ({p.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
