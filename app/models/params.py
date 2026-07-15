from __future__ import annotations

import random
from typing import Any, Union

from pydantic import BaseModel, Field, model_validator

# --------------------------------------------------------------------------
# A "param" is either a literal value or a distribution the resolver samples
# from. This is what lets a recipe pin some values and leave the rest random:
#
#     "width": 640                       -> always 640
#     "font_size": {"range": [12, 28]}   -> uniform in [12, 28]
#     "align": {"choice": ["left", "center"], "weights": [3, 1]}
# --------------------------------------------------------------------------


class Range(BaseModel):
    """Uniform sample in the closed interval [lo, hi]."""

    range: tuple[float, float]
    step: float | None = Field(
        default=None, description="Snap the sample to a grid of this size."
    )

    @model_validator(mode="after")
    def _ordered(self) -> "Range":
        lo, hi = self.range
        if lo > hi:
            raise ValueError(f"range lower bound {lo} is above upper bound {hi}")
        if self.step is not None and self.step <= 0:
            raise ValueError("step must be positive")
        return self

    def sample(self, rng: random.Random) -> float:
        lo, hi = self.range
        value = rng.uniform(lo, hi)
        if self.step:
            value = lo + round((value - lo) / self.step) * self.step
            value = min(value, hi)
        return value


class Choice(BaseModel):
    """Weighted pick from a list of literal options."""

    choice: list[Any] = Field(min_length=1)
    weights: list[float] | None = None

    @model_validator(mode="after")
    def _weights_match(self) -> "Choice":
        if self.weights is not None and len(self.weights) != len(self.choice):
            raise ValueError("weights must have the same length as choice")
        return self

    def sample(self, rng: random.Random) -> Any:
        return rng.choices(self.choice, weights=self.weights, k=1)[0]


Dist = Union[Range, Choice]

IntParam = Union[int, Range, Choice]
FloatParam = Union[float, int, Range, Choice]
StrParam = Union[str, Choice]
BoolParam = Union[bool, Choice]
ColorParam = Union[str, Choice]  # "#rrggbb", "rgba(...)", or the literal "auto"


def sample(value: Any, rng: random.Random) -> Any:
    """Collapse a param into a concrete value."""
    if isinstance(value, (Range, Choice)):
        return value.sample(rng)
    return value


def sample_int(value: Any, rng: random.Random) -> int:
    return int(round(sample(value, rng)))


def sample_float(value: Any, rng: random.Random) -> float:
    return float(sample(value, rng))


def sample_bool(value: Any, rng: random.Random) -> bool:
    return bool(sample(value, rng))
