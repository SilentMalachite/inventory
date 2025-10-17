"""
Enhanced tests for the inventory system API.
"""

import pytest
from fastapi.testclient import TestClient
from uuid import uuid4
import tempfile
import os
from unittest.mock import patch

from app.main import app


def test_health_ja():
    """Test health endpoint with Japanese locale."""
    with TestClient(app) as client:
        r = client.get("/health", headers={"Accept-Language": "ja"})
        assert r.status_code == 200
        assert r.json()["status"] in ("正常",)


def test_health_en():
    """Test health endpoint with English locale."""
    with TestClient(app) as client:
        r = client.get("/health", headers={"Accept-Language": "en"})
        assert r.status_code == 200
        assert r.json()["status"] in ("OK", "ok")


def test_item_crud_and_stock_flows():
    """Test complete CRUD operations and stock flows."""
    with TestClient(app) as client:
        # Create item
        r = client.post(
            "/items/",
            json={"sku": f"T-{uuid4().hex[:6]}", "name": "テスト商品", "min_stock": 0},
            headers={"Accept-Language": "ja"},
        )
        assert r.status_code == 201, r.text
        item = r.json()
        item_id = item["id"]

        # Read item
        r = client.get(f"/items/{item_id}")
        assert r.status_code == 200
        assert r.json()["id"] == item_id

        # Update item
        r = client.put(f"/items/{item_id}", json={"min_stock": 2})
        assert r.status_code == 200
        assert r.json()["min_stock"] == 2

        # Stock in 5
        r = client.post("/stock/in", json={"item_id": item_id, "qty": 5})
        assert r.status_code == 201

        # Stock out 2
        r = client.post("/stock/out", json={"item_id": item_id, "qty": 2})
        assert r.status_code == 201

        # Adjust -1
        r = client.post("/stock/adjust", json={"item_id": item_id, "qty": -1})
        assert r.status_code == 201

        # Balance should be 2
        r = client.get(f"/stock/balance/{item_id}")
        assert r.status_code == 200
        assert r.json()["balance"] == 2

        # Delete item
        r = client.delete(f"/items/{item_id}")
        assert r.status_code == 204

        # Verify deletion
        r = client.get(f"/items/{item_id}")
        assert r.status_code == 404


def test_duplicate_sku_error():
    """Test error handling for duplicate SKU."""
    with TestClient(app) as client:
        sku = f"DUPLICATE-{uuid4().hex[:6]}"

        # Create first item
        r = client.post(
            "/items/",
            json={"sku": sku, "name": "最初の商品", "min_stock": 0},
        )
        assert r.status_code == 201

        # Try to create duplicate
        r = client.post(
            "/items/",
            json={"sku": sku, "name": "重複商品", "min_stock": 0},
        )
        assert r.status_code == 409


def test_insufficient_stock_error():
    """Test error handling for insufficient stock."""
    with TestClient(app) as client:
        # Create item
        r = client.post(
            "/items/",
            json={
                "sku": f"STOCK-{uuid4().hex[:6]}",
                "name": "在庫テスト商品",
                "min_stock": 0,
            },
        )
        assert r.status_code == 201
        item_id = r.json()["id"]

        # Stock in 5
        r = client.post("/stock/in", json={"item_id": item_id, "qty": 5})
        assert r.status_code == 201

        # Try to stock out more than available
        r = client.post("/stock/out", json={"item_id": item_id, "qty": 10})
        assert r.status_code == 400


def test_item_not_found_error():
    """Test error handling for non-existent item."""
    with TestClient(app) as client:
        # Try to get non-existent item
        r = client.get("/items/99999")
        assert r.status_code == 404

        # Try to update non-existent item
        r = client.put("/items/99999", json={"min_stock": 5})
        assert r.status_code == 404

        # Try to delete non-existent item
        r = client.delete("/items/99999")
        assert r.status_code == 404

        # Try stock operations on non-existent item
        r = client.post("/stock/in", json={"item_id": 99999, "qty": 5})
        assert r.status_code == 404


