import math
import os
import sqlite3
import threading
import time
from typing import Any, List, Optional


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


def insert_ping_results(db_path: str, rows: List[dict]) -> None:
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


def insert_dns_check(db_path: str, timestamp: float, resolution_ms: Optional[float], is_success: bool, error_message: Optional[str]) -> None:
    conn = get_connection(db_path)
    conn.execute("INSERT INTO dns_checks (timestamp, resolution_ms, is_success, error_message) VALUES (?, ?, ?, ?)",
        (timestamp, resolution_ms, int(is_success), error_message))
    conn.commit()
    conn.close()


def insert_http_check(db_path: str, timestamp: float, response_ms: Optional[float], status_code: Optional[int], is_success: bool, error_message: Optional[str]) -> None:
    conn = get_connection(db_path)
    conn.execute("INSERT INTO http_checks (timestamp, response_ms, status_code, is_success, error_message) VALUES (?, ?, ?, ?, ?)",
        (timestamp, response_ms, status_code, int(is_success), error_message))
    conn.commit()
    conn.close()


def insert_speed_test(db_path: str, timestamp: float, download_mbps: float, upload_mbps: float, ping_ms: float, server_name: str) -> None:
    conn = get_connection(db_path)
    conn.execute("INSERT INTO speed_tests (timestamp, download_mbps, upload_mbps, ping_ms, server_name) VALUES (?, ?, ?, ?, ?)",
        (timestamp, download_mbps, upload_mbps, ping_ms, server_name))
    conn.commit()
    conn.close()


def get_latest_pings(db_path: str) -> List[dict]:
    conn = get_connection(db_path)
    cursor = conn.execute(
        """SELECT p.* FROM ping_results p
           INNER JOIN (
               SELECT target, MAX(timestamp) as max_ts
               FROM ping_results GROUP BY target
           ) latest ON p.target = latest.target AND p.timestamp = latest.max_ts
           ORDER BY p.target_name""")
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results


def get_ping_timeline(db_path: str, hours: int = 24, target: Optional[str] = None) -> List[dict]:
    cutoff = time.time() - (hours * 3600)
    conn = get_connection(db_path)
    if hours <= 48:
        sql = "SELECT * FROM ping_results WHERE timestamp >= ?"
        params: List[Any] = [cutoff]
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


def get_dns_checks(db_path: str, limit: int = 100) -> List[dict]:
    conn = get_connection(db_path)
    cursor = conn.execute("SELECT * FROM dns_checks ORDER BY timestamp DESC LIMIT ?", (limit,))
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results


def get_http_checks(db_path: str, limit: int = 100) -> List[dict]:
    conn = get_connection(db_path)
    cursor = conn.execute("SELECT * FROM http_checks ORDER BY timestamp DESC LIMIT ?", (limit,))
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results


def get_speed_tests(db_path: str) -> List[dict]:
    conn = get_connection(db_path)
    cursor = conn.execute("SELECT * FROM speed_tests ORDER BY timestamp DESC")
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results


def get_outages(db_path: str, hours: int = 24, page: int = 1, limit: int = 50) -> List[dict]:
    cutoff = time.time() - (hours * 3600)
    conn = get_connection(db_path)
    cursor = conn.execute(
        """SELECT timestamp, target, target_name, is_success, error_message
           FROM ping_results WHERE timestamp >= ?
           ORDER BY target, timestamp ASC""", (cutoff,))
    rows = cursor.fetchall()
    conn.close()

    outages: List[dict] = []
    current_target = None
    fail_run: List[dict] = []

    def _flush_run():
        if len(fail_run) >= 3:
            error_msgs = list(set(r["error_message"] for r in fail_run if r["error_message"]))
            outages.append({
                "target": fail_run[0]["target"],
                "target_name": fail_run[0]["target_name"],
                "start_time": fail_run[0]["timestamp"],
                "end_time": fail_run[-1]["timestamp"],
                "duration_seconds": fail_run[-1]["timestamp"] - fail_run[0]["timestamp"],
                "failed_count": len(fail_run),
                "error_messages": ", ".join(error_msgs) if error_msgs else None,
            })

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

    _flush_run()
    outages.sort(key=lambda o: o["start_time"], reverse=True)
    start = (page - 1) * limit
    return outages[start : start + limit]


