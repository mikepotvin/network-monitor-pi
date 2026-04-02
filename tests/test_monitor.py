import time
from unittest.mock import MagicMock, patch
from urllib.error import URLError

from src.monitor import execute_ping, classify_ping_error, check_dns, check_http


def _make_ping_host_result(is_alive, avg_rtt=10.0, jitter=1.0, packet_loss=0):
    mock = MagicMock()
    mock.is_alive = is_alive
    mock.avg_rtt = avg_rtt
    mock.jitter = jitter
    mock.packets_sent = 1
    mock.packets_received = 0 if not is_alive else 1
    mock.packet_loss = packet_loss
    return mock


@patch("src.monitor.ping")
def test_execute_ping_success(mock_ping):
    mock_ping.return_value = _make_ping_host_result(True, avg_rtt=12.5, jitter=1.3)
    result = execute_ping("1.1.1.1", "Cloudflare")
    assert result["target"] == "1.1.1.1"
    assert result["target_name"] == "Cloudflare"
    assert result["rtt_ms"] == 12.5
    assert result["jitter_ms"] == 1.3
    assert result["is_success"] == 1
    assert result["error_message"] is None
    assert "timestamp" in result


@patch("src.monitor.ping")
def test_execute_ping_timeout(mock_ping):
    mock_ping.return_value = _make_ping_host_result(False)
    result = execute_ping("1.1.1.1", "Cloudflare")
    assert result["is_success"] == 0
    assert result["rtt_ms"] is None
    assert result["error_message"] == "Request timed out"


@patch("src.monitor.ping")
def test_execute_ping_exception(mock_ping):
    mock_ping.side_effect = OSError("Network is unreachable")
    result = execute_ping("1.1.1.1", "Cloudflare")
    assert result["is_success"] == 0
    assert result["error_message"] == "General failure: Network is unreachable"


@patch("src.monitor.socket.getaddrinfo")
def test_check_dns_success(mock_getaddrinfo):
    mock_getaddrinfo.return_value = [(2, 1, 6, "", ("142.250.80.46", 80))]
    result = check_dns()
    assert result["is_success"] is True
    assert result["resolution_ms"] is not None
    assert result["resolution_ms"] >= 0
    assert result["error_message"] is None


@patch("src.monitor.socket.getaddrinfo")
def test_check_dns_failure(mock_getaddrinfo):
    import socket as _socket
    mock_getaddrinfo.side_effect = _socket.gaierror("Name resolution failed")
    result = check_dns()
    assert result["is_success"] is False
    assert result["resolution_ms"] is None
    assert "DNS resolution failed" in result["error_message"]


@patch("src.monitor.urlopen")
def test_check_http_success(mock_urlopen):
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)
    mock_urlopen.return_value = mock_response
    result = check_http()
    assert result["is_success"] is True
    assert result["status_code"] == 200
    assert result["response_ms"] >= 0


@patch("src.monitor.urlopen")
def test_check_http_failure(mock_urlopen):
    mock_urlopen.side_effect = URLError("Connection refused")
    result = check_http()
    assert result["is_success"] is False
    assert result["status_code"] is None
    assert "HTTP request failed" in result["error_message"]
