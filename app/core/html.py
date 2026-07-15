from __future__ import annotations

import base64
import io
from html import escape

from PIL import Image

from app.core import backgrounds, fonts
from app.models.spec import ImageSpec, TextBlockSpec

# Rendering the mask is the *same DOM* with this stylesheet bolted on: the
# background disappears, every glyph goes pure white on black, and anything
# that softens the text (opacity, blur, shadow) is switched off. Transforms are
# deliberately left alone so the mask stays pixel-aligned with the image.
MASK_CSS = """
html, body { background: #000 !important; }
#bg { display: none !important; }
.tb {
  color: #fff !important;
  opacity: 1 !important;
  filter: none !important;
  text-shadow: none !important;
  background: transparent !important;
  mix-blend-mode: normal !important;
  /* Keep the stroke width -- it is real ink -- but paint it white like the fill. */
  -webkit-text-stroke-color: #fff !important;
}
.tb * { color: #fff !important; opacity: 1 !important; }
"""


def _img_data_uri(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG", compress_level=1)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def _block_style(block: TextBlockSpec) -> str:
    # Single quotes around the family: this whole string goes into a
    # style="..." attribute, and a double quote here would close the attribute
    # early and silently drop every declaration after it.
    parts = [
        f"left:{block.x}px",
        f"top:{block.y}px",
        f"font-family:'{block.font_family}', sans-serif",
        f"font-size:{block.font_size}px",
        f"font-weight:{block.font_weight}",
        f"color:{block.color}",
        f"line-height:{block.line_height}",
        f"text-align:{block.align}",
    ]
    if block.width is not None:
        parts.append(f"width:{block.width}px")
    if block.height is not None:
        parts.append(f"height:{block.height}px")
        parts.append("overflow:hidden")
    if block.italic:
        parts.append("font-style:italic")
    if block.opacity != 1.0:
        parts.append(f"opacity:{block.opacity}")
    if block.letter_spacing:
        parts.append(f"letter-spacing:{block.letter_spacing}px")
    if block.word_spacing:
        parts.append(f"word-spacing:{block.word_spacing}px")
    if block.angle:
        parts.append(f"transform:rotate({block.angle}deg)")
    if block.text_stroke:
        parts.append(f"-webkit-text-stroke:{block.text_stroke}px {block.stroke_color}")
    if block.shadow:
        parts.append("text-shadow:1px 1px 2px rgba(0,0,0,0.45)")
    if block.blur:
        parts.append(f"filter:blur({block.blur}px)")
    if block.kind != "paragraph":
        parts.append("white-space:nowrap")
    return ";".join(parts)


def _spans(text: str) -> str:
    """One span per whitespace-separated token -- these are the word boxes.

    Splitting on whitespace and re-joining with a single space is layout-neutral
    (CSS collapses runs of whitespace anyway), so the spans don't move anything.
    """
    tokens = text.split()
    return " ".join(f'<span class="w">{escape(tok)}</span>' for tok in tokens)


def build_html(spec: ImageSpec) -> str:
    bg = backgrounds.build(spec.background, spec.width, spec.height)
    used = {b.font_family: fonts.FontAsset(b.font_family, b.font_file) for b in spec.blocks}
    face_css = fonts.face_css(list(used.values()))

    divs = []
    for block in spec.blocks:
        divs.append(
            f'<div class="tb" data-id="{block.id}" data-kind="{block.kind}" '
            f'data-angle="{block.angle}" data-ls="{block.letter_spacing}" '
            f'style="{escape(_block_style(block), quote=True)}">{_spans(block.text)}</div>'
        )

    return f"""<!doctype html>
<html><head><meta charset="utf-8"><style>
{face_css}
* {{ margin:0; padding:0; box-sizing:border-box; }}
html, body {{ width:{spec.width}px; height:{spec.height}px; overflow:hidden; background:#fff; }}
#bg {{ position:absolute; left:0; top:0; width:{spec.width}px; height:{spec.height}px; }}
.tb {{ position:absolute; transform-origin:center center; }}
</style></head><body>
<img id="bg" src="{_img_data_uri(bg)}" alt="">
{chr(10).join(divs)}
</body></html>"""


def font_families(spec: ImageSpec) -> list[str]:
    return sorted({b.font_family for b in spec.blocks})
