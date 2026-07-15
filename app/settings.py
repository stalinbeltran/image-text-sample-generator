from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _dir(env: str, default: str) -> Path:
    p = Path(os.environ.get(env, ROOT / default))
    p.mkdir(parents=True, exist_ok=True)
    return p


FONTS_DIR = _dir("ITF_FONTS_DIR", "assets/fonts")
PHOTOS_DIR = _dir("ITF_PHOTOS_DIR", "assets/backgrounds")
DATA_DIR = _dir("ITF_DATA_DIR", "data")
DATASETS_DIR = DATA_DIR / "datasets"
DATASETS_DIR.mkdir(parents=True, exist_ok=True)

# Max concurrent browser pages used when materializing a dataset.
RENDER_CONCURRENCY = int(os.environ.get("ITF_RENDER_CONCURRENCY", "4"))

# Point at a chrome.exe / chrome binary to use instead of the one Playwright
# downloads into %LOCALAPPDATA%\ms-playwright. Unset = use Playwright's own.
_chromium = os.environ.get("ITF_CHROMIUM_PATH")
CHROMIUM_PATH = Path(_chromium) if _chromium else None

