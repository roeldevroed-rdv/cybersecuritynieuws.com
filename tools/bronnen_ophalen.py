"""Haalt de feeds met `snapshot: true` op en schrijft ze naar een map (voor de branch 'bronnen').

Draait elk uur in GitHub Actions (.github/workflows/bronnen.yml). Zo kan de nieuwsronde ook bronnen
gebruiken waarvan de host in de Claude-omgeving geblokkeerd is.

  python -m tools.bronnen_ophalen <uitvoermap>
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

from pipeline.fetch import _get, snapshot_name

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "bronnen")
    out.mkdir(parents=True, exist_ok=True)
    config = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    status = []
    for src in config["sources"]:
        if not src.get("snapshot"):
            continue
        try:
            data = _get(src["url"], timeout=30)
            (out / snapshot_name(src)).write_bytes(data)
            status.append(f"OK    {src['name']}: {len(data)} bytes")
        except Exception as exc:
            status.append(f"FOUT  {src['name']}: {exc}")
    (out / "status.txt").write_text("\n".join(status) + "\n", encoding="utf-8")
    print("\n".join(status))


if __name__ == "__main__":
    main()
