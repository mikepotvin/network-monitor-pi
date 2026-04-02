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
