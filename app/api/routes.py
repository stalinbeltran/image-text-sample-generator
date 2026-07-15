from __future__ import annotations

import asyncio
import base64
import io
import zipfile

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse, StreamingResponse

from app.api.schemas import (
    BuildRequest,
    CreateDatasetRequest,
    CreateRecipeRequest,
    DatasetSummary,
    DuplicateRecipeRequest,
    RecipeDefaults,
    RenderRequest,
    RenderResponse,
    ResolveRequest,
    UpdateDatasetRequest,
    UpdateRecipeRequest,
    random_seed,
)
from app.core import backgrounds, fonts, recipes_store, storage
from app.core.renderer import Renderer
from app.core.resolver import resolve
from app.models.recipe import BlockRecipe, Recipe
from app.models.spec import ImageSpec
from app.settings import PHOTOS_DIR

router = APIRouter()

# One in-flight build per dataset.
_builds: dict[str, asyncio.Task] = {}

# A background build and a browser asking for a thumbnail can land on the same
# item at the same moment. Striped locks keep one item from being rendered and
# written twice concurrently, without growing a lock per item on a 200k dataset.
_ITEM_LOCKS = [asyncio.Lock() for _ in range(64)]


def _item_lock(dataset_id: str, index: int) -> asyncio.Lock:
    return _ITEM_LOCKS[hash((dataset_id, index)) % len(_ITEM_LOCKS)]


def _renderer(request: Request) -> Renderer:
    return request.app.state.renderer


def _png(img) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# --------------------------------------------------------------------------
# Assets
# --------------------------------------------------------------------------


@router.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok"}


@router.get("/fonts", tags=["assets"])
async def get_fonts() -> dict:
    registry = fonts.registry()
    return {
        "count": len(registry),
        "using_system_fallback": all(f.is_system for f in registry),
        "fonts": [{"family": f.family, "file": f.file} for f in registry],
    }


@router.post("/fonts/refresh", tags=["assets"])
async def refresh_fonts() -> dict:
    registry = fonts.refresh()
    return {"count": len(registry), "fonts": [f.family for f in registry]}


@router.get("/backgrounds/photos", tags=["assets"])
async def get_photos(subdir: str | None = None) -> dict:
    files = backgrounds.list_photos(subdir)
    return {
        "root": str(PHOTOS_DIR),
        "count": len(files),
        "files": [p.relative_to(PHOTOS_DIR).as_posix() for p in files],
    }


# --------------------------------------------------------------------------
# Recipes: the stored definitions that generate datasets
#
# Route order matters: /recipes/defaults and /recipes/resolve are declared
# before /recipes/{recipe_id}, or the literal paths would be swallowed as ids.
# --------------------------------------------------------------------------


@router.get("/recipes/defaults", response_model=RecipeDefaults, tags=["recipes"])
async def recipe_defaults() -> RecipeDefaults:
    """A blank recipe and a blank block, straight from the Pydantic models."""
    return RecipeDefaults(recipe=Recipe(), block=BlockRecipe())


@router.get("/recipes", tags=["recipes"])
async def list_recipes() -> dict:
    return {"recipes": recipes_store.list_all()}


@router.post(
    "/recipes", response_model=recipes_store.RecipeRecord, status_code=201, tags=["recipes"]
)
async def create_recipe(body: CreateRecipeRequest) -> recipes_store.RecipeRecord:
    return recipes_store.create(body.name, body.recipe)


@router.get("/recipes/{recipe_id}", response_model=recipes_store.RecipeRecord, tags=["recipes"])
async def get_recipe(recipe_id: str) -> recipes_store.RecipeRecord:
    return _load_recipe(recipe_id)


@router.put("/recipes/{recipe_id}", response_model=recipes_store.RecipeRecord, tags=["recipes"])
async def update_recipe(
    recipe_id: str, body: UpdateRecipeRequest
) -> recipes_store.RecipeRecord:
    _load_recipe(recipe_id)
    return recipes_store.update(recipe_id, body.name, body.recipe)


@router.post(
    "/recipes/{recipe_id}/duplicate",
    response_model=recipes_store.RecipeRecord,
    status_code=201,
    tags=["recipes"],
)
async def duplicate_recipe(
    recipe_id: str, body: DuplicateRecipeRequest
) -> recipes_store.RecipeRecord:
    _load_recipe(recipe_id)
    return recipes_store.duplicate(recipe_id, body.name)


@router.delete("/recipes/{recipe_id}", status_code=204, tags=["recipes"])
async def delete_recipe(recipe_id: str) -> Response:
    _load_recipe(recipe_id)
    recipes_store.delete(recipe_id)
    return Response(status_code=204)


