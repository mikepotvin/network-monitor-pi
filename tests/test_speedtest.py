from unittest.mock import patch, MagicMock

from src.speedtest_runner import run_speed_test


@patch("src.speedtest_runner.speedtest.Speedtest")
def test_run_speed_test_success(mock_speedtest_class):
    mock_instance = MagicMock()
    mock_speedtest_class.return_value = mock_instance
    mock_instance.results.dict.return_value = {
        "download": 100_000_000,
        "upload": 25_000_000,
        "ping": 15.2,
        "server": {"sponsor": "TestISP", "name": "CityName"},
    }
    result = run_speed_test()
    assert result is not None
    assert result["download_mbps"] == 100.0
    assert result["upload_mbps"] == 25.0
    assert result["ping_ms"] == 15.2
    assert "TestISP" in result["server_name"]


@patch("src.speedtest_runner.speedtest.Speedtest")
def test_run_speed_test_failure(mock_speedtest_class):
    mock_speedtest_class.side_effect = Exception("speedtest error")
    result = run_speed_test()
    assert result is None


@patch("src.speedtest_runner.speedtest.Speedtest")
def test_run_speed_test_bad_data(mock_speedtest_class):
    mock_instance = MagicMock()
    mock_speedtest_class.return_value = mock_instance
    mock_instance.results.dict.return_value = {}
    result = run_speed_test()
    assert result is None
