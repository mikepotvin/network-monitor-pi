# Network Monitor for Raspberry Pi 3 — Design Spec

## Overview

A lightweight, always-on network monitor running on a Raspberry Pi 3 that tracks packet loss, disconnects, latency, and other network health metrics. Data is stored locally and served via a web dashboard accessible from any device on the LAN.

## Goals

- Detect and log network outages with duration and error details
- Track packet loss, latency, and jitter continuously
- Provide a web dashboard for viewing current status and historical data
- Run passively with negligible bandwidth usage
- Auto-start on boot, no manual intervention required
- Run headless, managed via SSH

## Non-Goals

- No push notifications or alerting
- No external cloud services or accounts required
- No traffic inspection or deep packet analysis
- No WiFi monitoring (Pi is ethernet-connected)

## Architecture

Single Python process handling both monitoring and web serving. One systemd service, one SQLite database. The monitoring engine runs as a background thread spawned during Flask app initialization (before the first request). Gunicorn starts Flask, which starts the monitor thread — one process, one entry point.

```
[Monitoring Thread]                [Flask Web Server]
        |                                  |
   icmplib pings (1s)              GET /api/status
   DNS checks (60s)                GET /api/timeline
   HTTP checks (60s)               GET /api/outages
   Speed tests (1AM daily)         GET /api/speedtests
        |                                  |
        v                                  v
  [In-Memory Buffer]  ------>  [SQLite Database]
   (flush every 30s)            monitor.db
```

## Technology Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Language | Python 3 | Great Pi support, lightweight, rich networking libraries |
| Ping/ICMP | icmplib (async) | Pure Python, no root needed with capabilities, returns jitter natively |
| DNS timing | socket.getaddrinfo() | Stdlib, zero dependencies |
| HTTP check | urllib3 | Lightweight, connection pooling |
| Speed test | speedtest-cli | Standard Ookla speed test from CLI |
| Database | SQLite (WAL mode) | Flexible queries, stdlib support, single file |
| Web framework | Flask | Light, well-documented, right-sized for single-user dashboard |
| Charting | uPlot | 8 KB, purpose-built for time-series, handles large datasets |
| Frontend | Vanilla JS + HTML/CSS | No build step, no framework overhead |
| Process mgmt | systemd | Standard, auto-restart, boot integration |
| Deployment | gunicorn (1 worker) | Production-grade WSGI server, low overhead |

## Monitoring Engine

### Ping Targets

Pinged every 1 second (matching terminal `ping` default behavior):

1. **Default gateway** — auto-detected from `ip route` at startup. Detects LAN/router issues.
2. **1.1.1.1** (Cloudflare DNS) — primary internet connectivity check.
3. **8.8.8.8** (Google DNS) — secondary internet check.
4. **208.67.222.222** (OpenDNS) — tertiary confirmation for triangulation.

Pinging multiple targets allows triangulating where failures occur: if the gateway responds but external targets don't, the issue is upstream of the router.

### Metrics Per Ping Cycle

- Round-trip time (ms)
- Packet loss (calculated from success/failure ratio over a window)
- Jitter (ms) — built into icmplib response
- Status classification: `ok`, `degraded` (high latency >200ms or >10% loss), `down` (unreachable)

### Additional Checks

**DNS Resolution (every 60 seconds):**
- Resolve `google.com` via `socket.getaddrinfo()`
- Measure resolution time in milliseconds
- Detects DNS-specific failures that ping (which uses IPs) would miss

**HTTP Reachability (every 60 seconds):**
- HEAD request to `http://captive.apple.com/hotspot-detect.html`
- Measures response time and checks for HTTP 200
- Catches issues ping misses: transparent proxy failures, DNS poisoning, captive portals

**Speed Test (daily at 1:00 AM local time):**
- Full Ookla speed test via `speedtest-cli`
- Captures download (Mbps), upload (Mbps), and latency to test server
- Scheduled at 1 AM to minimize impact on daytime usage
- Each test uses ~10-40 MB bandwidth and takes 15-30 seconds

### Error Messages

