from __future__ import annotations

import json
import os
import re
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from app.core.rng import derive_seed
from app.core.resolver import resolve
from app.models.recipe import Recipe
from app.models.spec import SPEC_VERSION, ImageSpec
from app.settings import DATASETS_DIR

BuildState = Literal["empty", "building", "ready", "error"]


class BuildStatus(BaseModel):
    state: BuildState = "empty"
    done: int = 0
    total: int = 0
    error: str | None = None


class DatasetMeta(BaseModel):
    id: str
    name: str
    seed: int
    count: int
    created_at: str
    spec_version: int = SPEC_VERSION

    # Provenance, plus a frozen copy of the recipe as it was at creation time.
    # Editing the stored recipe afterwards must never change an existing
    # dataset, so the copy -- not the id -- is what regenerates the images.
    recipe_id: str | None = None
    recipe: Recipe

    build: BuildStatus = Field(default_factory=BuildStatus)


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "dataset"


def root(dataset_id: str) -> Path:
    # Reject traversal: ids are ours, but this is a filesystem path from an API.
    if not re.fullmatch(r"[a-z0-9][a-z0-9\-]{0,80}", dataset_id):
        raise ValueError(f"invalid dataset id {dataset_id!r}")
    return DATASETS_DIR / dataset_id


def image_path(dataset_id: str, index: int) -> Path:
    return root(dataset_id) / "images" / f"{index:06d}.png"


def mask_path(dataset_id: str, index: int) -> Path:
    return root(dataset_id) / "masks" / f"{index:06d}.png"


def label_path(dataset_id: str, index: int) -> Path:
    return root(dataset_id) / "labels" / f"{index:06d}.json"


def item_seed(dataset_seed: int, index: int) -> int:
    return derive_seed(dataset_seed, f"item[{index}]")


# --------------------------------------------------------------------------


def create(
    recipe: Recipe,
    count: int,
    seed: int,
    name: str | None = None,
    recipe_id: str | None = None,
) -> DatasetMeta:
    """Resolve `count` frozen specs and write them to disk. No pixels yet."""
    label = name or recipe.name
    dataset_id = f"{_slug(label)}-{uuid4().hex[:8]}"
    base = root(dataset_id)
    base.mkdir(parents=True, exist_ok=False)

    with (base / "specs.jsonl").open("w", encoding="utf-8") as fh:
        for i in range(count):
            spec = resolve(recipe, item_seed(seed, i), image_id=f"{dataset_id}/{i:06d}")
            fh.write(spec.model_dump_json() + "\n")

    meta = DatasetMeta(
        id=dataset_id,
        name=label,
        seed=seed,
        count=count,
        created_at=datetime.now(timezone.utc).isoformat(),
        recipe_id=recipe_id,
        recipe=recipe,
        build=BuildStatus(state="empty", total=count),
    )
    save_meta(meta)
    return meta


def images_built(dataset_id: str) -> int:
    d = root(dataset_id) / "images"
    return sum(1 for _ in d.glob("*.png")) if d.is_dir() else 0


def bytes_on_disk(dataset_id: str) -> int:
    return sum(f.stat().st_size for f in root(dataset_id).rglob("*") if f.is_file())


def save_meta(meta: DatasetMeta) -> None:
    path = root(meta.id) / "dataset.json"
    path.write_text(meta.model_dump_json(indent=2), encoding="utf-8")


def load_meta(dataset_id: str) -> DatasetMeta:
    path = root(dataset_id) / "dataset.json"
    if not path.is_file():
        raise FileNotFoundError(f"no such dataset: {dataset_id}")
    return DatasetMeta.model_validate_json(path.read_text(encoding="utf-8"))


def list_all() -> list[DatasetMeta]:
    out = []
    for child in sorted(DATASETS_DIR.iterdir()) if DATASETS_DIR.is_dir() else []:
        if (child / "dataset.json").is_file():
            out.append(load_meta(child.name))
    return sorted(out, key=lambda m: m.created_at, reverse=True)


