"""
Test configuration and utilities.
"""

import pytest
import tempfile
import os
from pathlib import Path

from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture
def test_app_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        os.environ["INVENTORY_APP_DIR"] = temp_dir
        os.environ["INVENTORY_AUDIT_DISABLED"] = "1"
        os.environ["INVENTORY_DEV_MODE"] = "true"
        yield temp_dir
        # Cleanup
        for key in [
            "INVENTORY_APP_DIR",
            "INVENTORY_AUDIT_DISABLED",
            "INVENTORY_DEV_MODE",
        ]:
            if key in os.environ:
                del os.environ[key]


@pytest.fixture
def client(test_app_dir):
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def sample_item_data():
    """Sample item data for testing."""
    return {
        "sku": "TEST-001",
        "name": "テスト商品",
        "category": "電子機器",
        "unit": "個",
        "min_stock": 10,
    }
