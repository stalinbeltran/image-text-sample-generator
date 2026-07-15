from __future__ import annotations

import colorsys
import math
import random
from typing import Callable

from PIL import Image

from app.core import backgrounds, corpus, fonts
from app.core.rng import derive_seed, rng_for
from app.models.params import sample, sample_bool, sample_float, sample_int
from app.models.recipe import BlockRecipe, Recipe
from app.models.spec import BackgroundSpec, ImageSpec, PostSpec, TextBlockSpec

PLACEMENT_TRIES = 120
HEIGHT_SAFETY = 1.15


# --------------------------------------------------------------------------
# Geometry estimates
#
# Real boxes come from the DOM at render time. These estimates exist only so
# the resolver can lay blocks out without overlapping -- being a few pixels off
# costs nothing, because the labels never come from here.
# --------------------------------------------------------------------------


def _avg_char_width(font_size: float, letter_spacing: float) -> float:
    return 0.52 * font_size + letter_spacing


def estimate_size(
    text: str, width: float | None, font_size: float, line_height: float, letter_spacing: float
) -> tuple[float, float]:
    char_w = _avg_char_width(font_size, letter_spacing)
    if width is None:
        return len(text) * char_w, font_size * line_height
    # Words don't split, so a wrapped line leaves a ragged tail unused. Ignoring
    # that underestimates the height, which is the dangerous direction: the
    # resolver would think a paragraph fits where it doesn't. Measured against
    # real renders, 0.92 puts the estimate at ~1.05x the truth on average, and
    # HEIGHT_SAFETY covers the fonts whose glyphs run wider than the 0.52em
    # assumption (the estimate bottomed out at 0.77x without it).
    per_line = max(1.0, (width / char_w) * 0.92)
    lines = max(1, math.ceil(len(text) / per_line))
    return width, lines * font_size * line_height * HEIGHT_SAFETY


def rotated_aabb(x: float, y: float, w: float, h: float, angle: float) -> tuple[float, float, float, float]:
    """Axis-aligned bounds of a box rotated about its own center."""
    if not angle:
        return x, y, w, h
    rad = math.radians(angle)
    cos, sin = abs(math.cos(rad)), abs(math.sin(rad))
    nw = w * cos + h * sin
    nh = w * sin + h * cos
    return x + (w - nw) / 2, y + (h - nh) / 2, nw, nh