def get_uptime_stats(db_path: str, hours: int) -> List[dict]:
    """Return per-target uptime percentage for the given time window."""
    cutoff = time.time() - (hours * 3600)
    conn = get_connection(db_path)

    if hours <= 48:
        cursor = conn.execute(
            """SELECT target, target_name,
                      COUNT(*) AS total,
                      SUM(is_success) AS successes,
                      ROUND(100.0 * SUM(is_success) / COUNT(*), 3) AS uptime_pct
               FROM ping_results WHERE timestamp >= ?
               GROUP BY target""",
            (cutoff,),
        )
        results = [dict(row) for row in cursor.fetchall()]
    else:
        # Blend raw (last 48h) + aggregated (remainder)
        raw_cutoff = time.time() - (48 * 3600)

        cursor = conn.execute(
            """SELECT target, target_name,
                      COUNT(*) AS total,
                      SUM(is_success) AS successes
               FROM ping_results WHERE timestamp >= ?
               GROUP BY target""",
            (raw_cutoff,),
        )
        raw_stats = {row["target"]: dict(row) for row in cursor.fetchall()}

        cursor = conn.execute(
            """SELECT target, target_name,
                      AVG(100.0 - packet_loss_pct) AS avg_uptime_pct,
                      COUNT(*) AS bucket_count
               FROM ping_results_aggregated
               WHERE timestamp >= ? AND timestamp < ?
               GROUP BY target""",
            (cutoff, raw_cutoff),
        )
        agg_stats = {row["target"]: dict(row) for row in cursor.fetchall()}

        all_targets = set(raw_stats.keys()) | set(agg_stats.keys())
        results = []
        for target in all_targets:
            raw = raw_stats.get(target, {})
            agg = agg_stats.get(target, {})
            raw_total = raw.get("total", 0)
            raw_successes = raw.get("successes", 0)
            agg_buckets = agg.get("bucket_count", 0)
            agg_uptime = agg.get("avg_uptime_pct", 0) or 0

            if raw_total + agg_buckets == 0:
                continue

            # Weight: each agg bucket represents ~3600 pings (1/sec for 1 hour)
            agg_weight = agg_buckets * 3600
            raw_uptime = (100.0 * raw_successes / raw_total) if raw_total else 0
            total_weight = raw_total + agg_weight
            blended = (raw_uptime * raw_total + agg_uptime * agg_weight) / total_weight

            results.append({
                "target": target,
                "target_name": raw.get("target_name") or agg.get("target_name", target),
                "uptime_pct": round(blended, 3),
                "total": raw_total + agg_weight,
                "successes": None,
            })

    conn.close()
    return results