When a ping fails, the error type is captured with descriptive messages matching familiar `ping` output:

- "Request timed out" — no response within timeout period
- "Destination host unreachable" — ICMP unreachable received from a router
- "General failure" — network interface is down
- "TTL expired in transit" — routing loop detected

### In-Memory Buffer

Ping results are buffered in memory and flushed to SQLite every 30 seconds. This reduces SD card write operations from ~4/second to ~1/30 seconds while keeping data loss on crash to at most 30 seconds.

## Database Schema

SQLite database at `/opt/network-monitor/data/monitor.db`

Configuration: WAL mode, `PRAGMA synchronous=NORMAL`, `PRAGMA journal_size_limit=1048576`

### ping_results

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| timestamp | REAL | Unix timestamp |
| target | TEXT | IP address pinged |
| target_name | TEXT | Friendly name ("Gateway", "Cloudflare", "Google", "OpenDNS") |
| rtt_ms | REAL | Round-trip time in ms (NULL if failed) |
| jitter_ms | REAL | Jitter in ms (NULL if failed) |
| is_success | INTEGER | 1=success, 0=failure |
| error_message | TEXT | Error description if failed (NULL if success) |

Indexes: `(timestamp)`, `(target, timestamp)`

### dns_checks

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| timestamp | REAL | Unix timestamp |
| resolution_ms | REAL | DNS resolution time in ms (NULL if failed) |
| is_success | INTEGER | 1=success, 0=failure |
| error_message | TEXT | Error description if failed |

Index: `(timestamp)`

### http_checks

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| timestamp | REAL | Unix timestamp |
| response_ms | REAL | HTTP response time in ms (NULL if failed) |
| status_code | INTEGER | HTTP status code (NULL if failed) |
| is_success | INTEGER | 1=success, 0=failure |
| error_message | TEXT | Error description if failed |

Index: `(timestamp)`

### speed_tests

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| timestamp | REAL | Unix timestamp |
| download_mbps | REAL | Download speed in Mbps |
| upload_mbps | REAL | Upload speed in Mbps |
| ping_ms | REAL | Latency to speed test server in ms |
| server_name | TEXT | Name of speed test server used |

Index: `(timestamp)`

### ping_results_hourly (aggregated)

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| timestamp | REAL | Start of the 1-minute window (Unix timestamp) |
| target | TEXT | IP address |
| target_name | TEXT | Friendly name |
| avg_rtt_ms | REAL | Average RTT over the minute |
| max_rtt_ms | REAL | Max RTT over the minute |
| packet_loss_pct | REAL | % of pings that failed in the minute |
| avg_jitter_ms | REAL | Average jitter over the minute |

Index: `(target, timestamp)`

### Data Retention

- Nightly cleanup job runs after speed test (e.g., 1:15 AM)
- Deletes all records older than 30 days from all tables
- Runs `VACUUM` weekly to reclaim space

### Data Aggregation & Storage Estimate

To keep storage manageable on an SD card, older data is automatically downsampled:

- **Last 48 hours**: Full 1-second granularity (~345,600 rows/day across 4 targets)
- **3-49 days old**: Aggregated to 1-minute averages (avg RTT, max RTT, packet loss %, avg jitter per target)
- **Over 30 days**: Deleted

A nightly job (1:15 AM, after speed test) handles both aggregation and cleanup.

Estimated storage: ~50-80 MB total (48h of raw data + 28 days of aggregated data). Well within SD card limits.

## Web Dashboard

Flask app served via gunicorn on port 5000. Accessible at `http://<pi-ip>:5000` from any device on the LAN. No authentication (trusted home network).

### Page 1: Live Status (Home)

- Large banner: "Network UP for 2d 14h 23m" or "Network DOWN since 10:34 AM (42 minutes)"
- Status cards for each target: green (ok), yellow (degraded), red (down)
- Current latency, jitter, and packet loss per target
- DNS resolution time and HTTP check status
- Auto-refreshes every 5 seconds via `fetch()` polling

### Page 2: Timeline View

