"""Plaatst Instagram-posts op @cybersecuritynieuws via de Instagram Graph API.

  python -m tools.instagram_post klaarzetten <slug> [<slug> ...]
      Maakt slides (JPEG), reel en bijschrift (tools.instagram) en zet ze in content/instagram/<slug>/.
      Daarna committen en pushen: de site publiceert ze op https://cybersecuritynieuws.com/ig/<slug>/...
      (Instagram haalt media op via een openbare URL).
  python -m tools.instagram_post ronde [--uren 3]
      Voor elk nieuwsbericht (type nieuws) van de laatste 3 uur (rondes zijn elke 2 uur) dat nog niet op Instagram staat:
      klaarzetten (alleen slides), committen + pushen, wachten tot het online staat, carrousel plaatsen,
      log committen. Hoort bij elke nieuwsronde (stap 7 in CLAUDE.md).
  python -m tools.instagram_post plaatsen <slug> [--reel]
      Plaatst de carrousel (standaard) of de reel met bijschrift. Wacht tot de bestanden online staan.
      Bij een reel komt een AI-vermelding in het bijschrift (AI-label kan niet via de API).

De token (systeemgebruiker Publisher) staat als netwerksecret voor graph.facebook.com in de
Claude-omgeving: de proxy voegt hem toe, er staat nergens een sleutel in code of repo.
Al geplaatste posts staan in content/instagram/gepost.json (voorkomt dubbel plaatsen)."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
IG_DIR = ROOT / "content" / "instagram"
LOG = IG_DIR / "gepost.json"
SITE = "https://cybersecuritynieuws.com"
GRAPH = "https://graph.facebook.com/v21.0"
IG_USER = "17841457186203235"  # @cybersecuritynieuws


def _api(path: str, params: dict | None = None, post: bool = False) -> dict:
    data = urllib.parse.urlencode(params or {}).encode() if post else None
    url = f"{GRAPH}/{path}" + ("" if post or not params else "?" + urllib.parse.urlencode(params))
    req = urllib.request.Request(url, data=data, method="POST" if post else "GET")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"Graph API-fout ({e.code}) bij {path}: {e.read().decode()[:500]}")


def _log() -> dict:
    return json.loads(LOG.read_text()) if LOG.exists() else {}


def klaarzetten(slug: str, video: bool = True) -> None:
    subprocess.run([sys.executable, "-m", "tools.instagram", slug] + ([] if video else ["--geen-video"]),
                   check=True, cwd=ROOT, stdout=subprocess.DEVNULL)
    src, dst = ROOT / "social" / slug, IG_DIR / slug
    dst.mkdir(parents=True, exist_ok=True)
    for p in sorted(src.glob("slide-*.png")):
        Image.open(p).convert("RGB").save(dst / (p.stem + ".jpg"), quality=88, optimize=True)
    if video:
        shutil.copy(src / "reel.mp4", dst / "reel.mp4")
    shutil.copy(src / "bijschrift.txt", dst / "bijschrift.txt")
    print(f"Klaargezet: content/instagram/{slug}/ (nu committen en pushen)")


def _wait_online(url: str) -> None:
    for _ in range(40):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=20) as r:
                if r.status == 200:
                    return
        except Exception:
            pass
        time.sleep(15)
    sys.exit(f"Niet online: {url}")


def _wait_ready(container: str) -> None:
    for _ in range(60):
        st = _api(container, {"fields": "status_code,status"})
        if st.get("status_code") == "FINISHED":
            return
        if st.get("status_code") in ("ERROR", "EXPIRED"):
            sys.exit(f"Container {container} mislukt: {st}")
        time.sleep(5)
    sys.exit(f"Container {container} niet klaar")


def plaatsen(slug: str, reel: bool = False) -> None:
    log = _log()
    key = f"{slug}:{'reel' if reel else 'carrousel'}"
    if key in log:
        print(f"Al geplaatst: {key} -> {log[key]['permalink']}")
        return
    d = IG_DIR / slug
    caption = (d / "bijschrift.txt").read_text(encoding="utf-8").strip()
    base = f"{SITE}/ig/{urllib.parse.quote(slug)}"
    if reel:
        caption += "\n\nDeze video is gemaakt met AI."
        _wait_online(f"{base}/reel.mp4")
        c = _api(f"{IG_USER}/media", {"media_type": "REELS", "video_url": f"{base}/reel.mp4",
                                       "caption": caption, "share_to_feed": "true"}, post=True)["id"]
        _wait_ready(c)
    else:
        slides = sorted(d.glob("slide-*.jpg"))
        _wait_online(f"{base}/{slides[-1].name}")
        kids = []
        for s in slides:
            k = _api(f"{IG_USER}/media", {"image_url": f"{base}/{s.name}", "is_carousel_item": "true"}, post=True)["id"]
            _wait_ready(k)
            kids.append(k)
        c = _api(f"{IG_USER}/media", {"media_type": "CAROUSEL", "children": ",".join(kids), "caption": caption}, post=True)["id"]
        _wait_ready(c)
    media = _api(f"{IG_USER}/media_publish", {"creation_id": c}, post=True)["id"]
    link = _api(media, {"fields": "permalink"}).get("permalink", "")
    log[key] = {"id": media, "permalink": link, "datum": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    LOG.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Geplaatst: {key} -> {link}")


def _git(*args: str) -> None:
    subprocess.run(["git", *args], check=True, cwd=ROOT)


def _push(msg: str) -> None:
    _git("add", "content/instagram")
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT).returncode == 0:
        return
    _git("commit", "-q", "-m", msg)
    for _ in range(4):
        if subprocess.run(["git", "pull", "-q", "--rebase"], cwd=ROOT).returncode == 0 and \
           subprocess.run(["git", "push", "-q", "origin", "HEAD:main"], cwd=ROOT).returncode == 0:
            return
        time.sleep(5)
    sys.exit("Pushen mislukt")


def ronde(uren: float = 3) -> None:
    grens = datetime.now(timezone.utc).timestamp() - uren * 3600
    log = _log()
    nieuw = []
    for p in sorted((ROOT / "content" / "articles").glob("*.json")):
        a = json.loads(p.read_text(encoding="utf-8"))
        if a.get("type", "nieuws") != "nieuws" or f"{a['slug']}:carrousel" in log:
            continue
        if datetime.fromisoformat(a["published"]).timestamp() >= grens:
            nieuw.append(a["slug"])
    if not nieuw:
        print("Instagram: niets nieuws te plaatsen.")
        return
    for slug in nieuw:
        if not (IG_DIR / slug / "slide-5.jpg").exists():
            klaarzetten(slug, video=False)
    _push(f"Instagram: media klaargezet ({len(nieuw)})")
    for slug in nieuw:
        plaatsen(slug)
    _push("Instagram: geplaatste posts bijgewerkt")


def main() -> None:
    if sys.argv[1:2] == ["ronde"]:
        uren = float(sys.argv[sys.argv.index("--uren") + 1]) if "--uren" in sys.argv else 3
        return ronde(uren)
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) < 2 or args[0] not in ("klaarzetten", "plaatsen"):
        sys.exit(__doc__)
    for slug in args[1:]:
        klaarzetten(slug) if args[0] == "klaarzetten" else plaatsen(slug, reel="--reel" in sys.argv)


if __name__ == "__main__":
    main()
