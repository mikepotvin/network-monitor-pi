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
