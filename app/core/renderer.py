from __future__ import annotations

import asyncio
import io
from dataclasses import dataclass
from typing import Any

import numpy as np
from PIL import Image, ImageFilter
from playwright.async_api import Browser, async_playwright

from app.core import html as html_mod
from app.core import labels as labels_mod
from app.models.spec import ImageSpec, Labels, PostSpec
from app.settings import CHROMIUM_PATH, RENDER_CONCURRENCY

# Grayscale antialiasing and no hinting keep glyph rasterisation stable across
# machines. Chromium still makes no cross-platform pixel guarantee, but the
# labels come from the spec, not the pixels, so they are always exact.
LAUNCH_ARGS = [
    "--disable-lcd-text",
    "--font-render-hinting=none",
    "--force-color-profile=srgb",
    "--hide-scrollbars",
]

# Pull the layout rects out of the DOM. Transforms are switched off for the
# read (reading a rect forces a synchronous reflow, so this is exact), then
# restored -- rotation is re-applied analytically when the labels are built.
EXTRACT_JS = """
() => {
  const style = document.createElement('style');
  style.textContent = '.tb { transform: none !important; }';
  document.head.appendChild(style);
  const out = [];
  for (const div of document.querySelectorAll('.tb')) {
    const r = div.getBoundingClientRect();
    const words = [];
    for (const span of div.querySelectorAll('.w')) {
      const s = span.getBoundingClientRect();
      words.push({ text: span.textContent, x: s.x, y: s.y, w: s.width, h: s.height });
    }
    out.push({
      id: div.dataset.id,
      kind: div.dataset.kind,
      angle: parseFloat(div.dataset.angle || '0'),
      ls: parseFloat(div.dataset.ls || '0'),
      x: r.x, y: r.y, w: r.width, h: r.height,
      words,
    });
  }
  style.remove();
  return out;
}
"""

READY_JS = """
async (families) => {
  await Promise.all(families.map(f => document.fonts.load(`16px "${f}"`)));
  await document.fonts.ready;
  const bg = document.getElementById('bg');
  if (bg && !bg.complete) await bg.decode();
}
"""


@dataclass
class RenderResult:
    image: Image.Image
    labels: Labels
    mask: Image.Image | None = None


class Renderer:
    """A long-lived Chromium. Start it once per process, reuse for every render."""

    def __init__(self, concurrency: int = RENDER_CONCURRENCY):
        self._pw = None
        self._browser: Browser | None = None
        self._sem = asyncio.Semaphore(concurrency)

    async def start(self) -> None:
        if self._browser is not None:
            return
        self._pw = await async_playwright().start()

        launch: dict[str, Any] = {"args": LAUNCH_ARGS}
        if CHROMIUM_PATH is not None:
            if not CHROMIUM_PATH.is_file():
                raise FileNotFoundError(f"ITF_CHROMIUM_PATH does not exist: {CHROMIUM_PATH}")
            launch["executable_path"] = str(CHROMIUM_PATH)

        try:
            self._browser = await self._pw.chromium.launch(**launch)
        except NotImplementedError as exc:  # pragma: no cover - Windows loop trap
            raise RuntimeError(
                "Playwright could not spawn its driver: this event loop cannot create "
                "subprocesses. On Windows that means a SelectorEventLoop, which is what "
                "`uvicorn --reload` selects. Start the server with `python -m app.serve "
                "--reload` instead, or drop --reload."
            ) from exc

    async def stop(self) -> None:
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._pw is not None:
            await self._pw.stop()
            self._pw = None

    async def render(
        self, spec: ImageSpec, *, want_mask: bool = True, mask_threshold: int = 128
    ) -> RenderResult:
        if self._browser is None:
            raise RuntimeError("Renderer.start() was never awaited")

        markup = html_mod.build_html(spec)
        families = html_mod.font_families(spec)
        clip = {"x": 0, "y": 0, "width": spec.width, "height": spec.height}

        async with self._sem:
            page = await self._browser.new_page(
                viewport={"width": spec.width, "height": spec.height},
                device_scale_factor=1,
            )
            try:
                await page.set_content(markup, wait_until="load")
                await page.evaluate(READY_JS, families)

                image_png = await page.screenshot(type="png", clip=clip)
                dom: list[dict[str, Any]] = await page.evaluate(EXTRACT_JS)

                mask_img = None
                if want_mask:
                    await page.add_style_tag(content=html_mod.MASK_CSS)
                    mask_png = await page.screenshot(type="png", clip=clip)
                    mask_img = _to_mask(mask_png, mask_threshold)
            finally:
                await page.close()

        image = Image.open(io.BytesIO(image_png)).convert("RGB")
        image = apply_post(image, spec.post)
        labels = labels_mod.build(spec.id, spec.width, spec.height, dom)
        return RenderResult(image=image, labels=labels, mask=mask_img)


def _to_mask(png: bytes, threshold: int) -> Image.Image:
    """White text on black. threshold <= 0 keeps the soft (antialiased) mask."""
    gray = Image.open(io.BytesIO(png)).convert("L")
    if threshold <= 0:
        return gray
    return gray.point(lambda v: 255 if v >= threshold else 0, mode="L")


def apply_post(img: Image.Image, post: PostSpec) -> Image.Image:
    """Degradations that mimic a camera or a scan. Never applied to the mask."""
    if post.blur > 0:
        img = img.filter(ImageFilter.GaussianBlur(post.blur))
    if post.noise > 0:
        rng = np.random.default_rng(post.seed % (2**32))
        arr = np.asarray(img, dtype=np.float32)
        arr += rng.normal(0.0, post.noise, arr.shape)
        img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")
    if post.grayscale:
        img = img.convert("L").convert("RGB")
    if post.jpeg_quality is not None:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=int(post.jpeg_quality))
        buf.seek(0)
        img = Image.open(buf).convert("RGB")
    return img
