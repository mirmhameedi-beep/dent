import asyncio
import concurrent.futures
import contextlib
import threading
import uuid

import httpx
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


def tap(client, mac="device-aaaa-1111", x=0.5, y=0.5, tap_id=None):
    payload = {"mac": mac, "x": x, "y": y}
    if tap_id is not None:
        payload["id"] = tap_id
    return client.post("/tap", json=payload)


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


def test_same_tap_id_twice_counts_once():
    tap_id = "55555555-5555-5555-5555-555555555555"
    client = TestClient(app)
    with client:
        first = tap(client, tap_id=tap_id).json()
        second = tap(client, tap_id=tap_id).json()
        assert first["total"] == 1
        assert second["total"] == 1
        assert first["dent"]["id"] == tap_id
        assert second["dent"] == first["dent"]
        assert len(client.get("/stone").json()["dents"]) == 1
        assert client.get("/wall").json()[0]["taps"] == 1


def test_concurrent_same_id_async_counts_once():
    tap_id = "22222222-2222-2222-2222-222222222222"
    main.init_db()

    async def run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            async def post():
                return await client.post("/tap", json={"id": tap_id, "mac": "async-same-aaaa", "x": 0.4, "y": 0.4})
            return await asyncio.gather(*(post() for _ in range(20)))

    responses = asyncio.run(run())
    assert all(r.status_code == 200 for r in responses)
    bodies = [r.json() for r in responses]
    assert {b["dent"]["id"] for b in bodies} == {tap_id}
    with main.db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM dents").fetchone()[0] == 1
        assert conn.execute("SELECT total FROM counters WHERE id = 1").fetchone()["total"] == 1
        assert conn.execute("SELECT taps FROM tappers").fetchone()["taps"] == 1


def test_concurrent_same_id_threaded_counts_once():
    tap_id = "33333333-3333-3333-3333-333333333333"
    barrier = threading.Barrier(8)

    def run(index):
        barrier.wait()
        response = clients[index].post("/tap", json={"id": tap_id, "mac": "thread-same-aaaa", "x": 0.6, "y": 0.6})
        return response.status_code, response.json()

    with contextlib.ExitStack() as stack:
        clients = [stack.enter_context(TestClient(app)) for _ in range(8)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(run, range(8)))
    assert all(code == 200 for code, _ in results)
    bodies = [body for _, body in results]
    assert {b["dent"]["id"] for b in bodies} == {tap_id}
    with main.db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM dents").fetchone()[0] == 1
        assert conn.execute("SELECT total FROM counters WHERE id = 1").fetchone()["total"] == 1
        assert conn.execute("SELECT taps FROM tappers").fetchone()["taps"] == 1


