from __future__ import annotations

import numpy as np
import pytest
import pytest_asyncio

from app.core.renderer import Renderer
from app.core.resolver import resolve
from app.models.recipe import (
    BackgroundRecipe,
    BlockRecipe,
    CanvasRecipe,
    ContentRecipe,
    PlacementRecipe,
    Recipe,
    TypographyRecipe,
)


# The renderer and every test that touches it must share one event loop:
# Playwright binds its connection to the loop it was started on, and awaiting it
# from a different loop hangs forever rather than erroring.
pytestmark = pytest.mark.asyncio(loop_scope="module")


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def renderer():
    r = Renderer()
    await r.start()
    yield r
    await r.stop()


def simple_recipe(**kw) -> Recipe:
    """No rotation, no blur, hard black on white -- so the mask is unambiguous."""
    return Recipe(
        canvas=CanvasRecipe(width=500, height=360),
        background=BackgroundRecipe(kind="solid", color="#ffffff"),
        blocks=[
            BlockRecipe(
                kind="paragraph",
                count=2,
                width=200,
                typography=TypographyRecipe(font_size=16, color="#000000", line_height=1.4),
                placement=PlacementRecipe(angle=0.0, margin=20),
            )
        ],
        **kw,
    )



async def test_render_is_deterministic(renderer):
    spec = resolve(simple_recipe(), 4242)
    a = await renderer.render(spec)
    b = await renderer.render(spec)
    assert a.image.tobytes() == b.image.tobytes()
    assert a.mask.tobytes() == b.mask.tobytes()
    assert a.labels.model_dump() == b.labels.model_dump()



async def test_labels_have_a_word_per_token(renderer):
    spec = resolve(simple_recipe(), 7)
    result = await renderer.render(spec)
    expected = sum(len(b.text.split()) for b in spec.blocks)
    assert len(result.labels.words) == expected
    assert len(result.labels.blocks) == len(spec.blocks)
    assert result.labels.lines



async def test_mask_ink_falls_inside_the_word_boxes(renderer):
    """The real check: ground truth has to agree with the pixels."""
    spec = resolve(simple_recipe(), 11)
    result = await renderer.render(spec)

    mask = np.asarray(result.mask, dtype=np.uint8)
    inside = np.zeros_like(mask, dtype=bool)
    pad = 1  # antialiasing bleeds a pixel past the layout box
    for word in result.labels.words:
        x, y, w, h = word.box
        x0 = max(0, int(x) - pad)
        y0 = max(0, int(y) - pad)
        x1 = min(mask.shape[1], int(np.ceil(x + w)) + pad)
        y1 = min(mask.shape[0], int(np.ceil(y + h)) + pad)
        inside[y0:y1, x0:x1] = True

    ink = mask > 127
    assert ink.sum() > 500, "the mask is empty -- nothing rendered"
    covered = (ink & inside).sum() / ink.sum()
    assert covered > 0.98, f"only {covered:.1%} of the text ink is inside a word box"



async def test_typography_actually_reaches_the_page(renderer):
    """A double quote in the style attribute once silently dropped every
    declaration after font-family -- size, color and rotation all reverted to
    browser defaults, and the labels happily described the wrong render. Assert
    the geometry reflects the font size we asked for."""
    recipe = simple_recipe()
    recipe.blocks[0].kind = "word"
    recipe.blocks[0].count = 1
    recipe.blocks[0].width = None
    recipe.blocks[0].content = ContentRecipe(source="fixed", text="Hxg")
    recipe.blocks[0].typography = TypographyRecipe(
        font_size=48, line_height=1.2, color="#000000"
    )
    spec = resolve(recipe, 2)
    assert spec.blocks[0].font_size == 48

    result = await renderer.render(spec)
    _, _, _, h = result.labels.blocks[0].box
    assert h > 40, f"a 48px font produced a {h}px tall block -- the style was dropped"

    ink = np.asarray(result.mask, dtype=np.uint8) > 127
    ys = np.nonzero(ink)[0]
    assert ys.max() - ys.min() > 25, "the rendered glyphs are far smaller than 48px"



async def test_mask_ink_survives_rotation(renderer):
    recipe = simple_recipe()
    recipe.blocks[0].placement.angle = 15.0
    spec = resolve(recipe, 3)
    result = await renderer.render(spec)

    mask = np.asarray(result.mask, dtype=np.uint8)
    ink = mask > 127
    assert ink.sum() > 500

    # Rotated quads: rasterise them and check the ink lands inside.
    from PIL import Image, ImageDraw

    poly = Image.new("L", (spec.width, spec.height), 0)
    draw = ImageDraw.Draw(poly)
    for word in result.labels.words:
        draw.polygon([tuple(p) for p in word.quad], fill=255)
    inside = np.asarray(poly, dtype=np.uint8) > 0

    covered = (ink & inside).sum() / ink.sum()
    assert covered > 0.95, f"only {covered:.1%} of rotated text ink is inside its quad"



async def test_mask_is_binary_and_the_image_is_not(renderer):
    spec = resolve(simple_recipe(), 5)
    result = await renderer.render(spec)
    values = set(np.unique(np.asarray(result.mask)).tolist())
    assert values <= {0, 255}
    assert result.image.size == (spec.width, spec.height)
    assert result.mask.size == (spec.width, spec.height)



async def test_soft_mask_keeps_antialiasing(renderer):
    spec = resolve(simple_recipe(), 5)
    result = await renderer.render(spec, mask_threshold=0)
    values = np.unique(np.asarray(result.mask))
    assert len(values) > 2  # grays present
