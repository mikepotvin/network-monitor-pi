import sqlite3
import time

import pytest

from src.database import init_db


def test_init_db_creates_tables(tmp_db_path):
    init_db(tmp_db_path)
    conn = sqlite3.connect(tmp_db_path)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    assert "dns_checks" in tables
    assert "http_checks" in tables
    assert "ping_results" in tables
    assert "ping_results_aggregated" in tables
    assert "speed_tests" in tables


def test_init_db_enables_wal_mode(tmp_db_path):
    init_db(tmp_db_path)
    conn = sqlite3.connect(tmp_db_path)
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    conn.close()
    assert mode == "wal"


def test_init_db_is_idempotent(tmp_db_path):
    init_db(tmp_db_path)
    init_db(tmp_db_path)  # Should not raise
    conn = sqlite3.connect(tmp_db_path)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    assert "ping_results" in tables


from src.database import (
    insert_ping_results,
    insert_dns_check,
    insert_http_check,
    insert_speed_test,
    get_latest_pings,
    get_ping_timeline,
    get_dns_checks,
    get_http_checks,
    get_speed_tests,
)


def test_insert_and_query_ping_results(db_connection, tmp_db_path):
    now = time.time()
    rows = [
        {"timestamp": now, "target": "1.1.1.1", "target_name": "Cloudflare", "rtt_ms": 12.5, "jitter_ms": 1.2, "is_success": 1, "error_message": None},
        {"timestamp": now, "target": "8.8.8.8", "target_name": "Google", "rtt_ms": None, "jitter_ms": None, "is_success": 0, "error_message": "Request timed out"},
    ]
    insert_ping_results(tmp_db_path, rows)
    results = get_latest_pings(tmp_db_path)
    assert len(results) == 2
    cf = [r for r in results if r["target"] == "1.1.1.1"][0]
    assert cf["rtt_ms"] == 12.5
    assert cf["is_success"] == 1
    goog = [r for r in results if r["target"] == "8.8.8.8"][0]
    assert goog["error_message"] == "Request timed out"


def test_insert_and_query_dns_check(db_connection, tmp_db_path):
    now = time.time()
    insert_dns_check(tmp_db_path, now, 15.3, True, None)
    results = get_dns_checks(tmp_db_path, limit=1)
    assert len(results) == 1
    assert results[0]["resolution_ms"] == 15.3


def test_insert_and_query_http_check(db_connection, tmp_db_path):
    now = time.time()
    insert_http_check(tmp_db_path, now, 85.0, 200, True, None)
    results = get_http_checks(tmp_db_path, limit=1)
    assert len(results) == 1
    assert results[0]["response_ms"] == 85.0
    assert results[0]["status_code"] == 200


def test_insert_and_query_speed_test(db_connection, tmp_db_path):
    now = time.time()
    insert_speed_test(tmp_db_path, now, 95.5, 22.3, 15.0, "TestServer")
    results = get_speed_tests(tmp_db_path)
    assert len(results) == 1
    assert results[0]["download_mbps"] == 95.5
    assert results[0]["server_name"] == "TestServer"


def test_get_ping_timeline_24h(db_connection, tmp_db_path):
    now = time.time()
    rows = []
    for i in range(10):
        rows.append({"timestamp": now - (i * 60), "target": "1.1.1.1", "target_name": "Cloudflare", "rtt_ms": 10.0 + i, "jitter_ms": 1.0, "is_success": 1, "error_message": None})
    insert_ping_results(tmp_db_path, rows)
    timeline = get_ping_timeline(tmp_db_path, hours=24)
    assert len(timeline) == 10
    assert timeline[0]["timestamp"] <= timeline[-1]["timestamp"]


from src.database import get_outages


