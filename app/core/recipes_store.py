from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel

from app.models.recipe import Recipe
from app.settings import DATA_DIR

RECIPES_DIR = DATA_DIR / "recipes"
RECIPES_DIR.mkdir(parents=True, exist_ok=True)


class RecipeRecord(BaseModel):
    id: str
    name: str
    created_at: str
    updated_at: str
    recipe: Recipe


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "recipe"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def path_of(recipe_id: str) -> Path:
    if not re.fullmatch(r"[a-z0-9][a-z0-9\-]{0,80}", recipe_id):
        raise ValueError(f"invalid recipe id {recipe_id!r}")
    return RECIPES_DIR / f"{recipe_id}.json"


def create(name: str, recipe: Recipe) -> RecipeRecord:
    recipe_id = f"{_slug(name)}-{uuid4().hex[:8]}"
    now = _now()
    record = RecipeRecord(
        id=recipe_id, name=name, created_at=now, updated_at=now, recipe=recipe
    )
    _write(record)
    return record


def _write(record: RecipeRecord) -> None:
    path_of(record.id).write_text(record.model_dump_json(indent=2), encoding="utf-8")


def get(recipe_id: str) -> RecipeRecord:
    path = path_of(recipe_id)
    if not path.is_file():
        raise FileNotFoundError(f"no such recipe: {recipe_id}")
    return RecipeRecord.model_validate_json(path.read_text(encoding="utf-8"))


def list_all() -> list[RecipeRecord]:
    records = [
        RecipeRecord.model_validate_json(p.read_text(encoding="utf-8"))
        for p in RECIPES_DIR.glob("*.json")
    ]
    return sorted(records, key=lambda r: r.updated_at, reverse=True)


def update(recipe_id: str, name: str | None, recipe: Recipe | None) -> RecipeRecord:
    record = get(recipe_id)
    if name is not None:
        record.name = name
    if recipe is not None:
        record.recipe = recipe
    record.updated_at = _now()
    _write(record)
    return record


def duplicate(recipe_id: str, name: str | None = None) -> RecipeRecord:
    source = get(recipe_id)
    return create(name or f"{source.name} (copy)", source.recipe)


def delete(recipe_id: str) -> None:
    path_of(recipe_id).unlink(missing_ok=True)


def seed_examples() -> int:
    """Load examples/*.json on first run, so the UI is never an empty page."""
    if any(RECIPES_DIR.glob("*.json")):
        return 0
    examples = Path(__file__).resolve().parent.parent.parent / "examples"
    loaded = 0
    for path in sorted(examples.glob("*.json")):
        try:
            recipe = Recipe.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 - a broken example must not stop startup
            continue
        create(recipe.name or path.stem, recipe)
        loaded += 1
    return loaded


def disk_usage(base: Path) -> int:
    return sum(f.stat().st_size for f in base.rglob("*") if f.is_file())


__all__ = [
    "RecipeRecord",
    "create",
    "delete",
    "disk_usage",
    "duplicate",
    "get",
    "list_all",
    "seed_examples",
    "update",
]
