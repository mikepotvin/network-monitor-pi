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


def test_api_health(client):
    response = client.get("/api/health?range=24h")
    assert response.status_code == 200
    data = response.get_json()
    assert "targets" in data
    assert len(data["targets"]) >= 2
    for t in data["targets"]:
        assert "uptime_pct" in t
        assert "current_streak" in t
        assert "outage_count" in t
        assert "percentiles_available" in t


def test_api_health_invalid_range(client):
    response = client.get("/api/health?range=999h")
    assert response.status_code == 400


def test_api_packet_loss(client):
    response = client.get("/api/packet-loss?range=24h")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)


def test_api_packet_loss_invalid_range(client):
    response = client.get("/api/packet-loss?range=999h")
    assert response.status_code == 400


def test_api_errors(client):
    response = client.get("/api/errors?hours=24")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)


@patch("src.web.subprocess.run")
def test_api_logs(mock_run, client):
    mock_run.return_value = MagicMock(stdout="Apr 02 01:00:00 pi systemd[1]: Started.\n")
    response = client.get("/api/logs")
    assert response.status_code == 200
    assert response.content_type.startswith("text/plain")
    assert b"Started" in response.data


@patch("src.web.subprocess.run")
def test_api_logs_custom_lines(mock_run, client):
    mock_run.return_value = MagicMock(stdout="line1\nline2\n")
    response = client.get("/api/logs?lines=200")
    assert response.status_code == 200
    args = mock_run.call_args[0][0]
    assert "-n" in args
    assert "200" in args


@patch("src.web.subprocess.run")
def test_api_logs_clamps_lines(mock_run, client):
    mock_run.return_value = MagicMock(stdout="")
    client.get("/api/logs?lines=9999")
    args = mock_run.call_args[0][0]
    assert "1000" in args


@patch("src.web.subprocess.run", side_effect=FileNotFoundError("no journalctl"))
def test_api_logs_journalctl_missing(mock_run, client):
    response = client.get("/api/logs")
    assert response.status_code == 500


def test_api_speedtest_status(client):
    response = client.get("/api/speedtest/status")
    assert response.status_code == 200
    data = response.get_json()
    assert "running" in data
    assert "last_run_time" in data


@patch("src.web.run_speed_test")
def test_api_speedtest_run_returns_202(mock_run, client):
    mock_run.return_value = {
        "timestamp": time.time(), "download_mbps": 50.0, "upload_mbps": 10.0,
        "ping_ms": 20.0, "server_name": "Test",
    }
    import src.web as web
    web._speed_test_status["running"] = False
    web._speed_test_status["last_run_time"] = 0.0
    response = client.post("/api/speedtest/run")
    assert response.status_code == 202
    data = response.get_json()
    assert data["status"] == "started"
    # Wait briefly for thread to finish, then reset
    time.sleep(0.5)
    web._speed_test_status["running"] = False
    web._speed_test_status["last_run_time"] = 0.0


@patch("src.web.run_speed_test")
def test_api_speedtest_run_409_when_running(mock_run, client):
    import src.web as web
    web._speed_test_status["running"] = True
    response = client.post("/api/speedtest/run")
    assert response.status_code == 409
    web._speed_test_status["running"] = False


@patch("src.web.run_speed_test")
def test_api_speedtest_run_429_rate_limit(mock_run, client):
    import src.web as web
    web._speed_test_status["running"] = False
    web._speed_test_status["last_run_time"] = time.time()
    response = client.post("/api/speedtest/run")
    assert response.status_code == 429
    web._speed_test_status["last_run_time"] = 0.0


def test_index_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Network Monitor" in response.data
