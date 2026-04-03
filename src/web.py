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
    get_uptime_stats,
    get_current_streak,
    get_latency_percentiles,
    get_packet_loss_timeline,
    get_error_log,
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

    return app


# Gunicorn entry point
app = create_app(start_scheduler=os.environ.get("MONITOR_NO_SCHEDULER") != "1")