def _overlap_area(a: tuple[float, ...], b: tuple[float, ...], margin: float) -> float:
    """Area of the intersection once `a` is grown by `margin` on every side."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ax, ay = ax - margin, ay - margin
    aw, ah = aw + 2 * margin, ah + 2 * margin
    dx = min(ax + aw, bx + bw) - max(ax, bx)
    dy = min(ay + ah, by + bh) - max(ay, by)
    return dx * dy if dx > 0 and dy > 0 else 0.0


# --------------------------------------------------------------------------
# Color
# --------------------------------------------------------------------------


def pick_contrasting_color(
    bg_rgb: tuple[float, float, float], min_ratio: float, rng: random.Random
) -> str:
    """A random color that clears `min_ratio` contrast against the background."""
    go_dark = backgrounds.relative_luminance(bg_rgb) > 0.35
    for _ in range(30):
        hue = rng.random()
        sat = rng.uniform(0.0, 0.7)
        val = rng.uniform(0.0, 0.30) if go_dark else rng.uniform(0.78, 1.0)
        rgb = tuple(int(round(c * 255)) for c in colorsys.hsv_to_rgb(hue, sat, val))
        if backgrounds.contrast_ratio(rgb, bg_rgb) >= min_ratio:
            return backgrounds.rgb_to_hex(rgb)
    # Nothing random cleared the bar (very mid-gray background) -- take whichever
    # extreme is furthest away and accept whatever ratio that gives.
    black, white = (0, 0, 0), (255, 255, 255)
    best = max(
        (black, white), key=lambda c: backgrounds.contrast_ratio(c, bg_rgb)
    )
    return backgrounds.rgb_to_hex(best)


# --------------------------------------------------------------------------
# Background
# --------------------------------------------------------------------------


def resolve_background(recipe: Recipe, seed: int, width: int, height: int) -> BackgroundSpec:
    rng = rng_for(seed, "background")
    br = recipe.background
    kind = sample(br.kind, rng)

    spec = BackgroundSpec(
        kind=kind,
        color=sample(br.color, rng),
        color2=sample(br.color2, rng),
        angle=sample_float(br.angle, rng),
        intensity=sample_float(br.intensity, rng),
        scale=sample_float(br.scale, rng),
        line_color=sample(br.line_color, rng),
        seed=derive_seed(seed, "background.pixels") % (2**32),
    )

    if kind == "photo":
        if br.photo_file is not None:
            spec.photo_file = sample(br.photo_file, rng)
        else:
            candidates = backgrounds.list_photos(br.photo_dir)
            if not candidates:
                raise ValueError(
                    f"background kind 'photo' needs images in {backgrounds.PHOTOS_DIR}"
                    + (f"/{br.photo_dir}" if br.photo_dir else "")
                )
            chosen = rng.choice(candidates)
            spec.photo_file = chosen.relative_to(backgrounds.PHOTOS_DIR).as_posix()

        spec.photo_crop = _pick_crop(spec.photo_file, width, height, rng)
        spec.photo_brightness = sample_float(br.photo_brightness, rng)
        spec.photo_blur = sample_float(br.photo_blur, rng)
        spec.overlay_color = sample(br.overlay_color, rng)
        spec.overlay_alpha = sample_float(br.overlay_alpha, rng)

    return spec


def _pick_crop(rel: str, width: int, height: int, rng: random.Random) -> tuple[int, int, int, int]:
    """A random crop of the source photo matching the canvas aspect ratio."""
    with Image.open(backgrounds.PHOTOS_DIR / rel) as img:
        sw, sh = img.size
    target = width / height
    # Largest box with the canvas aspect ratio that fits in the source.
    if sw / sh > target:
        ch = sh
        cw = int(round(sh * target))
    else:
        cw = sw
        ch = int(round(sw / target))
    # Then shrink a little and slide it around, so two images from the same
    # photo don't come out identical.
    zoom = rng.uniform(0.75, 1.0)
    cw, ch = max(8, int(cw * zoom)), max(8, int(ch * zoom))
    x = rng.randint(0, max(0, sw - cw))
    y = rng.randint(0, max(0, sh - ch))
    return x, y, cw, ch


# --------------------------------------------------------------------------
# Text blocks
# --------------------------------------------------------------------------


def _resolve_content(block: BlockRecipe, rng: random.Random) -> str:
    c = block.content
    source = sample(c.source, rng)
    if source == "fixed":
        if c.text is None:
            raise ValueError("content.source == 'fixed' requires content.text")
        text = str(sample(c.text, rng))
    elif source == "chars":
        text = corpus.make_chars(rng, sample_int(c.chars, rng), str(sample(c.alphabet, rng)))
    else:  # words
        lang = str(sample(c.lang, rng))
        if block.kind == "letter":
            text = corpus.make_chars(rng, sample_int(c.chars, rng), str(sample(c.alphabet, rng)))
        elif block.kind in ("word", "spaced"):
            text = corpus.make_word(rng, lang)
        else:
            text = corpus.make_words(rng, sample_int(c.words, rng), lang)
    if sample_bool(c.uppercase, rng):
        text = text.upper()
    return text


def _resolve_block(
    block: BlockRecipe,
    index: int,
    path: str,
    seed: int,
    canvas: tuple[int, int],
    font_pool: list[fonts.FontAsset],
    bg_img: Callable[[], Image.Image],
    placed: list[tuple[float, float, float, float]],
) -> TextBlockSpec:
    rng = rng_for(seed, path)
    cw, ch = canvas
    t = block.typography

    text = _resolve_content(block, rng)

    family = sample(t.font_family, rng) if t.font_family is not None else None
    asset = fonts.find(str(family)) if family else rng.choice(font_pool)

    font_size = sample_float(t.font_size, rng)
    line_height = sample_float(t.line_height, rng)

    letter_spacing = sample_float(t.letter_spacing, rng)
    if block.kind == "spaced" and letter_spacing == 0.0:
        letter_spacing = font_size * rng.uniform(0.15, 0.6)

    if block.width is not None:
        width = sample_float(block.width, rng)
    elif block.kind == "paragraph":
        width = cw * rng.uniform(0.40, 0.70)
    else:
        width = None  # shrink-to-fit

    height = sample_float(block.height, rng) if block.height is not None else None

    est_w, est_h = estimate_size(text, width, font_size, line_height, letter_spacing)
    if height is not None:
        est_h = height

    angle = sample_float(block.placement.angle, rng)
    margin = sample_float(block.placement.margin, rng)
    x, y = _place(block, rng, canvas, est_w, est_h, angle, margin, placed)
    placed.append(rotated_aabb(x, y, est_w, est_h, angle))

    color = sample(t.color, rng)
    if color == "auto":
        bg_rgb = backgrounds.mean_color(bg_img(), (x, y, est_w, est_h))
        color = pick_contrasting_color(bg_rgb, sample_float(t.min_contrast, rng), rng)

    return TextBlockSpec(
        id=f"b{index}",
        kind=block.kind,
        text=text,
        x=round(x, 2),
        y=round(y, 2),
        width=round(width, 2) if width is not None else None,
        height=round(height, 2) if height is not None else None,
        font_family=asset.family,
        font_file=asset.file,
        font_size=round(font_size, 2),
        font_weight=sample_int(t.font_weight, rng),
        italic=sample_bool(t.italic, rng),
        color=color,
        opacity=round(sample_float(t.opacity, rng), 3),
        letter_spacing=round(letter_spacing, 2),
        word_spacing=round(sample_float(t.word_spacing, rng), 2),
        line_height=round(line_height, 3),
        align=str(sample(t.align, rng)),
        angle=round(angle, 2),
        uppercase=False,  # already applied to `text`, so the DOM text matches the labels
        text_stroke=round(sample_float(t.text_stroke, rng), 2),
        stroke_color=str(sample(t.stroke_color, rng)),
        shadow=sample_bool(t.shadow, rng),
        blur=round(sample_float(t.blur, rng), 2),
    )


def _place(
    block: BlockRecipe,
    rng: random.Random,
    canvas: tuple[int, int],
    est_w: float,
    est_h: float,
    angle: float,
    margin: float,
    placed: list[tuple[float, float, float, float]],
) -> tuple[float, float]:
    cw, ch = canvas
    p = block.placement

    if p.x is not None and p.y is not None:
        return sample_float(p.x, rng), sample_float(p.y, rng)

    fx0, fy0, fx1, fy1 = p.area
    x0, y0 = fx0 * cw, fy0 * ch
    x1, y1 = fx1 * cw, fy1 * ch

    # Keep the *rotated* footprint inside the area.
    _, _, rw, rh = rotated_aabb(0, 0, est_w, est_h, angle)
    hi_x = max(x0, x1 - rw)
    hi_y = max(y0, y1 - rh)

    best: tuple[float, float] = (x0, y0)
    best_cost = float("inf")
    for _ in range(PLACEMENT_TRIES if p.avoid_overlap else 1):
        x = sample_float(p.x, rng) if p.x is not None else rng.uniform(x0, hi_x)
        y = sample_float(p.y, rng) if p.y is not None else rng.uniform(y0, hi_y)
        if not p.avoid_overlap:
            return x, y

        candidate = rotated_aabb(x, y, est_w, est_h, angle)
        cost = sum(_overlap_area(candidate, other, margin) for other in placed)
        if cost < best_cost:
            best, best_cost = (x, y), cost
        if cost == 0:
            break

    # When the canvas is genuinely too crowded, no position is free. Keeping the
    # *least* overlapping candidate degrades gracefully; keeping the last one
    # tried would land a paragraph squarely on top of another at random.
    return best


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def resolve(recipe: Recipe, seed: int, image_id: str | None = None) -> ImageSpec:
    """(recipe, seed) -> a fully concrete ImageSpec. Same inputs, same output."""
    root = rng_for(seed, "canvas")
    width = sample_int(recipe.canvas.width, root)
    height = sample_int(recipe.canvas.height, root)

    background = resolve_background(recipe, seed, width, height)
    font_pool = fonts.pool(recipe.fonts)

    # Only rasterised if a block actually asks for `color: "auto"` -- for a
    # recipe with fixed colors this saves a full background render per item,
    # which is the difference between minutes and seconds on a large dataset.
    cached: list[Image.Image] = []

    def bg_img() -> Image.Image:
        if not cached:
            cached.append(backgrounds.build(background, width, height))
        return cached[0]

    blocks: list[TextBlockSpec] = []
    placed: list[tuple[float, float, float, float]] = []
    index = 0
    for gi, block in enumerate(recipe.blocks):
        count = sample_int(block.count, rng_for(seed, f"blocks[{gi}].count"))
        for k in range(count):
            blocks.append(
                _resolve_block(
                    block,
                    index,
                    f"blocks[{gi}][{k}]",
                    seed,
                    (width, height),
                    font_pool,
                    bg_img,
                    placed,
                )
            )
            index += 1

    prng = rng_for(seed, "post")
    post = PostSpec(
        blur=sample_float(recipe.post.blur, prng),
        noise=sample_float(recipe.post.noise, prng),
        jpeg_quality=(
            sample_int(recipe.post.jpeg_quality, prng)
            if recipe.post.jpeg_quality is not None
            else None
        ),
        grayscale=sample_bool(recipe.post.grayscale, prng),
        seed=derive_seed(seed, "post.noise") % (2**32),
    )

    return ImageSpec(
        id=image_id or f"{seed:016x}",
        seed=seed,
        width=width,
        height=height,
        background=background,
        blocks=blocks,
        post=post,
    )
