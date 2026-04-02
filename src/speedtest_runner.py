import json
import logging
import subprocess
import time

logger = logging.getLogger(__name__)


def run_speed_test():
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
