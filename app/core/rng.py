from __future__ import annotations

import hashlib
import random

import numpy as np

_MAX32 = 2**32


def derive_seed(root_seed: int, path: str) -> int:
    """Derive a stable sub-seed from a root seed and a structural path.

    Sub-seeds are keyed by *path* rather than drawn from a running stream, so
    adding a block to a recipe does not shift the values sampled for the
    blocks around it.
    """
    h = hashlib.blake2b(f"{root_seed}|{path}".encode(), digest_size=8).digest()
    return int.from_bytes(h, "big")


def rng_for(root_seed: int, path: str) -> random.Random:
    return random.Random(derive_seed(root_seed, path))


def np_rng_for(root_seed: int, path: str) -> np.random.Generator:
    return np.random.default_rng(derive_seed(root_seed, path) % _MAX32)
