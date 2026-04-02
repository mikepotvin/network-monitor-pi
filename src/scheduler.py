import logging
import threading
import time
from datetime import datetime

from src.config import (
    PING_INTERVAL_SECONDS,
    DNS_CHECK_INTERVAL_SECONDS,
    HTTP_CHECK_INTERVAL_SECONDS,
    BUFFER_FLUSH_INTERVAL_SECONDS,
    SPEED_TEST_HOUR,
    SPEED_TEST_MINUTE,
    CLEANUP_HOUR,
    CLEANUP_MINUTE,
    EXTERNAL_TARGETS,
    detect_gateway,
)
from src.database import (
    init_db,
    insert_ping_results,
    insert_dns_check,
    insert_http_check,
    insert_speed_test,
    aggregate_old_data,
    cleanup_old_data,
)
from src.monitor import execute_ping, check_dns, check_http
from src.speedtest_runner import run_speed_test

logger = logging.getLogger(__name__)


class MonitorScheduler:
    """Manages all background monitoring threads."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._stop_event = threading.Event()
        self._ping_buffer: list[dict] = []
        self._buffer_lock = threading.Lock()
        self._threads: list[threading.Thread] = []
        self._gateway: str | None = None

    def start(self) -> None:
        """Initialize the database and start all monitoring threads."""
        init_db(self.db_path)

        # Detect gateway
        self._gateway = detect_gateway()
        if self._gateway:
            logger.info("Detected gateway: %s", self._gateway)
        else:
            logger.warning("Could not detect gateway — only monitoring external targets")

        threads_to_start = [
            ("ping_loop", self._ping_loop),
            ("dns_loop", self._dns_loop),
            ("http_loop", self._http_loop),
            ("buffer_flush_loop", self._buffer_flush_loop),
            ("daily_jobs_loop", self._daily_jobs_loop),
        ]
        for name, target in threads_to_start:
            t = threading.Thread(target=target, name=name, daemon=True)
            t.start()
            self._threads.append(t)

        logger.info("Monitor scheduler started with %d threads", len(self._threads))

    def stop(self) -> None:
        """Signal all threads to stop."""
        self._stop_event.set()
        # Flush any remaining buffered data
        self._flush_buffer()
        logger.info("Monitor scheduler stopped")

    def get_targets(self) -> list[dict]:
        """Return the list of targets being monitored."""
        targets = []
        if self._gateway:
            targets.append({"ip": self._gateway, "name": "Gateway"})
        targets.extend(EXTERNAL_TARGETS)
        return targets

    def _ping_loop(self) -> None:
        """Ping all targets every PING_INTERVAL_SECONDS."""
        while not self._stop_event.is_set():
            targets = self.get_targets()
            for t in targets:
                if self._stop_event.is_set():
                    return
                result = execute_ping(t["ip"], t["name"])
                with self._buffer_lock:
                    self._ping_buffer.append(result)
            self._stop_event.wait(PING_INTERVAL_SECONDS)

    def _dns_loop(self) -> None:
        """Run DNS checks every DNS_CHECK_INTERVAL_SECONDS."""
        while not self._stop_event.is_set():
            result = check_dns()
            insert_dns_check(
                self.db_path,
                result["timestamp"],
                result["resolution_ms"],
                result["is_success"],
                result["error_message"],
            )
            self._stop_event.wait(DNS_CHECK_INTERVAL_SECONDS)

    def _http_loop(self) -> None:
        """Run HTTP checks every HTTP_CHECK_INTERVAL_SECONDS."""
        while not self._stop_event.is_set():
            result = check_http()
            insert_http_check(
                self.db_path,
                result["timestamp"],
                result["response_ms"],
                result.get("status_code"),
                result["is_success"],
                result["error_message"],
            )
            self._stop_event.wait(HTTP_CHECK_INTERVAL_SECONDS)

    def _buffer_flush_loop(self) -> None:
        """Flush the ping buffer to the database every BUFFER_FLUSH_INTERVAL_SECONDS."""
        while not self._stop_event.is_set():
            self._stop_event.wait(BUFFER_FLUSH_INTERVAL_SECONDS)
            self._flush_buffer()

    def _flush_buffer(self) -> None:
        """Write all buffered ping results to the database."""
        with self._buffer_lock:
            if not self._ping_buffer:
                return
            rows = list(self._ping_buffer)
            self._ping_buffer.clear()
        try:
            insert_ping_results(self.db_path, rows)
            logger.debug("Flushed %d ping results to database", len(rows))
        except Exception as e:
            logger.error("Failed to flush ping buffer: %s", e)

    def _daily_jobs_loop(self) -> None:
        """Run speed test and cleanup at scheduled times."""
        last_speed_test_date = None
        last_cleanup_date = None

        while not self._stop_event.is_set():
            now = datetime.now()
            today = now.date()

            # Speed test at 1:00 AM
            if (
                now.hour == SPEED_TEST_HOUR
                and now.minute == SPEED_TEST_MINUTE
                and last_speed_test_date != today
            ):
                logger.info("Running nightly speed test")
                result = run_speed_test()
                if result:
                    insert_speed_test(
                        self.db_path,
                        result["timestamp"],
                        result["download_mbps"],
                        result["upload_mbps"],
                        result["ping_ms"],
                        result["server_name"],
                    )
                    logger.info(
                        "Speed test complete: %.1f↓ / %.1f↑ Mbps",
                        result["download_mbps"],
                        result["upload_mbps"],
                    )
                else:
                    logger.error("Speed test failed")
                last_speed_test_date = today

            # Aggregation + cleanup at 1:15 AM
            if (
                now.hour == CLEANUP_HOUR
                and now.minute == CLEANUP_MINUTE
                and last_cleanup_date != today
            ):
                logger.info("Running nightly aggregation and cleanup")
                try:
                    aggregate_old_data(self.db_path)
                    cleanup_old_data(self.db_path)
                    logger.info("Aggregation and cleanup complete")
                except Exception as e:
                    logger.error("Aggregation/cleanup failed: %s", e)
                last_cleanup_date = today

            # Check every 30 seconds
            self._stop_event.wait(30)