def test_get_outages_detects_outage(db_connection, tmp_db_path):
    now = time.time()
    rows = []
    for i in range(5):
        rows.append({"timestamp": now - 14 + i, "target": "1.1.1.1", "target_name": "Cloudflare", "rtt_ms": 10.0, "jitter_ms": 1.0, "is_success": 1, "error_message": None})
    for i in range(5):
        rows.append({"timestamp": now - 9 + i, "target": "1.1.1.1", "target_name": "Cloudflare", "rtt_ms": None, "jitter_ms": None, "is_success": 0, "error_message": "Request timed out"})
    for i in range(5):
        rows.append({"timestamp": now - 4 + i, "target": "1.1.1.1", "target_name": "Cloudflare", "rtt_ms": 10.0, "jitter_ms": 1.0, "is_success": 1, "error_message": None})
    insert_ping_results(tmp_db_path, rows)
    outages = get_outages(tmp_db_path, hours=1)
    assert len(outages) == 1
    assert outages[0]["target"] == "1.1.1.1"
    assert outages[0]["error_messages"] == "Request timed out"
    assert outages[0]["failed_count"] == 5


def test_get_outages_ignores_single_blip(db_connection, tmp_db_path):
    now = time.time()
    rows = []
    for i in range(5):
        rows.append({"timestamp": now - 6 + i, "target": "1.1.1.1", "target_name": "Cloudflare", "rtt_ms": 10.0, "jitter_ms": 1.0, "is_success": 1, "error_message": None})
    for i in range(2):
        rows.append({"timestamp": now - 1 + i, "target": "1.1.1.1", "target_name": "Cloudflare", "rtt_ms": None, "jitter_ms": None, "is_success": 0, "error_message": "Request timed out"})
    rows.append({"timestamp": now + 1, "target": "1.1.1.1", "target_name": "Cloudflare", "rtt_ms": 10.0, "jitter_ms": 1.0, "is_success": 1, "error_message": None})
    insert_ping_results(tmp_db_path, rows)
    outages = get_outages(tmp_db_path, hours=1)
    assert len(outages) == 0


from src.database import aggregate_old_data, cleanup_old_data


def test_aggregate_old_data(db_connection, tmp_db_path):
    old_time = time.time() - (50 * 3600)
    rows = []
    for i in range(60):
        rows.append({"timestamp": old_time + i, "target": "1.1.1.1", "target_name": "Cloudflare", "rtt_ms": 10.0 + (i % 5), "jitter_ms": 1.0, "is_success": 1 if i < 57 else 0, "error_message": None if i < 57 else "Request timed out"})
    insert_ping_results(tmp_db_path, rows)
    aggregate_old_data(tmp_db_path)
    conn = sqlite3.connect(tmp_db_path)
    conn.row_factory = sqlite3.Row
    raw_count = conn.execute("SELECT COUNT(*) as c FROM ping_results WHERE timestamp < ?", (time.time() - 48 * 3600,)).fetchone()["c"]
    assert raw_count == 0
    agg_rows = conn.execute("SELECT * FROM ping_results_aggregated ORDER BY timestamp").fetchall()
    assert len(agg_rows) >= 1
    # Check that all aggregated rows belong to the right target
    for row in agg_rows:
        assert dict(row)["target"] == "1.1.1.1"
        assert dict(row)["avg_rtt_ms"] is not None or dict(row)["packet_loss_pct"] == 100.0
    # Total loss across all buckets should be ~5% (3 failures out of 60)
    total_rows = sum(1 for _ in agg_rows)
    rows_with_loss = [dict(r) for r in agg_rows if dict(r)["packet_loss_pct"] > 0]
    assert len(rows_with_loss) >= 1  # At least one bucket has failures
    conn.close()


def test_cleanup_old_data(db_connection, tmp_db_path):
    old_time = time.time() - (31 * 24 * 3600)
    insert_ping_results(tmp_db_path, [{"timestamp": old_time, "target": "1.1.1.1", "target_name": "Cloudflare", "rtt_ms": 10.0, "jitter_ms": 1.0, "is_success": 1, "error_message": None}])
    insert_dns_check(tmp_db_path, old_time, 10.0, True, None)
    insert_http_check(tmp_db_path, old_time, 50.0, 200, True, None)
    cleanup_old_data(tmp_db_path)
    conn = sqlite3.connect(tmp_db_path)
    assert conn.execute("SELECT COUNT(*) FROM ping_results").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM dns_checks").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM http_checks").fetchone()[0] == 0
    conn.close()
