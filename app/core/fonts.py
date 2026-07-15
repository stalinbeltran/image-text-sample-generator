from __future__ import annotations

import base64
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.settings import FONTS_DIR

# Families we can rely on being installed on a typical Windows/macOS box. Used
# only when assets/fonts/ is empty -- dropping .ttf/.otf files in there is the
# reproducible path, since embedded fonts render the same anywhere.
SYSTEM_FALLBACK = [
    "Arial",
    "Times New Roman",
    "Courier New",
    "Verdana",
    "Georgia",
    "Tahoma",
    "Trebuchet MS",
    "Calibri",
]

_MIME = {".ttf": "font/ttf", ".otf": "font/otf", ".woff": "font/woff", ".woff2": "font/woff2"}


@dataclass(frozen=True)
class FontAsset:
    family: str
    file: str | None  # path relative to FONTS_DIR; None for system fonts

    @property
    def is_system(self) -> bool:
        return self.file is None


def _family_from_filename(path: Path) -> str:
    # "Roboto-BoldItalic.ttf" -> "Roboto"
    return path.stem.split("-")[0].split("_")[0]


@lru_cache(maxsize=1)
def registry() -> list[FontAsset]:
    """All fonts available to recipes. Cached; call `refresh()` after adding files."""
    assets: list[FontAsset] = []
    for path in sorted(FONTS_DIR.rglob("*")):
        if path.suffix.lower() in _MIME:
            rel = path.relative_to(FONTS_DIR).as_posix()
            assets.append(FontAsset(family=_family_from_filename(path), file=rel))
    if not assets:
        assets = [FontAsset(family=f, file=None) for f in SYSTEM_FALLBACK]
    return assets


def refresh() -> list[FontAsset]:
    registry.cache_clear()
    _data_uri.cache_clear()
    return registry()


def pool(families: list[str] | None) -> list[FontAsset]:
    """The candidate fonts for a recipe, optionally narrowed to `families`."""
    all_fonts = registry()
    if not families:
        return all_fonts
    wanted = {f.casefold() for f in families}
    picked = [f for f in all_fonts if f.family.casefold() in wanted]
    if not picked:
        raise ValueError(
            f"none of the requested fonts {families} are registered; "
            f"available: {sorted({f.family for f in all_fonts})}"
        )
    return picked


def find(family: str) -> FontAsset:
    for asset in registry():
        if asset.family.casefold() == family.casefold():
            return asset
    return FontAsset(family=family, file=None)


@lru_cache(maxsize=64)
def _data_uri(rel: str) -> str:
    path = FONTS_DIR / rel
    mime = _MIME.get(path.suffix.lower(), "application/octet-stream")
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def face_css(assets: list[FontAsset]) -> str:
    """@font-face rules for the local fonts used by a spec, embedded as data URIs.

    Only the fonts a spec actually uses get embedded -- a full registry would
    bloat the HTML by megabytes.
    """
    rules = []
    for asset in assets:
        if asset.file is None:
            continue
        rules.append(
            f'@font-face {{ font-family: "{asset.family}"; '
            f'src: url("{_data_uri(asset.file)}"); font-display: block; }}'
        )
    return "\n".join(rules)
