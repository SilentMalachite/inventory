from __future__ import annotations

import threading
import time
from typing import List
from fastapi.testclient import TestClient
from uuid import uuid4

from app.main import app


def create_item(client: TestClient) -> int:
    r = client.post(
        "/items/",
        json={"sku": f"C-{uuid4().hex[:6]}", "name": "並行テスト", "min_stock": 0},
        def do_out():
            with TestClient(app) as thread_client:
                r2 = thread_client.post("/stock/out", json={"item_id": item_id, "qty": 2})
                results.append(r2.status_code)


def test_concurrent_out_conflict_then_retry():
    with TestClient(app) as client:
        item_id = create_item(client)

        # stock in 3
        r = client.post("/stock/in", json={"item_id": item_id, "qty": 3})
        assert r.status_code == 201

        # We will attempt two concurrent OUT of qty=2; only one should succeed
        results: List[int] = []

        def do_out():
            r2 = client.post("/stock/out", json={"item_id": item_id, "qty": 2})
            results.append(r2.status_code)

        t1 = threading.Thread(target=do_out)
        t2 = threading.Thread(target=do_out)
        t1.start(); t2.start(); t1.join(); t2.join()

        # One succeeds (201), one fails with insufficient stock (400) or conflict (409)
        assert 201 in results
        assert any(code in (400, 409) for code in results)

        # Balance should be 1 or  - depending on ordering the failed one shouldn't change balance
        r = client.get(f"/stock/balance/{item_id}")
        assert r.status_code == 200
        bal = r.json()["balance"] if isinstance(r.json(), dict) else r.json()["data"]["balance"]
        assert bal in (1,)


def test_adjust_with_parallel_out_protected():
    with TestClient(app) as client:
        item_id = create_item(client)
        client.post("/stock/in", json={"item_id": item_id, "qty": 5})

        # Start a long adjust (+2) while out (4) happens quickly
        done = []

        def do_adjust():
            # Simulate a slightly delayed adjust
            time.sleep(0.05)
            r = client.post("/stock/adjust", json={"item_id": item_id, "qty": 2})
            done.append(r.status_code)

        t = threading.Thread(target=do_adjust)
        t.start()
        r2 = client.post("/stock/out", json={"item_id": item_id, "qty": 4})
        t.join()

        assert r2.status_code in (201, 400)  # may pass or fail depending on exact interleaving
        assert done[0] == 201  # adjust should succeed

        r = client.get(f"/stock/balance/{item_id}")
        assert r.status_code == 200
        bal = r.json()["balance"] if isinstance(r.json(), dict) else r.json()["data"]["balance"]
        # Possible balances: (5 in - 4 out + 2 adjust) = 3 if out succeeded; or 7 if out failed
        assert bal in (3, 7)
