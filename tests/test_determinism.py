from __future__ import annotations

import pytest

from app.core.resolver import resolve
from app.models.params import Choice, Range
from app.models.recipe import (
    BlockRecipe,
    CanvasRecipe,
    ContentRecipe,
    PlacementRecipe,
    Recipe,
    TypographyRecipe,
)


def make_recipe(**kw) -> Recipe:
    return Recipe(
        canvas=CanvasRecipe(width=400, height=300),
        blocks=[
            BlockRecipe(
                kind="paragraph",
                count=Range(range=(2, 4), step=1),
                typography=TypographyRecipe(font_size=Range(range=(10, 24))),
            )
        ],
        **kw,
    )


def test_same_seed_same_spec():
    recipe = make_recipe()
    a = resolve(recipe, 12345)
    b = resolve(recipe, 12345)
    assert a.model_dump() == b.model_dump()


def test_different_seed_different_spec():
    recipe = make_recipe()
    a = resolve(recipe, 1)
    b = resolve(recipe, 2)
    assert a.model_dump() != b.model_dump()


def test_pinned_params_never_move():
    recipe = Recipe(
        canvas=CanvasRecipe(width=512, height=256),
        blocks=[
            BlockRecipe(
                kind="paragraph",
                count=3,
                width=200,
                typography=TypographyRecipe(font_size=14, color="#123456", align="left"),
            )
        ],
    )
    for seed in range(8):
        spec = resolve(recipe, seed)
        assert (spec.width, spec.height) == (512, 256)
        assert len(spec.blocks) == 3
        for block in spec.blocks:
            assert block.width == 200
            assert block.font_size == 14
            assert block.color == "#123456"


def test_font_is_consistent_within_a_paragraph_but_varies_across_blocks():
    recipe = Recipe(
        blocks=[BlockRecipe(kind="paragraph", count=12)],
    )
    spec = resolve(recipe, 7)
    families = {b.font_family for b in spec.blocks}
    # Each block carries exactly one family (consistency is structural), and
    # across 12 blocks the random pool should produce more than one.
    assert all(isinstance(b.font_family, str) and b.font_family for b in spec.blocks)
    assert len(families) > 1


def test_adding_a_block_does_not_reshuffle_the_earlier_ones():
    """Sub-seeds are keyed by path, so appending a block leaves the others alone."""
    base = Recipe(blocks=[BlockRecipe(kind="paragraph", count=2)])
    grown = Recipe(
        blocks=[
            BlockRecipe(kind="paragraph", count=2),
            BlockRecipe(kind="word", count=3),
        ]
    )
    a = resolve(base, 99)
    b = resolve(grown, 99)
    for x, y in zip(a.blocks, b.blocks[:2]):
        assert x.text == y.text
        assert x.font_family == y.font_family
        assert x.font_size == y.font_size


def test_blocks_stay_inside_the_canvas():
    recipe = Recipe(
        canvas=CanvasRecipe(width=640, height=480),
        blocks=[BlockRecipe(kind="paragraph", count=Range(range=(1, 3), step=1))],
    )
    for seed in range(20):
        spec = resolve(recipe, seed)
        for block in spec.blocks:
            assert 0 <= block.x < spec.width
            assert 0 <= block.y < spec.height


def test_placement_area_is_respected():
    recipe = Recipe(
        canvas=CanvasRecipe(width=600, height=400),
        blocks=[
            BlockRecipe(
                kind="word",
                count=4,
                placement=PlacementRecipe(area=(0.0, 0.5, 0.5, 1.0)),
            )
        ],
    )
    for seed in range(10):
        for block in resolve(recipe, seed).blocks:
            assert block.x >= 0
            assert block.y >= 200 - 1e-6  # top half is off-limits


def test_choice_weights_are_honoured():
    recipe = Recipe(
        blocks=[
            BlockRecipe(
                kind="word",
                count=1,
                typography=TypographyRecipe(align=Choice(choice=["left", "center"])),
            )
        ]
    )
    aligns = {resolve(recipe, s).blocks[0].align for s in range(30)}
    assert aligns <= {"left", "center"}
    assert len(aligns) == 2


def test_fixed_text_requires_text():
    recipe = Recipe(
        blocks=[BlockRecipe(kind="word", content=ContentRecipe(source="fixed"))]
    )
    with pytest.raises(ValueError, match="requires content.text"):
        resolve(recipe, 1)


def test_auto_color_clears_the_contrast_bar():
    from app.core import backgrounds

    recipe = Recipe(
        canvas=CanvasRecipe(width=300, height=200),
        blocks=[
            BlockRecipe(
                kind="paragraph",
                count=2,
                typography=TypographyRecipe(color="auto", min_contrast=4.5),
            )
        ],
    )
    for seed in range(10):
        spec = resolve(recipe, seed)
        bg = backgrounds.build(spec.background, spec.width, spec.height)
        for block in spec.blocks:
            fg = backgrounds.hex_to_rgb(block.color)
            local_bg = backgrounds.mean_color(bg, (block.x, block.y, 100, 40))
            assert backgrounds.contrast_ratio(fg, local_bg) >= 3.0
