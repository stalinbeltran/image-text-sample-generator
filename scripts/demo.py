"""Render a few samples from a recipe and draw the labels on top.

    python scripts/demo.py examples/mixed_layout.json --n 4 --out out/demo

Produces, per sample: the image, the mask, and an overlay with the word quads
in green and the block quads in red -- the quickest way to see that the ground
truth actually lines up with the pixels.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Run as a plain script (`python scripts/demo.py`), so the repo root is not on
# sys.path -- only scripts/ is. `app` is not installed either, since the README
# sets up with requirements.txt rather than `pip install -e .`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw

from app.core.renderer import Renderer
from app.core.resolver import resolve
from app.models.recipe import Recipe


def overlay(img: Image.Image, labels) -> Image.Image:
    canvas = img.convert("RGB").copy()
    draw = ImageDraw.Draw(canvas)
    for word in labels.words:
        draw.polygon([tuple(p) for p in word.quad], outline=(0, 220, 0))
    for block in labels.blocks:
        draw.polygon([tuple(p) for p in block.quad], outline=(230, 0, 0))
    return canvas


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("recipe", type=Path)
    ap.add_argument("--n", type=int, default=4)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", type=Path, default=Path("out/demo"))
    args = ap.parse_args()

    recipe = Recipe.model_validate(json.loads(args.recipe.read_text(encoding="utf-8")))
    args.out.mkdir(parents=True, exist_ok=True)

    renderer = Renderer()
    await renderer.start()
    try:
        for i in range(args.n):
            seed = args.seed + i
            spec = resolve(recipe, seed)
            result = await renderer.render(spec)
            result.image.save(args.out / f"{i:02d}_image.png")
            if result.mask:
                result.mask.save(args.out / f"{i:02d}_mask.png")
            overlay(result.image, result.labels).save(args.out / f"{i:02d}_overlay.png")
            (args.out / f"{i:02d}_spec.json").write_text(
                spec.model_dump_json(indent=2), encoding="utf-8"
            )
            print(
                f"[{i}] seed={seed} {spec.width}x{spec.height} "
                f"blocks={len(result.labels.blocks)} words={len(result.labels.words)} "
                f"overlap={result.labels.has_overlap}"
            )
    finally:
        await renderer.stop()
    print(f"\nwrote {args.n} samples to {args.out.resolve()}")


if __name__ == "__main__":
    asyncio.run(main())
