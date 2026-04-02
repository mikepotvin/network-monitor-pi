# Network Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a lightweight, always-on network monitor for Raspberry Pi 3 that tracks packet loss, disconnects, latency, jitter, DNS/HTTP health, and nightly speed tests — viewable via a web dashboard from any LAN device.

**Architecture:** Single Python process — Flask serves the dashboard and API while a background thread runs the monitoring engine (pings every 1s, DNS/HTTP checks every 60s, speed test at 1 AM). Results buffer in memory and flush to SQLite every 30s. A nightly job aggregates old data and cleans up records older than 30 days.

**Tech Stack:** Python 3, icmplib, Flask, gunicorn, SQLite, speedtest-cli, uPlot, vanilla JS/CSS

**Spec:** `docs/superpowers/specs/2026-04-02-network-monitor-design.md`

---

## File Structure

```
network-monitor-pi/
  src/
    __init__.py            # Package init
    config.py              # All configuration constants
    database.py            # Schema, CRUD, buffer flush, aggregation
    monitor.py             # Ping/DNS/HTTP monitoring engine
    speedtest_runner.py    # Speed test execution
    scheduler.py           # Background scheduling (monitor loop, speed test, cleanup)
    web.py                 # Flask app, API endpoints, app factory
  static/
    css/style.css          # Dashboard styles (dark theme, responsive)
    js/app.js              # Dashboard logic (tabs, API calls, chart rendering)
    js/uplot.min.js        # uPlot charting library (vendored)
    js/uplot.min.css       # uPlot styles (vendored)
  templates/
    index.html             # Single-page dashboard template
  tests/
    __init__.py
    conftest.py            # Shared fixtures (test DB, mock time)
    test_database.py       # Database CRUD and aggregation tests
    test_monitor.py        # Monitoring engine tests (mocked icmplib)
    test_speedtest.py      # Speed test runner tests
    test_web.py            # API endpoint tests
  requirements.txt         # Production dependencies
  requirements-dev.txt     # Dev/test dependencies
  setup.sh                 # Pi deployment script
  network-monitor.service  # systemd unit file
  pytest.ini               # Pytest configuration
  README.md                # Setup and usage instructions
```

---

## Task 1: Project Scaffolding

**Files:**
- Create: `src/__init__.py`
- Create: `src/config.py`
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `pytest.ini`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Initialize git repo**

```bash
cd /Users/mike/Projects/network-monitor-pi
git init
```

- [ ] **Step 2: Create .gitignore**

Create `.gitignore`:

```
__pycache__/
*.pyc
*.pyo
venv/
.venv/
*.db
*.db-wal
*.db-shm
.pytest_cache/
*.egg-info/
dist/
build/
.env
data/
```

- [ ] **Step 3: Create requirements.txt**

```
icmplib>=3.0,<4.0
flask>=3.0,<4.0
gunicorn>=22.0,<23.0
speedtest-cli>=2.1,<3.0
```

- [ ] **Step 4: Create requirements-dev.txt**

```
-r requirements.txt
pytest>=8.0,<9.0
pytest-mock>=3.0,<4.0
```

- [ ] **Step 5: Create pytest.ini**

```ini
[pytest]
testpaths = tests
pythonpath = .
```

- [ ] **Step 6: Create src/__init__.py**

```python
```

(Empty file — makes `src` a package.)

- [ ] **Step 7: Create src/config.py**

```python
import subprocess


# --- Ping Configuration ---
PING_INTERVAL_SECONDS = 1
PING_TIMEOUT_SECONDS = 2
PING_COUNT = 1  # pings per cycle per target

# --- Ping Targets ---
# Gateway is detected at startup; these are the fixed external targets.
EXTERNAL_TARGETS = [
    {"ip": "1.1.1.1", "name": "Cloudflare"},
    {"ip": "8.8.8.8", "name": "Google"},
    {"ip": "208.67.222.222", "name": "OpenDNS"},
]

# --- DNS Check ---
DNS_CHECK_INTERVAL_SECONDS = 60
DNS_CHECK_HOSTNAME = "google.com"

# --- HTTP Check ---
HTTP_CHECK_INTERVAL_SECONDS = 60
HTTP_CHECK_URL = "http://captive.apple.com/hotspot-detect.html"
HTTP_CHECK_TIMEOUT_SECONDS = 10

# --- Speed Test ---
SPEED_TEST_HOUR = 1  # 1 AM local time
SPEED_TEST_MINUTE = 0

# --- Database ---
DB_PATH = "data/monitor.db"
BUFFER_FLUSH_INTERVAL_SECONDS = 30

# --- Data Retention ---
RAW_DATA_RETENTION_HOURS = 48
AGGREGATED_DATA_RETENTION_DAYS = 30
CLEANUP_HOUR = 1
CLEANUP_MINUTE = 15

# --- Web ---
WEB_HOST = "0.0.0.0"
WEB_PORT = 5000

# --- Status Thresholds ---
DEGRADED_LATENCY_MS = 200
DEGRADED_LOSS_PCT = 10
OUTAGE_CONSECUTIVE_FAILURES = 3


def detect_gateway() -> str | None:
    """Detect the default gateway IP from the system routing table."""
    try:
        result = subprocess.run(
            ["ip", "route", "show", "default"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        # Output: "default via 192.168.1.1 dev eth0 ..."
        parts = result.stdout.strip().split()
        if len(parts) >= 3 and parts[0] == "default" and parts[1] == "via":
            return parts[2]
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None
```

- [ ] **Step 8: Create tests/__init__.py**

```python
```

(Empty file.)

- [ ] **Step 9: Create tests/conftest.py**

```python
import os
import sqlite3
import tempfile

import pytest


@pytest.fixture
def tmp_db_path(tmp_path):
    """Return a path for a temporary SQLite database."""
    return str(tmp_path / "test_monitor.db")


@pytest.fixture
def db_connection(tmp_db_path):
    """Create a temporary SQLite database with the schema applied."""
    from src.database import init_db

    init_db(tmp_db_path)
    conn = sqlite3.connect(tmp_db_path)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()
```

- [ ] **Step 10: Create virtual environment and install deps**

```bash
cd /Users/mike/Projects/network-monitor-pi
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt
```

- [ ] **Step 11: Run pytest to verify setup**

Run: `cd /Users/mike/Projects/network-monitor-pi && source venv/bin/activate && pytest -v`
Expected: `no tests ran` (0 collected, no errors)

- [ ] **Step 12: Commit**

```bash
git add .gitignore requirements.txt requirements-dev.txt pytest.ini src/__init__.py src/config.py tests/__init__.py tests/conftest.py
git commit -m "chore: scaffold project with config, deps, and test fixtures"
```

---

## Task 2: Database Layer

**Files:**
- Create: `src/database.py`
- Create: `tests/test_database.py`

- [ ] **Step 1: Write tests for schema initialization**

Create `tests/test_database.py`:

```python
import sqlite3
import time

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/mike/Projects/network-monitor-pi && source venv/bin/activate && pytest tests/test_database.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.database'`

- [ ] **Step 3: Implement init_db**

Create `src/database.py`:

```python
import os
import sqlite3
import threading
import time
from typing import Any


def get_connection(db_path: str) -> sqlite3.Connection:
    """Create a new SQLite connection with standard settings."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA journal_size_limit=1048576")
    return conn


def init_db(db_path: str) -> None:
    """Create the database and all tables if they don't exist."""
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = get_connection(db_path)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS ping_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL NOT NULL,
            target TEXT NOT NULL,
            target_name TEXT NOT NULL,
            rtt_ms REAL,
            jitter_ms REAL,
            is_success INTEGER NOT NULL,
            error_message TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_ping_timestamp ON ping_results(timestamp);
        CREATE INDEX IF NOT EXISTS idx_ping_target_timestamp ON ping_results(target, timestamp);

        CREATE TABLE IF NOT EXISTS dns_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL NOT NULL,
            resolution_ms REAL,
            is_success INTEGER NOT NULL,
            error_message TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_dns_timestamp ON dns_checks(timestamp);

        CREATE TABLE IF NOT EXISTS http_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL NOT NULL,
            response_ms REAL,
            status_code INTEGER,
            is_success INTEGER NOT NULL,
            error_message TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_http_timestamp ON http_checks(timestamp);

        CREATE TABLE IF NOT EXISTS speed_tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL NOT NULL,
            download_mbps REAL,
            upload_mbps REAL,
            ping_ms REAL,
            server_name TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_speed_timestamp ON speed_tests(timestamp);

        CREATE TABLE IF NOT EXISTS ping_results_aggregated (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL NOT NULL,
            target TEXT NOT NULL,
            target_name TEXT NOT NULL,
            avg_rtt_ms REAL,
            max_rtt_ms REAL,
            packet_loss_pct REAL,
            avg_jitter_ms REAL
        );
        CREATE INDEX IF NOT EXISTS idx_ping_agg_target_timestamp
            ON ping_results_aggregated(target, timestamp);
        """
    )
    conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/mike/Projects/network-monitor-pi && source venv/bin/activate && pytest tests/test_database.py -v`