def _load_recipe(recipe_id: str) -> recipes_store.RecipeRecord:
    try:
        return recipes_store.get(recipe_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# --------------------------------------------------------------------------
# Recipe -> spec -> render
# --------------------------------------------------------------------------


@router.post("/recipes/resolve", response_model=ImageSpec, tags=["render"])
async def resolve_recipe(body: ResolveRequest) -> ImageSpec:
    seed = body.seed if body.seed is not None else random_seed()
    try:
        return resolve(body.recipe, seed)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _spec_of(body: RenderRequest) -> ImageSpec:
    if body.spec is not None:
        return body.spec
    seed = body.seed if body.seed is not None else random_seed()
    return resolve(body.recipe, seed)  # type: ignore[arg-type]


@router.post("/render", response_model=RenderResponse, tags=["render"])
async def render(body: RenderRequest, request: Request) -> RenderResponse:
    """Render without persisting anything. Returns the spec, the labels, and base64 PNGs."""
    try:
        spec = _spec_of(body)
        result = await _renderer(request).render(
            spec, want_mask=body.mask, mask_threshold=body.mask_threshold
        )
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return RenderResponse(
        spec=spec,
        labels=result.labels,
        image_png=base64.b64encode(_png(result.image)).decode("ascii"),
        mask_png=(
            base64.b64encode(_png(result.mask)).decode("ascii") if result.mask else None
        ),
    )


@router.post("/render/preview.png", tags=["render"])
async def render_preview(body: RenderRequest, request: Request) -> Response:
    """The same render, straight back as a PNG -- handy for eyeballing a recipe."""
    want_mask = body.target == "mask"
    try:
        spec = _spec_of(body)
        result = await _renderer(request).render(
            spec, want_mask=want_mask, mask_threshold=body.mask_threshold
        )
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    img = result.mask if want_mask else result.image
    return Response(
        content=_png(img),
        media_type="image/png",
        headers={"X-Image-Seed": str(spec.seed), "X-Image-Id": spec.id},
    )


# --------------------------------------------------------------------------
# Datasets
# --------------------------------------------------------------------------


@router.post("/datasets", response_model=storage.DatasetMeta, status_code=201, tags=["datasets"])
async def create_dataset(body: CreateDatasetRequest) -> storage.DatasetMeta:
    """Resolve N frozen specs and store them as JSONL. Renders nothing yet."""
    seed = body.seed if body.seed is not None else random_seed()

    if body.recipe_id is not None:
        record = _load_recipe(body.recipe_id)
        # The dataset keeps its own copy: editing the recipe later must not
        # silently change what this dataset regenerates.
        recipe, name = record.recipe, body.name or record.name
    else:
        recipe, name = body.recipe, body.name

    try:
        return storage.create(recipe, body.count, seed, name, recipe_id=body.recipe_id)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/datasets", tags=["datasets"])
async def list_datasets() -> dict:
    """Each row carries what it costs on disk, so the UI can show what freeing
    the artifacts would actually buy back."""
    summaries = []
    for meta in storage.list_all():
        summaries.append(
            DatasetSummary(
                id=meta.id,
                name=meta.name,
                seed=meta.seed,
                count=meta.count,
                created_at=meta.created_at,
                recipe_id=meta.recipe_id,
                recipe_name=meta.recipe.name,
                build=meta.build.model_dump(),
                images_built=storage.images_built(meta.id),
                bytes_on_disk=storage.bytes_on_disk(meta.id),
            )
        )
    return {"datasets": summaries}


@router.get("/datasets/{dataset_id}", response_model=storage.DatasetMeta, tags=["datasets"])
async def get_dataset(dataset_id: str) -> storage.DatasetMeta:
    return _load(dataset_id)


@router.patch("/datasets/{dataset_id}", response_model=storage.DatasetMeta, tags=["datasets"])
async def rename_dataset(dataset_id: str, body: UpdateDatasetRequest) -> storage.DatasetMeta:
    meta = _load(dataset_id)
    meta.name = body.name
    storage.save_meta(meta)
    return meta


@router.get("/datasets/{dataset_id}/specs/{index}", response_model=ImageSpec, tags=["datasets"])
async def get_spec(dataset_id: str, index: int) -> ImageSpec:
    _load(dataset_id)
    try:
        return storage.read_spec(dataset_id, index)
    except IndexError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/datasets/{dataset_id}/build", tags=["datasets"])
async def build_dataset(dataset_id: str, body: BuildRequest, request: Request) -> dict:
    """Materialize PNGs + masks + labels in the background. Poll GET .../build."""
    meta = _load(dataset_id)
    if dataset_id in _builds and not _builds[dataset_id].done():
        raise HTTPException(status_code=409, detail="a build is already running")

    task = asyncio.create_task(_run_build(dataset_id, body, _renderer(request)))
    _builds[dataset_id] = task
    return {"dataset": dataset_id, "state": "building", "total": meta.count}


@router.get("/datasets/{dataset_id}/build", tags=["datasets"])
async def build_status(dataset_id: str) -> storage.BuildStatus:
    return _load(dataset_id).build


async def _run_build(dataset_id: str, body: BuildRequest, renderer: Renderer) -> None:
    meta = storage.load_meta(dataset_id)
    start = max(0, body.start)
    end = min(meta.count, body.end if body.end is not None else meta.count)

    todo = [
        i
        for i in range(start, end)
        if body.overwrite or not storage.image_path(dataset_id, i).is_file()
    ]
    meta.build = storage.BuildStatus(state="building", done=0, total=len(todo))
    storage.save_meta(meta)

    done = 0
    lock = asyncio.Lock()

    async def one(index: int) -> None:
        nonlocal done
        async with _item_lock(dataset_id, index):
            # A browser opening the gallery may have rendered this item lazily
            # while the build was queued. Same spec, same pixels -- skip it.
            if not body.overwrite and storage.image_path(dataset_id, index).is_file():
                pass
            else:
                spec = storage.read_spec(dataset_id, index)
                result = await renderer.render(
                    spec, want_mask=body.masks, mask_threshold=body.mask_threshold
                )
                storage.write_item(
                    dataset_id,
                    index,
                    result.image,
                    result.mask,
                    result.labels,
                    save_masks=body.masks,
                    save_labels=body.labels,
                    overwrite=body.overwrite,
                )
        async with lock:
            done += 1
            if done % 25 == 0:
                meta.build.done = done
                storage.save_meta(meta)

    try:
        await asyncio.gather(*(one(i) for i in todo))
        if body.labels:
            storage.write_index(dataset_id)
        meta.build = storage.BuildStatus(state="ready", done=done, total=len(todo))
    except Exception as exc:  # noqa: BLE001 - surfaced to the client via the status route
        meta.build = storage.BuildStatus(
            state="error", done=done, total=len(todo), error=f"{type(exc).__name__}: {exc}"
        )
    storage.save_meta(meta)


# --------------------------------------------------------------------------
# Item access -- renders lazily and caches, so images are always disposable
# --------------------------------------------------------------------------


async def _ensure_item(dataset_id: str, index: int, renderer: Renderer, threshold: int) -> None:
    if storage.image_path(dataset_id, index).is_file():
        return
    async with _item_lock(dataset_id, index):
        # Re-check: a build (or another request for the same thumbnail) may have
        # produced it while we waited for the lock.
        if storage.image_path(dataset_id, index).is_file():
            return
        spec = storage.read_spec(dataset_id, index)
        result = await renderer.render(spec, want_mask=True, mask_threshold=threshold)
        storage.write_item(dataset_id, index, result.image, result.mask, result.labels)


@router.get("/datasets/{dataset_id}/items/{index}/image.png", tags=["items"])
async def item_image(dataset_id: str, index: int, request: Request, threshold: int = 128):
    _load(dataset_id)
    await _ensure_item(dataset_id, index, _renderer(request), threshold)
    return FileResponse(storage.image_path(dataset_id, index), media_type="image/png")


@router.get("/datasets/{dataset_id}/items/{index}/mask.png", tags=["items"])
async def item_mask(dataset_id: str, index: int, request: Request, threshold: int = 128):
    _load(dataset_id)
    await _ensure_item(dataset_id, index, _renderer(request), threshold)
    return FileResponse(storage.mask_path(dataset_id, index), media_type="image/png")


@router.get("/datasets/{dataset_id}/items/{index}/labels.json", tags=["items"])
async def item_labels(dataset_id: str, index: int, request: Request):
    _load(dataset_id)
    await _ensure_item(dataset_id, index, _renderer(request), 128)
    return FileResponse(storage.label_path(dataset_id, index), media_type="application/json")


@router.get("/datasets/{dataset_id}/archive.zip", tags=["datasets"])
async def archive(dataset_id: str):
    """Zip up whatever has been built, for handing to a training box."""
    meta = _load(dataset_id)
    base = storage.root(dataset_id)

    def stream():
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(base.rglob("*")):
                if path.is_file():
                    zf.write(path, path.relative_to(base).as_posix())
        buf.seek(0)
        yield from buf

    return StreamingResponse(
        stream(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{meta.id}.zip"'},
    )


@router.delete("/datasets/{dataset_id}/artifacts", tags=["datasets"])
async def free_space(dataset_id: str) -> dict:
    """Delete the PNGs and labels but keep the specs -- they regenerate identically."""
    _load(dataset_id)
    return storage.delete_artifacts(dataset_id)


@router.delete("/datasets/{dataset_id}", status_code=204, tags=["datasets"])
async def delete_dataset(dataset_id: str) -> Response:
    _load(dataset_id)
    storage.delete(dataset_id)
    return Response(status_code=204)


def _load(dataset_id: str) -> storage.DatasetMeta:
    try:
        return storage.load_meta(dataset_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