def iter_specs(dataset_id: str) -> Iterator[ImageSpec]:
    with (root(dataset_id) / "specs.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield ImageSpec.model_validate_json(line)


def read_spec(dataset_id: str, index: int) -> ImageSpec:
    with (root(dataset_id) / "specs.jsonl").open(encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            if i == index:
                return ImageSpec.model_validate_json(line)
    raise IndexError(f"dataset {dataset_id} has no item {index}")


def delete_artifacts(dataset_id: str) -> dict[str, int]:
    """Drop the rendered PNGs and labels, keep specs.jsonl. Frees the disk;
    everything deleted here can be rebuilt byte-for-byte from the specs."""
    base = root(dataset_id)
    freed = 0
    removed = 0
    for sub in ("images", "masks", "labels"):
        d = base / sub
        if not d.is_dir():
            continue
        for f in d.rglob("*"):
            if f.is_file():
                freed += f.stat().st_size
                removed += 1
        shutil.rmtree(d)

    index = base / "labels.jsonl"
    if index.is_file():
        freed += index.stat().st_size
        removed += 1
        index.unlink()

    meta = load_meta(dataset_id)
    meta.build = BuildStatus(state="empty", total=meta.count)
    save_meta(meta)
    return {"files_removed": removed, "bytes_freed": freed}


def delete(dataset_id: str) -> None:
    shutil.rmtree(root(dataset_id), ignore_errors=True)


REPLACE_RETRIES = 6


def _atomic(path: Path, write: "Callable[[Path], None]", *, overwrite: bool) -> None:
    """Write via a temp file and rename into place.

    A reader (the lazy image route) can hit the same path while a build writes
    it. Saving straight to `path` lets that reader stream a half-written PNG --
    HTTP 200, a blank image in the browser, and a perfectly good file on disk
    afterwards. The rename is atomic, so a reader sees the old file or the new
    one, never a torn one.

    Two Windows-specific wrinkles:
      * os.replace onto an *open* file raises PermissionError, and FileResponse
        holds the file open for the length of the download -- hence the retry.
      * Rendering is deterministic, so rewriting an existing item would only
        reproduce identical bytes. Skipping it is both faster and the reason
        the retry above almost never has to fire.
    """
    if path.exists() and not overwrite:
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{uuid4().hex[:8]}.tmp")
    try:
        write(tmp)
        for attempt in range(REPLACE_RETRIES):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                if attempt == REPLACE_RETRIES - 1:
                    raise
                time.sleep(0.05 * (attempt + 1))  # a reader still has it open
    finally:
        tmp.unlink(missing_ok=True)


def write_item(
    dataset_id: str,
    index: int,
    image,
    mask,
    labels,
    *,
    save_masks: bool = True,
    save_labels: bool = True,
    overwrite: bool = False,
) -> None:
    _atomic(
        image_path(dataset_id, index),
        lambda p: image.save(p, format="PNG"),
        overwrite=overwrite,
    )

    if save_masks and mask is not None:
        _atomic(
            mask_path(dataset_id, index),
            lambda p: mask.save(p, format="PNG", optimize=True),
            overwrite=overwrite,
        )

    if save_labels:
        _atomic(
            label_path(dataset_id, index),
            lambda p: p.write_text(labels.model_dump_json(indent=1), encoding="utf-8"),
            overwrite=overwrite,
        )


def write_index(dataset_id: str) -> Path:
    """One line per built item -- the file a dataloader iterates.

    JSONL rather than a single JSON array: a 200k-image dataset's labels never
    have to be held in memory, on either end.
    """
    path = root(dataset_id) / "labels.jsonl"
    with path.open("w", encoding="utf-8") as out:
        for i in range(load_meta(dataset_id).count):
            lp = label_path(dataset_id, i)
            if not lp.is_file():
                continue
            record = {
                "index": i,
                "image": f"images/{i:06d}.png",
                "mask": f"masks/{i:06d}.png" if mask_path(dataset_id, i).is_file() else None,
                "labels": json.loads(lp.read_text(encoding="utf-8")),
            }
            out.write(json.dumps(record) + "\n")
    return path
