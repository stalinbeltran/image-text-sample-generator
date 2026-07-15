from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.routes import router
from app.core import recipes_store
from app.core.renderer import Renderer

STATIC_DIR = Path(__file__).resolve().parent / "web" / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    recipes_store.seed_examples()
    renderer = Renderer()
    await renderer.start()
    app.state.renderer = renderer
    try:
        yield
    finally:
        await renderer.stop()


app = FastAPI(
    title="image-text-finder dataset API",
    version=__version__,
    summary="Synthetic text-on-image datasets for training a text-detection CNN.",
    description=(
        "Recipes describe a distribution of images. Resolving a recipe with a seed "
        "produces a frozen spec with no randomness left in it; rendering is a pure "
        "function of that spec. The specs are the dataset -- the PNGs are a cache "
        "you can delete and rebuild byte-for-byte."
    ),
    lifespan=lifespan,
)
app.include_router(router)


@app.get("/", include_in_schema=False)
async def index() -> RedirectResponse:
    return RedirectResponse(url="/ui/")


# Mounted last: the API routes above must win any path they both match.
# The UI is a plain HTTP client of those routes -- it holds no logic of its own.
app.mount("/ui", StaticFiles(directory=STATIC_DIR, html=True), name="ui")
