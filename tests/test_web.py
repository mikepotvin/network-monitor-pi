import json
import time
from unittest.mock import patch, MagicMock

import pytest

from src.database import (
    init_db,
    insert_ping_results,
    insert_dns_check,
    insert_http_check,
    insert_speed_test,
)


@pytest.fixture
def app(tmp_db_path):
    """Create a test Flask app with a temporary database."""
    init_db(tmp_db_path)

    # Seed some data
    now = time.time()
    insert_ping_results(
        tmp_db_path,
        [
            {
                "timestamp": now,
                "target": "1.1.1.1",
                "target_name": "Cloudflare",
                "rtt_ms": 12.5,
                "jitter_ms": 1.2,
                "is_success": 1,
                "error_message": None,
            },
            {
                "timestamp": now,
                "target": "8.8.8.8",
                "target_name": "Google",
                "rtt_ms": 15.0,
                "jitter_ms": 2.0,
                "is_success": 1,
                "error_message": None,
            },
        ],
    )
    insert_dns_check(tmp_db_path, now, 8.5, True, None)
    insert_http_check(tmp_db_path, now, 95.0, 200, True, None)
    insert_speed_test(tmp_db_path, now, 100.0, 25.0, 12.0, "TestServer")

    with patch("src.web.get_db_path", return_value=tmp_db_path):
        with patch("src.web.scheduler", new=None):
            from src.web import create_app

            app = create_app(start_scheduler=False)
            app.config["TESTING"] = True
            yield app


@pytest.fixture
def client(app):
    return app.test_client()


def test_api_status(client):
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.get_json()
    assert "targets" in data
    assert len(data["targets"]) >= 2
    assert "dns" in data
    assert "http" in data


def test_api_timeline_24h(client):
    response = client.get("/api/timeline?range=24h")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert len(data) >= 2


def test_api_timeline_invalid_range(client):
    response = client.get("/api/timeline?range=999h")
    assert response.status_code == 400


def test_api_outages(client):
    response = client.get("/api/outages")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)


def test_api_speedtests(client):
    response = client.get("/api/speedtests")
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 1
    assert data[0]["download_mbps"] == 100.0


def test_index_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Network Monitor" in response.data
