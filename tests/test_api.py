import json
from unittest.mock import patch

import pytest

from tests.test_utils import create_api_test_app


@pytest.fixture(scope="function")
def api_app():
    """Create a fresh app for API testing."""
    return create_api_test_app()


@pytest.fixture(scope="function")
def api_client(api_app):
    """Create a test client for the API app."""
    with api_app.test_client() as client:
        yield client


def test_simple_api_endpoint(api_client):
    """Test a simple API endpoint."""
    response = api_client.get("/api/test")
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["status"] == "success"
    assert data["message"] == "API is working"


@pytest.mark.parametrize(
    "query,expected_status",
    [
        ("test_query", 200),
        ("", 400),
    ],
)
def test_search_endpoint_with_params(api_client, query, expected_status):
    """Test a search endpoint with different parameters."""
    response = api_client.get(f"/api/search?q={query}")
    assert response.status_code == expected_status

    data = json.loads(response.data)
    if expected_status == 200:
        assert data["status"] == "success"
        assert len(data["results"]) > 0
    else:
        assert data["status"] == "error"