Expected: 3 passed

- [ ] **Step 5: Write tests for insert and query operations**

Append to `tests/test_database.py`:

```python
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
            "rtt_ms": None,
            "jitter_ms": None,
            "is_success": 0,
            "error_message": "Request timed out",
        },
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
    # Insert 10 pings over the last hour
    for i in range(10):
        rows.append(
            {
                "timestamp": now - (i * 60),
                "target": "1.1.1.1",
                "target_name": "Cloudflare",
                "rtt_ms": 10.0 + i,
                "jitter_ms": 1.0,
                "is_success": 1,
                "error_message": None,
            }
        )
    insert_ping_results(tmp_db_path, rows)
    timeline = get_ping_timeline(tmp_db_path, hours=24)
    assert len(timeline) == 10
    # Should be ordered by timestamp ascending
    assert timeline[0]["timestamp"] <= timeline[-1]["timestamp"]
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `cd /Users/mike/Projects/network-monitor-pi && source venv/bin/activate && pytest tests/test_database.py -v`
Expected: FAIL — `ImportError: cannot import name 'insert_ping_results'`

- [ ] **Step 7: Implement insert and query functions**

Append to `src/database.py`:

```python
def insert_ping_results(db_path: str, rows: list[dict[str, Any]]) -> None:
    """Batch insert ping results."""
    if not rows:
        return
    conn = get_connection(db_path)
    conn.executemany(
        """INSERT INTO ping_results
           (timestamp, target, target_name, rtt_ms, jitter_ms, is_success, error_message)
           VALUES (:timestamp, :target, :target_name, :rtt_ms, :jitter_ms, :is_success, :error_message)""",
        rows,
    )
    conn.commit()
    conn.close()


def insert_dns_check(
    db_path: str,
    timestamp: float,
    resolution_ms: float | None,
    is_success: bool,
    error_message: str | None,
) -> None:
    """Insert a single DNS check result."""
    conn = get_connection(db_path)
    conn.execute(
        """INSERT INTO dns_checks (timestamp, resolution_ms, is_success, error_message)
           VALUES (?, ?, ?, ?)""",
        (timestamp, resolution_ms, int(is_success), error_message),
    )
    conn.commit()
    conn.close()


def insert_http_check(
    db_path: str,
    timestamp: float,
    response_ms: float | None,
    status_code: int | None,
    is_success: bool,
    error_message: str | None,
) -> None:
    """Insert a single HTTP check result."""
    conn = get_connection(db_path)
    conn.execute(
        """INSERT INTO http_checks (timestamp, response_ms, status_code, is_success, error_message)
           VALUES (?, ?, ?, ?, ?)""",
        (timestamp, response_ms, status_code, int(is_success), error_message),
    )
    conn.commit()
    conn.close()


def insert_speed_test(
    db_path: str,
    timestamp: float,
    download_mbps: float,
    upload_mbps: float,
    ping_ms: float,
    server_name: str,
) -> None:
    """Insert a single speed test result."""
    conn = get_connection(db_path)
    conn.execute(
        """INSERT INTO speed_tests (timestamp, download_mbps, upload_mbps, ping_ms, server_name)
           VALUES (?, ?, ?, ?, ?)""",
        (timestamp, download_mbps, upload_mbps, ping_ms, server_name),
    )
    conn.commit()
    conn.close()


def get_latest_pings(db_path: str) -> list[dict]:
    """Get the most recent ping result for each target."""
    conn = get_connection(db_path)
    cursor = conn.execute(
        """SELECT p.* FROM ping_results p
           INNER JOIN (
               SELECT target, MAX(timestamp) as max_ts
               FROM ping_results GROUP BY target
           ) latest ON p.target = latest.target AND p.timestamp = latest.max_ts
           ORDER BY p.target_name"""
    )
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results


def get_ping_timeline(
    db_path: str, hours: int = 24, target: str | None = None
) -> list[dict]:
    """Get ping results for the timeline chart.

    For ranges <= 48h, returns raw data.
    For ranges > 48h, returns aggregated 1-minute data.
    """
    cutoff = time.time() - (hours * 3600)

    conn = get_connection(db_path)
    if hours <= 48:
        sql = "SELECT * FROM ping_results WHERE timestamp >= ?"
        params: list[Any] = [cutoff]
        if target:
            sql += " AND target = ?"
            params.append(target)
        sql += " ORDER BY timestamp ASC"
        cursor = conn.execute(sql, params)
    else:
        sql = "SELECT * FROM ping_results_aggregated WHERE timestamp >= ?"
        params = [cutoff]
        if target:
            sql += " AND target = ?"
            params.append(target)
        sql += " ORDER BY timestamp ASC"
        cursor = conn.execute(sql, params)

    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results


def get_dns_checks(db_path: str, limit: int = 100) -> list[dict]:
    """Get recent DNS check results."""
    conn = get_connection(db_path)
    cursor = conn.execute(
        "SELECT * FROM dns_checks ORDER BY timestamp DESC LIMIT ?", (limit,)
    )
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results


def get_http_checks(db_path: str, limit: int = 100) -> list[dict]:
    """Get recent HTTP check results."""
    conn = get_connection(db_path)
    cursor = conn.execute(
        "SELECT * FROM http_checks ORDER BY timestamp DESC LIMIT ?", (limit,)
    )
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results


def get_speed_tests(db_path: str) -> list[dict]:
    """Get all speed test results."""
    conn = get_connection(db_path)
    cursor = conn.execute("SELECT * FROM speed_tests ORDER BY timestamp DESC")
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `cd /Users/mike/Projects/network-monitor-pi && source venv/bin/activate && pytest tests/test_database.py -v`
Expected: 8 passed

- [ ] **Step 9: Write tests for outage detection**

Append to `tests/test_database.py`:

```python
from src.database import get_outages


def test_get_outages_detects_outage(db_connection, tmp_db_path):
    """3+ consecutive failures on a target = an outage."""
    now = time.time()
    rows = []
    # 5 successful pings, then 5 failures, then 5 successes
    for i in range(5):
        rows.append(
            {
                "timestamp": now - 14 + i,
                "target": "1.1.1.1",
                "target_name": "Cloudflare",
                "rtt_ms": 10.0,
                "jitter_ms": 1.0,
                "is_success": 1,
                "error_message": None,
            }
        )
    for i in range(5):
        rows.append(
            {
                "timestamp": now - 9 + i,
                "target": "1.1.1.1",
                "target_name": "Cloudflare",
                "rtt_ms": None,
                "jitter_ms": None,
                "is_success": 0,
                "error_message": "Request timed out",
            }
        )
    for i in range(5):
        rows.append(
            {
                "timestamp": now - 4 + i,
                "target": "1.1.1.1",
                "target_name": "Cloudflare",
                "rtt_ms": 10.0,
                "jitter_ms": 1.0,
                "is_success": 1,
                "error_message": None,
            }
        )
    insert_ping_results(tmp_db_path, rows)

    outages = get_outages(tmp_db_path, hours=1)
    assert len(outages) == 1
    assert outages[0]["target"] == "1.1.1.1"
    assert outages[0]["error_messages"] == "Request timed out"
    assert outages[0]["failed_count"] == 5


def test_get_outages_ignores_single_blip(db_connection, tmp_db_path):
    """1-2 consecutive failures should NOT be an outage."""
    now = time.time()
    rows = []
    for i in range(5):
        rows.append(
            {
                "timestamp": now - 6 + i,
                "target": "1.1.1.1",
                "target_name": "Cloudflare",
                "rtt_ms": 10.0,
                "jitter_ms": 1.0,
                "is_success": 1,
                "error_message": None,
            }
        )
    # Only 2 failures — not enough for outage
    for i in range(2):
        rows.append(
            {
                "timestamp": now - 1 + i,
                "target": "1.1.1.1",
                "target_name": "Cloudflare",
                "rtt_ms": None,
                "jitter_ms": None,
                "is_success": 0,
                "error_message": "Request timed out",
            }
        )
    rows.append(
        {
            "timestamp": now + 1,
            "target": "1.1.1.1",
            "target_name": "Cloudflare",
            "rtt_ms": 10.0,
            "jitter_ms": 1.0,
            "is_success": 1,
            "error_message": None,
        }
    )
    insert_ping_results(tmp_db_path, rows)

    outages = get_outages(tmp_db_path, hours=1)
    assert len(outages) == 0
```