def _percentile(sorted_values: List[float], p: float) -> Optional[float]:
    """Compute the p-th percentile from a pre-sorted list using linear interpolation."""
    if not sorted_values:
        return None
    k = (len(sorted_values) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return round(sorted_values[int(k)], 2)
    return round(sorted_values[f] * (c - k) + sorted_values[c] * (k - f), 2)


def get_latency_percentiles(db_path: str, hours: int = 24) -> List[dict]:
    """Return P50/P95/P99 latency per target from raw ping data.

    Only meaningful for hours <= 48 (raw data). Returns empty list for longer ranges.
    """
    if hours > 48:
        return []

    cutoff = time.time() - (hours * 3600)
    conn = get_connection(db_path)
    cursor = conn.execute(
        """SELECT target, target_name, rtt_ms
           FROM ping_results
           WHERE timestamp >= ? AND is_success = 1 AND rtt_ms IS NOT NULL
           ORDER BY target, rtt_ms ASC""",
        (cutoff,),
    )

    # Group pre-sorted RTT values by target
    by_target: dict[str, dict] = {}
    for row in cursor:
        t = row["target"]
        if t not in by_target:
            by_target[t] = {"target": t, "target_name": row["target_name"], "values": []}
        by_target[t]["values"].append(row["rtt_ms"])
    conn.close()

    results = []
    for info in by_target.values():
        vals = info["values"]
        results.append({
            "target": info["target"],
            "target_name": info["target_name"],
            "p50": _percentile(vals, 50),
            "p95": _percentile(vals, 95),
            "p99": _percentile(vals, 99),
            "sample_count": len(vals),
        })
    return results


def get_current_streak(db_path: str) -> List[dict]:
    """Return per-target count of consecutive recent successes."""
    conn = get_connection(db_path)
    cursor = conn.execute(
        """SELECT p.target, p.target_name, COUNT(*) AS streak
           FROM ping_results p
           LEFT JOIN (
               SELECT target, MAX(timestamp) AS last_fail_ts
               FROM ping_results WHERE is_success = 0
               GROUP BY target
           ) f ON p.target = f.target
           WHERE p.is_success = 1
             AND p.timestamp > COALESCE(f.last_fail_ts, 0)
           GROUP BY p.target"""
    )
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results


def get_error_log(db_path: str, hours: int = 24, page: int = 1, limit: int = 100) -> List[dict]:
    """Return recent errors across all check types in reverse chronological order."""
    cutoff = time.time() - (hours * 3600)
    offset = (page - 1) * limit
    conn = get_connection(db_path)
    cursor = conn.execute(
        """SELECT * FROM (
               SELECT timestamp, 'ping' AS check_type, target_name AS source, error_message
               FROM ping_results
               WHERE timestamp >= ? AND is_success = 0 AND error_message IS NOT NULL
               UNION ALL
               SELECT timestamp, 'dns' AS check_type, 'DNS' AS source, error_message
               FROM dns_checks
               WHERE timestamp >= ? AND is_success = 0 AND error_message IS NOT NULL
               UNION ALL
               SELECT timestamp, 'http' AS check_type, 'HTTP' AS source, error_message
               FROM http_checks
               WHERE timestamp >= ? AND is_success = 0 AND error_message IS NOT NULL
           ) ORDER BY timestamp DESC
           LIMIT ? OFFSET ?""",
        (cutoff, cutoff, cutoff, limit, offset),
    )
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results


def get_packet_loss_timeline(db_path: str, hours: int = 24, target: Optional[str] = None) -> List[dict]:
    """Return packet loss percentage over time, bucketed by 5 minutes (raw) or 1 hour (aggregated)."""
    cutoff = time.time() - (hours * 3600)
    conn = get_connection(db_path)

    if hours <= 48:
        sql = """SELECT CAST(timestamp / 300 AS INTEGER) * 300 AS bucket_ts,
                        target, target_name,
                        ROUND(100.0 * SUM(CASE WHEN is_success = 0 THEN 1 ELSE 0 END) / COUNT(*), 2) AS packet_loss_pct
                 FROM ping_results WHERE timestamp >= ?"""
        params: List[Any] = [cutoff]
        if target:
            sql += " AND target = ?"
            params.append(target)
        sql += " GROUP BY bucket_ts, target ORDER BY bucket_ts ASC"
        cursor = conn.execute(sql, params)
        results = [
            {"timestamp": row["bucket_ts"], "target": row["target"],
             "target_name": row["target_name"], "packet_loss_pct": row["packet_loss_pct"]}
            for row in cursor.fetchall()
        ]
    else:
        sql = """SELECT timestamp, target, target_name, packet_loss_pct
                 FROM ping_results_aggregated WHERE timestamp >= ?"""
        params = [cutoff]
        if target:
            sql += " AND target = ?"
            params.append(target)
        sql += " ORDER BY timestamp ASC"
        cursor = conn.execute(sql, params)
        results = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return results


def aggregate_old_data(db_path: str) -> None:
    cutoff = time.time() - (48 * 3600)
    conn = get_connection(db_path)
    conn.execute(
        """INSERT INTO ping_results_aggregated
           (timestamp, target, target_name, avg_rtt_ms, max_rtt_ms, packet_loss_pct, avg_jitter_ms)
           SELECT
               CAST(timestamp / 3600 AS INTEGER) * 3600 AS hour_ts,
               target, target_name,
               AVG(CASE WHEN is_success = 1 THEN rtt_ms END),
               MAX(CASE WHEN is_success = 1 THEN rtt_ms END),
               (100.0 * SUM(CASE WHEN is_success = 0 THEN 1 ELSE 0 END)) / COUNT(*),
               AVG(CASE WHEN is_success = 1 THEN jitter_ms END)
           FROM ping_results WHERE timestamp < ?
           GROUP BY hour_ts, target""", (cutoff,))
    conn.execute("DELETE FROM ping_results WHERE timestamp < ?", (cutoff,))
    conn.commit()
    conn.close()


def cleanup_old_data(db_path: str) -> None:
    cutoff = time.time() - (30 * 24 * 3600)
    conn = get_connection(db_path)
    conn.execute("DELETE FROM ping_results WHERE timestamp < ?", (cutoff,))
    conn.execute("DELETE FROM ping_results_aggregated WHERE timestamp < ?", (cutoff,))
    conn.execute("DELETE FROM dns_checks WHERE timestamp < ?", (cutoff,))
    conn.execute("DELETE FROM http_checks WHERE timestamp < ?", (cutoff,))
    conn.execute("DELETE FROM speed_tests WHERE timestamp < ?", (cutoff,))
    conn.commit()
    conn.close()