def test_concurrent_distinct_ids_full_consistency():
    tap_ids = [str(uuid.UUID(int=i + 1000)) for i in range(200)]

    def run(index):
        response = clients[index % 16].post(
            "/tap", json={"id": tap_ids[index], "mac": f"distinct-mac-{index % 16:02d}", "x": 0.1, "y": 0.2}
        )
        return response.status_code, response.json()

    with contextlib.ExitStack() as stack:
        clients = [stack.enter_context(TestClient(app)) for _ in range(16)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
            results = list(pool.map(run, range(200)))

    codes = [code for code, _ in results]
    dent_ids = [body["dent"]["id"] for _, body in results]
    assert codes == [200] * 200
    assert len(set(dent_ids)) == 200
    assert set(dent_ids) == set(tap_ids)
    with main.db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM dents").fetchone()[0] == 200
        assert conn.execute("SELECT total FROM counters WHERE id = 1").fetchone()["total"] == 200
        assert conn.execute("SELECT COALESCE(SUM(taps), 0) FROM tappers").fetchone()[0] == 200


def test_duplicate_bypasses_rate_limit():
    main.MAC_TAPS_PER_SECOND = 1
    try:
        tap_id = "44444444-4444-4444-4444-444444444444"
        mac = "dup-limit-mac-001"
        client = TestClient(app)
        with client:
            assert tap(client, mac=mac, tap_id=tap_id).json()["total"] == 1
            fresh = client.post("/tap", json={"mac": mac, "x": 0.6, "y": 0.6})
            assert fresh.status_code == 429
            again = tap(client, mac=mac, tap_id=tap_id)
            assert again.status_code == 200
            assert again.json()["dent"]["id"] == tap_id
    finally:
        main.MAC_TAPS_PER_SECOND = 10_000


def test_tap_id_is_case_insensitive():
    client = TestClient(app)
    with client:
        first = tap(client, tap_id="AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE").json()
        second = tap(client, tap_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee").json()
        assert first["dent"]["id"] == second["dent"]["id"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        assert second["total"] == 1


def test_legacy_payload_without_id_still_works():
    client = TestClient(app)
    with client:
        first = tap(client).json()["total"]
        second = tap(client).json()["total"]
        assert (first, second) == (1, 2)
        assert len(client.get("/stone").json()["dents"]) == 2


def test_invalid_client_tap_ids_rejected():
    client = TestClient(app)
    with client:
        assert tap(client, tap_id="short").status_code == 422
        assert tap(client, tap_id="z" * 36).status_code == 422
        assert tap(client, tap_id="a" * 36).status_code == 422
        assert tap(client, tap_id="-" * 36).status_code == 422
        assert tap(client, tap_id="1234-12345678-1234-1234-123456789012").status_code == 422
        assert tap(client, tap_id="12345678-12345-1234-1234-123456789012").status_code == 422
        assert len(client.get("/stone").json()["dents"]) == 0


def test_database_restart_persists_all_rows():
    client = TestClient(app)
    with client:
        for i in range(3):
            tap(client, mac=f"restart-mac-00{i}", x=0.1 * i + 0.05)
    main.init_db()
    with TestClient(app) as client:
        body = client.get("/stone").json()
        assert body["total"] == 3
        assert len(body["dents"]) == 3


def seed_total(conn, total):
    conn.execute("UPDATE counters SET total = ? WHERE id = 1", (total,))


def db_state():
    with main.db() as conn:
        return {
            "total": conn.execute("SELECT total FROM counters WHERE id = 1").fetchone()["total"],
            "dents": conn.execute("SELECT COUNT(*) FROM dents").fetchone()[0],
            "taps": conn.execute("SELECT COALESCE(SUM(taps), 0) FROM tappers").fetchone()[0],
        }


def test_final_tap_reaches_exactly_one_billion():
    main.init_db()
    with main.db() as conn:
        seed_total(conn, TARGET - 1)
    tap_id = str(uuid.UUID(int=7001))
    client = TestClient(app)
    with client:
        body = tap(client, mac="final-tap-mac-001", tap_id=tap_id).json()
        assert body["total"] == TARGET
        stone = client.get("/stone").json()
        assert stone["total"] == TARGET
        assert stone["remaining"] == 0
        assert stone["dents"][0]["id"] == tap_id


def test_new_tap_after_completion_receives_410():
    main.init_db()
    with main.db() as conn:
        seed_total(conn, TARGET)
    client = TestClient(app)
    with client:
        response = tap(client, mac="post-complete-mac1", tap_id=str(uuid.UUID(int=7002)))
        assert response.status_code == 410
        assert response.json()["detail"] == "The stone is complete."
        assert db_state() == {"total": TARGET, "dents": 0, "taps": 0}


def test_accepted_duplicate_still_succeeds_after_completion():
    main.init_db()
    original_id = str(uuid.UUID(int=7003))
    original_mac = "dup-complete-mac1"
    with main.db() as conn:
        seed_total(conn, TARGET)
        conn.execute(
            "INSERT INTO dents (id, x, y, mac, at) VALUES (?, ?, ?, ?, ?)",
            (original_id, 0.25, 0.75, original_mac, 1000.0),
        )
        conn.execute(
            "INSERT INTO tappers (mac, taps, first_seen, last_seen) VALUES (?, ?, ?, ?)",
            (original_mac, TARGET, 1000.0, 1000.0),
        )
    client = TestClient(app)
    with client:
        body = tap(client, mac=original_mac, x=0.25, y=0.75, tap_id=original_id).json()
        assert body["total"] == TARGET
        assert body["dent"]["id"] == original_id
        assert body["dent"]["x"] == 0.25


def test_duplicate_after_completion_does_not_double_count():
    main.init_db()
    original_id = str(uuid.UUID(int=7004))
    original_mac = "dup-nodouble-mac1"
    with main.db() as conn:
        seed_total(conn, TARGET)
        conn.execute(
            "INSERT INTO dents (id, x, y, mac, at) VALUES (?, ?, ?, ?, ?)",
            (original_id, 0.5, 0.5, original_mac, 1000.0),
        )
        conn.execute(
            "INSERT INTO tappers (mac, taps, first_seen, last_seen) VALUES (?, ?, ?, ?)",
            (original_mac, TARGET, 1000.0, 1000.0),
        )
    client = TestClient(app)
    with client:
        for _ in range(5):
            response = tap(client, mac=original_mac, tap_id=original_id)
            assert response.status_code == 200
            assert response.json()["dent"]["id"] == original_id
        assert db_state() == {"total": TARGET, "dents": 1, "taps": TARGET}


def test_concurrent_taps_at_completion_boundary():
    main.init_db()
    with main.db() as conn:
        seed_total(conn, TARGET - 1)
    tap_ids = [str(uuid.UUID(int=8000 + i)) for i in range(16)]
    barrier = threading.Barrier(16)

    def run(index):
        barrier.wait()
        response = clients[index % 8].post(
            "/tap",
            json={"id": tap_ids[index], "mac": f"boundary-mac-{index % 8:02d}", "x": 0.3, "y": 0.3},
        )
        return response.status_code, response.json()

    with contextlib.ExitStack() as stack:
        clients = [stack.enter_context(TestClient(app)) for _ in range(8)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
            results = list(pool.map(run, range(16)))

    codes = [code for code, _ in results]
    assert codes.count(200) == 1
    assert codes.count(410) == 15
    winner_index = codes.index(200)
    assert results[winner_index][1]["total"] == TARGET
    with main.db() as conn:
        assert conn.execute("SELECT total FROM counters WHERE id = 1").fetchone()["total"] == TARGET
        assert conn.execute("SELECT COUNT(*) FROM dents").fetchone()[0] == 1
        assert conn.execute("SELECT COALESCE(SUM(taps), 0) FROM tappers").fetchone()[0] == 1
        assert conn.execute("SELECT id FROM dents").fetchone()["id"] == tap_ids[winner_index]


def test_ceiling_small_scale_full_invariant(monkeypatch):
    monkeypatch.setattr(main, "TARGET", 3)
    main.init_db()
    with main.db() as conn:
        conn.execute(
            "INSERT INTO tappers (mac, taps, first_seen, last_seen) VALUES ('seed-mac-001', 2, 0.0, 0.0)"
        )
        conn.execute(
            "INSERT INTO dents (id, x, y, mac, at) VALUES (?, 0.1, 0.1, 'seed-mac-001', 0.0)",
            (str(uuid.UUID(int=9001)),),
        )
        conn.execute(
            "INSERT INTO dents (id, x, y, mac, at) VALUES (?, 0.2, 0.2, 'seed-mac-001', 0.0)",
            (str(uuid.UUID(int=9002)),),
        )
        seed_total(conn, 2)

    def state():
        with main.db() as conn:
            return (
                conn.execute("SELECT COUNT(*) FROM dents").fetchone()[0],
                conn.execute("SELECT total FROM counters WHERE id = 1").fetchone()["total"],
                conn.execute("SELECT COALESCE(SUM(taps), 0) FROM tappers").fetchone()[0],
            )

    assert state() == (2, 2, 2)
    client = TestClient(app)
    with client:
        first = tap(client, mac="small-scale-mac1", tap_id=str(uuid.UUID(int=9003)))
        assert first.status_code == 200
        assert first.json()["total"] == 3
        assert client.get("/stone").json()["remaining"] == 0
        assert state() == (3, 3, 3)
        for i in range(4):
            response = tap(client, mac=f"small-scale-mac{i % 2}", tap_id=str(uuid.UUID(int=9100 + i)))
            assert response.status_code == 410
        assert state() == (3, 3, 3)


def test_rejected_request_rolls_back_completely():
    main.init_db()
    with main.db() as conn:
        seed_total(conn, TARGET)
    state_before = db_state()
    late_ids = [str(uuid.UUID(int=9200 + i)) for i in range(4)]
    client = TestClient(app)
    with client:
        for tap_id in late_ids:
            response = tap(client, mac="rollback-mac-0001", tap_id=tap_id)
            assert response.status_code == 410
        with main.db() as conn:
            for tap_id in late_ids:
                assert conn.execute("SELECT 1 FROM dents WHERE id = ?", (tap_id,)).fetchone() is None
            assert conn.execute("SELECT COUNT(*) FROM tappers WHERE mac = 'rollback-mac-0001'").fetchone()[0] == 0
    assert db_state() == state_before
