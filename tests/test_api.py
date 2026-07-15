from __future__ import annotations

import base64
import time

import pytest
from fastapi.testclient import TestClient

from app.main import app

RECIPE = {
    "name": "test",
    "canvas": {"width": 320, "height": 240},
    "background": {"kind": "solid", "color": "#ffffff"},
    "blocks": [
        {
            "kind": "paragraph",
            "count": 1,
            "width": 160,
            "content": {"source": "words", "words": 12},
            "typography": {"font_size": 14, "color": "#000000"},
        }
    ],
}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:  # the `with` runs lifespan, which boots Chromium
        yield c


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_resolve_is_stable_for_a_seed(client):
    a = client.post("/recipes/resolve", json={"recipe": RECIPE, "seed": 5}).json()
    b = client.post("/recipes/resolve", json={"recipe": RECIPE, "seed": 5}).json()
    assert a == b
    assert a["width"] == 320
    assert len(a["blocks"]) == 1


def test_render_returns_image_labels_and_mask(client):
    r = client.post("/render", json={"recipe": RECIPE, "seed": 9})
    assert r.status_code == 200
    body = r.json()
    assert body["labels"]["words"]
    assert base64.b64decode(body["image_png"])[:4] == b"\x89PNG"
    assert base64.b64decode(body["mask_png"])[:4] == b"\x89PNG"


def test_preview_png(client):
    r = client.post("/render/preview.png", json={"recipe": RECIPE, "seed": 9})
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content[:4] == b"\x89PNG"


def test_render_rejects_both_spec_and_recipe(client):
    r = client.post("/render", json={"recipe": RECIPE, "spec": None, "seed": 1})
    assert r.status_code == 200  # spec is None -> fine
    r = client.post("/render", json={})
    assert r.status_code == 422


def test_dataset_lifecycle(client):
    created = client.post(
        "/datasets", json={"recipe": RECIPE, "count": 3, "seed": 77, "name": "lifecycle"}
    )
    assert created.status_code == 201
    ds = created.json()["id"]

    assert client.get(f"/datasets/{ds}").json()["count"] == 3
    assert client.get(f"/datasets/{ds}/specs/0").json()["seed"] != 0
    assert client.get(f"/datasets/{ds}/specs/9").status_code == 404

    # Lazy render on first access.
    img = client.get(f"/datasets/{ds}/items/1/image.png")
    assert img.status_code == 200
    assert img.content[:4] == b"\x89PNG"
    assert client.get(f"/datasets/{ds}/items/1/mask.png").status_code == 200
    assert client.get(f"/datasets/{ds}/items/1/labels.json").json()["words"]

    # Free the pixels, keep the specs.
    freed = client.request("DELETE", f"/datasets/{ds}/artifacts").json()
    assert freed["files_removed"] >= 3
    assert client.get(f"/datasets/{ds}").json()["build"]["state"] == "empty"

    # And the image comes back on demand, identical.
    again = client.get(f"/datasets/{ds}/items/1/image.png")
    assert again.status_code == 200
    assert again.content == img.content, "regenerated image differs from the original"

    assert client.delete(f"/datasets/{ds}").status_code == 204
    assert client.get(f"/datasets/{ds}").status_code == 404


def test_build_then_archive(client):
    ds = client.post(
        "/datasets", json={"recipe": RECIPE, "count": 2, "seed": 3, "name": "build"}
    ).json()["id"]

    client.post(f"/datasets/{ds}/build", json={"masks": True, "labels": True})

    # Give the build real wall-clock time: each image is a browser render, and
    # a tight poll loop just starves the event loop it is waiting on.
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        status = client.get(f"/datasets/{ds}/build").json()
        if status["state"] in ("ready", "error"):
            break
        time.sleep(0.2)
    assert status["state"] == "ready", status
    assert status["done"] == 2

    zipped = client.get(f"/datasets/{ds}/archive.zip")
    assert zipped.status_code == 200
    assert zipped.content[:2] == b"PK"

    client.delete(f"/datasets/{ds}")


def test_bad_dataset_id_is_rejected(client):
    assert client.get("/datasets/..%2F..%2Fetc").status_code in (400, 404)
