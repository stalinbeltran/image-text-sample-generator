from __future__ import annotations

import asyncio
from io import BytesIO

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image

from app.main import app

pytestmark = pytest.mark.asyncio(loop_scope="module")

RECIPE = {
    "name": "race",
    "canvas": {"width": 260, "height": 200},
    "background": {"kind": "solid", "color": "#ffffff"},
    "blocks": [
        {
            "kind": "paragraph",
            "count": 1,
            "width": 140,
            "content": {"source": "words", "words": 14},
            "typography": {"font_size": 12, "color": "#000000"},
        }
    ],
}
N = 8


async def test_fetching_items_while_the_dataset_builds_never_serves_a_torn_png():
    """A browser opening the gallery hits the same files the build is writing.

    Saving in place let a reader stream a half-written PNG: HTTP 200, valid
    length, and a blank image in the browser. Every response must decode fully.
    """
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            ds = (await client.post("/datasets", json={"recipe": RECIPE, "count": N})).json()
            ds_id = ds["id"]

            await client.post(f"/datasets/{ds_id}/build", json={"masks": True, "labels": True})

            # Hammer the item routes while the build is still running.
            for _ in range(4):
                responses = await asyncio.gather(
                    *(client.get(f"/datasets/{ds_id}/items/{i}/image.png") for i in range(N))
                )
                for i, res in enumerate(responses):
                    assert res.status_code == 200, f"item {i}: {res.status_code}"
                    img = Image.open(BytesIO(res.content))
                    img.load()  # raises on a truncated file rather than half-decoding
                    assert img.size == (260, 200)

            for _ in range(100):
                status = (await client.get(f"/datasets/{ds_id}/build")).json()
                if status["state"] in ("ready", "error"):
                    break
                await asyncio.sleep(0.1)
            assert status["state"] == "ready", status

            # The atomic writes must not leave scratch files behind.
            leftovers = list((await _root(ds_id)).rglob("*.tmp"))
            assert not leftovers, f"temp files left on disk: {leftovers}"

            await client.delete(f"/datasets/{ds_id}")


async def _root(dataset_id: str):
    from app.core import storage

    return storage.root(dataset_id)
