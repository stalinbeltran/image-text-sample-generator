from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SPEC_VERSION = 1

# --------------------------------------------------------------------------
# The frozen spec: zero randomness left. Rendering is a pure function of this
# object, so the PNGs are a cache you can delete and rebuild byte-for-byte.
# --------------------------------------------------------------------------


class BackgroundSpec(BaseModel):
    kind: Literal[
        "solid", "gradient", "noise", "paper", "lines", "grid", "dots", "photo"
    ]
    color: str = "#ffffff"
    color2: str = "#d8d8d8"
    angle: float = 0.0
    intensity: float = 0.0
    scale: float = 4.0
    line_color: str = "#9fb6d1"
    seed: int = 0

    photo_file: str | None = None
    photo_crop: tuple[int, int, int, int] | None = None  # x, y, w, h in source px
    photo_brightness: float = 1.0
    photo_blur: float = 0.0
    overlay_color: str = "#ffffff"
    overlay_alpha: float = 0.0


class TextBlockSpec(BaseModel):
    id: str
    kind: Literal["paragraph", "word", "letter", "spaced"]
    text: str

    x: float
    y: float
    width: float | None = None
    height: float | None = None

    font_family: str
    font_file: str | None = None  # relative to the fonts root; None = system font
    font_size: float
    font_weight: int = 400
    italic: bool = False

    color: str = "#000000"
    opacity: float = 1.0
    letter_spacing: float = 0.0
    word_spacing: float = 0.0
    line_height: float = 1.4
    align: str = "left"
    angle: float = 0.0
    uppercase: bool = False

    text_stroke: float = 0.0
    stroke_color: str = "#000000"
    shadow: bool = False
    blur: float = 0.0


class PostSpec(BaseModel):
    blur: float = 0.0
    noise: float = 0.0
    jpeg_quality: int | None = None
    grayscale: bool = False
    seed: int = 0  # drives the noise field; carried in the spec so it stays reproducible


class ImageSpec(BaseModel):
    version: int = SPEC_VERSION
    id: str
    seed: int
    width: int
    height: int
    background: BackgroundSpec
    blocks: list[TextBlockSpec] = Field(default_factory=list)
    post: PostSpec = Field(default_factory=PostSpec)


# --------------------------------------------------------------------------
# Labels
# --------------------------------------------------------------------------

Box = tuple[float, float, float, float]  # x, y, w, h (axis-aligned)
Quad = list[tuple[float, float]]  # 4 corners, clockwise from top-left


class WordLabel(BaseModel):
    block_id: str
    line_index: int
    text: str
    box: Box
    quad: Quad


class LineLabel(BaseModel):
    block_id: str
    index: int
    text: str
    box: Box
    quad: Quad


class BlockLabel(BaseModel):
    block_id: str
    kind: str
    text: str
    angle: float
    box: Box
    quad: Quad


class Labels(BaseModel):
    image_id: str
    width: int
    height: int
    blocks: list[BlockLabel] = Field(default_factory=list)
    lines: list[LineLabel] = Field(default_factory=list)
    words: list[WordLabel] = Field(default_factory=list)
    # True when two rendered blocks actually overlap. Best-effort avoidance
    # happens at resolve time on estimated heights, so this is the honest,
    # post-render answer -- filter on it if your training needs clean samples.
    has_overlap: bool = False
