"""
utils.py
--------
Shared utility functions used across the PlaceMux project:
- SQLite connection management
- Logging setup
- Small helper/formatting functions
"""

import logging
import sqlite3
from contextlib import contextmanager

import config


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger with a consistent format across modules."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


@contextmanager
def get_connection(db_path=None):
    """
    Context manager for a SQLite connection.
    Ensures foreign keys are enforced and the connection is always closed.
    """
    path = db_path or config.DB_PATH
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def run_query(query: str, params: tuple = (), db_path=None):
    """Run a SELECT query and return results as a list of sqlite3.Row objects."""
    with get_connection(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(query, params)
        return cursor.fetchall()


def format_currency(amount: float) -> str:
    """Format a number as Indian-style currency string, e.g. 12,34,567."""
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return "N/A"
    s = f"{amount:,.2f}"
    return f"₹{s}"


def format_percentage(value: float, decimals: int = 1) -> str:
    """Format a fractional or already-percent value as a percentage string."""
    try:
        return f"{float(value):.{decimals}f}%"
    except (TypeError, ValueError):
        return "N/A"


def safe_divide(numerator, denominator, default=0.0):
    """Divide safely, returning `default` when the denominator is zero/None."""
    try:
        if not denominator:
            return default
        return numerator / denominator
    except (TypeError, ZeroDivisionError):
        return default
