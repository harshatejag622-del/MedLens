"""
Centralized Datetime Utilities for MedLens.
Provides Python 3.11/3.12/3.13 compliant timezone-aware UTC timestamps,
eliminating deprecated datetime.utcnow() usage.
"""

from datetime import datetime, timezone

def utc_now() -> datetime:
    """Returns timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)

def utc_now_naive() -> datetime:
    """Returns naive UTC datetime for legacy SQLite DateTime column compatibility."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

def utc_iso() -> str:
    """Returns ISO-8601 formatted UTC timestamp with trailing Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