def test_stock_search_pagination():
    """Test stock search with pagination."""
    with TestClient(app) as client:
        # Create multiple items
        item_ids = []
        for i in range(5):
            r = client.post(
                "/items/",
                json={
                    "sku": f"SEARCH-{uuid4().hex[:6]}",
                    "name": f"検索商品{i}",
                    "min_stock": 0,
                },
            )
            assert r.status_code == 201
            item_ids.append(r.json()["id"])

            # Add some stock
            client.post("/stock/in", json={"item_id": r.json()["id"], "qty": 10})

        # Test pagination
        r = client.get("/stock/search?page=1&size=2")
        assert r.status_code == 200
        data = r.json()
        assert len(data["items"]) == 2
        assert data["total"] >= 5
        assert data["page"] == 1
        assert data["size"] == 2

        # Test second page
        r = client.get("/stock/search?page=2&size=2")
        assert r.status_code == 200
        data = r.json()
        assert len(data["items"]) == 2
        assert data["page"] == 2


def test_stock_search_filtering():
    """Test stock search with various filters."""
    with TestClient(app) as client:
        # Create items with different categories
        categories = ["電子機器", "食品", "衣類"]
        item_ids = []

        for i, category in enumerate(categories):
            r = client.post(
                "/items/",
                json={
                    "sku": f"CAT-{uuid4().hex[:6]}",
                    "name": f"{category}商品{i}",
                    "category": category,
                    "min_stock": 5,
                },
            )
            assert r.status_code == 201
            item_id = r.json()["id"]
            item_ids.append(item_id)

            # Add different stock amounts
            stock_qty = (i + 1) * 10
            client.post("/stock/in", json={"item_id": item_id, "qty": stock_qty})

        # Test category filter
        r = client.get("/stock/search?category=電子機器")
        assert r.status_code == 200
        data = r.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["category"] == "電子機器"

        # Test low stock filter
        r = client.get("/stock/search?low_only=true")
        assert r.status_code == 200
        data = r.json()
        # All items should have stock > min_stock, so no low stock items
        assert len(data["items"]) == 0

        # Test balance range filter
        r = client.get("/stock/search?min_balance=15&max_balance=25")
        assert r.status_code == 200
        data = r.json()
        assert len(data["items"]) == 1
        assert 15 <= data["items"][0]["balance"] <= 25


def test_validation_error_handling():
    """Test validation error handling."""
    with TestClient(app) as client:
        # Test invalid item creation (missing required fields)
        r = client.post("/items/", json={"name": "テスト商品"})  # Missing SKU
        assert r.status_code == 422

        # Test invalid stock quantity
        r = client.post(
            "/stock/in", json={"item_id": 1, "qty": -5}
        )  # Negative quantity
        assert r.status_code == 422


def test_api_key_security():
    """Test API key security."""
    # Set environment variables for testing
    os.environ["INVENTORY_API_KEY"] = "test-api-key"
    os.environ["INVENTORY_DEV_MODE"] = "false"

    with TestClient(app) as client:
        # Create item first
        r = client.post(
            "/items/",
            json={
                "sku": f"SECURE-{uuid4().hex[:6]}",
                "name": "セキュリティテスト商品",
                "min_stock": 0,
            },
        )
        assert r.status_code == 201
        item_id = r.json()["id"]

        # Test without API key (should fail)
        r = client.get(f"/items/{item_id}")
        assert r.status_code == 500  # Configuration error

        # Test with wrong API key
        r = client.get(f"/items/{item_id}", headers={"X-API-Key": "wrong-key"})
        assert r.status_code == 401

        # Test with correct API key
        r = client.get(f"/items/{item_id}", headers={"X-API-Key": "test-api-key"})
        assert r.status_code == 200

    # Clean up
    del os.environ["INVENTORY_API_KEY"]
    del os.environ["INVENTORY_DEV_MODE"]


def test_stock_trend():
    """Test stock trend endpoint."""
    with TestClient(app) as client:
        # Create item
        r = client.post(
            "/items/",
            json={
                "sku": f"TREND-{uuid4().hex[:6]}",
                "name": "トレンドテスト商品",
                "min_stock": 0,
            },
        )
        assert r.status_code == 201
        item_id = r.json()["id"]

        # Add some stock movements
        for qty in [10, -5, 3, -2]:
            r = client.post("/stock/in", json={"item_id": item_id, "qty": qty})
            assert r.status_code == 201

        # Get trend
        r = client.get(f"/stock/trend/{item_id}?days=7")
        assert r.status_code == 200
        data = r.json()
        assert "trend" in data
        assert len(data["trend"]) <= 7


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