- [ ] **Step 10: Run tests to verify they fail**

Run: `cd /Users/mike/Projects/network-monitor-pi && source venv/bin/activate && pytest tests/test_database.py::test_get_outages_detects_outage -v`
Expected: FAIL — `ImportError: cannot import name 'get_outages'`

- [ ] **Step 11: Implement get_outages**

Append to `src/database.py`:

```python
def get_outages(
    db_path: str, hours: int = 24, page: int = 1, limit: int = 50
) -> list[dict]:
    """Detect outages from ping data.

    An outage is 3+ consecutive failures for a single target.
    Returns outage periods with start/end times and error messages.
    """
    cutoff = time.time() - (hours * 3600)
    conn = get_connection(db_path)
    cursor = conn.execute(
        """SELECT timestamp, target, target_name, is_success, error_message
           FROM ping_results
           WHERE timestamp >= ?
           ORDER BY target, timestamp ASC""",
        (cutoff,),
    )
    rows = cursor.fetchall()
    conn.close()

    # Group by target and find consecutive failure runs
    outages = []
    current_target = None
    fail_run: list[dict] = []

    def _flush_run():
        if len(fail_run) >= 3:
            error_msgs = list(set(r["error_message"] for r in fail_run if r["error_message"]))
            outages.append(
                {
                    "target": fail_run[0]["target"],
                    "target_name": fail_run[0]["target_name"],
                    "start_time": fail_run[0]["timestamp"],
                    "end_time": fail_run[-1]["timestamp"],
                    "duration_seconds": fail_run[-1]["timestamp"] - fail_run[0]["timestamp"],
                    "failed_count": len(fail_run),
                    "error_messages": ", ".join(error_msgs) if error_msgs else None,
                }
            )

    for row in rows:
        row = dict(row)
        if row["target"] != current_target:
            _flush_run()
            fail_run = []
            current_target = row["target"]

        if row["is_success"] == 0:
            fail_run.append(row)
        else:
            _flush_run()
            fail_run = []

    _flush_run()  # flush last run

    # Sort by start_time descending, paginate
    outages.sort(key=lambda o: o["start_time"], reverse=True)
    start = (page - 1) * limit
    return outages[start : start + limit]
```

- [ ] **Step 12: Run tests to verify they pass**

Run: `cd /Users/mike/Projects/network-monitor-pi && source venv/bin/activate && pytest tests/test_database.py -v`
Expected: 10 passed

- [ ] **Step 13: Write tests for aggregation and cleanup**

Append to `tests/test_database.py`:

```python
from src.database import aggregate_old_data, cleanup_old_data


def test_aggregate_old_data(db_connection, tmp_db_path):
    """Data older than 48h should be aggregated into 1-minute buckets."""
    old_time = time.time() - (50 * 3600)  # 50 hours ago
    rows = []
    # 60 pings in the same minute, 50 hours ago
    for i in range(60):
        rows.append(
            {
                "timestamp": old_time + i,
                "target": "1.1.1.1",
                "target_name": "Cloudflare",
                "rtt_ms": 10.0 + (i % 5),
                "jitter_ms": 1.0,
                "is_success": 1 if i < 57 else 0,  # 3 failures = 5% loss
                "error_message": None if i < 57 else "Request timed out",
            }
        )
    insert_ping_results(tmp_db_path, rows)

    aggregate_old_data(tmp_db_path)

    conn = sqlite3.connect(tmp_db_path)
    conn.row_factory = sqlite3.Row
    # Raw rows older than 48h should be deleted
    raw_count = conn.execute(
        "SELECT COUNT(*) as c FROM ping_results WHERE timestamp < ?",
        (time.time() - 48 * 3600,),
    ).fetchone()["c"]
    assert raw_count == 0

    # Aggregated rows should exist
    agg_rows = conn.execute("SELECT * FROM ping_results_aggregated").fetchall()
    assert len(agg_rows) >= 1
    agg = dict(agg_rows[0])
    assert agg["target"] == "1.1.1.1"
    assert agg["avg_rtt_ms"] is not None
    assert agg["packet_loss_pct"] == pytest.approx(5.0, abs=1.0)
    conn.close()


def test_cleanup_old_data(db_connection, tmp_db_path):
    """Data older than 30 days should be deleted from all tables."""
    old_time = time.time() - (31 * 24 * 3600)  # 31 days ago
    insert_ping_results(
        tmp_db_path,
        [
            {
                "timestamp": old_time,
                "target": "1.1.1.1",
                "target_name": "Cloudflare",
                "rtt_ms": 10.0,
                "jitter_ms": 1.0,
                "is_success": 1,
                "error_message": None,
            }
        ],
    )
    insert_dns_check(tmp_db_path, old_time, 10.0, True, None)
    insert_http_check(tmp_db_path, old_time, 50.0, 200, True, None)

    cleanup_old_data(tmp_db_path)

    conn = sqlite3.connect(tmp_db_path)
    assert conn.execute("SELECT COUNT(*) FROM ping_results").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM dns_checks").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM http_checks").fetchone()[0] == 0
    conn.close()
```

- [ ] **Step 14: Run tests to verify they fail**

Run: `cd /Users/mike/Projects/network-monitor-pi && source venv/bin/activate && pytest tests/test_database.py::test_aggregate_old_data -v`
Expected: FAIL — `ImportError: cannot import name 'aggregate_old_data'`

- [ ] **Step 15: Implement aggregation and cleanup**

Append to `src/database.py`:

```python
def aggregate_old_data(db_path: str) -> None:
    """Aggregate ping data older than 48h into 1-minute buckets, then delete the raw rows."""
    cutoff = time.time() - (48 * 3600)
    conn = get_connection(db_path)

    # Aggregate into 1-minute windows
    conn.execute(
        """INSERT INTO ping_results_aggregated
           (timestamp, target, target_name, avg_rtt_ms, max_rtt_ms, packet_loss_pct, avg_jitter_ms)
           SELECT
               CAST(timestamp / 60 AS INTEGER) * 60 AS minute_ts,
               target,
               target_name,
               AVG(CASE WHEN is_success = 1 THEN rtt_ms END),
               MAX(CASE WHEN is_success = 1 THEN rtt_ms END),
               (100.0 * SUM(CASE WHEN is_success = 0 THEN 1 ELSE 0 END)) / COUNT(*),
               AVG(CASE WHEN is_success = 1 THEN jitter_ms END)
           FROM ping_results
           WHERE timestamp < ?
           GROUP BY minute_ts, target""",
        (cutoff,),
    )

    # Delete the raw rows that were aggregated
    conn.execute("DELETE FROM ping_results WHERE timestamp < ?", (cutoff,))
    conn.commit()
    conn.close()


def cleanup_old_data(db_path: str) -> None:
    """Delete all data older than 30 days from every table."""
    cutoff = time.time() - (30 * 24 * 3600)
    conn = get_connection(db_path)
    conn.execute("DELETE FROM ping_results WHERE timestamp < ?", (cutoff,))
    conn.execute("DELETE FROM ping_results_aggregated WHERE timestamp < ?", (cutoff,))
    conn.execute("DELETE FROM dns_checks WHERE timestamp < ?", (cutoff,))
    conn.execute("DELETE FROM http_checks WHERE timestamp < ?", (cutoff,))
    conn.execute("DELETE FROM speed_tests WHERE timestamp < ?", (cutoff,))
    conn.commit()
    conn.close()
```

- [ ] **Step 16: Run all database tests**

Run: `cd /Users/mike/Projects/network-monitor-pi && source venv/bin/activate && pytest tests/test_database.py -v`
Expected: 12 passed

- [ ] **Step 17: Commit**

```bash
git add src/database.py tests/test_database.py
git commit -m "feat: add database layer with schema, CRUD, outage detection, and aggregation"
```

---

## Task 3: Monitoring Engine (Ping, DNS, HTTP)

**Files:**
- Create: `src/monitor.py`
- Create: `tests/test_monitor.py`

- [ ] **Step 1: Write tests for ping execution**

Create `tests/test_monitor.py`:

```python
import time
from unittest.mock import MagicMock, patch

from src.monitor import execute_ping, classify_ping_error, check_dns, check_http


def _make_ping_host_result(is_alive, avg_rtt=10.0, jitter=1.0, packet_loss=0):
    """Helper to create a mock icmplib ping result."""
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/mike/Projects/network-monitor-pi && source venv/bin/activate && pytest tests/test_monitor.py::test_execute_ping_success -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.monitor'`

- [ ] **Step 3: Implement ping execution**

Create `src/monitor.py`:

```python
import socket
import time
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

from icmplib import ping, NameLookupError, SocketPermissionError, ICMPLibError

from src.config import (
    PING_TIMEOUT_SECONDS,
    PING_COUNT,
    DNS_CHECK_HOSTNAME,
    HTTP_CHECK_URL,
    HTTP_CHECK_TIMEOUT_SECONDS,
)


def execute_ping(target: str, target_name: str) -> dict:
    """Ping a single target and return a result dict ready for database insertion."""
    timestamp = time.time()
    try:
        result = ping(
            target, count=PING_COUNT, timeout=PING_TIMEOUT_SECONDS, privileged=False
        )
        if result.is_alive:
            return {
                "timestamp": timestamp,
                "target": target,
                "target_name": target_name,
                "rtt_ms": round(result.avg_rtt, 2),
                "jitter_ms": round(result.jitter, 2),
                "is_success": 1,
                "error_message": None,
            }
        else:
            return {
                "timestamp": timestamp,
                "target": target,
                "target_name": target_name,
                "rtt_ms": None,
                "jitter_ms": None,
                "is_success": 0,
                "error_message": classify_ping_error(result),
            }
    except OSError as e:
        return {
            "timestamp": timestamp,
            "target": target,
            "target_name": target_name,
            "rtt_ms": None,
            "jitter_ms": None,
            "is_success": 0,
            "error_message": f"General failure: {e}",
        }
    except ICMPLibError as e:
        return {
            "timestamp": timestamp,
            "target": target,
            "target_name": target_name,
            "rtt_ms": None,
            "jitter_ms": None,
            "is_success": 0,
            "error_message": f"General failure: {e}",
        }


def classify_ping_error(result) -> str:
    """Convert an icmplib failed ping result into a human-readable error message."""
    # icmplib doesn't differentiate error types in unprivileged mode,
    # so we default to "Request timed out" for unreachable hosts.
    return "Request timed out"


def check_dns() -> dict:
    """Resolve a hostname and measure the time taken."""
    timestamp = time.time()
    try:
        start = time.perf_counter()
        socket.getaddrinfo(DNS_CHECK_HOSTNAME, 80)
        elapsed_ms = (time.perf_counter() - start) * 1000
        return {
            "timestamp": timestamp,
            "resolution_ms": round(elapsed_ms, 2),
            "is_success": True,
            "error_message": None,
        }
    except socket.gaierror as e:
        return {
            "timestamp": timestamp,
            "resolution_ms": None,
            "is_success": False,
            "error_message": f"DNS resolution failed: {e}",
        }


def check_http() -> dict:
    """Make an HTTP HEAD request and measure the response time."""
    timestamp = time.time()
    try:
        req = Request(HTTP_CHECK_URL, method="HEAD")
        start = time.perf_counter()
        response = urlopen(req, timeout=HTTP_CHECK_TIMEOUT_SECONDS)
        elapsed_ms = (time.perf_counter() - start) * 1000
        return {
            "timestamp": timestamp,
            "response_ms": round(elapsed_ms, 2),
            "status_code": response.status,
            "is_success": True,
            "error_message": None,
        }
    except HTTPError as e:
        return {
            "timestamp": timestamp,
            "response_ms": None,
            "status_code": e.code,
            "is_success": False,
            "error_message": f"HTTP error: {e.code} {e.reason}",
        }
    except (URLError, OSError) as e:
        return {
            "timestamp": timestamp,
            "response_ms": None,
            "status_code": None,
            "is_success": False,
            "error_message": f"HTTP request failed: {e}",
        }
```

- [ ] **Step 4: Run ping tests**

Run: `cd /Users/mike/Projects/network-monitor-pi && source venv/bin/activate && pytest tests/test_monitor.py -v -k ping`
Expected: 3 passed

- [ ] **Step 5: Write tests for DNS and HTTP checks**

Append to `tests/test_monitor.py`:

```python
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
```

Add the import at the top of the test file:

```python
from urllib.error import URLError
```

- [ ] **Step 6: Run all monitor tests**

Run: `cd /Users/mike/Projects/network-monitor-pi && source venv/bin/activate && pytest tests/test_monitor.py -v`
Expected: 7 passed

- [ ] **Step 7: Commit**

```bash
git add src/monitor.py tests/test_monitor.py
git commit -m "feat: add monitoring engine with ping, DNS, and HTTP checks"
```

---

## Task 4: Speed Test Runner

**Files:**
- Create: `src/speedtest_runner.py`
- Create: `tests/test_speedtest.py`

- [ ] **Step 1: Write tests for speed test execution**

Create `tests/test_speedtest.py`:

```python
import json
from unittest.mock import patch, MagicMock

from src.speedtest_runner import run_speed_test


@patch("src.speedtest_runner.subprocess.run")
def test_run_speed_test_success(mock_run):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps(
            {
                "download": 100_000_000,  # 100 Mbps in bits/s
                "upload": 25_000_000,
                "ping": 15.2,
                "server": {"sponsor": "TestISP", "name": "CityName"},
            }
        ),
    )

    result = run_speed_test()

    assert result is not None
    assert result["download_mbps"] == 100.0
    assert result["upload_mbps"] == 25.0
    assert result["ping_ms"] == 15.2
    assert "TestISP" in result["server_name"]


@patch("src.speedtest_runner.subprocess.run")
def test_run_speed_test_failure(mock_run):
    mock_run.side_effect = Exception("speedtest-cli not found")

    result = run_speed_test()

    assert result is None


@patch("src.speedtest_runner.subprocess.run")
def test_run_speed_test_bad_json(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="not json")

    result = run_speed_test()

    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/mike/Projects/network-monitor-pi && source venv/bin/activate && pytest tests/test_speedtest.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.speedtest_runner'`

- [ ] **Step 3: Implement speed test runner**

Create `src/speedtest_runner.py`:

```python
import json
import logging
import subprocess
import time

logger = logging.getLogger(__name__)


def run_speed_test() -> dict | None:
    """Run a speed test using speedtest-cli and return results.

    Returns a dict with download_mbps, upload_mbps, ping_ms, server_name,
    and timestamp. Returns None if the test fails.
    """
    try:
        result = subprocess.run(
            ["speedtest-cli", "--json"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        data = json.loads(result.stdout)
        return {
            "timestamp": time.time(),
            "download_mbps": round(data["download"] / 1_000_000, 2),
            "upload_mbps": round(data["upload"] / 1_000_000, 2),
            "ping_ms": data["ping"],
            "server_name": f"{data['server']['sponsor']} ({data['server']['name']})",
        }
    except (json.JSONDecodeError, KeyError, subprocess.TimeoutExpired) as e:
        logger.error("Speed test failed to parse: %s", e)
        return None
    except Exception as e:
        logger.error("Speed test failed: %s", e)
        return None
```

- [ ] **Step 4: Run speed test tests**

Run: `cd /Users/mike/Projects/network-monitor-pi && source venv/bin/activate && pytest tests/test_speedtest.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/speedtest_runner.py tests/test_speedtest.py
git commit -m "feat: add speed test runner with speedtest-cli integration"
```

---

## Task 5: Background Scheduler

**Files:**
- Create: `src/scheduler.py`

This module ties together the monitoring engine, database buffer, speed test, and cleanup jobs into background threads that the Flask app starts.

- [ ] **Step 1: Implement the scheduler**

Create `src/scheduler.py`:

