# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Raspberry Pi network monitor that tracks ping latency/loss, DNS/HTTP health, and nightly speed tests. Single Python process: Flask serves the web dashboard while background threads handle monitoring. Results buffer in memory and flush to SQLite every 30 seconds.

## Commands

```bash
# Dev setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt

# Run tests
pytest -v

# Run a single test
pytest tests/test_monitor.py -v
pytest tests/test_monitor.py::test_execute_ping_success -v

# Run Flask locally (without monitoring threads)
MONITOR_NO_SCHEDULER=1 flask --app src.web run --debug

# Production (via systemd on Pi)
sudo bash setup.sh
```

## Architecture

```
Browser ──→ Flask (port 5000) ──→ SQLite ←── MonitorScheduler (daemon threads)
                                               ├── ping_loop (1s)
                                               ├── dns_loop (60s)
                                               ├── http_loop (60s)
                                               ├── buffer_flush_loop (30s)
                                               └── daily_jobs_loop (speed test 1AM, cleanup 1:15AM)
```

- **`src/web.py`** — Flask app factory (`create_app`). The module-level `app` is the gunicorn entry point. Set `MONITOR_NO_SCHEDULER=1` to disable background threads during development/testing.
- **`src/scheduler.py`** — `MonitorScheduler` owns all background threads and the ping buffer. Buffer is flushed in batch; DNS/HTTP results are written immediately.
- **`src/monitor.py`** — Stateless check functions (`execute_ping`, `check_dns`, `check_http`). Uses `icmplib` with `privileged=False` (requires `cap_net_raw` on the Python binary).
- **`src/database.py`** — All SQLite access. Connections use WAL mode. Raw pings older than 48h are aggregated into hourly buckets (`ping_results_aggregated`), then raw data is deleted. All data older than 30 days is purged.
- **`src/config.py`** — All constants and intervals. `detect_gateway()` reads the system routing table.
- **`src/speedtest_runner.py`** — Wraps `speedtest-cli --json` in a subprocess.

## Testing

Tests use `tmp_path` fixtures for isolated SQLite databases (see `tests/conftest.py`). The web tests patch `src.web.get_db_path` to point at the temp database and create the app with `start_scheduler=False`.

## Data Model

Six SQLite tables: `ping_results`, `ping_results_aggregated`, `dns_checks`, `http_checks`, `speed_tests`. Timestamps are Unix epoch floats. The timeline API serves raw data for <=48h ranges and aggregated data for longer ranges.

## Deployment

Target: Raspberry Pi running as systemd service (`network-monitor.service`). Installs to `/opt/network-monitor`, runs as `networkmon` user via gunicorn with a single worker.

## Workflow

When tests pass after completing a task, always commit and push without asking.

## Model Usage

Use Opus for planning and design. Use Sonnet for implementation and execution.