- uPlot time-series chart showing latency over time for all 4 targets
- Red bands overlaid on the timeline showing outage periods
- Packet loss percentage as a secondary axis
- Time range selector: 24h (default), 7d, 30d
- 7d and 30d views use 1-minute aggregated averages for performance
- Hover to see exact values at any point in time

### Page 3: Outage Log

- Table listing all detected outages
- Columns: Start Time, End Time, Duration, Affected Targets, Error Messages
- Outage definition: a target unreachable for 3+ consecutive pings (filters single-packet blips)
- Outage ends when 3+ consecutive pings succeed
- Error messages show the familiar ping-style descriptions
- Sortable and filterable

### Page 4: Speed Test History

- uPlot chart of download/upload speeds over time
- Table of all speed test results with timestamp, download, upload, ping, server
- Shows trends in ISP performance over the 30-day window

### API Endpoints

All return JSON. The frontend consumes these via `fetch()`.

- `GET /api/status` — current status of all targets, latest metrics
- `GET /api/timeline?range=24h&target=all` — time-series data for charts
- `GET /api/outages?page=1&limit=50` — paginated outage log
- `GET /api/speedtests` — all speed test results

### Frontend Design

- Responsive layout using CSS Grid — works on phone, tablet, desktop
- Dark theme (easier on the eyes for a monitoring dashboard)
- Minimal dependencies: uPlot for charts, everything else is vanilla JS/CSS
- Navigation: simple top nav bar with 4 tabs
- No build step — plain HTML/CSS/JS served directly by Flask

## Deployment

### Raspberry Pi Setup

1. Flash Raspberry Pi OS Lite (64-bit) using Raspberry Pi Imager
2. Pre-configure in imager: hostname (`networkmon`), enable SSH, set user/password, timezone
3. Connect Pi to router via ethernet
4. SSH in: `ssh user@networkmon.local`
5. Update system: `sudo apt update && sudo apt upgrade -y`

### Application Install

Install location: `/opt/network-monitor/`

```
/opt/network-monitor/
  venv/                  # Python virtual environment
  data/
    monitor.db           # SQLite database
  src/
    monitor.py           # Monitoring engine
    web.py               # Flask app and API endpoints
    database.py          # Database operations
    config.py            # Configuration constants
  static/
    css/style.css
    js/app.js
    js/uplot.min.js
  templates/
    index.html           # Dashboard template
  setup.sh               # Automated setup script
  requirements.txt       # Python dependencies
  network-monitor.service  # systemd unit file
```

### Dependencies (requirements.txt)

```
icmplib>=3.0
flask>=3.0
gunicorn>=21.0
speedtest-cli>=2.1
```

### Setup Script (setup.sh)

Automated script that handles:
1. Create `networkmon` system user
2. Create `/opt/network-monitor/` directory structure
3. Create Python venv and install dependencies
4. Set `cap_net_raw` capability on venv Python binary
5. Install and enable systemd service
6. Start the service

### Systemd Service

```ini
[Unit]
Description=Network Monitor
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=networkmon
WorkingDirectory=/opt/network-monitor
ExecStart=/opt/network-monitor/venv/bin/gunicorn -w 1 -b 0.0.0.0:5000 src.web:app
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1
WatchdogSec=60

[Install]
WantedBy=multi-user.target
```

### GitHub

- Repository: `network-monitor-pi` (already created as working directory)
- README with setup instructions
- Deploy to Pi: clone repo, run `setup.sh`
- Updates: `git pull` on Pi, restart service

## Verification Plan

1. **Unit tests**: Test monitoring functions, database operations, API endpoints
2. **Local development**: Run on dev machine first, verify dashboard renders correctly
3. **Pi deployment**: Deploy to Pi, verify systemd service starts and survives reboot
4. **Monitoring accuracy**: Compare ping results with terminal `ping` output
5. **Dashboard check**: Access from phone and desktop, verify responsive layout
6. **Outage simulation**: Disconnect ethernet briefly, verify outage is logged with correct error messages
7. **Speed test**: Verify nightly speed test runs and results appear in dashboard
8. **30-day cleanup**: Manually insert old data, verify cleanup job removes it
