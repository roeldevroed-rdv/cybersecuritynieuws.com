"""Maakt van een presentatorvideo (bijv. HeyGen-avatar) een nieuwsreel in huisstijl.

  python -m tools.nieuwsreel <video.mp4> <slug> <script.txt> [--uit pad.mp4]

- Opener (±4 s): logo, rubriek, korte kop met blauw gemarkeerde woorden, eigen nieuwstune (tikkende puls + akkoordslagen).
- Ondertiteling in huisstijl (wit op merkblauw), getimed op de pauzes in de spraak: elke zin uit
  script.txt (één regel of zin per spraakblok) hoort bij één spraakblok; binnen een regel kun je met ' | ' deelzinnen scheiden die op kortere pauzes worden getimed. Klopt het aantal niet, dan wordt per tekenaantal verdeeld.
- Logo linksboven; naambalk met de presentator (PRESENTATOR) in de eerste seconden. AI-vermelding staat in het bijschrift en via het AI-label van Instagram (niet in beeld).
- Afsluiter (±3,5 s): slotakkoorden van de tune, logo, "Lees het hele artikel op cybersecuritynieuws.com", "Volg @cybersecuritynieuws".
Een eventueel watermerk van de videodienst blijft zichtbaar (wordt niet afgedekt).
Uitvoer: 1080x1920, 30 fps, AAC; standaard content/instagram/<slug>/reel.mp4.
"""
from __future__ import annotations

import json
import math
import re
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import yaml
from PIL import Image, ImageDraw

from pipeline.covers import BG, BLUE, DANGER, _font, draw_logo

ROOT = Path(__file__).resolve().parent.parent
W, H, FPS, SR = 1080, 1920, 30, 48000
WIT = (255, 255, 255)


# ---------- timing ----------

def speech_blocks(video: Path, pauze: float = 0.35, noise: int = -35) -> list[tuple[float, float]]:
    out = subprocess.run(["ffmpeg", "-i", str(video), "-af", f"silencedetect=noise={noise}dB:d={pauze}", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    dur = float(re.search(r"Duration: (\d+):(\d+):([\d.]+)", out).group(3)) + \
        60 * float(re.search(r"Duration: (\d+):(\d+)", out).group(2))
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", out)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", out)]
    blocks, t = [], 0.0
    for s, e in zip(starts, ends + [dur] * (len(starts) - len(ends))):
        if s - t > 0.15:
            blocks.append((t, s))
        t = e
    if dur - t > 0.15:
        blocks.append((t, dur))
    return blocks


def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text.strip()))
    return [p for p in parts if p]


def align(sents: list[str], blocks: list[tuple[float, float]]) -> list[tuple[float, float, str]]:
    if len(sents) == len(blocks):
        return [(a, b, s) for (a, b), s in zip(blocks, sents)]
    # anders: totale spraaktijd evenredig verdelen naar tekenaantal
    t0, t1 = blocks[0][0], blocks[-1][1]
    total = sum(len(s) for s in sents)
    out, t = [], t0
    for s in sents:
        d = (t1 - t0) * len(s) / total
        out.append((t, t + d, s)); t += d
    return out


def chunks(text: str, max_chars: int = 30) -> list[str]:
    """Zin in ondertitelregels van max. 2 regels."""
    words, lines, cur = text.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > max_chars:
            lines.append(cur); cur = w
        else:
            cur = (cur + " " + w).strip()
    lines.append(cur)
    return [" \n".join(lines[i:i + 2]) for i in range(0, len(lines), 2)]


# ---------- beeld ----------

