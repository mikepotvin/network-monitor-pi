import os
import sqlite3
import tempfile

import pytest


@pytest.fixture
def tmp_db_path(tmp_path):
    """Return a path for a temporary SQLite database."""
    return str(tmp_path / "test_monitor.db")


@pytest.fixture
def db_connection(tmp_db_path):
    """Create a temporary SQLite database with the schema applied."""
    from src.database import init_db

    init_db(tmp_db_path)
    conn = sqlite3.connect(tmp_db_path)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()
