import logging
import time

import speedtest

logger = logging.getLogger(__name__)


def run_speed_test():
    """Run a speed test using the speedtest-cli Python API and return results.
    Returns a dict with download_mbps, upload_mbps, ping_ms, server_name,
    and timestamp. Returns None if the test fails.
    """
    try:
        s = speedtest.Speedtest()
        s.get_best_server()
        s.download()
        s.upload()
        data = s.results.dict()
        return {
            "timestamp": time.time(),
            "download_mbps": round(data["download"] / 1_000_000, 2),
            "upload_mbps": round(data["upload"] / 1_000_000, 2),
            "ping_ms": data["ping"],
            "server_name": f"{data['server']['sponsor']} ({data['server']['name']})",
        }
    except KeyError as e:
        logger.error("Speed test failed to parse: %s", e)
        return None
    except Exception as e:
        logger.error("Speed test failed: %s", e)
        return None
