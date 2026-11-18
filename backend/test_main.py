import pytest
from fastapi.testclient import TestClient

import main
from main import TARGET, app


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", str(tmp_path / "dent-test.db"))


def test_stone_starts_empty():
    client = TestClient(app)
    with client:
        response = client.get("/stone")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 0
        assert body["target"] == TARGET
        assert body["remaining"] == TARGET


def test_tap_increments_global_and_per_device():
    client = TestClient(app)
    with client:
        assert client.post("/tap", json={"mac": "device-aaaa-1111", "x": 0.5, "y": 0.5}).json()["total"] == 1
        assert client.post("/tap", json={"mac": "device-aaaa-1111", "x": 0.2, "y": 0.7}).json()["total"] == 2
        assert client.post("/tap", json={"mac": "device-bbbb-2222", "x": 0.1, "y": 0.1}).json()["total"] == 3


def test_wall_ranks_devices_by_taps():
    client = TestClient(app)
    with client:
        client.post("/tap", json={"mac": "device-aaaa-1111", "x": 0.5, "y": 0.5})
        client.post("/tap", json={"mac": "device-aaaa-1111", "x": 0.2, "y": 0.7})
        client.post("/tap", json={"mac": "device-bbbb-2222", "x": 0.1, "y": 0.1})
        wall = client.get("/wall").json()
        assert wall[0]["mac"] == "device-aaaa-1111"
        assert wall[0]["taps"] == 2
        assert "at" in wall[0]


def test_tap_rejects_bad_input():
    client = TestClient(app)
    with client:
        assert client.post("/tap", json={"mac": "short", "x": 0.5, "y": 0.5}).status_code == 422
        assert client.post("/tap", json={"mac": "device-cccc-3333", "x": 1.5, "y": 0.5}).status_code == 422
        assert client.post("/tap", json={"mac": "device-dddd-4444", "x": 0.5, "y": -0.1}).status_code == 422


def test_website_served_at_root():
    client = TestClient(app)
    with client:
        response = client.get("/")
        assert response.status_code == 200
        assert "Dent" in response.text