def subtitle_png(text: str, path: Path) -> None:
    f = _font("Carlito-Bold.ttf", 58)
    probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    lines = [l.strip() for l in text.split("\n")]
    img = Image.new("RGBA", (W, 220), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    y = 220 - len(lines) * 84
    for l in lines:
        tw = probe.textlength(l, font=f)
        x = (W - tw) / 2
        d.rounded_rectangle([x - 22, y, x + tw + 22, y + 74], radius=10, fill=BLUE + (235,))
        d.text((x, y + 5), l, font=f, fill=WIT)
        y += 84
    img.save(path)


PAUZE, NOISE = 0.35, -35  # aan te passen met --pauze 0.15 (fijnere zinsdelen)
PRESENTATOR = "Sophie Carter"  # vaste (fictieve) AI-presentator van CyberSecurityNieuws


def naambalk_png(path: Path, naam: str = PRESENTATOR, sub: str = "CyberSecurityNieuws") -> None:
    """Naambalk (lower third) zoals bij tv-nieuws: naam op merkblauw, kanaal eronder."""
    f1, f2 = _font("Carlito-Bold.ttf", 52), _font("Carlito-Regular.ttf", 34)
    probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    w1, w2 = probe.textlength(naam, font=f1), probe.textlength(sub, font=f2)
    img = Image.new("RGBA", (W, 160), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x = 60
    d.rectangle([x, 10, x + w1 + 56, 84], fill=BLUE + (245,))
    d.rectangle([x, 10, x + 10, 84], fill=WIT)
    d.text((x + 32, 18), naam, font=f1, fill=WIT)
    d.rectangle([x, 84, x + w2 + 56, 136], fill=(17, 19, 23, 230))
    d.text((x + 32, 90), sub, font=f2, fill=(220, 226, 234))
    img.save(path)


def label_png(path: Path) -> None:
    f = _font("Carlito-Bold.ttf", 30)
    txt = "AI-PRESENTATOR"
    tw = int(ImageDraw.Draw(Image.new("L", (1, 1))).textlength(txt, font=f))
    img = Image.new("RGBA", (tw + 40, 52), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, tw + 39, 51], radius=26, fill=(17, 19, 23, 200))
    d.ellipse([16, 20, 28, 32], fill=BLUE)
    d.text((34, 9), txt[0:], font=f, fill=WIT)
    big = Image.new("RGBA", (W, 200), (0, 0, 0, 0))
    draw_logo(big, 48, 60, 1.25)
    big.save(path)  # geen AI-label in beeld (op verzoek eigenaar): vermelding in bijschrift + Instagram-AI-label


def _ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def _kop(d, words, hl, f, x0, y, maxw, alpha):
    sp = d.textlength(" ", font=f)
    lines, cur = [], []
    for i, w in enumerate(words):
        if cur and d.textlength(" ".join(x for _, x in cur + [(i, w)]), font=f) > maxw:
            lines.append(cur); cur = []
        cur.append((i, w))
    lines.append(cur)
    lh = int(f.size * 1.2)
    for line in lines:
        x = x0
        for i, w in line:
            tw = d.textlength(w, font=f)
            if i in hl:
                ext = sp if (i + 1) in hl and line[-1][0] != i else 0
                d.rectangle([x - 10, y + 0.12 * f.size, x + tw + ext + 10, y + 1.14 * f.size], fill=BLUE + (alpha,))
            x += tw + sp
        x = x0
        for i, w in line:
            d.text((x, y), w, font=f, fill=WIT + (alpha,))
            x += d.textlength(w, font=f) + sp
        y += lh
    return y


def card_frames(a: dict, kind: str, secs: float):
    """Opener of afsluiter als reeks frames (RGB-bytes)."""
    from tools.instagram import _background, _highlights
    bg = _background(W, H, a["slug"] + kind)
    cats = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))["categories"]
    n = int(secs * FPS)
    title = a.get("ig_title") or a["title"]
    words = title.split()
    hl = _highlights(a, words)
    for fi in range(n):
        t = fi / FPS
        img = bg.copy()
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        # horizontale "nieuwsbalk" die binnen schuift
        p = _ease(t / (1.45 if kind == "open" else 0.6))
        d.rectangle([0, 0, int(W * p), 14], fill=BLUE)
        if kind == "open":
            # beeld valt samen met de akkoordslagen van de tune (1,5 / 2,0 / 2,5 s)
            pl = _ease((t - 1.45) / 0.35)
            logo = Image.new("RGBA", (W, 260), (0, 0, 0, 0))
            draw_logo(logo, 0, 0, 3.2)
            bb = logo.getbbox()
            logo = logo.crop(bb)
            al = logo.getchannel("A").point(lambda v: int(v * pl)); logo.putalpha(al)
            layer.alpha_composite(logo, ((W - logo.width) // 2, int(560 - 30 * (1 - pl))))
            pc = _ease((t - 1.95) / 0.3)
            cat = (cats.get(a.get("category"), "") or "").upper()
            if a.get("exploited"):
                cat = "ACTIEF MISBRUIKT"
            if cat and pc > 0:
                fc = _font("Carlito-Bold.ttf", 40)
                tw = d.textlength(cat, font=fc)
                d.rounded_rectangle([96, 860, 96 + tw + 44, 922], radius=31,
                                    fill=(DANGER if a.get("exploited") else BLUE) + (int(255 * pc),))
                d.text((118, 866), cat, font=fc, fill=WIT + (int(255 * pc),))
            pk = _ease((t - 2.45) / 0.4)
            if pk > 0:
                _kop(d, words, hl, _font("Caladea-Bold.ttf", 92), 96, int(960 + 40 * (1 - pk)), W - 192, int(255 * pk))
        else:
            pl = _ease((t - 0.7) / 0.35)
            logo = Image.new("RGBA", (W, 260), (0, 0, 0, 0))
            draw_logo(logo, 0, 0, 3.2)
            logo = logo.crop(logo.getbbox())
            al = logo.getchannel("A").point(lambda v: int(v * pl)); logo.putalpha(al)
            layer.alpha_composite(logo, ((W - logo.width) // 2, 640))
            p2 = _ease((t - 1.2) / 0.4)
            f1, f2 = _font("Caladea-Bold.ttf", 66), _font("Carlito-Regular.ttf", 46)
            for txt, f, y in (("Lees het hele artikel op", f1, 960), ("cybersecuritynieuws.com", f1, 1040)):
                tw = d.textlength(txt, font=f)
                d.text(((W - tw) / 2, y), txt, font=f, fill=WIT + (int(255 * p2),))
            p3 = _ease((t - 1.6) / 0.4)
            txt = "Volg @cybersecuritynieuws"
            fv = _font("Carlito-Bold.ttf", 46)
            tw = d.textlength(txt, font=fv)
            d.rounded_rectangle([(W - tw) / 2 - 34, 1200, (W + tw) / 2 + 34, 1280], radius=40, fill=BLUE + (int(255 * p3),))
            d.text(((W - tw) / 2, 1212), txt, font=fv, fill=WIT + (int(255 * p3),))
        img.alpha_composite(layer)
        fade = _ease((t - (secs - 0.35)) / 0.35) if kind == "open" else 0
        if t < 0.3 and kind == "dicht":
            fade = 1 - _ease(t / 0.3)
        if fade > 0:
            img = Image.blend(img, Image.new("RGBA", (W, H), BG + (255,)), fade)
        yield img.convert("RGB").tobytes()


# ---------- geluid ----------
# Eigen gecomponeerde nieuwstune (synthese met numpy; geen samples of melodieën van derden).

def _saw(f, t, n=14):
    import numpy as np
    out = np.zeros_like(t)
    for k in range(1, n + 1):
        if f * k > 12000:
            break
        out += np.sin(2 * np.pi * f * k * t) / k
    return out


def _brass(freqs, dur, sr=SR):
    import numpy as np
    from scipy.signal import butter, sosfilt
    t = np.arange(int(dur * sr)) / sr
    x = sum(_saw(f * d, t) for f in freqs for d in (0.997, 1.0, 1.004)) / (3 * len(freqs))
    env = np.minimum(1, t / 0.012) * np.exp(-t * 2.2)
    # filter-"blaas": helder bij de aanslag, daarna donkerder
    a = sosfilt(butter(2, 4200, fs=sr, output="sos"), x)
    b = sosfilt(butter(2, 900, fs=sr, output="sos"), x)
    mix = np.exp(-t * 9)
    return (a * mix + b * (1 - mix)) * env


def _boom(dur, sr=SR):
    import numpy as np
    t = np.arange(int(dur * sr)) / sr
    f = 38 + 70 * np.exp(-t * 18)
    ph = 2 * np.pi * np.cumsum(f) / sr
    noise = np.random.default_rng(1).standard_normal(len(t)) * np.exp(-t * 40) * 0.35
    return (np.sin(ph) * np.exp(-t * 3.5) + noise)


def _tick(dur, sr=SR, bright=7000):
    import numpy as np
    from scipy.signal import butter, sosfilt
    t = np.arange(int(dur * sr)) / sr
    n = np.random.default_rng(2).standard_normal(len(t)) * np.exp(-t * 90)
    return sosfilt(butter(2, bright, btype="high", fs=sr, output="sos"), n)


def _bell(f, dur, sr=SR):
    import numpy as np
    t = np.arange(int(dur * sr)) / sr
    return (np.sin(2 * np.pi * f * t) + 0.4 * np.sin(2 * np.pi * f * 2.76 * t)) * np.exp(-t * 2.5) * np.minimum(1, t / 0.004)


def _place(buf, x, at, gain=1.0):
    i = int(at * SR)
    n = min(len(x), len(buf) - i)
    if n > 0:
        buf[i:i + n] += gain * x[:n]


def _reverb(x):
    import numpy as np
    from scipy.signal import fftconvolve
    t = np.arange(int(1.6 * SR)) / SR
    ir = np.random.default_rng(3).standard_normal(len(t)) * np.exp(-t * 3.2)
    wet = fftconvolve(x, ir)[: len(x)]
    return x + 0.12 * wet / (np.max(np.abs(wet)) + 1e-9) * np.max(np.abs(x))


def _write(path, buf):
    import numpy as np
    buf = buf / (np.max(np.abs(buf)) + 1e-9) * 0.89
    fade = int(0.25 * SR)
    buf[-fade:] *= np.linspace(1, 0, fade)
    st = np.stack([buf, buf], axis=1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((st * 32767).astype("<i2").tobytes())


# akkoorden (Hz): D-mineur, Bes, C, D-mineur hoog
DM = (146.83, 174.61, 220.00, 293.66)
BES = (116.54, 174.61, 233.08, 293.66)
C = (130.81, 196.00, 261.63, 329.63)
DM2 = (146.83, 220.00, 293.66, 349.23, 440.00)


def tune_open(path: Path, secs: float) -> None:
    """Opener: tikkende puls (nieuws-'klok'), opbouw, vier krachtige akkoordslagen, nagalm."""
    import numpy as np
    buf = np.zeros(int(secs * SR))
    beat = 0.125  # 16e noten op 120 bpm
    for i in range(int(1.5 / beat)):
        _place(buf, _tick(0.08), i * beat, 0.18 + (0.12 if i % 4 == 0 else 0))
    t = np.arange(int(1.5 * SR)) / SR
    riser = np.random.default_rng(4).standard_normal(len(t)) * (t / 1.5) ** 2
    from scipy.signal import butter, sosfilt
    _place(buf, sosfilt(butter(2, [800, 5000], btype="band", fs=SR, output="sos"), riser), 0, 0.35)
    _place(buf, _saw(73.42, t, 6) * np.minimum(1, t / 0.05) * 0.25, 0, 1)  # lage D-puls eronder
    for at, ch, g in ((1.5, DM, 1.0), (2.0, BES, 0.85), (2.5, C, 0.9), (3.0, DM2, 1.1)):
        _place(buf, _brass(ch, secs - at + 0.2), at, g)
        _place(buf, _boom(1.2), at, 0.9 if at in (1.5, 3.0) else 0.55)
        _place(buf, _tick(0.15, bright=3000), at, 0.5)
    _place(buf, _bell(587.33, 1.2), 3.0, 0.35)
    _place(buf, _bell(880.0, 1.2), 3.06, 0.25)
    _write(path, _reverb(buf))


def tune_close(path: Path, secs: float) -> None:
    """Afsluiter: kort tikken, dan C -> D-mineur slot met lange nagalm."""
    import numpy as np
    buf = np.zeros(int(secs * SR))
    for i in range(6):
        _place(buf, _tick(0.08), i * 0.125, 0.2 + (0.1 if i % 4 == 0 else 0))
    for at, ch, g in ((0.75, C, 0.9), (1.25, DM2, 1.1)):
        _place(buf, _brass(ch, secs - at + 0.2), at, g)
        _place(buf, _boom(1.4), at, 0.8)
    _place(buf, _bell(587.33, 1.6), 1.25, 0.3)
    _write(path, _reverb(buf))


# ---------- samenstellen ----------

def build(video: Path, slug: str, script: str, out: Path) -> None:
    from tools.instagram import _article
    a = _article(slug)
    a.setdefault("exploited", bool(a.get("kev")))
    blocks = speech_blocks(video, PAUZE, NOISE)
    cues = []
    lines = [l.strip() for l in script.splitlines() if l.strip()]
    units = lines if len(lines) == len(blocks) else sentences(script)
    print(f"{len(blocks)} spraakblokken, {len(units)} zinnen/regels" + ("" if len(units) == len(blocks) else " -> verdeeld naar lengte"))
    fine = None
    aligned = []
    for s, e, sent in align(units, blocks):
        parts_ = [x.strip() for x in sent.split("|") if x.strip()]
        if len(parts_) > 1:  # regel met " | ": deelzinnen op fijnere pauzes binnen dit spraakblok
            fine = fine or speech_blocks(video, 0.15, -32)
            sub = [(a, b) for a, b in fine if a >= s - 0.05 and b <= e + 0.05]
            if len(sub) == len(parts_):
                aligned += [(a, b, t) for (a, b), t in zip(sub, parts_)]
                continue
            print(f"  ! {len(sub)} fijne blokken voor {len(parts_)} deelzinnen: verdeeld naar lengte")
            aligned += align(parts_, [(s, e)])
            continue
        aligned.append((s, e, sent))
    for s, e, sent in aligned:
        parts = chunks(sent)
        tot = sum(len(p) for p in parts)
        t = s
        for p in parts:
            d = (e - s) * len(p) / tot
            cues.append((t, t + d + 0.15, p)); t += d
    # geen overlap: een ondertitel stopt zodra de volgende begint
    cues = [(s0, min(e0, cues[i + 1][0] - 0.02) if i + 1 < len(cues) else e0, txt) for i, (s0, e0, txt) in enumerate(cues)]
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        o_secs, d_secs = 4.2, 3.6
        for kind, secs in (("open", o_secs), ("dicht", d_secs)):
            p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                                  "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                                  "-crf", "19", str(tmp / f"{kind}.mp4")], stdin=subprocess.PIPE)
            for fr in card_frames(a, kind, secs):
                p.stdin.write(fr)
            p.stdin.close(); p.wait()
            (tune_open if kind == "open" else tune_close)(tmp / f"{kind}.wav", secs)
        label_png(tmp / "label.png")
        naambalk_png(tmp / "naam.png")
        inputs, filt = ["-i", str(video), "-i", str(tmp / "label.png")], []
        filt.append(f"[0:v]scale={W}:{H}:flags=lanczos,fps={FPS},setsar=1[v0]")
        filt.append("[v0][1:v]overlay=0:0[v1]")
        inputs += ["-i", str(tmp / "naam.png")]
        filt.append("[v1][2:v]overlay=0:1080:enable='between(t,0.4,4.4)'[v2]")
        last = "v2"
        for i, (s, e, txt) in enumerate(cues):
            png = tmp / f"sub{i}.png"
            subtitle_png(txt, png)
            inputs += ["-i", str(png)]
            filt.append(f"[{last}][{i + 3}:v]overlay=0:1290:enable='between(t,{s:.2f},{e:.2f})'[s{i}]")
            last = f"s{i}"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(filt),
                        "-map", f"[{last}]", "-map", "0:a", "-c:v", "libx264", "-crf", "19", "-pix_fmt", "yuv420p",
                        "-c:a", "pcm_s16le", "-ar", str(SR), "-ac", "2", str(tmp / "midden.mkv")], check=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                        "-i", str(tmp / "open.mp4"), "-i", str(tmp / "open.wav"),
                        "-i", str(tmp / "midden.mkv"),
                        "-i", str(tmp / "dicht.mp4"), "-i", str(tmp / "dicht.wav"),
                        "-filter_complex",
                        "[0:v][1:a][2:v][2:a][3:v][4:a]concat=n=3:v=1:a=1[v][a];[a]loudnorm=I=-16:TP=-1.5:LRA=11[an]",
                        "-map", "[v]", "-map", "[an]", "-c:v", "libx264", "-crf", "20", "-preset", "medium",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-ar", "44100",
                        "-movflags", "+faststart", str(out)], check=True)
    (out.parent / "ondertitels.json").write_text(json.dumps(cues, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Klaar: {out}")


def main() -> None:
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    if len(args) < 3:
        sys.exit(__doc__)
    global PAUZE, NOISE
    if "--pauze" in sys.argv:
        PAUZE, NOISE = float(sys.argv[sys.argv.index("--pauze") + 1]), -32
        args = [a for a in args if a != sys.argv[sys.argv.index("--pauze") + 1]]
    video, slug, script = Path(args[0]), args[1], Path(args[2]).read_text(encoding="utf-8")
    out = Path(sys.argv[sys.argv.index("--uit") + 1]) if "--uit" in sys.argv else ROOT / "content" / "instagram" / slug / "reel.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    build(video, slug, script, out)


if __name__ == "__main__":
    main()