```python
import logging
import threading
import time
from datetime import datetime

from src.config import (
    PING_INTERVAL_SECONDS,
    DNS_CHECK_INTERVAL_SECONDS,
    HTTP_CHECK_INTERVAL_SECONDS,
    BUFFER_FLUSH_INTERVAL_SECONDS,
    SPEED_TEST_HOUR,
    SPEED_TEST_MINUTE,
    CLEANUP_HOUR,
    CLEANUP_MINUTE,
    EXTERNAL_TARGETS,
    detect_gateway,
)
from src.database import (
    init_db,
    insert_ping_results,
    insert_dns_check,
    insert_http_check,
    insert_speed_test,
    aggregate_old_data,
    cleanup_old_data,
)
from src.monitor import execute_ping, check_dns, check_http
from src.speedtest_runner import run_speed_test

logger = logging.getLogger(__name__)


class MonitorScheduler:
    """Manages all background monitoring threads."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._stop_event = threading.Event()
        self._ping_buffer: list[dict] = []
        self._buffer_lock = threading.Lock()
        self._threads: list[threading.Thread] = []
        self._gateway: str | None = None

    def start(self) -> None:
        """Initialize the database and start all monitoring threads."""
        init_db(self.db_path)

        # Detect gateway
        self._gateway = detect_gateway()
        if self._gateway:
            logger.info("Detected gateway: %s", self._gateway)
        else:
            logger.warning("Could not detect gateway — only monitoring external targets")

        threads_to_start = [
            ("ping_loop", self._ping_loop),
            ("dns_loop", self._dns_loop),
            ("http_loop", self._http_loop),
            ("buffer_flush_loop", self._buffer_flush_loop),
            ("daily_jobs_loop", self._daily_jobs_loop),
        ]
        for name, target in threads_to_start:
            t = threading.Thread(target=target, name=name, daemon=True)
            t.start()
            self._threads.append(t)

        logger.info("Monitor scheduler started with %d threads", len(self._threads))

    def stop(self) -> None:
        """Signal all threads to stop."""
        self._stop_event.set()
        # Flush any remaining buffered data
        self._flush_buffer()
        logger.info("Monitor scheduler stopped")

    def get_targets(self) -> list[dict]:
        """Return the list of targets being monitored."""
        targets = []
        if self._gateway:
            targets.append({"ip": self._gateway, "name": "Gateway"})
        targets.extend(EXTERNAL_TARGETS)
        return targets

    def _ping_loop(self) -> None:
        """Ping all targets every PING_INTERVAL_SECONDS."""
        while not self._stop_event.is_set():
            targets = self.get_targets()
            for t in targets:
                if self._stop_event.is_set():
                    return
                result = execute_ping(t["ip"], t["name"])
                with self._buffer_lock:
                    self._ping_buffer.append(result)
            self._stop_event.wait(PING_INTERVAL_SECONDS)

    def _dns_loop(self) -> None:
        """Run DNS checks every DNS_CHECK_INTERVAL_SECONDS."""
        while not self._stop_event.is_set():
            result = check_dns()
            insert_dns_check(
                self.db_path,
                result["timestamp"],
                result["resolution_ms"],
                result["is_success"],
                result["error_message"],
            )
            self._stop_event.wait(DNS_CHECK_INTERVAL_SECONDS)

    def _http_loop(self) -> None:
        """Run HTTP checks every HTTP_CHECK_INTERVAL_SECONDS."""
        while not self._stop_event.is_set():
            result = check_http()
            insert_http_check(
                self.db_path,
                result["timestamp"],
                result["response_ms"],
                result.get("status_code"),
                result["is_success"],
                result["error_message"],
            )
            self._stop_event.wait(HTTP_CHECK_INTERVAL_SECONDS)

    def _buffer_flush_loop(self) -> None:
        """Flush the ping buffer to the database every BUFFER_FLUSH_INTERVAL_SECONDS."""
        while not self._stop_event.is_set():
            self._stop_event.wait(BUFFER_FLUSH_INTERVAL_SECONDS)
            self._flush_buffer()

    def _flush_buffer(self) -> None:
        """Write all buffered ping results to the database."""
        with self._buffer_lock:
            if not self._ping_buffer:
                return
            rows = list(self._ping_buffer)
            self._ping_buffer.clear()
        try:
            insert_ping_results(self.db_path, rows)
            logger.debug("Flushed %d ping results to database", len(rows))
        except Exception as e:
            logger.error("Failed to flush ping buffer: %s", e)

    def _daily_jobs_loop(self) -> None:
        """Run speed test and cleanup at scheduled times."""
        last_speed_test_date = None
        last_cleanup_date = None

        while not self._stop_event.is_set():
            now = datetime.now()
            today = now.date()

            # Speed test at 1:00 AM
            if (
                now.hour == SPEED_TEST_HOUR
                and now.minute == SPEED_TEST_MINUTE
                and last_speed_test_date != today
            ):
                logger.info("Running nightly speed test")
                result = run_speed_test()
                if result:
                    insert_speed_test(
                        self.db_path,
                        result["timestamp"],
                        result["download_mbps"],
                        result["upload_mbps"],
                        result["ping_ms"],
                        result["server_name"],
                    )
                    logger.info(
                        "Speed test complete: %.1f↓ / %.1f↑ Mbps",
                        result["download_mbps"],
                        result["upload_mbps"],
                    )
                else:
                    logger.error("Speed test failed")
                last_speed_test_date = today

            # Aggregation + cleanup at 1:15 AM
            if (
                now.hour == CLEANUP_HOUR
                and now.minute == CLEANUP_MINUTE
                and last_cleanup_date != today
            ):
                logger.info("Running nightly aggregation and cleanup")
                try:
                    aggregate_old_data(self.db_path)
                    cleanup_old_data(self.db_path)
                    logger.info("Aggregation and cleanup complete")
                except Exception as e:
                    logger.error("Aggregation/cleanup failed: %s", e)
                last_cleanup_date = today

            # Check every 30 seconds
            self._stop_event.wait(30)
```

- [ ] **Step 2: Verify all tests still pass**

Run: `cd /Users/mike/Projects/network-monitor-pi && source venv/bin/activate && pytest -v`
Expected: All existing tests pass (no regressions)

- [ ] **Step 3: Commit**

```bash
git add src/scheduler.py
git commit -m "feat: add background scheduler for ping/DNS/HTTP loops, speed test, and cleanup"
```

---

## Task 6: Flask App and API Endpoints

**Files:**
- Create: `src/web.py`
- Create: `tests/test_web.py`

- [ ] **Step 1: Write tests for API endpoints**

Create `tests/test_web.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/mike/Projects/network-monitor-pi && source venv/bin/activate && pytest tests/test_web.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.web'`

- [ ] **Step 3: Implement Flask app**

Create `src/web.py`:

```python
import logging
import os

from flask import Flask, jsonify, render_template, request

from src.config import DB_PATH
from src.database import (
    get_latest_pings,
    get_ping_timeline,
    get_outages,
    get_dns_checks,
    get_http_checks,
    get_speed_tests,
)

logger = logging.getLogger(__name__)

scheduler = None

VALID_RANGES = {"24h": 24, "7d": 168, "30d": 720}


def get_db_path() -> str:
    """Return the database path, allowing override for testing."""
    return DB_PATH


def create_app(start_scheduler: bool = True) -> Flask:
    """Application factory for the Flask web server."""
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), "..", "templates"),
        static_folder=os.path.join(os.path.dirname(__file__), "..", "static"),
    )

    if start_scheduler:
        global scheduler
        from src.scheduler import MonitorScheduler

        scheduler = MonitorScheduler(get_db_path())
        scheduler.start()

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/status")
    def api_status():
        db_path = get_db_path()
        targets = get_latest_pings(db_path)
        dns = get_dns_checks(db_path, limit=1)
        http = get_http_checks(db_path, limit=1)
        return jsonify(
            {
                "targets": targets,
                "dns": dns[0] if dns else None,
                "http": http[0] if http else None,
            }
        )

    @app.route("/api/timeline")
    def api_timeline():
        db_path = get_db_path()
        range_param = request.args.get("range", "24h")
        target = request.args.get("target")

        if range_param not in VALID_RANGES:
            return jsonify({"error": f"Invalid range. Use: {list(VALID_RANGES.keys())}"}), 400

        hours = VALID_RANGES[range_param]
        data = get_ping_timeline(db_path, hours=hours, target=target or None)
        return jsonify(data)

    @app.route("/api/outages")
    def api_outages():
        db_path = get_db_path()
        page = request.args.get("page", 1, type=int)
        limit = request.args.get("limit", 50, type=int)
        hours = request.args.get("hours", 720, type=int)  # default 30 days
        data = get_outages(db_path, hours=hours, page=page, limit=limit)
        return jsonify(data)

    @app.route("/api/speedtests")
    def api_speedtests():
        db_path = get_db_path()
        data = get_speed_tests(db_path)
        return jsonify(data)

    return app


# Gunicorn entry point
app = create_app(start_scheduler=os.environ.get("MONITOR_NO_SCHEDULER") != "1")
```

- [ ] **Step 4: Create a minimal index.html template so tests pass**

Create `templates/index.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Network Monitor</title>
</head>
<body>
    <h1>Network Monitor</h1>
    <p>Dashboard placeholder — will be built in Task 7.</p>
</body>
</html>
```

