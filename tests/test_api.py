from fastapi.testclient import TestClient
from uuid import uuid4

from app.main import app


def test_health_ja():
    with TestClient(app) as client:
        r = client.get("/health", headers={"Accept-Language": "ja"})
        assert r.status_code == 200
        assert r.json()["status"] in ("正常",)


def test_item_crud_and_stock_flows():
    with TestClient(app) as client:
        # create
        r = client.post(
            "/items/",
            json={"sku": f"T-{uuid4().hex[:6]}", "name": "テスト商品", "min_stock": 0},
            headers={"Accept-Language": "ja"},
        )
        assert r.status_code == 201, r.text
        item = r.json()
        item_id = item["id"]

        # read
        r = client.get(f"/items/{item_id}")
        assert r.status_code == 200

        # update
        r = client.put(f"/items/{item_id}", json={"min_stock": 2})
        assert r.status_code == 200
        assert r.json()["min_stock"] == 2

        # stock in 5
        r = client.post("/stock/in", json={"item_id": item_id, "qty": 5})
        assert r.status_code == 201

        # stock out 2
        r = client.post("/stock/out", json={"item_id": item_id, "qty": 2})
        assert r.status_code == 201

        # adjust -1
        r = client.post("/stock/adjust", json={"item_id": item_id, "qty": -1})
        assert r.status_code == 201

        # balance should be 2
        r = client.get(f"/stock/balance/{item_id}")
        assert r.status_code == 200
        assert r.json()["balance"] == 2
