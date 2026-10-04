import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import extract, main

client = TestClient(main.app)

RECIPE = {
    "name": "Veg chilli",
    "portions": 10,
    "ingredients": [
        {"name": "Onion", "quantity": 200, "unit": "g"},
        {"name": "Red kidney beans", "quantity": 1, "unit": "kg"},
    ],
}


def jpeg(size=(40, 30)):
    buf = io.BytesIO()
    Image.new("RGB", size, "white").save(buf, "JPEG")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def reset(monkeypatch):
    main._counts.clear()
    main._day = ""
    monkeypatch.setattr(
        extract,
        "call_claude",
        lambda images: {
            "name": " Chilli ",
            "portions": 10,
            "ingredients": [
                {"name": "Onion", "quantity": 200, "unit": "g"},
                {"name": "Salt", "quantity": None, "unit": None, "note": "to taste"},
                {"name": "Smudged", "quantity": -3, "unit": "g"},
            ],
        },
    )


def test_health():
    assert client.get("/api/health").json() == {"ok": True}


def test_index_served():
    assert "Recipe Scaler" in client.get("/").text


def test_scale_portions():
    r = client.post("/api/scale", json={"recipe": RECIPE, "mode": "portions", "target_portions": 50})
    assert r.status_code == 200
    assert r.json()["ingredients"][1]["display"] == "5 kg"


def test_scale_ingredient():
    r = client.post(
        "/api/scale",
        json={"recipe": RECIPE, "mode": "ingredient", "ingredient_index": 1, "amount": 2500, "unit": "g"},
    )
    body = r.json()
    assert body["portions"] == 25
    assert body["ingredients"][0]["display"] == "500 g"


def test_scale_per_portion():
    r = client.post("/api/scale", json={"recipe": RECIPE, "mode": "portions", "per_portion": True})
    assert r.json()["ingredients"][0]["display"] == "20 g"


def test_scale_errors_are_friendly():
    r = client.post(
        "/api/scale",
        json={"recipe": RECIPE, "mode": "ingredient", "ingredient_index": 0, "amount": 5, "unit": "ml"},
    )
    assert r.status_code == 422 and "measured in g" in r.json()["detail"]


def test_extract_cleans_result():
    r = client.post("/api/extract", files=[("files", ("a.jpg", jpeg(), "image/jpeg"))])
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Chilli"
    assert body["ingredients"][1]["quantity"] is None
    assert body["ingredients"][2]["uncertain"] is True


def test_extract_rejects_non_image_and_too_many():
    bad = client.post("/api/extract", files=[("files", ("a.txt", b"hello", "text/plain"))])
    assert bad.status_code == 400
    three = client.post("/api/extract", files=[("files", (f"{i}.jpg", jpeg(), "image/jpeg")) for i in range(3)])
    assert three.status_code == 400


def test_rate_limit(monkeypatch):
    monkeypatch.setattr(main, "DAILY_PER_IP", 2)
    codes = [
        client.post("/api/extract", files=[("files", ("a.jpg", jpeg(), "image/jpeg"))]).status_code
        for _ in range(3)
    ]
    assert codes == [200, 200, 429]


def test_prepare_image_shrinks_big_photos():
    media, b64 = extract.prepare_image(jpeg((4000, 3000)))
    assert media == "image/jpeg" and len(b64) > 0
