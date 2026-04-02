import socket
import time
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

from icmplib import ping, ICMPLibError

from src.config import (
    PING_TIMEOUT_SECONDS,
    PING_COUNT,
    DNS_CHECK_HOSTNAME,
    HTTP_CHECK_URL,
    HTTP_CHECK_TIMEOUT_SECONDS,
)


def execute_ping(target: str, target_name: str) -> dict:
    timestamp = time.time()
    try:
        result = ping(target, count=PING_COUNT, timeout=PING_TIMEOUT_SECONDS, privileged=False)
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
            "timestamp": timestamp, "target": target, "target_name": target_name,
            "rtt_ms": None, "jitter_ms": None, "is_success": 0,
            "error_message": f"General failure: {e}",
        }
    except ICMPLibError as e:
        return {
            "timestamp": timestamp, "target": target, "target_name": target_name,
            "rtt_ms": None, "jitter_ms": None, "is_success": 0,
            "error_message": f"General failure: {e}",
        }


def classify_ping_error(result) -> str:
    return "Request timed out"


def check_dns() -> dict:
    timestamp = time.time()
    try:
        start = time.perf_counter()
        socket.getaddrinfo(DNS_CHECK_HOSTNAME, 80)
        elapsed_ms = (time.perf_counter() - start) * 1000
        return {"timestamp": timestamp, "resolution_ms": round(elapsed_ms, 2), "is_success": True, "error_message": None}
    except socket.gaierror as e:
        return {"timestamp": timestamp, "resolution_ms": None, "is_success": False, "error_message": f"DNS resolution failed: {e}"}


def check_http() -> dict:
    timestamp = time.time()
    try:
        req = Request(HTTP_CHECK_URL, method="HEAD")
        start = time.perf_counter()
        response = urlopen(req, timeout=HTTP_CHECK_TIMEOUT_SECONDS)
        elapsed_ms = (time.perf_counter() - start) * 1000
        return {"timestamp": timestamp, "response_ms": round(elapsed_ms, 2), "status_code": response.status, "is_success": True, "error_message": None}
    except HTTPError as e:
        return {"timestamp": timestamp, "response_ms": None, "status_code": e.code, "is_success": False, "error_message": f"HTTP error: {e.code} {e.reason}"}
    except (URLError, OSError) as e:
        return {"timestamp": timestamp, "response_ms": None, "status_code": None, "is_success": False, "error_message": f"HTTP request failed: {e}"}