- [ ] **Step 5: Run web tests**

Run: `cd /Users/mike/Projects/network-monitor-pi && MONITOR_NO_SCHEDULER=1 source venv/bin/activate && pytest tests/test_web.py -v`
Expected: 6 passed

- [ ] **Step 6: Run all tests to check for regressions**

Run: `cd /Users/mike/Projects/network-monitor-pi && source venv/bin/activate && MONITOR_NO_SCHEDULER=1 pytest -v`
Expected: All tests pass

- [ ] **Step 7: Commit**

```bash
git add src/web.py tests/test_web.py templates/index.html
git commit -m "feat: add Flask app with API endpoints for status, timeline, outages, and speed tests"
```

---

## Task 7: Frontend Dashboard

**Files:**
- Create: `static/css/style.css`
- Create: `static/js/app.js`
- Download: `static/js/uplot.min.js` and `static/js/uplot.min.css`
- Modify: `templates/index.html`

- [ ] **Step 1: Download uPlot**

```bash
cd /Users/mike/Projects/network-monitor-pi
mkdir -p static/js static/css
curl -sL "https://unpkg.com/uplot@1.6.31/dist/uPlot.iife.min.js" -o static/js/uplot.min.js
curl -sL "https://unpkg.com/uplot@1.6.31/dist/uPlot.min.css" -o static/js/uplot.min.css
```

- [ ] **Step 2: Create the CSS stylesheet**

Create `static/css/style.css`:

```css
/* --- Reset & Base --- */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
    --bg-primary: #0f1117;
    --bg-secondary: #1a1d27;
    --bg-card: #222533;
    --text-primary: #e4e6f0;
    --text-secondary: #8b8fa3;
    --accent: #4c8bfa;
    --green: #34d399;
    --yellow: #fbbf24;
    --red: #f87171;
    --border: #2d3044;
    --radius: 8px;
    --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    --mono: "SF Mono", "Fira Code", "Fira Mono", monospace;
}

body {
    font-family: var(--font);
    background: var(--bg-primary);
    color: var(--text-primary);
    line-height: 1.5;
    min-height: 100vh;
}

/* --- Navigation --- */
nav {
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border);
    padding: 0 1rem;
    display: flex;
    align-items: center;
    gap: 0;
    position: sticky;
    top: 0;
    z-index: 100;
}

nav .logo {
    font-weight: 700;
    font-size: 1rem;
    padding: 0.75rem 1rem 0.75rem 0;
    border-right: 1px solid var(--border);
    margin-right: 0.5rem;
    white-space: nowrap;
}

nav button {
    background: none;
    border: none;
    color: var(--text-secondary);
    padding: 0.75rem 1rem;
    font-size: 0.875rem;
    cursor: pointer;
    border-bottom: 2px solid transparent;
    transition: color 0.2s, border-color 0.2s;
    font-family: var(--font);
}

nav button:hover { color: var(--text-primary); }
nav button.active {
    color: var(--accent);
    border-bottom-color: var(--accent);
}

/* --- Main Content --- */
main {
    max-width: 1200px;
    margin: 0 auto;
    padding: 1.5rem;
}

.page { display: none; }
.page.active { display: block; }

/* --- Banner --- */
.status-banner {
    padding: 1.25rem 1.5rem;
    border-radius: var(--radius);
    margin-bottom: 1.5rem;
    font-size: 1.1rem;
    font-weight: 600;
}

.status-banner.up { background: rgba(52, 211, 153, 0.1); border: 1px solid var(--green); color: var(--green); }
.status-banner.down { background: rgba(248, 113, 113, 0.1); border: 1px solid var(--red); color: var(--red); }

/* --- Cards Grid --- */
.cards {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: 1rem;
    margin-bottom: 1.5rem;
}

.card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1rem 1.25rem;
}

.card .label {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-secondary);
    margin-bottom: 0.25rem;
}

.card .value {
    font-size: 1.5rem;
    font-weight: 700;
    font-family: var(--mono);
}

.card .meta {
    font-size: 0.8rem;
    color: var(--text-secondary);
    margin-top: 0.25rem;
}

/* --- Status Indicator --- */
.status-dot {
    display: inline-block;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    margin-right: 0.5rem;
    vertical-align: middle;
}

.status-dot.ok { background: var(--green); }
.status-dot.degraded { background: var(--yellow); }
.status-dot.down { background: var(--red); }

/* --- Range Selector --- */
.range-selector {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 1rem;
}

.range-selector button {
    background: var(--bg-card);
    border: 1px solid var(--border);
    color: var(--text-secondary);
    padding: 0.4rem 1rem;
    border-radius: var(--radius);
    cursor: pointer;
    font-size: 0.85rem;
    font-family: var(--font);
}

.range-selector button.active {
    background: var(--accent);
    color: white;
    border-color: var(--accent);
}

/* --- Chart Container --- */
.chart-container {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1rem;
    margin-bottom: 1.5rem;
    overflow-x: auto;
}

/* --- Tables --- */
table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.875rem;
}

th {
    text-align: left;
    padding: 0.75rem 1rem;
    border-bottom: 1px solid var(--border);
    color: var(--text-secondary);
    font-weight: 600;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

td {
    padding: 0.65rem 1rem;
    border-bottom: 1px solid var(--border);
}

tr:hover { background: rgba(255, 255, 255, 0.02); }

.table-container {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    overflow-x: auto;
}

/* --- Responsive --- */
@media (max-width: 640px) {
    nav { flex-wrap: wrap; }
    nav .logo { width: 100%; border-right: none; border-bottom: 1px solid var(--border); }
    main { padding: 1rem; }
    .cards { grid-template-columns: 1fr 1fr; }
}
```

- [ ] **Step 3: Create the full HTML template**

Replace `templates/index.html` with:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Network Monitor</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='js/uplot.min.css') }}">
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
</head>
<body>
    <nav>
        <span class="logo">Network Monitor</span>
        <button class="active" data-page="status">Live Status</button>
        <button data-page="timeline">Timeline</button>
        <button data-page="outages">Outage Log</button>
        <button data-page="speedtests">Speed Tests</button>
    </nav>

    <main>
        <!-- Live Status Page -->
        <div id="page-status" class="page active">
            <div id="status-banner" class="status-banner up">Loading...</div>
            <div id="target-cards" class="cards"></div>
            <div class="cards">
                <div class="card" id="dns-card">
                    <div class="label">DNS Resolution</div>
                    <div class="value" id="dns-value">--</div>
                    <div class="meta" id="dns-meta"></div>
                </div>
                <div class="card" id="http-card">
                    <div class="label">HTTP Reachability</div>
                    <div class="value" id="http-value">--</div>
                    <div class="meta" id="http-meta"></div>
                </div>
            </div>
        </div>

        <!-- Timeline Page -->
        <div id="page-timeline" class="page">
            <div class="range-selector">
                <button class="active" data-range="24h">24 Hours</button>
                <button data-range="7d">7 Days</button>
                <button data-range="30d">30 Days</button>
            </div>
            <div class="chart-container">
                <div id="latency-chart"></div>
            </div>
        </div>

        <!-- Outage Log Page -->
        <div id="page-outages" class="page">
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Start</th>
                            <th>End</th>
                            <th>Duration</th>
                            <th>Target</th>
                            <th>Error</th>
                        </tr>
                    </thead>
                    <tbody id="outage-table-body">
                    </tbody>
                </table>
            </div>
            <p id="outage-empty" style="display:none; text-align:center; padding:2rem; color:var(--text-secondary);">
                No outages detected. Your network is looking good!
            </p>
        </div>

        <!-- Speed Tests Page -->
        <div id="page-speedtests" class="page">
            <div class="chart-container">
                <div id="speed-chart"></div>
            </div>
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Download</th>
                            <th>Upload</th>
                            <th>Ping</th>
                            <th>Server</th>
                        </tr>
                    </thead>
                    <tbody id="speed-table-body">
                    </tbody>
                </table>
            </div>
        </div>
    </main>

    <script src="{{ url_for('static', filename='js/uplot.min.js') }}"></script>
    <script src="{{ url_for('static', filename='js/app.js') }}"></script>
</body>
</html>
```

- [ ] **Step 4: Create the JavaScript application**

Create `static/js/app.js`:

```javascript
// --- State ---
let currentPage = "status";
let currentRange = "24h";
let latencyPlot = null;
let speedPlot = null;
let statusInterval = null;

// --- Navigation ---
document.querySelectorAll("nav button").forEach((btn) => {
  btn.addEventListener("click", () => {
    switchPage(btn.dataset.page);
  });
});

