"""Maakt per artikel een omslagafbeelding in de huisstijl (1200x630 PNG).

Gebruikt als artikelafbeelding wanneer er geen stockfoto is, en altijd als deelafbeelding
(og:image) voor LinkedIn, WhatsApp, X enz. Geen auteursrecht van derden, geen kosten."""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "assets" / "fonts"
W, H = 1200, 630
BG = (17, 19, 23)
INK = (236, 238, 241)
MUTED = (150, 156, 166)
ACCENT = (255, 77, 46)

CAT_COLORS = {
    "kwetsbaarheden": (255, 77, 46), "ransomware": (214, 34, 79), "datalekken": (139, 92, 246),
    "cyberaanvallen": (232, 89, 12), "malware": (22, 163, 74), "phishing": (217, 154, 0),
    "privacy": (37, 99, 235), "overheid": (100, 116, 139), "ai": (13, 148, 136), "uitgelegd": (79, 70, 229),
}


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, width: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textlength(test, font=font) <= width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _fit_title(draw, title: str, width: int, max_lines: int = 4):
    for size in (68, 62, 56, 50, 46):
        f = _font("Caladea-Bold.ttf", size)
        lines = _wrap(draw, title, f, width)
        if len(lines) <= max_lines:
            return f, lines, size
    f = _font("Caladea-Bold.ttf", 46)
    lines = _wrap(draw, title, f, width)[:max_lines]
    lines[-1] = lines[-1].rstrip(".,:;") + "…"
    return f, lines, 46


def _motif(img: Image.Image, color: tuple, seed: str, x0: int = 760, span: int = 420) -> None:
    """Abstract 'netwerk'-patroon rechts: knooppunten en verbindingen in de themakleur."""
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    h = hashlib.sha256(seed.encode()).digest()
    pts = []
    for i in range(14):
        x = x0 + (h[i] / 255) * span
        y = 40 + (h[i + 14] / 255) * 550
        pts.append((x, y))
    for i, (x1, y1) in enumerate(pts):
        for x2, y2 in pts[i + 1:]:
            if math.dist((x1, y1), (x2, y2)) < (210 if span < 600 else 260):
                d.line([(x1, y1), (x2, y2)], fill=color + (70,), width=2)
    for i, (x, y) in enumerate(pts):
        r = 5 + (h[i] % 7)
        d.ellipse([x - r, y - r, x + r, y + r], fill=color + (190 if i % 3 else 255,))
    # concentrische ringen als 'radar'
    cx, cy = 1080, 120
    for r in (90, 150, 210, 270):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color + (40,), width=2)
    img.alpha_composite(layer)


def make_cover(a: dict, categories: dict, out: Path, site_name: str = "CyberSecurityNieuws", with_title: bool = True) -> None:
    """with_title=True: deelafbeelding (og:image). False: beeldversie voor op de site (titel staat er al naast)."""
    color = CAT_COLORS.get(a["category"], ACCENT)
    img = Image.new("RGBA", (W, H), BG + (255,))
    # zachte gloed in de themakleur
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for i in range(12):
        r = 520 - i * 36
        gd.ellipse([1000 - r, 330 - r, 1000 + r, 330 + r], fill=color + (6,))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(60)))
    _motif(img, color, a["slug"], *((760, 420) if with_title else (420, 760)))
    d = ImageDraw.Draw(img)

    # linker accentbalk
    d.rectangle([0, 0, 12, H], fill=color)

    x, y = 72, 64
    label = categories.get(a["category"], "").upper()
    if a.get("type") == "gids":
        label = "GIDS · " + label
    d.text((x, y), label, font=_font("Carlito-Bold.ttf", 26), fill=color)
    y += 52

    if with_title:
        f, lines, size = _fit_title(d, a["title"], 700)
        for line in lines:
            d.text((x, y), line, font=f, fill=INK)
            y += int(size * 1.12)
    else:
        subject = (a.get("keywords") or [""])[0]
        subject = subject[:1].upper() + subject[1:]
        if subject:
            f = _font("Caladea-Bold.ttf", 96)
            while d.textlength(subject, font=f) > 900 and f.size > 56:
                f = _font("Caladea-Bold.ttf", f.size - 8)
            d.text((x, y + 40), subject, font=f, fill=INK)

    # badges onderaan
    by = H - 120
    bx = x
    small = _font("Carlito-Bold.ttf", 22)
    badges = []
    if a.get("exploited"):
        badges.append(("● ACTIEF MISBRUIKT", ACCENT, (255, 255, 255)))
    if a.get("zero_day"):
        badges.append(("ZERO-DAY", (122, 47, 208), (255, 255, 255)))
    if a.get("severity") == "kritiek":
        badges.append(("KRITIEK", (60, 20, 16), (255, 140, 120)))
    for text, bg, fg in badges:
        tw = d.textlength(text, font=small)
        d.rounded_rectangle([bx, by, bx + tw + 28, by + 38], radius=19, fill=bg)
        d.text((bx + 14, by + 7), text, font=small, fill=fg)
        bx += tw + 40
    if a.get("cves"):
        d.text((bx + (4 if badges else 0), by + 6), a["cves"][0], font=_font("JetBrainsMono-Bold.ttf", 22), fill=(255, 143, 120))

    # logo onderaan
    ly = H - 62
    sx = x
    shield = [(sx + 14, ly - 4), (sx, ly + 2), (sx, ly + 14), (sx + 14, ly + 30), (sx + 28, ly + 14), (sx + 28, ly + 2)]
    d.polygon(shield, fill=ACCENT)
    d.line([(sx + 8, ly + 13), (sx + 13, ly + 18), (sx + 21, ly + 8)], fill=BG, width=4)
    name_font = _font("Carlito-Bold.ttf", 28)
    d.text((sx + 42, ly - 2), "CyberSecurity", font=name_font, fill=INK)
    d.text((sx + 42 + d.textlength("CyberSecurity", font=name_font), ly - 2), "Nieuws", font=name_font, fill=ACCENT)

    out.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out, "PNG", optimize=True)
