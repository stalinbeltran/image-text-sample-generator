from __future__ import annotations

import random

from pydantic import BaseModel, Field, model_validator

from app.models.recipe import BlockRecipe, Recipe
from app.models.spec import ImageSpec, Labels


def random_seed() -> int:
    return random.getrandbits(63)


class ResolveRequest(BaseModel):
    recipe: Recipe
    seed: int | None = Field(default=None, description="Omit for a fresh random seed.")


class RenderRequest(BaseModel):
    """Render either a frozen spec, or a recipe + seed (resolved on the fly)."""

    spec: ImageSpec | None = None
    recipe: Recipe | None = None
    seed: int | None = None

    mask: bool = True
    mask_threshold: int = Field(
        default=128, description="0 keeps the soft antialiased mask instead of binarising."
    )
    target: str = Field(default="image", description="For the .png route: image | mask")

    @model_validator(mode="after")
    def _one_source(self) -> "RenderRequest":
        if (self.spec is None) == (self.recipe is None):
            raise ValueError("provide exactly one of 'spec' or 'recipe'")
        return self


class RenderResponse(BaseModel):
    spec: ImageSpec
    labels: Labels
    image_png: str = Field(description="base64-encoded PNG")
    mask_png: str | None = None


class CreateRecipeRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    recipe: Recipe


class UpdateRecipeRequest(BaseModel):
    """Both fields optional -- send only what changed."""

    name: str | None = Field(default=None, min_length=1, max_length=80)
    recipe: Recipe | None = None


class DuplicateRecipeRequest(BaseModel):
    name: str | None = None


class RecipeDefaults(BaseModel):
    """What a brand-new recipe (and a brand-new block) looks like.

    The UI builds its form from this rather than hardcoding a second copy of the
    schema, so the two can't drift apart.
    """

    recipe: Recipe
    block: BlockRecipe


class CreateDatasetRequest(BaseModel):
    """Give a stored recipe's id, or an inline recipe -- one or the other."""

    recipe: Recipe | None = None
    recipe_id: str | None = None
    count: int = Field(ge=1, le=200_000)
    seed: int | None = None
    name: str | None = None

    @model_validator(mode="after")
    def _one_source(self) -> "CreateDatasetRequest":
        if (self.recipe is None) == (self.recipe_id is None):
            raise ValueError("provide exactly one of 'recipe' or 'recipe_id'")
        return self


class UpdateDatasetRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class DatasetSummary(BaseModel):
    """A dataset row for the listing: metadata plus what it costs on disk."""

    id: str
    name: str
    seed: int
    count: int
    created_at: str
    recipe_id: str | None = None
    recipe_name: str | None = None
    build: dict
    images_built: int = 0
    bytes_on_disk: int = 0


class BuildRequest(BaseModel):
    start: int = 0
    end: int | None = Field(default=None, description="Exclusive. None = to the end.")
    masks: bool = True
    labels: bool = True
    mask_threshold: int = 128
    overwrite: bool = Field(
        default=False, description="Re-render items whose PNG already exists."
    )
