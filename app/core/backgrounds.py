from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

from app.models.spec import BackgroundSpec
from app.settings import PHOTOS_DIR

PHOTO_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    v = value.strip().lstrip("#")
    if len(v) == 3:
        v = "".join(c * 2 for c in v)
    if len(v) != 6:
        raise ValueError(f"expected a #rrggbb color, got {value!r}")
    return int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#%02x%02x%02x" % tuple(int(max(0, min(255, c))) for c in rgb)


def relative_luminance(rgb: tuple[float, float, float]) -> float:
    """WCAG relative luminance, 0 (black) to 1 (white)."""
    channels = []
    for c in rgb:
        c = c / 255.0
        channels.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = channels
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    la, lb = relative_luminance(a), relative_luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def list_photos(subdir: str | None = None) -> list[Path]:
    root = PHOTOS_DIR / subdir if subdir else PHOTOS_DIR
    if not root.is_dir():
        return []
    return sorted(p for p in root.rglob("*") if p.suffix.lower() in PHOTO_EXTS)


# --------------------------------------------------------------------------
# Procedural fields
# --------------------------------------------------------------------------


def _gradient_field(w: int, h: int, angle: float) -> np.ndarray:
    """A 0..1 ramp running along `angle` degrees."""
    rad = math.radians(angle)
    xs = np.linspace(0, 1, w, dtype=np.float32)[None, :]
    ys = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    t = xs * math.cos(rad) + ys * math.sin(rad)
    lo, hi = float(t.min()), float(t.max())
    return (t - lo) / (hi - lo) if hi > lo else np.zeros((h, w), dtype=np.float32)


def _value_noise(w: int, h: int, cells: float, rng: np.random.Generator) -> np.ndarray:
    """Smooth 0..1 noise: a coarse random grid upscaled bicubically."""
    cw = max(2, int(w / max(1.0, cells)))
    ch = max(2, int(h / max(1.0, cells)))
    coarse = rng.random((ch, cw), dtype=np.float32)
    img = Image.fromarray((coarse * 255).astype(np.uint8), mode="L")
    img = img.resize((w, h), Image.BICUBIC)
    return np.asarray(img, dtype=np.float32) / 255.0


def _blend(base: np.ndarray, color: tuple[int, int, int], alpha: np.ndarray) -> np.ndarray:
    """Alpha-composite a flat color over an RGB float array."""
    col = np.array(color, dtype=np.float32)[None, None, :]
    a = alpha[..., None]
    return base * (1 - a) + col * a


# --------------------------------------------------------------------------
# Builder
# --------------------------------------------------------------------------


def build(spec: BackgroundSpec, width: int, height: int) -> Image.Image:
    """Render a background. Pure function of (spec, width, height)."""
    if spec.kind == "photo":
        return _build_photo(spec, width, height)

    rng = np.random.default_rng(spec.seed % (2**32))
    c1 = np.array(hex_to_rgb(spec.color), dtype=np.float32)
    c2 = np.array(hex_to_rgb(spec.color2), dtype=np.float32)
    canvas = np.tile(c1, (height, width, 1)).astype(np.float32)

    if spec.kind == "solid":
        pass

    elif spec.kind == "gradient":
        t = _gradient_field(width, height, spec.angle)[..., None]
        canvas = c1[None, None, :] * (1 - t) + c2[None, None, :] * t

    elif spec.kind == "noise":
        grain = rng.normal(0.0, spec.intensity * 255.0, (height, width, 1)).astype(np.float32)
        canvas = canvas + grain

    elif spec.kind == "paper":
        # Coarse blotches for the fibre, plus fine grain on top.
        blotch = _value_noise(width, height, max(2.0, spec.scale * 6), rng)
        canvas = _blend(canvas, tuple(c2.astype(int)), blotch * spec.intensity)
        grain = rng.normal(0.0, spec.intensity * 90.0, (height, width, 1)).astype(np.float32)
        canvas = canvas + grain

    elif spec.kind in ("lines", "grid", "dots"):
        spacing = max(6.0, spec.scale * 4.0)
        line = np.array(hex_to_rgb(spec.line_color), dtype=np.float32)
        ys = np.arange(height, dtype=np.float32)[:, None]
        xs = np.arange(width, dtype=np.float32)[None, :]
        # A 1px-ish band wherever the coordinate lands on the grid.
        h_band = (ys % spacing < 1.0).astype(np.float32)
        v_band = (xs % spacing < 1.0).astype(np.float32)
        if spec.kind == "lines":
            alpha = np.broadcast_to(h_band, (height, width)).copy()
        elif spec.kind == "grid":
            alpha = np.maximum(
                np.broadcast_to(h_band, (height, width)),
                np.broadcast_to(v_band, (height, width)),
            )
        else:  # dots
            alpha = np.broadcast_to(h_band, (height, width)) * np.broadcast_to(
                v_band, (height, width)
            )
            alpha = np.asarray(
                Image.fromarray((alpha * 255).astype(np.uint8), "L").filter(
                    ImageFilter.MaxFilter(3)
                ),
                dtype=np.float32,
            ) / 255.0
        canvas = _blend(canvas, tuple(line.astype(int)), alpha * 0.85)

    else:
        raise ValueError(f"unknown background kind {spec.kind!r}")

    return Image.fromarray(np.clip(canvas, 0, 255).astype(np.uint8), mode="RGB")


def _build_photo(spec: BackgroundSpec, width: int, height: int) -> Image.Image:
    if not spec.photo_file:
        raise ValueError("photo background has no photo_file")
    path = PHOTOS_DIR / spec.photo_file
    if not path.is_file():
        raise FileNotFoundError(f"background photo not found: {path}")

    img = _load_photo(str(path))
    if spec.photo_crop:
        x, y, w, h = spec.photo_crop
        img = img.crop((x, y, x + w, y + h))
    img = img.resize((width, height), Image.LANCZOS)

    if spec.photo_blur > 0:
        img = img.filter(ImageFilter.GaussianBlur(spec.photo_blur))
    if spec.photo_brightness != 1.0:
        img = ImageEnhance.Brightness(img).enhance(spec.photo_brightness)
    if spec.overlay_alpha > 0:
        wash = Image.new("RGB", (width, height), hex_to_rgb(spec.overlay_color))
        img = Image.blend(img, wash, min(1.0, spec.overlay_alpha))
    return img


@lru_cache(maxsize=32)
def _load_photo(path: str) -> Image.Image:
    return Image.open(path).convert("RGB")


def mean_color(img: Image.Image, box: tuple[float, float, float, float]) -> tuple[float, float, float]:
    """Average RGB inside `box` (x, y, w, h), clamped to the image."""
    x, y, w, h = box
    x0 = max(0, min(img.width - 1, int(x)))
    y0 = max(0, min(img.height - 1, int(y)))
    x1 = max(x0 + 1, min(img.width, int(x + w)))
    y1 = max(y0 + 1, min(img.height, int(y + h)))
    region = np.asarray(img.crop((x0, y0, x1, y1)), dtype=np.float32)
    return tuple(region.reshape(-1, 3).mean(axis=0).tolist())
