import logging
import os
import subprocess
import threading
import time as _time

from flask import Flask, jsonify, render_template, request

from src.config import DB_PATH
from src.database import (
    get_latest_pings,
    get_ping_timeline,
    get_outages,
    get_dns_checks,
    get_http_checks,
    get_speed_tests,
    get_uptime_stats,
    get_current_streak,
    get_latency_percentiles,
    get_packet_loss_timeline,
    get_error_log,
    insert_speed_test,
)
from src.speedtest_runner import run_speed_test

logger = logging.getLogger(__name__)

scheduler = None

VALID_RANGES = {"24h": 24, "7d": 168, "30d": 720}

# Speed test trigger state (safe with single gunicorn worker)
_speed_test_lock = threading.Lock()
_speed_test_status = {"running": False, "last_run_time": 0.0, "result": None, "error": None}
SPEED_TEST_COOLDOWN = 300  # 5 minutes


def get_db_path() -> str:
    """Return the database path, allowing override for testing."""
    return DB_PATH


def _run_speed_test_background(db_path: str) -> None:
    """Run speed test in background thread, update shared state."""
    try:
        result = run_speed_test()
        if result:
            insert_speed_test(
                db_path,
                result["timestamp"],
                result["download_mbps"],
                result["upload_mbps"],
                result["ping_ms"],
                result["server_name"],
            )
            _speed_test_status["result"] = result
            _speed_test_status["error"] = None
            logger.info(
                "Manual speed test complete: %.1f↓ / %.1f↑ Mbps",
                result["download_mbps"],
                result["upload_mbps"],
            )
        else:
            _speed_test_status["result"] = None
            _speed_test_status["error"] = "Speed test returned no results"
            logger.error("Manual speed test failed")
    except Exception as e:
        _speed_test_status["result"] = None
        _speed_test_status["error"] = str(e)
        logger.error("Manual speed test error: %s", e)
    finally:
        _speed_test_status["running"] = False
        _speed_test_status["last_run_time"] = _time.time()


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

    @app.route("/api/health")
    def api_health():
        db_path = get_db_path()
        range_param = request.args.get("range", "24h")
        if range_param not in VALID_RANGES:
            return jsonify({"error": f"Invalid range. Use: {list(VALID_RANGES.keys())}"}), 400

        hours = VALID_RANGES[range_param]
        uptime = get_uptime_stats(db_path, hours=hours)
        streak = get_current_streak(db_path)
        percentiles = get_latency_percentiles(db_path, hours=hours)
        outages = get_outages(db_path, hours=hours)

        # Index streak and percentiles by target for merging
        streak_by_target = {s["target"]: s["streak"] for s in streak}
        pct_by_target = {p["target"]: p for p in percentiles}

        # Count outages per target
        outage_counts: dict = {}
        for o in outages:
            t = o["target"]
            outage_counts[t] = outage_counts.get(t, 0) + 1

        percentiles_available = hours <= 48
        targets = []
        for u in uptime:
            t = u["target"]
            pct = pct_by_target.get(t, {})
            targets.append({
                "target": t,
                "target_name": u["target_name"],
                "uptime_pct": u["uptime_pct"],
                "current_streak": streak_by_target.get(t, 0),
                "outage_count": outage_counts.get(t, 0),
                "p50": pct.get("p50"),
                "p95": pct.get("p95"),
                "p99": pct.get("p99"),
                "percentiles_available": percentiles_available,
            })

        return jsonify({"targets": targets})

    @app.route("/api/packet-loss")
    def api_packet_loss():
        db_path = get_db_path()
        range_param = request.args.get("range", "24h")
        target = request.args.get("target")
        if range_param not in VALID_RANGES:
            return jsonify({"error": f"Invalid range. Use: {list(VALID_RANGES.keys())}"}), 400

        hours = VALID_RANGES[range_param]
        data = get_packet_loss_timeline(db_path, hours=hours, target=target or None)
        return jsonify(data)

    @app.route("/api/errors")
    def api_errors():
        db_path = get_db_path()
        hours = request.args.get("hours", 24, type=int)
        page = request.args.get("page", 1, type=int)
        limit = request.args.get("limit", 100, type=int)
        data = get_error_log(db_path, hours=hours, page=page, limit=limit)
        return jsonify(data)

    @app.route("/api/logs")
    def api_logs():
        lines = request.args.get("lines", 100, type=int)
        lines = min(max(lines, 10), 1000)
        try:
            result = subprocess.run(
                ["journalctl", "-u", "network-monitor", "--no-pager", "-n", str(lines)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout, 200, {"Content-Type": "text/plain; charset=utf-8"}
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            return f"Failed to read logs: {e}", 500, {"Content-Type": "text/plain; charset=utf-8"}

    @app.route("/api/speedtest/run", methods=["POST"])
    def api_speedtest_run():
        if _speed_test_status["running"]:
            return jsonify({"error": "Speed test already running"}), 409

        elapsed = _time.time() - _speed_test_status["last_run_time"]
        if _speed_test_status["last_run_time"] > 0 and elapsed < SPEED_TEST_COOLDOWN:
            wait = int(SPEED_TEST_COOLDOWN - elapsed)
            return jsonify({"error": f"Please wait {wait}s before running another test"}), 429

        with _speed_test_lock:
            if _speed_test_status["running"]:
                return jsonify({"error": "Speed test already running"}), 409
            _speed_test_status["running"] = True
            _speed_test_status["result"] = None
            _speed_test_status["error"] = None

        db_path = get_db_path()
        t = threading.Thread(target=_run_speed_test_background, args=(db_path,), daemon=True)
        t.start()
        return jsonify({"status": "started"}), 202

    @app.route("/api/speedtest/status")
    def api_speedtest_status():
        return jsonify({
            "running": _speed_test_status["running"],
            "last_run_time": _speed_test_status["last_run_time"],
            "result": _speed_test_status["result"],
            "error": _speed_test_status["error"],
        })

    return app


# Gunicorn entry point
app = create_app(start_scheduler=os.environ.get("MONITOR_NO_SCHEDULER") != "1")
