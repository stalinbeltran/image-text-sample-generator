from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.models.params import (
    BoolParam,
    ColorParam,
    FloatParam,
    IntParam,
    Range,
    StrParam,
)

# --------------------------------------------------------------------------
# The recipe is the template you author. Every field may be a literal or a
# distribution; the resolver turns (recipe, seed) into a frozen ImageSpec.
# --------------------------------------------------------------------------


class CanvasRecipe(BaseModel):
    width: IntParam = 640
    height: IntParam = 480


class BackgroundRecipe(BaseModel):
    kind: StrParam = Field(
        default="solid",
        description=(
            "solid | gradient | noise | paper | lines | grid | dots | photo. "
            'Use {"choice": [...]} to mix kinds across a dataset.'
        ),
    )
    # Palette the two base colors are drawn from. Any CSS-ish hex.
    color: ColorParam = "#ffffff"
    color2: ColorParam = "#d8d8d8"
    angle: FloatParam = Range(range=(0, 360))

    # noise / paper / lines / grid / dots
    intensity: FloatParam = Range(range=(0.05, 0.25))
    scale: FloatParam = Range(range=(2, 12))
    line_color: ColorParam = "#9fb6d1"

    # photo
    photo_dir: str | None = Field(
        default=None,
        description="Subdirectory of the photos root. None = the root itself.",
    )
    photo_file: StrParam | None = Field(
        default=None, description="Pin a specific file instead of picking at random."
    )
    photo_brightness: FloatParam = Range(range=(0.7, 1.1))
    photo_blur: FloatParam = 0.0
    # A flat wash over the photo. Raising alpha makes text easier to read.
    overlay_color: ColorParam = "#ffffff"
    overlay_alpha: FloatParam = Range(range=(0.0, 0.35))


class ContentRecipe(BaseModel):
    source: StrParam = Field(
        default="words", description="words | chars | fixed"
    )
    text: StrParam | None = Field(
        default=None, description="Used when source == 'fixed'."
    )
    lang: StrParam = "mixed"  # es | en | mixed
    words: IntParam = Range(range=(20, 60), step=1)
    chars: IntParam = Range(range=(1, 1), step=1)
    alphabet: StrParam = (
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    )
    uppercase: BoolParam = False


class TypographyRecipe(BaseModel):
    font_family: StrParam | None = Field(
        default=None, description="None = pick at random from the font registry."
    )
    font_size: FloatParam = Range(range=(12, 30))
    font_weight: IntParam = Field(
        default_factory=lambda: Range(range=(400, 700), step=300)
    )
    italic: BoolParam = False
    color: ColorParam = Field(
        default="auto",
        description="'auto' picks a color that meets min_contrast against the background.",
    )
    min_contrast: FloatParam = 3.0
    opacity: FloatParam = 1.0
    letter_spacing: FloatParam = 0.0
    word_spacing: FloatParam = 0.0
    line_height: FloatParam = Range(range=(1.15, 1.6))
    align: StrParam = "left"  # left | center | right | justify
    text_stroke: FloatParam = 0.0
    stroke_color: ColorParam = "#000000"
    shadow: BoolParam = False
    blur: FloatParam = 0.0


class PlacementRecipe(BaseModel):
    # Region of the canvas the block's top-left corner may land in, as
    # fractions of canvas size. Defaults to the whole canvas.
    area: tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0)
    x: FloatParam | None = Field(default=None, description="Pin the x in px.")
    y: FloatParam | None = Field(default=None, description="Pin the y in px.")
    angle: FloatParam = 0.0
    avoid_overlap: bool = True
    margin: FloatParam = 8.0


class BlockRecipe(BaseModel):
    kind: Literal["paragraph", "word", "letter", "spaced"] = "paragraph"
    count: IntParam = 1

    width: FloatParam | None = Field(
        default=None,
        description="Box width in px. None = auto (shrink-to-fit) for word/letter, "
        "or 40-70% of the canvas for paragraphs.",
    )
    height: FloatParam | None = Field(
        default=None, description="None = grow with the content. A value clips it."
    )

    content: ContentRecipe = Field(default_factory=ContentRecipe)
    typography: TypographyRecipe = Field(default_factory=TypographyRecipe)
    placement: PlacementRecipe = Field(default_factory=PlacementRecipe)


class PostRecipe(BaseModel):
    """Degradations applied to the rendered PNG (never to the mask)."""

    blur: FloatParam = 0.0
    noise: FloatParam = 0.0  # gaussian sigma, 0-255 scale
    jpeg_quality: IntParam | None = None
    grayscale: BoolParam = False


class Recipe(BaseModel):
    name: str = "unnamed"
    canvas: CanvasRecipe = Field(default_factory=CanvasRecipe)
    background: BackgroundRecipe = Field(default_factory=BackgroundRecipe)
    blocks: list[BlockRecipe] = Field(default_factory=lambda: [BlockRecipe()])
    post: PostRecipe = Field(default_factory=PostRecipe)
    fonts: list[str] | None = Field(
        default=None,
        description="Restrict the font pool to these families. None = all registered.",
    )
