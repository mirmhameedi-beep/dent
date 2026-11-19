import pytest
from fastapi.testclient import TestClient

import main
from main import TARGET, app


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", str(tmp_path / "dent-test.db"))
    monkeypatch.setattr(main, "MAC_TAPS_PER_SECOND", 10_000)
    monkeypatch.setattr(main, "IP_TAPS_PER_SECOND", 10_000)


def setup_function():
    main._rate.clear()


def tap(client, mac="device-aaaa-1111", x=0.5, y=0.5):
    return client.post("/tap", json={"mac": mac, "x": x, "y": y})


def test_stone_starts_empty():
    client = TestClient(app)
    with client:
        response = client.get("/stone")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 0
        assert body["target"] == TARGET
        assert body["remaining"] == TARGET
        assert body["dents"] == []


def test_tap_increments_global_and_per_device():
    client = TestClient(app)
    with client:
        assert tap(client).json()["total"] == 1
        assert tap(client).json()["total"] == 2
        assert tap(client, mac="device-bbbb-2222").json()["total"] == 3


def test_tap_persists_dents():
    client = TestClient(app)
    with client:
        first = tap(client, x=0.1, y=0.2).json()["dent"]
        second = tap(client, x=0.8, y=0.9).json()["dent"]
        assert first["id"] and second["id"] and first["id"] != second["id"]
        dents = client.get("/stone").json()["dents"]
        assert len(dents) == 2
        assert {d["id"] for d in dents} == {first["id"], second["id"]}
        positions = {(round(d["x"], 2), round(d["y"], 2)) for d in dents}
        assert (0.1, 0.2) in positions and (0.8, 0.9) in positions


def test_wall_ranks_devices_by_taps():
    client = TestClient(app)
    with client:
        tap(client)
        tap(client)
        tap(client, mac="device-bbbb-2222")
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


def test_rate_limit_kicks_in():
    main.MAC_TAPS_PER_SECOND = 3
    try:
        client = TestClient(app)
        with client:
            codes = [tap(client, mac="rate-limit-mac").status_code for i in range(5)]
        assert codes[:3] == [200, 200, 200]
        assert set(codes[3:]) == {429}
    finally:
        main.MAC_TAPS_PER_SECOND = 10_000


def test_rate_limit_is_per_key():
    main.MAC_TAPS_PER_SECOND = 2
    try:
        client = TestClient(app)
        with client:
            assert all(tap(client, mac=f"ip-limit-a-{i}").status_code == 200 for i in range(5))
            assert all(tap(client, mac=f"ip-limit-b-{i}").status_code == 200 for i in range(5))
    finally:
        main.MAC_TAPS_PER_SECOND = 10_000


def test_api_docs_disabled():
    client = TestClient(app)
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_website_served_at_root():
    client = TestClient(app)
    with client:
        response = client.get("/")
        assert response.status_code == 200
        assert "Dent" in response.text
