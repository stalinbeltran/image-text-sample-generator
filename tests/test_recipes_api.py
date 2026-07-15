from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

RECIPE = {
    "name": "crud",
    "canvas": {"width": 300, "height": 220},
    "background": {"kind": "solid", "color": "#ffffff"},
    "blocks": [
        {
            "kind": "paragraph",
            "count": 1,
            "width": 150,
            "content": {"source": "words", "words": 10},
            "typography": {"font_size": 13, "color": "#000000"},
        }
    ],
}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def recipe_id(client):
    rid = client.post("/recipes", json={"name": "fixture", "recipe": RECIPE}).json()["id"]
    yield rid
    client.delete(f"/recipes/{rid}")


def test_defaults_are_a_valid_recipe(client):
    """The form builds itself from this, so it must round-trip through create."""
    defaults = client.get("/recipes/defaults").json()
    assert defaults["recipe"]["blocks"]
    assert defaults["block"]["kind"] == "paragraph"

    created = client.post(
        "/recipes", json={"name": "from-defaults", "recipe": defaults["recipe"]}
    )
    assert created.status_code == 201
    client.delete(f"/recipes/{created.json()['id']}")


def test_crud_roundtrip(client):
    created = client.post("/recipes", json={"name": "mi receta", "recipe": RECIPE})
    assert created.status_code == 201
    rid = created.json()["id"]
    assert rid.startswith("mi-receta-")

    got = client.get(f"/recipes/{rid}").json()
    assert got["name"] == "mi receta"
    assert got["recipe"]["canvas"]["width"] == 300

    updated = client.put(f"/recipes/{rid}", json={"name": "renombrada"})
    assert updated.status_code == 200
    assert updated.json()["name"] == "renombrada"
    assert updated.json()["recipe"]["canvas"]["width"] == 300, "recipe was clobbered by a name-only update"

    listed = client.get("/recipes").json()["recipes"]
    assert any(r["id"] == rid for r in listed)

    assert client.delete(f"/recipes/{rid}").status_code == 204
    assert client.get(f"/recipes/{rid}").status_code == 404


def test_duplicate(client, recipe_id):
    copy = client.post(f"/recipes/{recipe_id}/duplicate", json={})
    assert copy.status_code == 201
    assert copy.json()["id"] != recipe_id
    assert copy.json()["name"].endswith("(copy)")
    assert copy.json()["recipe"] == client.get(f"/recipes/{recipe_id}").json()["recipe"]
    client.delete(f"/recipes/{copy.json()['id']}")


def test_invalid_recipe_is_rejected(client):
    bad = dict(RECIPE, canvas={"width": "no soy un número"})
    assert client.post("/recipes", json={"name": "bad", "recipe": bad}).status_code == 422


def test_dataset_from_recipe_id(client, recipe_id):
    ds = client.post("/datasets", json={"recipe_id": recipe_id, "count": 2})
    assert ds.status_code == 201
    meta = ds.json()
    assert meta["recipe_id"] == recipe_id
    assert meta["count"] == 2
    client.delete(f"/datasets/{meta['id']}")


def test_dataset_needs_exactly_one_source(client, recipe_id):
    assert client.post("/datasets", json={"count": 1}).status_code == 422
    both = {"count": 1, "recipe": RECIPE, "recipe_id": recipe_id}
    assert client.post("/datasets", json=both).status_code == 422


def test_editing_a_recipe_does_not_change_existing_datasets(client, recipe_id):
    """The whole point of freezing a copy at creation time."""
    ds_id = client.post("/datasets", json={"recipe_id": recipe_id, "count": 1}).json()["id"]
    before = client.get(f"/datasets/{ds_id}/specs/0").json()

    wider = dict(RECIPE, canvas={"width": 999, "height": 999})
    client.put(f"/recipes/{recipe_id}", json={"recipe": wider})

    after = client.get(f"/datasets/{ds_id}/specs/0").json()
    assert after == before
    assert after["width"] == 300, "the dataset followed the edited recipe"

    client.delete(f"/datasets/{ds_id}")


def test_dataset_listing_reports_disk_usage(client, recipe_id):
    ds_id = client.post("/datasets", json={"recipe_id": recipe_id, "count": 2}).json()["id"]

    row = next(d for d in client.get("/datasets").json()["datasets"] if d["id"] == ds_id)
    assert row["images_built"] == 0
    assert row["bytes_on_disk"] > 0  # the specs themselves
    assert row["recipe_name"] == "crud"

    client.get(f"/datasets/{ds_id}/items/0/image.png")
    row = next(d for d in client.get("/datasets").json()["datasets"] if d["id"] == ds_id)
    assert row["images_built"] == 1

    client.delete(f"/datasets/{ds_id}")


def test_rename_dataset(client, recipe_id):
    ds_id = client.post("/datasets", json={"recipe_id": recipe_id, "count": 1}).json()["id"]
    renamed = client.patch(f"/datasets/{ds_id}", json={"name": "otro nombre"})
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "otro nombre"
    assert client.get(f"/datasets/{ds_id}").json()["name"] == "otro nombre"
    client.delete(f"/datasets/{ds_id}")


def test_ui_is_served(client):
    assert client.get("/", follow_redirects=False).status_code in (302, 307)
    page = client.get("/ui/")
    assert page.status_code == 200
    assert "image-text-finder" in page.text