function switchPage(page) {
  currentPage = page;
  document.querySelectorAll("nav button").forEach((b) => b.classList.remove("active"));
  document.querySelector(`nav button[data-page="${page}"]`).classList.add("active");
  document.querySelectorAll(".page").forEach((p) => p.classList.remove("active"));
  document.getElementById(`page-${page}`).classList.add("active");

  clearInterval(statusInterval);

  if (page === "status") {
    loadStatus();
    statusInterval = setInterval(loadStatus, 5000);
  } else if (page === "timeline") {
    loadTimeline(currentRange);
  } else if (page === "outages") {
    loadOutages();
  } else if (page === "speedtests") {
    loadSpeedTests();
  }
}

// --- Range Selector ---
document.querySelectorAll(".range-selector button").forEach((btn) => {
  btn.addEventListener("click", () => {
    currentRange = btn.dataset.range;
    document.querySelectorAll(".range-selector button").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    loadTimeline(currentRange);
  });
});

// --- Helpers ---
function formatMs(ms) {
  if (ms === null || ms === undefined) return "--";
  return ms < 1 ? "<1 ms" : ms.toFixed(1) + " ms";
}

function formatDuration(seconds) {
  if (seconds < 60) return Math.round(seconds) + "s";
  if (seconds < 3600) return Math.round(seconds / 60) + "m";
  const h = Math.floor(seconds / 3600);
  const m = Math.round((seconds % 3600) / 60);
  return h + "h " + m + "m";
}

function formatTime(ts) {
  return new Date(ts * 1000).toLocaleString();
}

function statusClass(target) {
  if (!target.is_success) return "down";
  if (target.rtt_ms > 200) return "degraded";
  return "ok";
}

// --- Live Status ---
async function loadStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    renderStatus(data);
  } catch (e) {
    console.error("Failed to load status:", e);
  }
}

function renderStatus(data) {
  const targets = data.targets || [];
  const allUp = targets.length > 0 && targets.every((t) => t.is_success);
  const banner = document.getElementById("status-banner");

  if (targets.length === 0) {
    banner.className = "status-banner down";
    banner.textContent = "No monitoring data yet — waiting for first results...";
  } else if (allUp) {
    banner.className = "status-banner up";
    banner.textContent = "All targets reachable";
  } else {
    const downTargets = targets.filter((t) => !t.is_success);
    banner.className = "status-banner down";
    banner.textContent = downTargets.map((t) => t.target_name).join(", ") + " unreachable";
  }

  const cardsEl = document.getElementById("target-cards");
  cardsEl.innerHTML = targets
    .map((t) => {
      const cls = statusClass(t);
      return `
      <div class="card">
        <div class="label"><span class="status-dot ${cls}"></span>${t.target_name}</div>
        <div class="value">${formatMs(t.rtt_ms)}</div>
        <div class="meta">
          ${t.is_success ? `Jitter: ${formatMs(t.jitter_ms)}` : t.error_message || "Unreachable"}
          <br>${t.target}
        </div>
      </div>`;
    })
    .join("");

  // DNS card
  const dns = data.dns;
  document.getElementById("dns-value").textContent = dns ? formatMs(dns.resolution_ms) : "--";
  document.getElementById("dns-meta").textContent = dns
    ? dns.is_success
      ? "Resolving google.com"
      : dns.error_message
    : "";

  // HTTP card
  const http = data.http;
  document.getElementById("http-value").textContent = http ? formatMs(http.response_ms) : "--";
  document.getElementById("http-meta").textContent = http
    ? http.is_success
      ? `Status ${http.status_code}`
      : http.error_message
    : "";
}

// --- Timeline ---
async function loadTimeline(range) {
  try {
    const res = await fetch(`/api/timeline?range=${range}`);
    const data = await res.json();
    renderTimeline(data);
  } catch (e) {
    console.error("Failed to load timeline:", e);
  }
}

function renderTimeline(data) {
  const container = document.getElementById("latency-chart");
  container.innerHTML = "";

  if (!data.length) {
    container.innerHTML = '<p style="text-align:center;padding:2rem;color:var(--text-secondary)">No data for this time range</p>';
    return;
  }

  // Group by target
  const targets = {};
  data.forEach((row) => {
    const name = row.target_name || row.target;
    if (!targets[name]) targets[name] = [];
    targets[name].push(row);
  });

  const targetNames = Object.keys(targets);
  // Build aligned timestamp array from first target
  const firstTarget = targets[targetNames[0]];
  const timestamps = firstTarget.map((r) => r.timestamp);

  const series = [{}]; // first entry is for x-axis labels
  const dataArrays = [timestamps];
  const colors = ["#4c8bfa", "#34d399", "#fbbf24", "#f87171"];

  targetNames.forEach((name, i) => {
    series.push({
      label: name,
      stroke: colors[i % colors.length],
      width: 1.5,
    });
    // Use avg_rtt_ms for aggregated data, rtt_ms for raw
    const values = targets[name].map((r) => r.avg_rtt_ms ?? r.rtt_ms ?? null);
    dataArrays.push(values);
  });

  const opts = {
    width: container.clientWidth - 20,
    height: 300,
    series: series,
    axes: [
      {},
      {
        label: "Latency (ms)",
        stroke: "var(--text-secondary)",
        grid: { stroke: "rgba(255,255,255,0.05)" },
      },
    ],
    scales: { x: { time: true } },
    cursor: { show: true },
  };

  if (latencyPlot) latencyPlot.destroy();
  latencyPlot = new uPlot(opts, dataArrays, container);
}

// --- Outage Log ---
async function loadOutages() {
  try {
    const res = await fetch("/api/outages?hours=720");
    const data = await res.json();
    renderOutages(data);
  } catch (e) {
    console.error("Failed to load outages:", e);
  }
}

function renderOutages(outages) {
  const tbody = document.getElementById("outage-table-body");
  const emptyMsg = document.getElementById("outage-empty");

  if (!outages.length) {
    tbody.innerHTML = "";
    emptyMsg.style.display = "block";
    return;
  }

  emptyMsg.style.display = "none";
  tbody.innerHTML = outages
    .map(
      (o) => `
    <tr>
      <td>${formatTime(o.start_time)}</td>
      <td>${formatTime(o.end_time)}</td>
      <td>${formatDuration(o.duration_seconds)}</td>
      <td>${o.target_name}</td>
      <td>${o.error_messages || "--"}</td>
    </tr>`
    )
    .join("");
}

// --- Speed Tests ---
async function loadSpeedTests() {
  try {
    const res = await fetch("/api/speedtests");
    const data = await res.json();
    renderSpeedTests(data);
  } catch (e) {
    console.error("Failed to load speed tests:", e);
  }
}

function renderSpeedTests(data) {
  // Table
  const tbody = document.getElementById("speed-table-body");
  tbody.innerHTML = data
    .map(
      (s) => `
    <tr>
      <td>${formatTime(s.timestamp)}</td>
      <td>${s.download_mbps.toFixed(1)} Mbps</td>
      <td>${s.upload_mbps.toFixed(1)} Mbps</td>
      <td>${s.ping_ms.toFixed(1)} ms</td>
      <td>${s.server_name}</td>
    </tr>`
    )
    .join("");

  // Chart
  const container = document.getElementById("speed-chart");
  container.innerHTML = "";

  if (!data.length) return;

  const reversed = [...data].reverse(); // oldest first
  const timestamps = reversed.map((s) => s.timestamp);
  const downloads = reversed.map((s) => s.download_mbps);
  const uploads = reversed.map((s) => s.upload_mbps);

  const opts = {
    width: container.clientWidth - 20,
    height: 250,
    series: [
      {},
      { label: "Download (Mbps)", stroke: "#4c8bfa", width: 2, fill: "rgba(76,139,250,0.1)" },
      { label: "Upload (Mbps)", stroke: "#34d399", width: 2, fill: "rgba(52,211,153,0.1)" },
    ],
    axes: [
      {},
      { label: "Speed (Mbps)", stroke: "var(--text-secondary)", grid: { stroke: "rgba(255,255,255,0.05)" } },
    ],
    scales: { x: { time: true } },
  };

  if (speedPlot) speedPlot.destroy();
  speedPlot = new uPlot(opts, [timestamps, downloads, uploads], container);
}

// --- Init ---
loadStatus();
statusInterval = setInterval(loadStatus, 5000);
```

- [ ] **Step 5: Verify the frontend loads without errors**

Run: `cd /Users/mike/Projects/network-monitor-pi && source venv/bin/activate && MONITOR_NO_SCHEDULER=1 pytest tests/test_web.py::test_index_page -v`
Expected: PASS

- [ ] **Step 6: Run all tests**

Run: `cd /Users/mike/Projects/network-monitor-pi && source venv/bin/activate && MONITOR_NO_SCHEDULER=1 pytest -v`
Expected: All tests pass

- [ ] **Step 7: Commit**

```bash
git add static/ templates/index.html
git commit -m "feat: add web dashboard with dark theme, live status, timeline, outage log, and speed test views"
```

---

## Task 8: Deployment Files

**Files:**
- Create: `network-monitor.service`
- Create: `setup.sh`
- Create: `README.md`

- [ ] **Step 1: Create systemd service file**

Create `network-monitor.service`:

```ini
[Unit]
Description=Network Monitor
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=networkmon
Group=networkmon
WorkingDirectory=/opt/network-monitor
ExecStart=/opt/network-monitor/venv/bin/gunicorn -w 1 -b 0.0.0.0:5000 src.web:app
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: Create setup script**

Create `setup.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Network Monitor - Raspberry Pi Setup Script
# Run as root: sudo bash setup.sh

INSTALL_DIR="/opt/network-monitor"
SERVICE_NAME="network-monitor"
SERVICE_USER="networkmon"

echo "=== Network Monitor Setup ==="

# Check for root
if [[ $EUID -ne 0 ]]; then
    echo "Error: This script must be run as root (sudo bash setup.sh)"
    exit 1
fi

# Create system user
if ! id "$SERVICE_USER" &>/dev/null; then
    echo "Creating system user: $SERVICE_USER"
    useradd --system --no-create-home --shell /usr/sbin/nologin "$SERVICE_USER"
fi

# Create install directory
echo "Setting up $INSTALL_DIR"
mkdir -p "$INSTALL_DIR/data"

# Copy application files
cp -r src static templates requirements.txt "$INSTALL_DIR/"
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"

# Create virtual environment
echo "Creating Python virtual environment"
python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"

# Set raw socket capability for ICMP pings without root
echo "Setting network capabilities"
PYTHON_BIN="$INSTALL_DIR/venv/bin/python3"
# Resolve symlink to actual binary
PYTHON_REAL=$(readlink -f "$PYTHON_BIN")
setcap cap_net_raw+ep "$PYTHON_REAL"

# Install systemd service
echo "Installing systemd service"
cp network-monitor.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl start "$SERVICE_NAME"

echo ""
echo "=== Setup Complete ==="
echo "Service status: systemctl status $SERVICE_NAME"
echo "View logs:      journalctl -u $SERVICE_NAME -f"
echo "Dashboard:      http://$(hostname -I | awk '{print $1}'):5000"
```

- [ ] **Step 3: Create README**

Create `README.md`:

```markdown
# Network Monitor for Raspberry Pi

A lightweight, always-on network monitor that tracks packet loss, disconnects, latency, jitter, DNS/HTTP health, and nightly speed tests. View everything via a web dashboard from any device on your network.

## Features

- **Ping monitoring** — Pings gateway + 3 external DNS servers every second
- **DNS & HTTP checks** — Tests DNS resolution and HTTP reachability every 60 seconds
- **Nightly speed tests** — Runs at 1:00 AM via speedtest-cli
- **Outage detection** — Logs outages with start/end times, duration, and error messages
- **Web dashboard** — Dark-themed, responsive, works on phone/tablet/desktop
- **Auto-start** — Runs as a systemd service, survives reboots
- **Low resource** — ~50 MB RAM, ~50-80 MB storage for 30 days of data

## Requirements

- Raspberry Pi 3 (or newer) with Raspberry Pi OS Lite (64-bit)
- Ethernet connection to your router
- Python 3.11+

## Quick Setup

1. **Flash Raspberry Pi OS Lite (64-bit)** using [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
   - Set hostname to `networkmon`
   - Enable SSH
   - Set username and password
   - Set timezone

2. **Connect Pi via ethernet** and SSH in:
   ```bash
   ssh your-user@networkmon.local
   ```

3. **Update the system:**
   ```bash
   sudo apt update && sudo apt upgrade -y
   sudo apt install -y python3-venv git
   ```

4. **Clone and install:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/network-monitor-pi.git
   cd network-monitor-pi
   sudo bash setup.sh
   ```

5. **Open the dashboard** at `http://networkmon.local:5000`

## Managing the Service

```bash
# Check status
sudo systemctl status network-monitor

# View live logs
sudo journalctl -u network-monitor -f

# Restart
sudo systemctl restart network-monitor

# Stop
sudo systemctl stop network-monitor
```

## Updating

```bash
cd /path/to/network-monitor-pi
git pull
sudo bash setup.sh
```

## Development

```bash
# Set up dev environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt

# Run tests
pytest -v

# Run locally (monitoring requires cap_net_raw or root)
MONITOR_NO_SCHEDULER=1 flask --app src.web run --debug
```

## Architecture

Single Python process: Flask serves the web dashboard while a background thread handles all monitoring. Results buffer in memory and flush to SQLite every 30 seconds.

```
Browser ──→ Flask (port 5000) ──→ SQLite ←── Monitor Thread
                                              ├── Ping (1s)
                                              ├── DNS (60s)
                                              ├── HTTP (60s)
                                              └── Speed Test (1AM)
```
```

- [ ] **Step 4: Commit**

```bash
git add network-monitor.service setup.sh README.md
git commit -m "feat: add deployment files — systemd service, setup script, and README"
```

---

## Task 9: Integration Smoke Test

**Files:** None (testing only)

- [ ] **Step 1: Run the full test suite**

```bash
cd /Users/mike/Projects/network-monitor-pi
source venv/bin/activate
MONITOR_NO_SCHEDULER=1 pytest -v
```

Expected: All tests pass.

- [ ] **Step 2: Start the app locally (without monitoring)**

```bash
cd /Users/mike/Projects/network-monitor-pi
source venv/bin/activate
MONITOR_NO_SCHEDULER=1 flask --app src.web run --port 5000 --debug
```

Then open `http://localhost:5000` in a browser. Verify:
- Page loads with dark theme
- Navigation tabs work (Status, Timeline, Outage Log, Speed Tests)
- API calls work (check browser dev console for errors)
- Status page shows "No monitoring data yet"

- [ ] **Step 3: Stop the local server (Ctrl+C)**

- [ ] **Step 4: Final commit with any fixes**

If any issues were found in step 2, fix them and commit:

```bash
git add -A
git commit -m "fix: resolve integration issues found during smoke test"
```

If no issues, skip this step.

---

## Self-Review Checklist

### Spec Coverage
- [x] Ping 4 targets every 1 second — Task 3 + Task 5
- [x] DNS resolution check every 60s — Task 3 + Task 5
- [x] HTTP reachability check every 60s — Task 3 + Task 5
- [x] Speed test at 1 AM — Task 4 + Task 5
- [x] Error messages matching ping output — Task 3 (classify_ping_error)
- [x] In-memory buffer, flush every 30s — Task 5 (MonitorScheduler)
- [x] SQLite with WAL mode — Task 2
- [x] All 5 database tables + aggregation table — Task 2
- [x] Data aggregation (48h raw, then 1-min averages) — Task 2
- [x] 30-day cleanup — Task 2
- [x] Live Status page with banner, cards, DNS, HTTP — Task 7
- [x] Timeline with uPlot, range selector — Task 7
- [x] Outage log with table — Task 7
- [x] Speed test history with chart and table — Task 7
- [x] Auto-start on boot via systemd — Task 8
- [x] SSH-based remote access documented — Task 8 (README)
- [x] Setup script for Pi deployment — Task 8
- [x] Gateway auto-detection — Task 1 (config.py)

### Placeholder Scan
- No TBD, TODO, or "implement later" found
- All code blocks contain complete implementations
- All test steps include exact commands and expected output

### Type Consistency
- `execute_ping()` returns dict with `timestamp, target, target_name, rtt_ms, jitter_ms, is_success, error_message` — matches `insert_ping_results` schema
- `check_dns()` returns dict with `timestamp, resolution_ms, is_success, error_message` — matches `insert_dns_check` params
- `check_http()` returns dict with `timestamp, response_ms, status_code, is_success, error_message` — matches `insert_http_check` params
- `run_speed_test()` returns dict with `timestamp, download_mbps, upload_mbps, ping_ms, server_name` — matches `insert_speed_test` params
- API endpoints return JSON matching what `app.js` expects
